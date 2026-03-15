import argparse
import csv
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path


def deep_update(base: dict, patch: dict) -> dict:
    out = deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = v
    return out


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def rank_key(row: dict) -> tuple:
    # 必要條件優先：avg_rerank_gain_k >= 0
    gain_ok = 1 if float(row.get("retrieval.avg_rerank_gain_k", -999)) >= 0 else 0
    return (
        gain_ok,
        float(row.get("accuracy_relaxed", 0.0)),
        float(row.get("retrieval.final_k_hit_rate", 0.0)),
        float(row.get("refusal_f1", 0.0)),
        -float(row.get("retrieval.avg_rerank_latency_ms", 1e9)),
    )


def flatten_summary(summary: dict) -> dict:
    return {
        "accuracy": summary.get("accuracy"),
        "accuracy_strict": summary.get("accuracy_strict"),
        "accuracy_relaxed": summary.get("accuracy_relaxed"),
        "avg_coverage_score": summary.get("avg_coverage_score"),
        "refusal_f1": summary.get("refusal_f1"),
        "retrieval.fusion_k_hit_rate": summary.get("retrieval", {}).get("fusion_k_hit_rate"),
        "retrieval.final_k_hit_rate": summary.get("retrieval", {}).get("final_k_hit_rate"),
        "retrieval.final_context_hit_rate": summary.get("retrieval", {}).get("final_context_hit_rate"),
        "retrieval.avg_rerank_gain_k": summary.get("retrieval", {}).get("avg_rerank_gain_k"),
        "retrieval.pipeline_drop_from_20_to_k": summary.get("retrieval", {}).get("pipeline_drop_from_20_to_k"),
        "retrieval.rerank_gain": summary.get("retrieval", {}).get("rerank_gain"),
        "retrieval.avg_rerank_latency_ms": summary.get("retrieval", {}).get("avg_rerank_latency_ms"),
    }


def run_once(project_dir: Path, timeout_sec: int = 900) -> tuple[int, str]:
    proc = subprocess.run(
        ["uv", "run", "rag-eval"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, output.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--grid", default="experiments/rerank_grid.json")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--retry", type=int, default=1)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    config_path = project_dir / args.config
    grid_path = project_dir / args.grid

    base_config = load_json(config_path)
    grid = load_json(grid_path).get("experiments", [])

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    exp_root = project_dir / "artifacts" / "experiments" / run_id
    exp_root.mkdir(parents=True, exist_ok=True)

    original_config_text = config_path.read_text(encoding="utf-8")
    rows: list[dict] = []

    try:
        for i, exp in enumerate(grid, start=1):
            exp_name = exp.get("name", f"exp_{i:03d}")
            exp_dir = exp_root / f"exp_{i:03d}_{exp_name}"
            exp_dir.mkdir(parents=True, exist_ok=True)

            cfg = deep_update(base_config, exp.get("overrides", {}))
            write_json(exp_dir / "config_snapshot.json", cfg)
            write_json(config_path, cfg)

            status = "failed"
            run_output = ""
            last_code = -1
            attempts = 1 + max(0, int(args.retry))
            for _ in range(attempts):
                code, out = run_once(project_dir)
                run_output = out
                last_code = code
                if code == 0:
                    status = "ok"
                    break

            (exp_dir / "run.log").write_text(run_output, encoding="utf-8")

            summary = {}
            if status == "ok":
                summary_path = project_dir / "artifacts" / "eval_summary.json"
                results_path = project_dir / "artifacts" / "eval_results.json"
                retrieval_debug_path = project_dir / "artifacts" / "eval_retrieval_debug.json"

                if summary_path.exists():
                    summary = load_json(summary_path)
                    shutil.copy2(summary_path, exp_dir / "eval_summary.json")
                if results_path.exists():
                    shutil.copy2(results_path, exp_dir / "eval_results.json")
                if retrieval_debug_path.exists():
                    shutil.copy2(retrieval_debug_path, exp_dir / "eval_retrieval_debug.json")

            row = {
                "exp_id": i,
                "exp_name": exp_name,
                "status": status,
                "exit_code": last_code,
                "rerank.type": cfg.get("rerank", {}).get("type"),
                "rerank.candidate_pool": cfg.get("rerank", {}).get("candidate_pool"),
                "rerank.top_k": cfg.get("rerank", {}).get("top_k"),
                "fusion.rrf_k": cfg.get("fusion", {}).get("rrf_k"),
            }
            row.update(flatten_summary(summary) if summary else {})
            rows.append(row)

        # leaderboard
        ok_rows = [r for r in rows if r.get("status") == "ok"]
        ok_rows.sort(key=rank_key, reverse=True)

        leaderboard = ok_rows[: max(1, args.top_n)]
        write_json(exp_root / "leaderboard.json", leaderboard)

        # csv outputs
        columns = [
            "exp_id",
            "exp_name",
            "status",
            "exit_code",
            "rerank.type",
            "rerank.candidate_pool",
            "rerank.top_k",
            "fusion.rrf_k",
            "accuracy",
            "accuracy_strict",
            "accuracy_relaxed",
            "avg_coverage_score",
            "refusal_f1",
            "retrieval.fusion_k_hit_rate",
            "retrieval.final_k_hit_rate",
            "retrieval.final_context_hit_rate",
            "retrieval.avg_rerank_gain_k",
            "retrieval.pipeline_drop_from_20_to_k",
            "retrieval.rerank_gain",
            "retrieval.avg_rerank_latency_ms",
        ]

        for path, data in [
            (exp_root / "results.json", rows),
            (project_dir / "artifacts" / "experiments" / "latest_summary.json", rows),
        ]:
            write_json(path, data)

        for path, data in [
            (exp_root / "leaderboard.csv", leaderboard),
            (project_dir / "artifacts" / "experiments" / "latest_summary.csv", rows),
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for r in data:
                    writer.writerow({k: r.get(k) for k in columns})

        best = leaderboard[0] if leaderboard else None
        if best:
            print("Best config suggestion:")
            print(json.dumps(best, ensure_ascii=False, indent=2))
        else:
            print("No successful experiment runs.")

        print(f"Run id: {run_id}")
        print(f"Saved to: {exp_root}")
        return 0
    finally:
        config_path.write_text(original_config_text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
