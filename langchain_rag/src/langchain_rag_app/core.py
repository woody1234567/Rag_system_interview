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

from .retrieval import BM25Index, RetrievalCandidate, heuristic_rerank, rrf_fusion


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


def get_vectorstore() -> Chroma:
    cfg = load_config()
    persist_dir = project_root() / cfg["persist_directory"]
    return Chroma(
        persist_directory=str(persist_dir),
        embedding_function=get_embeddings(),
        collection_name="fubon_annual_report",
    )


def _dense_candidates(vs: Chroma, query: str, top_n: int) -> list[tuple[float, RetrievalCandidate]]:
    res = vs.similarity_search_with_relevance_scores(query, k=top_n)
    out: list[tuple[float, RetrievalCandidate]] = []
    for i, (doc, score) in enumerate(res, start=1):
        page = int(doc.metadata.get("page", -1)) + 1 if "page" in doc.metadata else -1
        did = str(doc.metadata.get("id", f"d-{page}-{i}"))
        c = RetrievalCandidate(doc_id=did, page=page, content=doc.page_content, metadata=doc.metadata)
        c.dense_rank = i
        c.dense_score = float(score)
        out.append((float(score), c))
    return out


def _all_docs_for_bm25(vs: Chroma) -> list[dict[str, Any]]:
    raw = vs.get(include=["documents", "metadatas"])
    ids = raw.get("ids", [])
    docs = raw.get("documents", [])
    metas = raw.get("metadatas", [])
    out = []
    for i, text in enumerate(docs):
        meta = metas[i] if i < len(metas) and metas[i] else {}
        page = int(meta.get("page", -1)) + 1 if "page" in meta else -1
        out.append({"doc_id": str(ids[i]) if i < len(ids) else f"bm25-{i}", "page": page, "content": text, "metadata": meta})
    return out


def retrieve_with_pipeline(query: str, cfg: dict[str, Any]) -> tuple[list[RetrievalCandidate], dict[str, Any]]:
    mode = cfg.get("retrieval_mode", "dense_only")
    dense_top_n = int(cfg.get("dense_top_n", 20))
    bm25_top_n = int(cfg.get("bm25_top_n", 20))
    rrf_k = int(cfg.get("fusion", {}).get("rrf_k", 60))
    rerank_cfg = cfg.get("rerank", {})
    rerank_enabled = bool(rerank_cfg.get("enabled", False)) and mode == "hybrid_rerank"
    rerank_top_k = int(rerank_cfg.get("top_k", cfg.get("k", 5)))
    candidate_pool = int(rerank_cfg.get("candidate_pool", 30))

    vs = get_vectorstore()
    dense = _dense_candidates(vs, query, dense_top_n)

    debug: dict[str, Any] = {
        "mode": mode,
        "dense_top": [{"doc_id": c.doc_id, "page": c.page, "score": round(float(s), 6)} for s, c in dense],
        "bm25_top": [],
        "fusion_top": [],
        "rerank_top": [],
        "final_docs": [],
    }

    if mode == "dense_only":
        final_docs = [c for _, c in dense[: int(cfg.get("k", 5))]]
    else:
        all_docs = _all_docs_for_bm25(vs)
        bm25 = BM25Index(all_docs)
        bm25_raw = bm25.search(query, top_n=bm25_top_n)
        bm25_list: list[tuple[float, RetrievalCandidate]] = []
        for rank, (score, d, _) in enumerate(bm25_raw, start=1):
            c = RetrievalCandidate(doc_id=d["doc_id"], page=d["page"], content=d["content"], metadata=d["metadata"])
            c.bm25_rank = rank
            c.bm25_score = float(score)
            bm25_list.append((float(score), c))

        fused = rrf_fusion(dense, bm25_list, rrf_k=rrf_k)

        debug["bm25_top"] = [{"doc_id": c.doc_id, "page": c.page, "score": round(float(s), 6)} for s, c in bm25_list]
        debug["fusion_top"] = [{"doc_id": c.doc_id, "page": c.page, "score": round(float(c.fusion_score or 0.0), 6)} for c in fused]

        if rerank_enabled:
            final_docs = heuristic_rerank(query, fused, top_k=rerank_top_k, candidate_pool=candidate_pool)
            debug["rerank_top"] = [
                {"doc_id": c.doc_id, "page": c.page, "score": round(float(c.rerank_score or 0.0), 6)} for c in final_docs
            ]
        else:
            final_docs = fused[: int(cfg.get("k", 5))]

    debug["final_docs"] = [{"doc_id": c.doc_id, "page": c.page} for c in final_docs]
    return final_docs, debug


def answer_question(question: str) -> dict[str, Any]:
    cfg = load_config()
    candidates, retrieval_debug = retrieve_with_pipeline(question, cfg)

    if not candidates:
        return {
            "answer": cfg["refusal_text"],
            "refusal": True,
            "reason": "no retrieved context",
            "sources": [],
            "retrieval_debug": retrieval_debug,
            "evidence_text": "",
        }

    context = "\n\n".join([c.content for c in candidates])
    pages = sorted({c.page for c in candidates if c.page >= 0})

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
        "retrieval_debug": retrieval_debug,
        "evidence_text": context,
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
                    "gold_pages": vals.get("F", ""),
                })
        return out

