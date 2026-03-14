def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def summarize_results(results: list[dict]) -> dict:
    total = len(results)

    strict_correct = sum(1 for r in results if r.get("is_correct_strict"))
    relaxed_correct = sum(1 for r in results if r.get("is_correct_relaxed"))
    final_correct = sum(1 for r in results if r.get("final_label") in {"correct_hard", "correct_semantic", "refusal_correct"})
    avg_cov = _safe_div(sum(float(r.get("coverage_score", 0.0)) for r in results), max(total, 1))
    citation_cov = _safe_div(sum(1 for r in results if r.get("pred_sources")), max(total, 1))

    tp = fp = fn = tn = 0
    for r in results:
        gold_ref = bool(r.get("gold_is_refusal"))
        pred_ref = bool(r.get("pred_refusal"))
        if gold_ref and pred_ref:
            tp += 1
        elif (not gold_ref) and pred_ref:
            fp += 1
        elif gold_ref and (not pred_ref):
            fn += 1
        else:
            tn += 1

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    llm_rows = [r for r in results if isinstance(r.get("llm_judge"), dict) and r["llm_judge"].get("enabled")]
    semantic_pass = sum(1 for r in llm_rows if r["llm_judge"].get("pass") is True)
    avg_sem = _safe_div(sum(float(r["llm_judge"].get("semantic_score") or 0.0) for r in llm_rows), max(len(llm_rows), 1))
    avg_comp = _safe_div(sum(float(r["llm_judge"].get("completeness_score") or 0.0) for r in llm_rows), max(len(llm_rows), 1))
    avg_faith = _safe_div(sum(float(r["llm_judge"].get("faithfulness_score") or 0.0) for r in llm_rows), max(len(llm_rows), 1))

    sim_rows = [r for r in results if isinstance(r.get("embedding_diagnostics"), dict) and r["embedding_diagnostics"].get("enabled")]
    avg_ag = _safe_div(sum(float(r["embedding_diagnostics"].get("ans_gold_sim") or 0.0) for r in sim_rows), max(len(sim_rows), 1))
    avg_aq = _safe_div(sum(float(r["embedding_diagnostics"].get("ans_q_sim") or 0.0) for r in sim_rows), max(len(sim_rows), 1))
    avg_ae = _safe_div(sum(float(r["embedding_diagnostics"].get("ans_evidence_sim") or 0.0) for r in sim_rows), max(len(sim_rows), 1))

    hard_rows = [r for r in results if r.get("question_type") in {"hard_fact_numeric", "hard_fact_entity", "multi_fact", "refusal_expected"}]
    hard_acc = _safe_div(sum(1 for r in hard_rows if r.get("final_label") in {"correct_hard", "refusal_correct"}), max(len(hard_rows), 1))
    sem_rows = [r for r in results if r.get("question_type") == "summary_strategy"]
    sem_pass = _safe_div(sum(1 for r in sem_rows if r.get("final_label") in {"correct_semantic", "partial"}), max(len(sem_rows), 1))

    retrieval_recall_at_20 = _safe_div(sum(1 for r in results if r.get("retrieval_recall_at_20")), max(total, 1))
    final_context_hit_rate = _safe_div(sum(1 for r in results if r.get("final_context_hit")), max(total, 1))
    rerank_gain = _safe_div(sum(float(r.get("rerank_gain", 0.0)) for r in results), max(total, 1))
    avg_rerank_latency_ms = _safe_div(sum(float(r.get("avg_rerank_latency_ms", 0.0)) for r in results), max(total, 1))

    # backward-compatible flat keys + new layered blocks
    summary = {
        "total": total,
        "accuracy": round(_safe_div(relaxed_correct, max(total, 1)), 4),
        "accuracy_strict": round(_safe_div(strict_correct, max(total, 1)), 4),
        "accuracy_relaxed": round(_safe_div(relaxed_correct, max(total, 1)), 4),
        "avg_coverage_score": round(avg_cov, 4),
        "citation_coverage": round(citation_cov, 4),
        "refusal_precision": round(precision, 4),
        "refusal_recall": round(recall, 4),
        "refusal_f1": round(f1, 4),
        "refusal_confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "layer1": {
            "accuracy_strict": round(_safe_div(strict_correct, max(total, 1)), 4),
            "accuracy_relaxed": round(_safe_div(relaxed_correct, max(total, 1)), 4),
        },
        "layer2": {
            "semantic_pass_rate": round(_safe_div(semantic_pass, max(len(llm_rows), 1)), 4),
            "avg_semantic_score": round(avg_sem, 4),
            "avg_completeness_score": round(avg_comp, 4),
            "avg_faithfulness_score": round(avg_faith, 4),
        },
        "layer3": {
            "avg_ans_gold_sim": round(avg_ag, 4),
            "avg_ans_q_sim": round(avg_aq, 4),
            "avg_ans_evidence_sim": round(avg_ae, 4),
        },
        "retrieval": {
            "retrieval_recall_at_20": round(retrieval_recall_at_20, 4),
            "final_context_hit_rate": round(final_context_hit_rate, 4),
            "rerank_gain": round(rerank_gain, 4),
            "avg_rerank_latency_ms": round(avg_rerank_latency_ms, 3),
        },
        "final": {
            "final_accuracy": round(_safe_div(final_correct, max(total, 1)), 4),
            "hard_fact_accuracy": round(hard_acc, 4),
            "semantic_task_pass": round(sem_pass, 4),
        },
    }
    return summary
