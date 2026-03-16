import unittest

from langchain_rag_app.gate import analyze_evidence, extract_question_signals, run_evidence_gate


class TestEvidenceGate(unittest.TestCase):
    def _cfg(self):
        return {
            "gate": {
                "enabled": True,
                "min_subquestion_coverage": 0.8,
                "min_evidence_confidence": 0.6,
                "hard_rules": {
                    "require_entity_match": True,
                    "require_numeric_evidence_for_hard_fact": True,
                    "block_out_of_scope": True,
                },
            }
        }

    def test_out_of_scope_force_refusal(self):
        q = "根據年報，國泰金控2024淨利是多少？"
        s = extract_question_signals(q, "hard_fact_numeric")
        e = analyze_evidence(s, "富邦金控資料", [7])
        g = run_evidence_gate(s, e, self._cfg())
        self.assertEqual(g["decision"], "force_refusal")
        self.assertIn("out_of_scope_question", g["reasons"])

    def test_hard_fact_without_numeric_force_refusal(self):
        q = "富邦金控 2024 年淨利是多少？"
        s = extract_question_signals(q, "hard_fact_numeric")
        e = analyze_evidence(s, "富邦金控表現良好", [7])
        g = run_evidence_gate(s, e, self._cfg())
        self.assertEqual(g["decision"], "force_refusal")
        self.assertIn("insufficient_numeric_evidence", g["reasons"])

    def test_multifact_low_coverage_force_refusal(self):
        q = "請回答總資產與每股盈餘"
        s = extract_question_signals(q, "multi_fact")
        # no connector in evidence -> low coverage
        e = analyze_evidence(s, "總資產為12兆673億元", [7])
        g = run_evidence_gate(s, e, self._cfg())
        self.assertEqual(g["decision"], "force_refusal")
        self.assertIn("subquestion_coverage_too_low", g["reasons"])

    def test_good_evidence_allow_answer(self):
        q = "富邦金控 2024 年淨利是多少？"
        s = extract_question_signals(q, "hard_fact_numeric")
        e = analyze_evidence(s, "富邦金控 2024 年合併稅後淨利 1508.2 億元", [7])
        g = run_evidence_gate(s, e, self._cfg())
        self.assertEqual(g["decision"], "allow_answer")

    def test_boundary_coverage_08(self):
        cfg = self._cfg()
        cfg["gate"]["min_subquestion_coverage"] = 0.8
        q = "請比較A與B與C與D與E"
        s = extract_question_signals(q, "multi_fact")
        e = {
            "entity_match": True,
            "year_match": True,
            "numeric_support": True,
            "subquestion_coverage": 0.8,
            "evidence_confidence": 0.9,
            "source_count": 1,
        }
        g = run_evidence_gate(s, e, cfg)
        self.assertEqual(g["decision"], "allow_answer")


if __name__ == "__main__":
    unittest.main()
