import argparse
import json
import re
from pathlib import Path

from .core import answer_question, build_index, load_config, parse_xlsx_questions, project_root
from .eval import (
    aggregate_three_layers,
    classify_question_type,
    compute_similarity_diagnostics,
    is_refusal_gold,
    judge_answer,
    judge_with_llm,
    summarize_results,
)


def index_cmd() -> None:
    n = build_index()
    print(json.dumps({"chunks": n}, ensure_ascii=False))


def query_cmd() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    args = parser.parse_args()
    ans = answer_question(args.question)
    print(json.dumps(ans, ensure_ascii=False, indent=2))


def _parse_gold_pages(raw: str) -> set[int]:
    text = (raw or "").replace("~", "-")
    nums = re.findall(r"\d+\s*-\s*\d+|\d+", text)
    pages: set[int] = set()
    for n in nums:
        if "-" in n:
            a, b = [int(x.strip()) for x in n.split("-")]
            lo, hi = min(a, b), max(a, b)
            for p in range(lo, hi + 1):
                pages.add(p)
        else:
            pages.add(int(n))
    return pages


def eval_cmd() -> None:
    cfg = load_config()
    qa_path = project_root() / cfg["qa_xlsx"]
    questions = parse_xlsx_questions(qa_path)

    results = []

    eval_cfg = cfg.get("eval", {}) if isinstance(cfg, dict) else {}
    llm_enable_types = set(eval_cfg.get("llm_judge_enable_types", ["summary_strategy", "multi_fact"]))
    llm_sample_rate = float(eval_cfg.get("llm_judge_sample_rate", 1.0))
    similarity_enabled = bool(eval_cfg.get("similarity_enabled", True))

    for row in questions:
        pred = answer_question(row["question"])
        gold_is_refusal = is_refusal_gold(row["gold_answer"])
        qtype = classify_question_type(row["question"], row["gold_answer"])

        jr = judge_answer(
            pred_answer=pred["answer"],
            pred_refusal=pred["refusal"],
            gold_answer=row["gold_answer"],
            question=row["question"],
        )

        evidence = pred.get("evidence_text", "")
        llm_enabled = (qtype in llm_enable_types) and (llm_sample_rate >= 1.0)
        llm_judge = judge_with_llm(
            question=row["question"],
            gold=row["gold_answer"],
            pred=pred["answer"],
            evidence=evidence,
            enabled=llm_enabled,
        )

        sim = compute_similarity_diagnostics(
            answer=pred["answer"],
            gold=row["gold_answer"],
            question=row["question"],
            evidence=evidence,
            enabled=similarity_enabled,
        )

        final_label = aggregate_three_layers(
            question_type=qtype,
            rule_relaxed=jr.is_correct_relaxed,
            pred_refusal=pred["refusal"],
            gold_is_refusal=gold_is_refusal,
            llm_pass=llm_judge.get("pass"),
        )

        gold_pages = _parse_gold_pages(row.get("gold_pages", ""))
        fusion_pages = {int(x.get("page", -1)) for x in pred.get("retrieval_debug", {}).get("fusion_top", []) if int(x.get("page", -1)) > 0}
        final_pages = {int(x.get("page", -1)) for x in pred.get("retrieval_debug", {}).get("final_docs", []) if int(x.get("page", -1)) > 0}
        retrieval_recall_at_20 = bool(gold_pages and (gold_pages & fusion_pages))
        final_context_hit = bool(gold_pages and (gold_pages & final_pages))

        results.append(
            {
                **row,
                "question_type": qtype,
                "gold_is_refusal": gold_is_refusal,
                "pred_answer": pred["answer"],
                "pred_refusal": pred["refusal"],
                "pred_sources": pred["sources"],
                "rule_judge": {
                    "strict": jr.is_correct_strict,
                    "relaxed": jr.is_correct_relaxed,
                    "coverage": jr.coverage_score,
                    "reasons": jr.reason_codes,
                },
                "is_correct_strict": jr.is_correct_strict,
                "is_correct_relaxed": jr.is_correct_relaxed,
                "coverage_score": jr.coverage_score,
                "judge_reason_codes": jr.reason_codes,
                "failed_numeric_facts": jr.failed_numeric_facts,
                "numeric_match_detail": {
                    "failed_count": len(jr.failed_numeric_facts),
                    "all_numeric_matched": len(jr.failed_numeric_facts) == 0,
                },
                "llm_judge": llm_judge,
                "embedding_diagnostics": sim,
                "final_label": final_label,
                "retrieval_debug": pred.get("retrieval_debug", {}),
                "reranker_type": pred.get("retrieval_debug", {}).get("reranker_type", "none"),
                "candidate_pool_size": pred.get("retrieval_debug", {}).get("candidate_pool_size", 0),
                "avg_rerank_latency_ms": pred.get("retrieval_debug", {}).get("rerank_latency_ms", 0.0),
                "retrieval_recall_at_20": retrieval_recall_at_20,
                "final_context_hit": final_context_hit,
                "rerank_gain": int(final_context_hit) - int(retrieval_recall_at_20),
            }
        )

    summary = summarize_results(results)

    out_dir = project_root() / "langchain_rag" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "eval_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    retrieval_debug = [
        {
            "qid": r.get("qid"),
            "question": r.get("question"),
            "gold_pages": r.get("gold_pages"),
            "retrieval_debug": r.get("retrieval_debug", {}),
        }
        for r in results
    ]
    (out_dir / "eval_retrieval_debug.json").write_text(json.dumps(retrieval_debug, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
