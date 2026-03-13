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
class NumericFact:
    raw: str
    value: float
    unit: str
    kind: str


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

    # 常見範圍：一到九十九
    return re.sub(r"[零〇一二兩三四五六七八九]?十[零〇一二兩三四五六七八九]?|[零〇一二兩三四五六七八九]", repl, s)


def canonical_text(s: str) -> str:
    t = normalize_chinese_numbers(normalize_text(s))
    t = t.replace(",", "")
    # 常見等價單位/字尾
    t = t.replace("元", "")
    t = t.replace("年", "")
    return t


def _unit_multiplier(unit: str) -> float:
    u = unit.lower()
    if u in {"億", "亿元", "億元"}:
        return 1e8
    if u in {"萬", "万元", "萬元"}:
        return 1e4
    if u in {"千", "千元"}:
        return 1e3
    return 1.0


def extract_numeric_facts(s: str) -> list[NumericFact]:
    text = normalize_chinese_numbers(normalize_text(s))
    facts: list[NumericFact] = []

    # 百分比
    percent_spans: list[tuple[int, int]] = []
    for m in re.finditer(r"([-+]?\d+(?:\.\d+)?)\s*%", text):
        v = float(m.group(1))
        facts.append(NumericFact(raw=m.group(0), value=v / 100.0, unit="%", kind="ratio"))
        percent_spans.append(m.span())

    def in_percent_span(idx: int) -> bool:
        return any(start <= idx < end for start, end in percent_spans)

    # 一般數值 + 單位
    for m in re.finditer(r"([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*(億|萬元|万|萬|千元|千|元|年)?", text, flags=re.I):
        if in_percent_span(m.start()):
            continue
        raw_num = m.group(1)
        unit = m.group(2) or ""
        try:
            val = float(raw_num)
        except ValueError:
            continue
        if unit == "%":
            continue
        mult = _unit_multiplier(unit)
        kind = "year" if unit == "年" else "number"
        facts.append(NumericFact(raw=m.group(0), value=val * mult, unit=unit, kind=kind))

    return facts


def numeric_equivalent(a: str, b: str, tolerance: float = 0.005) -> bool:
    af = extract_numeric_facts(a)
    bf = extract_numeric_facts(b)
    if not af or not bf:
        return False

    # b 的每個數值都要能在 a 找到近似值
    for target in bf:
        matched = False
        for pred in af:
            denom = max(abs(target.value), 1.0)
            rel_err = abs(pred.value - target.value) / denom
            if rel_err <= tolerance:
                matched = True
                break
        if not matched:
            return False
    return True


def split_subparts(question: str, gold: str) -> list[str]:
    # 優先以 gold 作為子題信息來源（通常較結構化）
    source = normalize_text(gold) if gold else normalize_text(question)
    parts = re.split(r"[;；]|\s+以及\s+|\s+與\s+|\s+及\s+", source)
    parts = [p.strip() for p in parts if p and p.strip()]
    return parts if len(parts) > 1 else [source]
