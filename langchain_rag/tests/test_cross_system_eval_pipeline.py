import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


report_mod = _load_module("build_comparison_report", ROOT / "scripts" / "build_comparison_report.py")
run_mod = _load_module("run_cross_system_eval", ROOT / "scripts" / "run_cross_system_eval.py")


class TestCrossSystemEvalPipeline(unittest.TestCase):
    def test_unified_evaluate_basic(self):
        rows = [
            {
                "qid": "1",
                "question": "富邦金控 113 年度合併稅後淨利是多少？",
                "gold_answer": "1,508.2 億元",
                "gold_pages": "7",
                "pred_answer": "1,508.2 億元",
                "pred_refusal": False,
                "pred_sources": [7],
            }
        ]
        results, summary = run_mod.unified_evaluate(rows)
        self.assertEqual(len(results), 1)
        self.assertIn("accuracy_relaxed", summary)

    def test_report_delta(self):
        b = {"accuracy_relaxed": 0.2, "final": {"final_accuracy": 0.2}, "retrieval": {}}
        l = {"accuracy_relaxed": 0.5, "final": {"final_accuracy": 0.4}, "retrieval": {}}
        rep = report_mod.build_report(b, l)
        metrics = {x["metric"]: x for x in rep["comparison"]}
        self.assertAlmostEqual(metrics["accuracy_relaxed"]["delta"], 0.3)


if __name__ == "__main__":
    unittest.main()
