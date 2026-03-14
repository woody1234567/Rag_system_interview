import unittest

from langchain_rag_app.retrieval import BM25Index, RetrievalCandidate, heuristic_rerank, rrf_fusion


class TestRetrievalPipeline(unittest.TestCase):
    def test_bm25_keyword_hit(self):
        docs = [
            {"doc_id": "a", "page": 7, "content": "富邦金控 合併稅後淨利 1508.2 億元", "metadata": {}},
            {"doc_id": "b", "page": 8, "content": "其他公司資訊", "metadata": {}},
        ]
        bm25 = BM25Index(docs)
        top = bm25.search("合併稅後淨利", top_n=1)
        self.assertEqual(top[0][1]["doc_id"], "a")

    def test_rrf_fusion_combines_sources(self):
        d1 = RetrievalCandidate(doc_id="a", page=1, content="a", metadata={})
        d2 = RetrievalCandidate(doc_id="b", page=2, content="b", metadata={})
        d3 = RetrievalCandidate(doc_id="c", page=3, content="c", metadata={})
        dense = [(0.9, d1), (0.8, d2)]
        bm25 = [(12.0, d3), (10.0, d1)]
        fused = rrf_fusion(dense, bm25, rrf_k=60)
        ids = [x.doc_id for x in fused]
        self.assertIn("a", ids)
        self.assertIn("b", ids)
        self.assertIn("c", ids)

    def test_rerank_prefers_keyword_overlap(self):
        q = "富邦金控 2024 淨利"
        c1 = RetrievalCandidate(doc_id="x", page=1, content="富邦金控 2024 淨利為 1508.2 億元", metadata={}, fusion_score=0.02)
        c2 = RetrievalCandidate(doc_id="y", page=2, content="無關內容", metadata={}, fusion_score=0.09)
        top = heuristic_rerank(q, [c1, c2], top_k=1, candidate_pool=2)
        self.assertEqual(top[0].doc_id, "x")


if __name__ == "__main__":
    unittest.main()
