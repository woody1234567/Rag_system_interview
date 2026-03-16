import json
from pathlib import Path


def load_langchain_predictions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for obj in data:
        rows.append(
            {
                "qid": str(obj.get("qid", "")),
                "question": obj.get("question", ""),
                "gold_answer": obj.get("gold_answer", ""),
                "gold_pages": obj.get("gold_pages", ""),
                "pred_answer": obj.get("pred_answer", ""),
                "pred_refusal": bool(obj.get("pred_refusal", False)),
                "pred_sources": obj.get("pred_sources", []) or [],
            }
        )
    return rows
