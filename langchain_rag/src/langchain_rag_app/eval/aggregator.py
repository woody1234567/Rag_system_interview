def aggregate_three_layers(
    question_type: str,
    rule_relaxed: bool,
    pred_refusal: bool,
    gold_is_refusal: bool,
    llm_pass_calibrated: bool | None,
    llm_faithfulness_score: float | None = None,
    judge_reason_codes: list[str] | None = None,
) -> str:
    if gold_is_refusal:
        return "refusal_correct" if pred_refusal else "refusal_incorrect"

    hard_types = {"hard_fact_numeric", "hard_fact_entity"}
    semantic_types = {"summary_strategy", "multi_fact"}

    if question_type in hard_types:
        return "correct_hard" if rule_relaxed else "incorrect"

    if question_type in semantic_types:
        faith = float(llm_faithfulness_score or 0.0)
        llm_ok = llm_pass_calibrated is True

        # safety guard: multi_fact 若明顯 numeric mismatch，最高只給 partial
        has_numeric_mismatch = any(
            (judge_reason_codes or [])
            and (
                "numeric_mismatch" in rc
                or "partial_numeric_match" in rc
            )
            for rc in (judge_reason_codes or [])
        )

        if rule_relaxed and llm_ok:
            if question_type == "multi_fact" and has_numeric_mismatch:
                return "partial"
            return "correct_semantic"

        if llm_ok and faith >= 0.8:
            if question_type == "multi_fact" and has_numeric_mismatch:
                return "partial"
            return "correct_semantic"

        if rule_relaxed or llm_ok:
            return "partial"
        return "incorrect"

    return "correct_hard" if rule_relaxed else "incorrect"
