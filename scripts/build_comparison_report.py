import json
from pathlib import Path


KEYS = [
    "accuracy_strict",
    "accuracy_relaxed",
    "final.final_accuracy",
    "refusal_precision",
    "refusal_recall",
    "refusal_f1",
    "avg_coverage_score",
    "final.semantic_task_pass",
    "retrieval.retrieval_recall_at_20",
    "retrieval.final_k_hit_rate",
    "retrieval.avg_rerank_gain_k",
]


def _get(d: dict, key: str):
    cur = d
    for p in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _to_num(v):
    if isinstance(v, (int, float)):
        return float(v)
    return None


def build_report(baseline_summary: dict, langchain_summary: dict) -> dict:
    items = []
    for k in KEYS:
        b = _get(baseline_summary, k)
        l = _get(langchain_summary, k)
        bn, ln = _to_num(b), _to_num(l)
        delta = (ln - bn) if bn is not None and ln is not None else None
        items.append({"metric": k, "baseline": b if b is not None else "N/A", "langchain": l if l is not None else "N/A", "delta": delta})

    return {
        "baseline": baseline_summary,
        "langchain": langchain_summary,
        "comparison": items,
    }


def write_markdown(report: dict, out_path: Path) -> None:
    lines = ["# Cross System Comparison", "", "| Metric | Baseline | LangChain | Delta |", "|---|---:|---:|---:|"]
    for row in report.get("comparison", []):
        d = row.get("delta")
        d_text = f"{d:.4f}" if isinstance(d, (int, float)) else "N/A"
        lines.append(f"| {row['metric']} | {row['baseline']} | {row['langchain']} | {d_text} |")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main(base_path: Path, lc_path: Path, out_json: Path, out_md: Path) -> None:
    base = json.loads(base_path.read_text(encoding="utf-8"))
    lc = json.loads(lc_path.read_text(encoding="utf-8"))
    report = build_report(base, lc)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, out_md)
