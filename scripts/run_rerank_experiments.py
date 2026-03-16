"""Compatibility wrapper to expose langchain_rag experiment runner under root scripts package."""

import importlib.util
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "langchain_rag" / "scripts" / "run_rerank_experiments.py"

spec = importlib.util.spec_from_file_location("lc_run_rerank_experiments", str(TARGET))
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


deep_update = module.deep_update
flatten_summary = module.flatten_summary
rank_key = module.rank_key
main = module.main
