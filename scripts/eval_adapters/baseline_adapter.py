import json
from pathlib import Path


def load_baseline_predictions(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            rows.append(
                {
                    "qid": str(obj.get("qid", "")),
                    "question": obj.get("question", ""),
                    "gold_answer": obj.get("gold_answer", ""),
                    "gold_pages": obj.get("gold_pages", ""),
                    "pred_answer": obj.get("pred_answer", ""),
                    "pred_refusal": bool(obj.get("pred_refused", False)),
                    "pred_sources": obj.get("pred_pages", []) or [],
                }
            )
    return rows
