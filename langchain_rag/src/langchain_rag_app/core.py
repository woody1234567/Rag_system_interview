import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


SYSTEM_PROMPT = """你是富邦年報問答助理。必須遵守：
1) 只能根據提供的 context 回答。
2) 若 context 不足以支持答案，請拒答。
3) 優先提供簡潔、可驗證的答案。
4) 最終輸出 JSON，格式如下：
{"answer":"...","refusal":true/false,"reason":"..."}
"""


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_env() -> None:
    env_path = project_root() / "langchain_rag" / ".env"
    load_dotenv(dotenv_path=env_path, override=False)


def load_config() -> dict[str, Any]:
    p = project_root() / "langchain_rag" / "config.json"
    return json.loads(p.read_text(encoding="utf-8"))


def normalize(t: str) -> str:
    t = t.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t.replace(",", "")


def get_embeddings() -> OpenAIEmbeddings:
    load_env()
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    return OpenAIEmbeddings(model=model)


def get_llm() -> ChatOpenAI:
    load_env()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model, temperature=0)


def build_index() -> int:
    cfg = load_config()
    pdf_path = project_root() / cfg["pdf_path"]
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["chunk_size"],
        chunk_overlap=cfg["chunk_overlap"],
        separators=["\n\n", "\n", " ", ""],
    )
    splits = splitter.split_documents(docs)

    persist_dir = project_root() / cfg["persist_directory"]
    persist_dir.parent.mkdir(parents=True, exist_ok=True)

    _ = Chroma.from_documents(
        documents=splits,
        embedding=get_embeddings(),
        persist_directory=str(persist_dir),
        collection_name="fubon_annual_report",
    )
    return len(splits)


def get_retriever():
    cfg = load_config()
    persist_dir = project_root() / cfg["persist_directory"]
    vs = Chroma(
        persist_directory=str(persist_dir),
        embedding_function=get_embeddings(),
        collection_name="fubon_annual_report",
    )
    return vs.as_retriever(search_kwargs={"k": cfg["k"]})


def answer_question(question: str) -> dict[str, Any]:
    cfg = load_config()
    retriever = get_retriever()
    docs = retriever.invoke(question)

    if not docs:
        return {
            "answer": cfg["refusal_text"],
            "refusal": True,
            "reason": "no retrieved context",
            "sources": [],
        }

    context = "\n\n".join([d.page_content for d in docs])
    pages = sorted({int(d.metadata.get("page", -1)) + 1 for d in docs if "page" in d.metadata})

    llm = get_llm()
    msg = [
        ("system", SYSTEM_PROMPT),
        (
            "user",
            f"問題：{question}\n\ncontext:\n{context}\n\n請輸出 JSON。若資料不足請 refusal=true。",
        ),
    ]
    resp = llm.invoke(msg)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)

    parsed = parse_json_safely(text)
    if not parsed:
        parsed = {
            "answer": cfg["refusal_text"],
            "refusal": True,
            "reason": "invalid model json",
        }

    return {
        "answer": parsed.get("answer", cfg["refusal_text"]),
        "refusal": bool(parsed.get("refusal", False)),
        "reason": parsed.get("reason", ""),
        "sources": pages,
    }


def parse_json_safely(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def parse_xlsx_questions(xlsx_path: Path):
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with zipfile.ZipFile(xlsx_path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                shared.append("".join((t.text or "") for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheet = wb.find("a:sheets/a:sheet", ns)
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rid_to_target[rid]
        if not target.startswith("xl/"):
            target = "xl/" + target

        root = ET.fromstring(z.read(target))
        rows = root.findall(".//a:sheetData/a:row", ns)
        out = []
        for r in rows[1:]:
            vals = {}
            for c in r.findall("a:c", ns):
                ref = c.attrib.get("r", "")
                col = re.match(r"([A-Z]+)", ref).group(1)
                t = c.attrib.get("t")
                v = c.find("a:v", ns)
                val = ""
                if v is not None:
                    val = v.text or ""
                    if t == "s" and val.isdigit():
                        val = shared[int(val)]
                vals[col] = val
            q = vals.get("D", "")
            if q:
                out.append({
                    "qid": vals.get("C", ""),
                    "question": q,
                    "gold_answer": vals.get("E", ""),
                })
        return out


def is_refusal_gold(gold: str) -> bool:
    return any(k in gold for k in ["拒答", "無法推論", "資料不足"])


def judge(pred: str, refused: bool, gold: str) -> bool:
    if is_refusal_gold(gold):
        return refused
    if refused:
        return False
    return normalize(gold) in normalize(pred)
