import unittest

from langchain_rag_app.eval.judge import judge_answer
from langchain_rag_app.eval.normalizers import numeric_equivalent


class TestEvaluator(unittest.TestCase):
    def test_format_equivalent(self):
        jr = judge_answer("每股現金股利為4.25", False, "4.25元", "現金股利每股多少")
        self.assertTrue(jr.is_correct_relaxed)

    def test_percentage_equivalent(self):
        self.assertTrue(numeric_equivalent("1.2E-3", "0.12%"))

    def test_chinese_number_equivalent(self):
        jr = judge_answer("已連續十六年", False, "16 年", "連續幾年")
        self.assertTrue(jr.is_correct_relaxed)

    def test_refusal_expected(self):
        jr = judge_answer("資料不足", True, "【正確拒答說法】年報未提供此資訊（或資料不足，無法推論）。", "預測 114 年 EPS")
        self.assertTrue(jr.is_correct_relaxed)

    def test_multi_subparts_coverage(self):
        jr = judge_answer("總資產12兆673億元", False, "12 兆 673 億元 ; 每股盈餘為10.77元", "總資產和每股盈餘")
        self.assertAlmostEqual(jr.coverage_score, 0.5)


if __name__ == "__main__":
    unittest.main()
