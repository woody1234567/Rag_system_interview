import re
from dataclasses import dataclass


CH_NUM_MAP = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


@dataclass
class NumericPolicy:
    year_tolerance: float = 0.0
    percentage_abs_tolerance: float = 0.0005
    currency_rel_tolerance: float = 0.001
    count_tolerance: float = 0.0
    generic_rel_tolerance: float = 0.005
    allow_unitless_currency_match: bool = False
    require_all_numeric_facts: bool = True


DEFAULT_NUMERIC_POLICY = NumericPolicy()


@dataclass
class NumericFact:
    raw: str
    value: float
    unit: str
    kind: str  # year | percentage | currency_amount | count | generic_number


@dataclass
class NumericMatchResult:
    matched: bool
    reason_codes: list[str]
    failed_facts: list[dict]


def normalize_text(s: str) -> str:
    t = (s or "").replace("\u3000", " ").lower()
    t = t.replace("，", ",").replace("；", ";").replace("：", ":")
    t = t.replace("（", "(").replace("）", ")")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def chinese_number_to_int(token: str) -> int | None:
    if not token:
        return None
    if token in CH_NUM_MAP:
        return CH_NUM_MAP[token]
    if "十" in token:
        left, _, right = token.partition("十")
        left_v = 1 if left == "" else CH_NUM_MAP.get(left)
        right_v = 0 if right == "" else CH_NUM_MAP.get(right)
        if left_v is None or right_v is None:
            return None
        return left_v * 10 + right_v
    return None


def normalize_chinese_numbers(s: str) -> str:
    def repl(m):
        n = chinese_number_to_int(m.group(0))
        return str(n) if n is not None else m.group(0)

    return re.sub(r"[零〇一二兩三四五六七八九]?十[零〇一二兩三四五六七八九]?|[零〇一二兩三四五六七八九]", repl, s)


def canonical_text(s: str) -> str:
    t = normalize_chinese_numbers(normalize_text(s))
    t = t.replace(",", "")
    t = t.replace("元", "")
    t = t.replace("年", "")
    return t


def _currency_multiplier(unit: str) -> float:
    u = (unit or "").lower()
    if u in {"億", "億元", "亿元"}:
        return 1e8
    if u in {"萬", "萬元", "万元", "万"}:
        return 1e4
    if u in {"千", "千元"}:
        return 1e3
    return 1.0


def _infer_kind(value: float, unit: str, raw_text: str) -> str:
    if unit == "%":
        return "percentage"
    if unit in {"年"}:
        return "year"
    if unit in {"元", "千元", "萬", "万", "萬元", "万元", "億", "億元", "亿元"}:
        return "currency_amount"
    if unit in {"件", "名", "人"}:
        return "count"

    # 兜底規則
    if 1900 <= value <= 2100 and ("年" in raw_text):
        return "year"
    return "generic_number"


def extract_typed_numeric_facts(s: str) -> list[NumericFact]:
    text = normalize_chinese_numbers(normalize_text(s))
    facts: list[NumericFact] = []

    percent_spans: list[tuple[int, int]] = []
    for m in re.finditer(r"([-+]?\d+(?:\.\d+)?)\s*%", text):
        v = float(m.group(1))
        facts.append(NumericFact(raw=m.group(0), value=v / 100.0, unit="%", kind="percentage"))
        percent_spans.append(m.span())

    def in_percent_span(idx: int) -> bool:
        return any(start <= idx < end for start, end in percent_spans)

    pattern = r"([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*(億|億元|亿元|萬元|万元|万|萬|千元|千|元|年|件|名|人)?"
    for m in re.finditer(pattern, text, flags=re.I):
        if in_percent_span(m.start()):
            continue
        raw_num = m.group(1)
        unit = m.group(2) or ""
        try:
            val = float(raw_num)
        except ValueError:
            continue

        kind = _infer_kind(val, unit, m.group(0))
        if kind == "currency_amount":
            val = val * _currency_multiplier(unit)

        facts.append(NumericFact(raw=m.group(0), value=val, unit=unit, kind=kind))

    return facts


