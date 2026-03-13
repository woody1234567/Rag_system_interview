import argparse
import json
import math
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


def load_config(project_root: Path) -> dict:
    cfg_path = project_root / "baseline_model" / "config.json"
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_for_compare(text: str) -> str:
    t = normalize_text(text).lower()
    t = t.replace(",", "")
    t = t.replace("，", "")
    return t


def tokenize_zh_en(text: str):
    # 字元級中文 + 英數 token 混合，簡單 baseline
    text = normalize_text(text)
    en = re.findall(r"[A-Za-z0-9_.%]+", text)
    zh = re.findall(r"[\u4e00-\u9fff]", text)
    return en + zh


def extract_pdf_pages(pdf_path: Path):
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError(
            "缺少 pypdf，請先安裝：pip install pypdf"
        ) from e

    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = normalize_text(text)
        if text:
            pages.append({"page": i, "text": text})
    return pages


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def chunk_pages(pages, chunk_size=800, overlap=120):
    chunks = []
    chunk_id = 0
    step = max(1, chunk_size - overlap)
    for p in pages:
        text = p["text"]
        page = p["page"]
        for start in range(0, len(text), step):
            part = text[start : start + chunk_size]
            if len(part) < 80:
                continue
            chunk_id += 1
            chunks.append(
                {
                    "chunk_id": f"c{chunk_id}",
                    "page_start": page,
                    "page_end": page,
                    "text": part,
                }
            )
    return chunks


@dataclass
class TFIDFIndex:
    idf: dict
    docs: list
    doc_vecs: list


def build_tfidf_index(chunks):
    docs_tokens = []
    df = Counter()

    for c in chunks:
        tokens = tokenize_zh_en(c["text"])
        docs_tokens.append(tokens)
        for t in set(tokens):
            df[t] += 1

    n_docs = max(1, len(docs_tokens))
    idf = {t: math.log((n_docs + 1) / (freq + 1)) + 1.0 for t, freq in df.items()}

    doc_vecs = []
    for tokens in docs_tokens:
        tf = Counter(tokens)
        norm = math.sqrt(sum((tf[t] * idf.get(t, 0.0)) ** 2 for t in tf)) or 1.0
        vec = {t: (tf[t] * idf.get(t, 0.0)) / norm for t in tf}
        doc_vecs.append(vec)

    return TFIDFIndex(idf=idf, docs=chunks, doc_vecs=doc_vecs)


def query_vec(query, idf):
    tokens = tokenize_zh_en(query)
    tf = Counter(tokens)
    norm = math.sqrt(sum((tf[t] * idf.get(t, 0.0)) ** 2 for t in tf)) or 1.0
    return {t: (tf[t] * idf.get(t, 0.0)) / norm for t in tf}


