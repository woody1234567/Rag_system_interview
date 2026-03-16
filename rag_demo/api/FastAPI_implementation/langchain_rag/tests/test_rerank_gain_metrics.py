import unittest

from langchain_rag_app.eval.metrics import summarize_results


class TestRerankGainMetrics(unittest.TestCase):
    def _row(self, fusion_hit: bool, final_hit: bool):
        return {
            "is_correct_strict": False,
            "is_correct_relaxed": False,
            "coverage_score": 0.0,
            "pred_sources": [1],
            "gold_is_refusal": False,
            "pred_refusal": False,
            "llm_judge": {"enabled": False},
            "embedding_diagnostics": {"enabled": False},
            "question_type": "hard_fact_numeric",
            "final_label": "incorrect",
            "retrieval_recall_at_20": False,
            "fusion_k_hit": fusion_hit,
            "final_k_hit": final_hit,
            "final_context_hit": final_hit,
            "rerank_gain_k": int(final_hit) - int(fusion_hit),
            "pipeline_drop_from_20_to_k": int(final_hit) - 0,
            "rerank_gain": int(final_hit) - 0,
            "avg_rerank_latency_ms": 1.0,
        }

    def test_gain_plus_one(self):
        s = summarize_results([self._row(False, True)])
        self.assertEqual(s["retrieval"]["avg_rerank_gain_k"], 1.0)

    def test_gain_zero_hit_hit(self):
        s = summarize_results([self._row(True, True)])
        self.assertEqual(s["retrieval"]["avg_rerank_gain_k"], 0.0)

    def test_gain_minus_one(self):
        s = summarize_results([self._row(True, False)])
        self.assertEqual(s["retrieval"]["avg_rerank_gain_k"], -1.0)

    def test_gain_zero_miss_miss(self):
        s = summarize_results([self._row(False, False)])
        self.assertEqual(s["retrieval"]["avg_rerank_gain_k"], 0.0)


if __name__ == "__main__":
    unittest.main()
