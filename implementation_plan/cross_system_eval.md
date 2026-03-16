# cross_system_eval.md — Baseline vs LangChain RAG 公平比較評測管線計畫

> 目標：建立一套 **cross-system eval pipeline**，用同一份題庫、同一套 judge、同一組 metrics，公平比較 `baseline_model` 與 `langchain_rag` 的實際能力差異。

---

## 1) 問題定義

目前 `baseline_model` 與 `langchain_rag` 的評測流程不同，導致比較可能失真。

### 核心要求
1. 同題庫（questions + gold + pages + question_type）
2. 同 judge（strict/relaxed/numeric/refusal/semantic）
3. 同 summary 指標
4. 同輸出 schema

---

## 2) 目標產出

建立以下標準化結果：

- `baseline_model/artifacts/eval_results.json`
- `baseline_model/artifacts/eval_summary.json`
- `langchain_rag/artifacts/eval_results.json`
- `langchain_rag/artifacts/eval_summary.json`
- `artifacts/cross_system/comparison_report.json`
- `artifacts/cross_system/comparison_report.md`

---

## 3) 架構設計

## 3.1 Single Judge Source of Truth

將 `langchain_rag` 目前 eval 模組視為唯一真實評測邏輯：
- `eval/judge.py`
- `eval/metrics.py`
- `eval/aggregator.py`
- `eval/llm_judge.py`（若啟用）
- `eval/similarity.py`（若啟用）

`baseline_model` 不再自帶另一套判分，改為「只產生預測」，再交由同一個 judge 評分。

## 3.2 兩段式流程

### Stage A — Prediction Generation
- Baseline 產生 `pred_answer/pred_refusal/pred_sources`
- LangChain 產生 `pred_answer/pred_refusal/pred_sources`

### Stage B — Unified Evaluation
- 兩系統都交給同一套 eval 函式
- 產生一致 schema 的 results/summary

---

## 4) 資料契約（Data Contract）

## 4.1 輸入題目欄位（必備）

- `qid`
- `question`
- `gold_answer`
- `gold_pages`
- `question_type`
- `gold_is_refusal`

## 4.2 系統預測欄位（必備）

- `pred_answer`
- `pred_refusal`
- `pred_sources`

## 4.3 統一評測輸出欄位（至少）

- `is_correct_strict`
- `is_correct_relaxed`
- `coverage_score`
- `judge_reason_codes`
- `llm_judge`（可啟用/關閉）
- `embedding_diagnostics`（可啟用/關閉）
- `final_label`

---

## 5) 檔案與腳本規劃

## 5.1 建議新增腳本

1. `scripts/run_cross_system_eval.py`
   - 入口腳本，一次跑兩個系統

2. `scripts/eval_adapters/baseline_adapter.py`
   - 將 baseline 輸出映射到統一 schema

3. `scripts/eval_adapters/langchain_adapter.py`
   - 讀取 langchain 預測輸出並映射

4. `scripts/build_comparison_report.py`
   - 匯總兩份 summary，輸出比較報告

## 5.2 建議輸出路徑

- `artifacts/cross_system/run_<timestamp>/`
  - `baseline_eval_summary.json`
  - `langchain_eval_summary.json`
  - `comparison_report.json`
  - `comparison_report.md`

---

## 6) 指標對齊與比較規則

## 6.1 主比較指標

- `accuracy_strict`
- `accuracy_relaxed`
- `final_accuracy`
- `refusal_precision / recall / f1`
- `avg_coverage_score`
- `semantic_task_pass`

## 6.2 檢索相關（僅 RAG 有）

- `retrieval_recall_at_20`
- `final_k_hit_rate`
- `avg_rerank_gain_k`

> 若 baseline 無檢索結構，可標註 `N/A`，避免錯誤比較。

## 6.3 報告格式

每個指標都顯示：
- baseline
- langchain_rag
- delta（langchain - baseline）

---

## 7) 公平性控制（必做）

1. 固定同一題庫版本（含 question_type）
2. 固定同一 judge 版本（commit hash）
3. 若啟用 LLM judge：固定同一模型/temperature
4. 若啟用 similarity：固定同一 embedding 模型
5. 固定評測時 config（存 snapshot）

---

## 8) 實作步驟（建議）

## Phase 1：最小可行版（MVP）

1. baseline 輸出對齊 unified schema
2. 直接重用 langchain eval judge + metrics
3. 產生 baseline 與 langchain 的 summary
4. 輸出 md 比較表

## Phase 2：完整版

1. 新增 run_id 與 config snapshot
2. 新增 by-question-type 比較
3. 新增錯題交集分析（兩系統都錯/只有一方錯）

## Phase 3：長期化

1. 接入 CI（每次改動自動跑）
2. 保留歷史趨勢檔（time series）

---

## 9) 建議比較報告章節（comparison_report.md）

1. 實驗設定（題庫、judge版本、模型）
2. 整體指標比較（表格）
3. 題型分解比較（hard_fact/multi_fact/summary/refusal）
4. 錯題分析（Top error reasons）
5. 結論與下一步

---

## 10) 驗收標準（DoD）

1. 兩系統可由同一條指令完成評測
2. 兩系統使用同一 judge/metrics
3. 產出可直接放簡報的比較報告（含 delta）
4. 比較結果可重跑、可追溯（含 run config）

---

## 11) 風險與緩解

1. **Baseline 欄位不完整**
   - 緩解：adapter 統一補預設值（如 `pred_sources=[]`）

2. **LLM judge 引入隨機性**
   - 緩解：temperature=0；必要時固定 seed / 重試策略

3. **版本漂移**
   - 緩解：在報告寫入 judge commit hash 與 config snapshot

---

## 12) 預期收益

- 得到可信、公平、可重複的 Baseline vs RAG 對照
- 明確量化「RAG 真正帶來多少提升」
- 後續每次優化都可用同一標準追蹤增益

---

## 13) 實作狀態（2026-03-16）

已完成並落地於 `projects/Fubon_interview/scripts`：

- ✅ `scripts/run_cross_system_eval.py`
  - 一次執行 baseline + langchain 的 unified evaluation
  - 可選 `--run-langchain-eval` 先觸發最新 `uv run rag-eval`
- ✅ `scripts/eval_adapters/baseline_adapter.py`
- ✅ `scripts/eval_adapters/langchain_adapter.py`
- ✅ `scripts/build_comparison_report.py`

### 主要能力
- 同一份 judge/metrics（重用 `langchain_rag_app.eval`）
- 輸出標準化 results/summary
- 產出 cross-system `comparison_report.json/.md`
- run_id 目錄 + snapshot 追溯

### 測試
- 新增 `langchain_rag/tests/test_cross_system_eval_pipeline.py`
- 與既有測試一起通過（36 tests）
