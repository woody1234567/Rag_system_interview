import re
from dataclasses import dataclass
from typing import Any


OUT_OF_SCOPE_COMPANIES = ["國泰金控", "國泰", "中信金", "玉山金", "兆豐金", "台新金"]
ENTITY_CANDIDATES = [
    "富邦金控",
    "富邦人壽",
    "富邦產險",
    "富邦證券",
    "台北富邦銀行",
    "北富銀",
    "富邦銀行",
]
METRIC_TERMS = ["多少", "幾", "比例", "總額", "每股", "淨利", "成長率", "eps", "逾放比", "car"]


@dataclass
class GateSignals:
    entities: list[str]
    years: list[str]
    metric_terms: list[str]
    question_type: str
    subparts_total: int
    out_of_scope: bool


def extract_question_signals(question: str, question_type: str = "") -> GateSignals:
    q = question or ""
    entities = [e for e in ENTITY_CANDIDATES if e in q]
    years = re.findall(r"(19\d{2}|20\d{2}|11\d)", q)
    metric_terms = [m for m in METRIC_TERMS if m.lower() in q.lower()]

    out_of_scope = any(c in q for c in OUT_OF_SCOPE_COMPANIES)
    subparts = re.split(r"[;；]|以及|與|及|、|比較", q)
    subparts_total = len([x for x in subparts if x.strip()])

    return GateSignals(
        entities=entities,
        years=years,
        metric_terms=metric_terms,
        question_type=question_type or "",
        subparts_total=max(1, subparts_total),
        out_of_scope=out_of_scope,
    )


def analyze_evidence(signals: GateSignals, evidence_text: str, sources: list[int]) -> dict[str, Any]:
    text = evidence_text or ""
    entity_match = True
    if signals.entities:
        entity_match = any(e in text for e in signals.entities)

    years_in_evidence = set(re.findall(r"(19\d{2}|20\d{2}|11\d)", text))
    year_match = True if not signals.years else any(y in years_in_evidence for y in signals.years)

    numeric_hits = re.findall(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?\s*(?:%|元|千元|萬|萬元|億|億元|年|件|名|人)?", text.lower())
    numeric_support = len([x for x in numeric_hits if x.strip()]) > 0

    subparts_hit = 0
    if signals.subparts_total > 1:
        for token in ["以及", "與", "及", "、", ";", "；"]:
            if token in text:
                subparts_hit += 1
        # heuristic cap
        subparts_hit = min(signals.subparts_total, max(1, subparts_hit + 1))
    else:
        subparts_hit = 1

    sub_cov = subparts_hit / max(signals.subparts_total, 1)

    # confidence (simple weighted)
    confidence = 0.0
    confidence += 0.35 if entity_match else 0.0
    confidence += 0.25 if year_match else 0.0
    confidence += 0.25 if numeric_support or not signals.metric_terms else 0.0
    confidence += 0.15 * min(sub_cov, 1.0)

    return {
        "entity_match": entity_match,
        "year_match": year_match,
        "numeric_support": numeric_support,
        "subquestion_coverage": round(sub_cov, 4),
        "evidence_confidence": round(min(confidence, 1.0), 4),
        "source_count": len(sources or []),
    }


def run_evidence_gate(signals: GateSignals, evidence: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    gate_cfg = cfg.get("gate", {}) if isinstance(cfg, dict) else {}
    enabled = bool(gate_cfg.get("enabled", False))
    if not enabled:
        return {
            "enabled": False,
            "decision": "allow_answer",
            "reasons": [],
            "evidence_confidence": evidence.get("evidence_confidence", 0.0),
            "entity_match": evidence.get("entity_match", True),
            "subquestion_coverage": evidence.get("subquestion_coverage", 1.0),
        }

    reasons: list[str] = []
    hard = gate_cfg.get("hard_rules", {})
    min_cov = float(gate_cfg.get("min_subquestion_coverage", 0.8))
    min_conf = float(gate_cfg.get("min_evidence_confidence", 0.6))

    if signals.out_of_scope and bool(hard.get("block_out_of_scope", True)):
        reasons.append("out_of_scope_question")

    if bool(hard.get("require_entity_match", True)) and not evidence.get("entity_match", True):
        reasons.append("missing_entity_match")

    is_hard_fact = signals.question_type in {"hard_fact_numeric", "multi_fact", "hard_fact_entity"} or bool(signals.metric_terms)
    if is_hard_fact and bool(hard.get("require_numeric_evidence_for_hard_fact", True)) and not evidence.get("numeric_support", False):
        reasons.append("insufficient_numeric_evidence")

    if signals.subparts_total > 1 and evidence.get("subquestion_coverage", 0.0) < min_cov:
        reasons.append("subquestion_coverage_too_low")

    if evidence.get("evidence_confidence", 0.0) < min_conf:
        reasons.append("low_evidence_confidence")

    decision = "force_refusal" if reasons else "allow_answer"

    return {
        "enabled": True,
        "decision": decision,
        "reasons": reasons,
        "evidence_confidence": evidence.get("evidence_confidence", 0.0),
        "entity_match": evidence.get("entity_match", True),
        "subquestion_coverage": evidence.get("subquestion_coverage", 1.0),
    }
