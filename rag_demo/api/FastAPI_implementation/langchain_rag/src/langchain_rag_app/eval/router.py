import re


def classify_question_type(question: str, gold_answer: str = "") -> str:
    q = (question or "").lower()
    g = (gold_answer or "").lower()

    if any(k in g for k in ["拒答", "無法推論", "資料不足"]):
        return "refusal_expected"

    if any(k in q for k in ["總結", "簡述", "彙整", "策略"]):
        return "summary_strategy"

    if any(k in q for k in ["比較", "各", "分別", "以及", "與", ";", "；"]):
        return "multi_fact"

    if any(k in q for k in ["多少", "幾", "比例", "總額", "每股", "成長率", "%", "率"]):
        return "hard_fact_numeric"

    if re.search(r"(是什麼|有哪些|哪.*)", q):
        return "hard_fact_entity"

    return "hard_fact_entity"
