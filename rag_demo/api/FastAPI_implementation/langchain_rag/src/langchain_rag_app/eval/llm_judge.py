import json
import re
from typing import Any

from ..core import get_llm


JUDGE_SYSTEM_PROMPT = """你是嚴格評分器。請根據 question / gold_answer / pred_answer / evidence 評分。
輸出 JSON，欄位：
- pass: boolean
- semantic_score: 0~1
- completeness_score: 0~1
- faithfulness_score: 0~1
- reason: string
- missing_points: string[]
- hallucination_flags: string[]
不要輸出其他文字。
"""


def parse_llm_judge_json(text: str) -> dict[str, Any] | None:
    t = (text or "").strip()
    try:
        obj = json.loads(t)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", t)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except Exception:
            return None

    need = ["pass", "semantic_score", "completeness_score", "faithfulness_score", "reason"]
    if not all(k in obj for k in need):
        return None
    obj.setdefault("missing_points", [])
    obj.setdefault("hallucination_flags", [])
    return obj


def calibrate_llm_pass(
    question_type: str,
    semantic_score: float | None,
    completeness_score: float | None,
    faithfulness_score: float | None,
) -> dict[str, Any]:
    s = float(semantic_score or 0.0)
    c = float(completeness_score or 0.0)
    f = float(faithfulness_score or 0.0)

    weighted = s * 0.4 + c * 0.4 + f * 0.2

    if f < 0.6:
        return {"pass_calibrated": False, "weighted_score": round(weighted, 4), "calibrated_reason": "faithfulness_below_floor"}

    threshold = 0.75 if question_type == "multi_fact" else 0.70
    if question_type == "multi_fact" and c < 0.75:
        return {"pass_calibrated": False, "weighted_score": round(weighted, 4), "calibrated_reason": "multifact_completeness_below_threshold"}

    passed = weighted >= threshold
    return {
        "pass_calibrated": bool(passed),
        "weighted_score": round(weighted, 4),
        "calibrated_reason": "weighted_pass" if passed else "weighted_below_threshold",
    }


def judge_with_llm(
    question: str,
    gold: str,
    pred: str,
    evidence: str,
    enabled: bool = True,
    question_type: str = "",
) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "pass": None,
            "pass_raw": None,
            "pass_calibrated": None,
            "weighted_score": None,
            "calibrated_reason": "disabled",
            "semantic_score": None,
            "completeness_score": None,
            "faithfulness_score": None,
            "reason": "disabled",
            "missing_points": [],
            "hallucination_flags": [],
        }

    llm = get_llm()
    user = f"question: {question}\n\ngold_answer: {gold}\n\npred_answer: {pred}\n\nevidence: {evidence}"

    for _ in range(2):
        resp = llm.invoke([("system", JUDGE_SYSTEM_PROMPT), ("user", user)])
        txt = resp.content if isinstance(resp.content, str) else str(resp.content)
        parsed = parse_llm_judge_json(txt)
        if parsed is not None:
            calibrated = calibrate_llm_pass(
                question_type=question_type,
                semantic_score=parsed.get("semantic_score"),
                completeness_score=parsed.get("completeness_score"),
                faithfulness_score=parsed.get("faithfulness_score"),
            )
            return {
                "enabled": True,
                **parsed,
                "pass_raw": parsed.get("pass"),
                **calibrated,
            }

    calibrated = calibrate_llm_pass(question_type, 0.0, 0.0, 0.0)
    return {
        "enabled": True,
        "pass": None,
        "pass_raw": None,
        **calibrated,
        "semantic_score": 0.0,
        "completeness_score": 0.0,
        "faithfulness_score": 0.0,
        "reason": "llm_judge_parse_failed",
        "missing_points": [],
        "hallucination_flags": [],
    }
