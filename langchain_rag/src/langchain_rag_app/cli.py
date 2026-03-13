import argparse
import json
from pathlib import Path

from .core import answer_question, build_index, load_config, parse_xlsx_questions, project_root
from .eval import is_refusal_gold, judge_answer, summarize_results


def index_cmd() -> None:
    n = build_index()
    print(json.dumps({"chunks": n}, ensure_ascii=False))


def query_cmd() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    args = parser.parse_args()
    ans = answer_question(args.question)
    print(json.dumps(ans, ensure_ascii=False, indent=2))


def eval_cmd() -> None:
    cfg = load_config()
    qa_path = project_root() / cfg["qa_xlsx"]
    questions = parse_xlsx_questions(qa_path)

    results = []

    for row in questions:
        pred = answer_question(row["question"])
        gold_is_refusal = is_refusal_gold(row["gold_answer"])
        jr = judge_answer(
            pred_answer=pred["answer"],
            pred_refusal=pred["refusal"],
            gold_answer=row["gold_answer"],
            question=row["question"],
        )

        results.append(
            {
                **row,
                "gold_is_refusal": gold_is_refusal,
                "pred_answer": pred["answer"],
                "pred_refusal": pred["refusal"],
                "pred_sources": pred["sources"],
                "is_correct_strict": jr.is_correct_strict,
                "is_correct_relaxed": jr.is_correct_relaxed,
                "coverage_score": jr.coverage_score,
                "judge_reason_codes": jr.reason_codes,
            }
        )

    summary = summarize_results(results)

    out_dir = project_root() / "langchain_rag" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "eval_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False))
