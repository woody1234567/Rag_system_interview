import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_comparison_report import build_report, write_markdown
from eval_adapters import load_baseline_predictions, load_langchain_predictions

# Reuse single source-of-truth judge from langchain_rag
sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "langchain_rag" / "src").resolve()))
from langchain_rag_app.eval import aggregate_three_layers, classify_question_type, is_refusal_gold, judge_answer, summarize_results  # type: ignore  # noqa: E402


def unified_evaluate(rows: list[dict]) -> tuple[list[dict], dict]:
    results = []
    for row in rows:
        qtype = classify_question_type(row.get("question", ""), row.get("gold_answer", ""))
        gold_is_refusal = is_refusal_gold(row.get("gold_answer", ""))
        jr = judge_answer(
            pred_answer=row.get("pred_answer", ""),
            pred_refusal=bool(row.get("pred_refusal", False)),
            gold_answer=row.get("gold_answer", ""),
            question=row.get("question", ""),
        )

        llm_judge = {
            "enabled": False,
            "pass_raw": None,
            "pass_calibrated": None,
            "weighted_score": None,
            "calibrated_reason": "cross_system_eval_disabled",
            "semantic_score": None,
            "completeness_score": None,
            "faithfulness_score": None,
        }
        embedding_diag = {"enabled": False, "ans_gold_sim": None, "ans_q_sim": None, "ans_evidence_sim": None}

        final_label = aggregate_three_layers(
            question_type=qtype,
            rule_relaxed=jr.is_correct_relaxed,
            pred_refusal=bool(row.get("pred_refusal", False)),
            gold_is_refusal=gold_is_refusal,
            llm_pass_calibrated=None,
            llm_faithfulness_score=None,
            judge_reason_codes=jr.reason_codes,
        )

        results.append(
            {
                **row,
                "question_type": qtype,
                "gold_is_refusal": gold_is_refusal,
                "is_correct_strict": jr.is_correct_strict,
                "is_correct_relaxed": jr.is_correct_relaxed,
                "coverage_score": jr.coverage_score,
                "judge_reason_codes": jr.reason_codes,
                "failed_numeric_facts": jr.failed_numeric_facts,
                "llm_judge": llm_judge,
                "embedding_diagnostics": embedding_diag,
                "final_label": final_label,
                "pred_sources": row.get("pred_sources", []),
                "gate_decision": "allow_answer",
                "retrieval_recall_at_20": False,
                "fusion_k_hit": False,
                "final_k_hit": False,
                "final_context_hit": False,
                "rerank_gain_k": 0,
                "pipeline_drop_from_20_to_k": 0,
                "rerank_gain": 0,
                "avg_rerank_latency_ms": 0.0,
            }
        )

    summary = summarize_results(results)
    return results, summary


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--run-langchain-eval", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    if args.run_langchain_eval:
        subprocess.run(["uv", "run", "rag-eval"], cwd=str(root / "langchain_rag"), check=True)

    baseline_in = root / "baseline_model" / "artifacts" / "eval_results.jsonl"
    langchain_in = root / "langchain_rag" / "artifacts" / "eval_results.json"

    baseline_rows = load_baseline_predictions(baseline_in)
    langchain_rows = load_langchain_predictions(langchain_in)

    b_results, b_summary = unified_evaluate(baseline_rows)
    l_results, l_summary = unified_evaluate(langchain_rows)

    # overwrite standardized outputs as requested
    save_json(root / "baseline_model" / "artifacts" / "eval_results.json", b_results)
    save_json(root / "baseline_model" / "artifacts" / "eval_summary.json", b_summary)
    save_json(root / "langchain_rag" / "artifacts" / "eval_results_unified.json", l_results)
    save_json(root / "langchain_rag" / "artifacts" / "eval_summary_unified.json", l_summary)

    run_id = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
    out_dir = root / "artifacts" / "cross_system" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    save_json(out_dir / "baseline_eval_summary.json", b_summary)
    save_json(out_dir / "langchain_eval_summary.json", l_summary)

    report = build_report(b_summary, l_summary)
    save_json(root / "artifacts" / "cross_system" / "comparison_report.json", report)
    write_markdown(report, root / "artifacts" / "cross_system" / "comparison_report.md")
    save_json(out_dir / "comparison_report.json", report)
    write_markdown(report, out_dir / "comparison_report.md")

    # config snapshot for traceability
    snapshot = {
        "baseline_input": str(baseline_in),
        "langchain_input": str(langchain_in),
        "judge_source": "langchain_rag_app.eval",
    }
    save_json(out_dir / "run_config_snapshot.json", snapshot)

    print(json.dumps({"status": "ok", "run_id": run_id, "out_dir": str(out_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
