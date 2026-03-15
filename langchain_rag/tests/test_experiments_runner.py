import unittest

from scripts.run_rerank_experiments import deep_update, flatten_summary, rank_key


class TestExperimentsRunner(unittest.TestCase):
    def test_deep_update(self):
        base = {"a": 1, "b": {"x": 1, "y": 2}}
        patch = {"b": {"y": 9, "z": 3}, "c": 4}
        out = deep_update(base, patch)
        self.assertEqual(out["b"]["x"], 1)
        self.assertEqual(out["b"]["y"], 9)
        self.assertEqual(out["b"]["z"], 3)
        self.assertEqual(out["c"], 4)

    def test_flatten_summary(self):
        s = {
            "accuracy": 0.5,
            "accuracy_strict": 0.2,
            "accuracy_relaxed": 0.5,
            "avg_coverage_score": 0.6,
            "refusal_f1": 0.3,
            "retrieval": {
                "final_context_hit_rate": 0.7,
                "rerank_gain": 0.1,
                "avg_rerank_latency_ms": 12.3,
            },
        }
        row = flatten_summary(s)
        self.assertEqual(row["retrieval.final_context_hit_rate"], 0.7)
        self.assertEqual(row["retrieval.rerank_gain"], 0.1)

    def test_rank_key_prefers_gain_non_negative(self):
        good = {
            "accuracy_relaxed": 0.4,
            "retrieval.final_context_hit_rate": 0.5,
            "refusal_f1": 0.2,
            "retrieval.avg_rerank_latency_ms": 10,
            "retrieval.rerank_gain": 0.0,
        }
        bad = {
            "accuracy_relaxed": 0.9,
            "retrieval.final_context_hit_rate": 0.9,
            "refusal_f1": 0.9,
            "retrieval.avg_rerank_latency_ms": 1,
            "retrieval.rerank_gain": -0.1,
        }
        self.assertGreater(rank_key(good), rank_key(bad))


if __name__ == "__main__":
    unittest.main()
