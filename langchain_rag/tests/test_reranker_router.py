import unittest

from langchain_rag_app.retrieval import RetrievalCandidate, rerank_candidates


class TestRerankerRouter(unittest.TestCase):
    def _cands(self):
        return [
            RetrievalCandidate(doc_id="a", page=1, content="富邦金控 2024 淨利 1508.2 億元", metadata={}, fusion_score=0.1),
            RetrievalCandidate(doc_id="b", page=2, content="其他內容", metadata={}, fusion_score=0.2),
            RetrievalCandidate(doc_id="c", page=3, content="富邦人壽 2025 策略", metadata={}, fusion_score=0.05),
        ]

    def test_none_reranker(self):
        cfg = {"k": 2, "rerank": {"type": "none", "top_k": 2, "candidate_pool": 3}}
        rr = rerank_candidates("富邦金控淨利", self._cands(), cfg)
        self.assertEqual(rr.reranker_type, "none")
        self.assertEqual(len(rr.candidates), 2)

    def test_heuristic_reranker(self):
        cfg = {"k": 2, "rerank": {"type": "heuristic", "top_k": 2, "candidate_pool": 3, "heuristic": {"year_bonus": 0.1}}}
        rr = rerank_candidates("富邦金控 2024 淨利", self._cands(), cfg)
        self.assertIn(rr.reranker_type, {"heuristic"})
        self.assertEqual(len(rr.candidates), 2)

    def test_cross_encoder_fallback(self):
        cfg = {
            "k": 2,
            "rerank": {
                "type": "cross_encoder",
                "top_k": 2,
                "candidate_pool": 3,
                "cross_encoder": {"model_name": "non-existent", "batch_size": 2, "max_length": 64, "device": "cpu"},
                "heuristic": {"year_bonus": 0.1},
            },
        }
        rr = rerank_candidates("富邦金控 2024 淨利", self._cands(), cfg)
        self.assertTrue(rr.fallback_used)
        self.assertEqual(rr.reranker_type, "cross_encoder_fallback_heuristic")


if __name__ == "__main__":
    unittest.main()
