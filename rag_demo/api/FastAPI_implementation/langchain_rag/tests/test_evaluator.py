import unittest

from langchain_rag_app.eval.judge import judge_answer
from langchain_rag_app.eval.normalizers import compare_numeric_facts, numeric_equivalent


class TestEvaluator(unittest.TestCase):
    def test_year_mismatch_should_fail(self):
        self.assertFalse(numeric_equivalent("目標年份2050年", "目標年份2040年"))

    def test_percentage_equivalent(self):
        self.assertTrue(numeric_equivalent("1.2E-3", "0.12%"))

    def test_currency_missing_unit_should_fail_by_default(self):
        # revised plan: allow_unitless_currency_match=false (default)
        self.assertFalse(numeric_equivalent("每股現金股利為4.25", "4.25元"))

    def test_multi_numeric_partial_should_fail_relaxed(self):
        jr = judge_answer("發明專利13件", False, "發明專利 13 件、新型專利 27 件", "發明與新型專利各多少")
        self.assertFalse(jr.is_correct_relaxed)
        self.assertTrue(any("partial_numeric_match" in c for c in jr.reason_codes))

    def test_chinese_number_equivalent(self):
        jr = judge_answer("已連續十六年", False, "16 年", "連續幾年")
        self.assertTrue(jr.is_correct_relaxed)

    def test_refusal_expected(self):
        jr = judge_answer("資料不足", True, "【正確拒答說法】年報未提供此資訊（或資料不足，無法推論）。", "預測 114 年 EPS")
        self.assertTrue(jr.is_correct_relaxed)

    def test_reason_code_year_mismatch(self):
        res = compare_numeric_facts("2050年", "2040年")
        self.assertFalse(res.matched)
        self.assertIn("numeric_mismatch_year", res.reason_codes)


if __name__ == "__main__":
    unittest.main()
