from dataclasses import dataclass

from .normalizers import canonical_text, compare_numeric_facts, split_subparts


REFUSAL_KEYS = ("拒答", "無法推論", "資料不足")


def is_refusal_gold(gold: str) -> bool:
    g = gold or ""
    return any(k in g for k in REFUSAL_KEYS)


@dataclass
class JudgeResult:
    is_correct_strict: bool
    is_correct_relaxed: bool
    coverage_score: float
    reason_codes: list[str]
    failed_numeric_facts: list[dict]


def _contains_strict(pred: str, gold: str) -> bool:
    return canonical_text(gold) in canonical_text(pred)


def _contains_relaxed(pred: str, gold: str) -> bool:
    cp, cg = canonical_text(pred), canonical_text(gold)
    numeric_ok = compare_numeric_facts(pred, gold).matched
    return (cg and cg in cp) or numeric_ok


def _coverage(pred: str, question: str, gold: str) -> tuple[float, int, int]:
    subparts = split_subparts(question, gold)
    total = max(1, len(subparts))
    hit = 0
    for part in subparts:
        if _contains_relaxed(pred, part):
            hit += 1
    return hit / total, total, hit


def judge_answer(pred_answer: str, pred_refusal: bool, gold_answer: str, question: str) -> JudgeResult:
    reason_codes: list[str] = []

    if is_refusal_gold(gold_answer):
        ok = bool(pred_refusal)
        reason_codes.append("refusal_expected")
        if ok:
            reason_codes.append("refusal_correct")
        else:
            reason_codes.append("missed_refusal")
        return JudgeResult(ok, ok, 1.0 if ok else 0.0, reason_codes, [])

    if pred_refusal:
        reason_codes.append("over_refusal")
        return JudgeResult(False, False, 0.0, reason_codes, [])

    strict = _contains_strict(pred_answer, gold_answer)
    numeric_cmp = compare_numeric_facts(pred_answer, gold_answer)
    relaxed = _contains_relaxed(pred_answer, gold_answer)
    cov, total, hit = _coverage(pred_answer, question, gold_answer)

    if strict:
        reason_codes.append("strict_match")
    if relaxed and not strict:
        reason_codes.append("relaxed_match")
    if not relaxed:
        reason_codes.append("no_match")
    if total > 1:
        reason_codes.append(f"partial_coverage:{hit}/{total}")

    for code in numeric_cmp.reason_codes:
        if code not in reason_codes:
            reason_codes.append(code)

    return JudgeResult(strict, relaxed, round(cov, 4), reason_codes, numeric_cmp.failed_facts)