def cosine_sparse(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def retrieve(index: TFIDFIndex, query: str, top_k=5):
    qv = query_vec(query, index.idf)
    scored = []
    for i, dv in enumerate(index.doc_vecs):
        s = cosine_sparse(qv, dv)
        scored.append((s, index.docs[i]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


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
                text = "".join((t.text or "") for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
                shared.append(text)

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

        records = []
        headers = {}
        for r in rows:
            values = {}
            for c in r.findall("a:c", ns):
                ref = c.attrib.get("r", "")
                col = re.match(r"([A-Z]+)", ref).group(1)
                t = c.attrib.get("t")
                v = c.find("a:v", ns)
                val = ""
                if v is not None:
                    val = v.text or ""
                    if t == "s":
                        val = shared[int(val)] if val.isdigit() else val
                else:
                    inline_t = c.find("a:is/a:t", ns)
                    if inline_t is not None:
                        val = inline_t.text or ""
                values[col] = val

            if r.attrib.get("r") == "1":
                headers = values
                continue

            if not values:
                continue

            rec = {
                "category": values.get("A", ""),
                "type": values.get("B", ""),
                "qid": values.get("C", ""),
                "question": values.get("D", ""),
                "gold_answer": values.get("E", ""),
                "gold_pages": values.get("F", ""),
            }
            if rec["question"]:
                records.append(rec)

    return records


def is_refusal_gold(gold_answer: str):
    g = normalize_for_compare(gold_answer)
    return "拒答" in gold_answer or "無法推論" in gold_answer or "資料不足" in gold_answer


def numeric_tokens(text: str):
    return re.findall(r"\d+(?:\.\d+)?", normalize_for_compare(text))


def answer_question(query, retrieved, cfg):
    if not retrieved:
        return cfg["refusal_text"], [], 0.0, True

    top_score = retrieved[0][0]
    if top_score < cfg["min_retrieval_score"]:
        return cfg["refusal_text"], [], top_score, True

    # baseline: 使用 top1 chunk 當答案依據（可再升級摘要/抽取）
    best = retrieved[0][1]
    answer = best["text"][:220]

    if top_score < cfg["min_answer_evidence_score"]:
        return cfg["refusal_text"], [best], top_score, True

    return answer, [x[1] for x in retrieved], top_score, False


def judge_correct(pred: str, gold: str, refused: bool):
    gold_is_refusal = is_refusal_gold(gold)
    if gold_is_refusal:
        return refused

    if refused:
        return False

    p = normalize_for_compare(pred)
    g = normalize_for_compare(gold)

    if g and g in p:
        return True

    # 數值弱比對
    pnums = set(numeric_tokens(p))
    gnums = set(numeric_tokens(g))
    if gnums and gnums.issubset(pnums):
        return True

    return False


def run_build(project_root: Path, cfg: dict):
    pdf_path = project_root / cfg["annual_report_pdf"]
    art_dir = project_root / cfg["artifacts_dir"]

    pages = extract_pdf_pages(pdf_path)
    chunks = chunk_pages(pages, cfg["chunk_size"], cfg["chunk_overlap"])

    write_jsonl(art_dir / "pages.jsonl", pages)
    write_jsonl(art_dir / "chunks.jsonl", chunks)

    print(f"[build] pages={len(pages)} chunks={len(chunks)}")


def run_eval(project_root: Path, cfg: dict):
    art_dir = project_root / cfg["artifacts_dir"]
    chunks = read_jsonl(art_dir / "chunks.jsonl")
    if not chunks:
        raise RuntimeError("找不到 chunks.jsonl，請先執行 build")

    index = build_tfidf_index(chunks)
    qa = parse_xlsx_questions(project_root / cfg["qa_xlsx"])

    results = []
    correct = 0
    refusal_total = 0
    refusal_correct = 0
    hallucinations = 0
    citation_covered = 0

    for row in qa:
        q = row["question"]
        gold = row["gold_answer"]
        retrieved = retrieve(index, q, cfg["top_k"])
        pred, ev, score, refused = answer_question(q, retrieved, cfg)

        ok = judge_correct(pred, gold, refused)
        correct += int(ok)

        gold_refusal = is_refusal_gold(gold)
        if gold_refusal:
            refusal_total += 1
            refusal_correct += int(refused)

        if (not gold_refusal) and refused:
            hallucinations += 1  # 在此 baseline 用「過度拒答」作為錯誤風險指標

        has_citation = len(ev) > 0
        citation_covered += int(has_citation)

        results.append(
            {
                **row,
                "pred_answer": pred,
                "pred_refused": refused,
                "top_score": round(score, 4),
                "pred_pages": [e["page_start"] for e in ev],
                "is_correct": ok,
            }
        )

    total = max(1, len(results))
    summary = {
        "total": len(results),
        "accuracy": round(correct / total, 4),
        "refusal_total": refusal_total,
        "refusal_precision": round(refusal_correct / max(1, refusal_total), 4),
        "citation_coverage": round(citation_covered / total, 4),
        "hallucination_risk_rate": round(hallucinations / total, 4),
    }

    write_jsonl(art_dir / "eval_results.jsonl", results)
    with (art_dir / "eval_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("[eval]", json.dumps(summary, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["build", "eval"])
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    cfg = load_config(project_root)

    if args.cmd == "build":
        run_build(project_root, cfg)
    elif args.cmd == "eval":
        run_eval(project_root, cfg)


if __name__ == "__main__":
    main()
