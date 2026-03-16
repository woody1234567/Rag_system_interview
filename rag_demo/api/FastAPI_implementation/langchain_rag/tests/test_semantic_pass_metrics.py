import unittest

from langchain_rag_app.eval.metrics import summarize_results


class TestSemanticPassMetrics(unittest.TestCase):
    def _row(self, qtype: str, final_label: str, llm_pass_calibrated: bool):
        return {
            "is_correct_strict": False,
            "is_correct_relaxed": False,
            "coverage_score": 0.0,
            "pred_sources": [1],
            "gold_is_refusal": False,
            "pred_refusal": False,
            "llm_judge": {
                "enabled": True,
                "pass_calibrated": llm_pass_calibrated,
                "semantic_score": 0.8,
                "completeness_score": 0.8,
                "faithfulness_score": 0.9,
            },
            "embedding_diagnostics": {"enabled": False},
            "question_type": qtype,
            "final_label": final_label,
            "retrieval_recall_at_20": False,
            "fusion_k_hit": False,
            "final_k_hit": False,
            "final_context_hit": False,
            "rerank_gain_k": 0,
            "pipeline_drop_from_20_to_k": 0,
            "rerank_gain": 0,
            "avg_rerank_latency_ms": 0.0,
            "gate_decision": "allow_answer",
        }

    def test_semantic_task_pass_includes_multifact(self):
        rows = [
            self._row("summary_strategy", "partial", True),
            self._row("multi_fact", "correct_semantic", True),
            self._row("hard_fact_numeric", "incorrect", False),
        ]
        s = summarize_results(rows)
        self.assertGreaterEqual(s["final"]["semantic_task_pass"], 0.9)
        self.assertGreaterEqual(s["final"]["semantic_task_pass_multifact"], 0.9)


if __name__ == "__main__":
    unittest.main()