def _compatible_units(kind: str, gold_unit: str, pred_unit: str, policy: NumericPolicy) -> tuple[bool, str | None]:
    if kind in {"year", "count"}:
        return True, None
    if kind == "currency_amount":
        if gold_unit and pred_unit:
            return True, None
        if not policy.allow_unitless_currency_match and (gold_unit != pred_unit):
            return False, "missing_unit_guard"
        return True, None
    return True, None


def _compare_fact(gold: NumericFact, pred: NumericFact, policy: NumericPolicy) -> tuple[bool, str | None]:
    # 允許 percentage 與無單位小數的跨型別比較（0.12% <-> 0.0012）
    if gold.kind != pred.kind:
        if {gold.kind, pred.kind} == {"percentage", "generic_number"}:
            gold_val = gold.value
            pred_val = pred.value
            if abs(pred_val - gold_val) <= policy.percentage_abs_tolerance:
                return True, None
            return False, "numeric_mismatch_tolerance"
        return False, None

    ok_units, unit_reason = _compatible_units(gold.kind, gold.unit, pred.unit, policy)
    if not ok_units:
        return False, unit_reason

    if gold.kind == "year":
        if abs(pred.value - gold.value) <= policy.year_tolerance:
            return True, None
        return False, "numeric_mismatch_year"

    if gold.kind == "percentage":
        if abs(pred.value - gold.value) <= policy.percentage_abs_tolerance:
            return True, None
        return False, "numeric_mismatch_tolerance"

    if gold.kind == "currency_amount":
        denom = max(abs(gold.value), 1.0)
        rel_err = abs(pred.value - gold.value) / denom
        if rel_err <= policy.currency_rel_tolerance:
            return True, None
        return False, "numeric_mismatch_tolerance"

    if gold.kind == "count":
        if abs(pred.value - gold.value) <= policy.count_tolerance:
            return True, None
        return False, "numeric_mismatch_tolerance"

    denom = max(abs(gold.value), 1.0)
    rel_err = abs(pred.value - gold.value) / denom
    if rel_err <= policy.generic_rel_tolerance:
        return True, None
    return False, "numeric_mismatch_tolerance"


def compare_numeric_facts(pred_text: str, gold_text: str, policy: NumericPolicy = DEFAULT_NUMERIC_POLICY) -> NumericMatchResult:
    pred_facts = extract_typed_numeric_facts(pred_text)
    gold_facts = extract_typed_numeric_facts(gold_text)

    # gold 無數值 -> 不交由數值規則判斷
    if not gold_facts:
        return NumericMatchResult(False, [], [])

    reason_codes: list[str] = []
    failed: list[dict] = []

    matched_count = 0
    for g in gold_facts:
        found = False
        failure_reason = "numeric_no_candidate"
        for p in pred_facts:
            ok, reason = _compare_fact(g, p, policy)
            if ok:
                found = True
                matched_count += 1
                break
            if reason:
                failure_reason = reason
        if not found:
            failed.append({"gold_raw": g.raw, "gold_kind": g.kind, "reason": failure_reason})
            reason_codes.append(failure_reason)

    all_matched = matched_count == len(gold_facts)
    if all_matched:
        reason_codes.append("numeric_equivalent_strict_type")
        return NumericMatchResult(True, reason_codes, [])

    if matched_count > 0:
        reason_codes.append("partial_numeric_match")

    # require_all_numeric_facts=true 時，部分命中不給過
    if policy.require_all_numeric_facts:
        return NumericMatchResult(False, reason_codes, failed)

    return NumericMatchResult(matched_count > 0, reason_codes, failed)


def numeric_equivalent(pred_text: str, gold_text: str, policy: NumericPolicy = DEFAULT_NUMERIC_POLICY) -> bool:
    return compare_numeric_facts(pred_text, gold_text, policy).matched


def split_subparts(question: str, gold: str) -> list[str]:
    source = normalize_text(gold) if gold else normalize_text(question)
    parts = re.split(r"[;；]|	|\s+以及\s+|\s+與\s+|\s+及\s+", source)
    parts = [p.strip() for p in parts if p and p.strip()]
    return parts if len(parts) > 1 else [source]
