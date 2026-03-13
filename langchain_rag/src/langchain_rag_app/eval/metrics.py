def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def summarize_results(results: list[dict]) -> dict:
    total = len(results)

    strict_correct = sum(1 for r in results if r.get("is_correct_strict"))
    relaxed_correct = sum(1 for r in results if r.get("is_correct_relaxed"))
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

    return {
        "total": total,
        "accuracy_strict": round(_safe_div(strict_correct, max(total, 1)), 4),
        "accuracy_relaxed": round(_safe_div(relaxed_correct, max(total, 1)), 4),
        "avg_coverage_score": round(avg_cov, 4),
        "citation_coverage": round(citation_cov, 4),
        "refusal_precision": round(precision, 4),
        "refusal_recall": round(recall, 4),
        "refusal_f1": round(f1, 4),
        "refusal_confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }
