# experiments_plan.md — 自動化 reranker 參數實驗計畫

> 目標：建立可重複執行的實驗流程，自動跑多組 reranker 設定、保存結果、輸出比較表，協助快速找出最佳參數組合。

---

## 1) 需求目標

建立一套自動化流程，能做到：

1. 一次跑多組 reranker 參數（含不同 reranker type）
2. 每組自動執行 `rag-eval`
3. 自動讀取 `eval_summary.json` 並抽取關鍵指標
4. 輸出統一比較表與 Top-N 最佳配置

---

## 2) 實作架構

## A. 實驗配置檔（Grid）

建立：`experiments/rerank_grid.json`

用途：集中定義要測的參數組合，例如：
- `rerank.type`: `heuristic` / `cross_encoder` / `cross_encoder_fallback_heuristic`
- `rerank.candidate_pool`: `12 / 20 / 30`
- `rerank.top_k`: `4 / 5 / 8`
- `fusion.rrf_k`: `20 / 60`

優點：後續新增組合只改配置檔，不改程式。

---

## B. Runner 腳本

建立：`scripts/run_rerank_experiments.py`

核心流程：
1. 讀取 base `config.json`
2. 逐組套用實驗參數（覆蓋到暫存 config）
3. 執行 `uv run rag-eval`
4. 讀取 `artifacts/eval_summary.json`
5. 抽取關鍵指標並彙整為 `csv/json`
6. 依排序規則輸出 Top-N

---

## C. 結果保存與版本化

避免覆蓋，採 run_id 目錄：

- `artifacts/experiments/<run_id>/exp_001/`
  - `config_snapshot.json`
  - `eval_summary.json`
  - `eval_results.json`（可選）

彙總輸出：
- `artifacts/experiments/<run_id>/leaderboard.csv`
- `artifacts/experiments/latest_summary.csv`

---

## 3) 必收指標（每組）

- `accuracy`
- `accuracy_strict`
- `accuracy_relaxed`
- `avg_coverage_score`
- `refusal_f1`
- `retrieval.final_context_hit_rate`
- `retrieval.rerank_gain`
- `retrieval.avg_rerank_latency_ms`

---

## 4) 比較與選型規則（建議）

為避免只看單一指標，採多指標排序：

1. **必要條件**：`rerank_gain >= 0`
2. 主要優化：`accuracy_relaxed` 最大化
3. 次要條件：`final_context_hit_rate` 及 `refusal_f1` 不惡化
4. 若成績接近：選 `avg_rerank_latency_ms` 較低者

---

## 5) 分階段落地

## Phase 1（半天）
- 完成最小 Runner（3~5 組）
- 輸出單一 `results.csv`

## Phase 2（半天）
- 新增 run_id 目錄管理
- 保存 config snapshot
- 失敗實驗重試（最多 1 次）

## Phase 3（半天）
- 產生 leaderboard（Top-N）
- 自動輸出「最佳配置建議」

---

## 6) 風險與對策

1. **實驗耗時過長**
   - 對策：先小 grid，再擴增

2. **結果被覆蓋**
   - 對策：每次 run 使用時間戳目錄

3. **變因污染導致無法比較**
   - 對策：固定題庫、固定 index、固定模型版本

4. **某些配置失敗中斷全流程**
   - 對策：單組失敗不中止全局，標記 `status=failed`

---

## 7) 建議最小實驗矩陣（起手式）

- Group A: `heuristic`, `candidate_pool=12`, `top_k=5`, `rrf_k=60`
- Group B: `cross_encoder`, `candidate_pool=12`, `top_k=5`, `rrf_k=60`
- Group C: `cross_encoder`, `candidate_pool=20`, `top_k=5`, `rrf_k=60`
- Group D: `cross_encoder_fallback_heuristic`, `candidate_pool=20`, `top_k=5`, `rrf_k=60`

先確認方向後，再擴充到 `top_k` 與 `rrf_k` 網格。

---

## 8) 完成定義（DoD）

1. 一條指令可執行多組 reranker 實驗
2. 每組有獨立結果資料夾與 config snapshot
3. 有可讀 leaderboard（csv）
4. 能自動輸出最佳候選設定
5. 可重跑且結果可追溯

---

## 9) 實作狀態（2026-03-15）

已完成並落地於 `langchain_rag`：

- ✅ `experiments/rerank_grid.json`（起手式 4 組）
- ✅ `scripts/run_rerank_experiments.py`
  - 逐組覆蓋 config
  - 自動執行 `uv run rag-eval`
  - 支援單組失敗重試（預設 1 次）
  - 不中斷全局流程
- ✅ run_id 目錄輸出
  - `artifacts/experiments/<run_id>/exp_xxx/`
  - 含 `config_snapshot.json`, `eval_summary.json`, `eval_results.json`, `run.log`
- ✅ 彙總輸出
  - `leaderboard.csv`, `leaderboard.json`, `results.json`
  - `artifacts/experiments/latest_summary.csv/json`
- ✅ Top-N 與最佳配置建議

### 單元測試
- 新增：`tests/test_experiments_runner.py`
- 覆蓋：`deep_update`, summary flatten, rank rule
