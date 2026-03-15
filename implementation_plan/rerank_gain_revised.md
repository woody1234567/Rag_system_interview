# rerank_gain_revised.md — rerank_gain 指標改版計畫

> 目標：修正目前 `rerank_gain` 定義造成的偏差，讓指標能更真實反映「reranker 排序本身」是否有帶來增益。

---

## 1) 現況與問題

目前每題 `rerank_gain` 的計算方式為：

- `retrieval_recall_at_20`：gold evidence 是否出現在 top-20 候選（bool）
- `final_context_hit`：gold evidence 是否出現在最終送入 LLM 的 final docs（bool）
- `rerank_gain = int(final_context_hit) - int(retrieval_recall_at_20)`

### 問題點

這個比較方式混合了兩種不同層級：
- top-20 候選命中（寬鬆）
- final top-k 命中（嚴格）

因此即使 reranker 沒有明顯變差，也容易出現負值（常見 `-1`），造成指標偏向「悲觀」，不利於公平比較不同 reranker 方案。

---

## 2) 改版原則

1. **公平比較同一層級**
   - 以相同 `k` 比較「rerank 前 vs rerank 後」
2. **主副指標分離**
   - reranker 品質 vs 檢索召回能力分開看
3. **保留舊指標但降級**
   - `retrieval_recall_at_20` 留作上限觀察，不再作 rerank_gain 基準

---

## 3) 新指標設計（核心）

## 3.1 每題新增欄位

- `fusion_k_hit`：fusion top-k 是否命中 gold（bool）
- `final_k_hit`：final top-k 是否命中 gold（bool）
- `rerank_gain_k`：
  - `int(final_k_hit) - int(fusion_k_hit)`
  - 值域同樣為 `-1/0/1`，但比較公平

## 3.2 保留欄位（但調整定位）

- `retrieval_recall_at_20`：召回天花板
- `final_context_hit`：最終命中率

> 註：`final_context_hit` 可與 `final_k_hit` 合併命名，避免概念重複。

---

## 4) summary 層指標調整

在 `eval_summary.retrieval` 建議新增/調整：

- `fusion_k_hit_rate`
- `final_k_hit_rate`
- `avg_rerank_gain_k`（新主指標）
- `retrieval_recall_at_20`（保留）
- `avg_rerank_latency_ms`（保留）

並把舊 `rerank_gain` 改名為：
- `pipeline_drop_from_20_to_k`（可選）

避免誤導為「reranker 增益」。

---

## 5) 實作任務拆解

## RG-1：每題 fusion@k 命中計算

- 在 eval 階段取得 fusion top-k docs（k 與 final 一致）
- 計算 `fusion_k_hit`

## RG-2：每題 final@k 命中計算

- 既有 final docs 計算 `final_k_hit`
- 與 `fusion_k_hit` 產生 `rerank_gain_k`

## RG-3：summary 聚合

- 彙總 `fusion_k_hit_rate`、`final_k_hit_rate`、`avg_rerank_gain_k`
- 與 latency 一起輸出

## RG-4：向後相容

- 暫時保留舊欄位 1~2 版
- 在文件註明 deprecated 欄位

## RG-5：單元測試與回歸

最小案例：
1. fusion miss, final hit → `gain_k = +1`
2. fusion hit, final hit → `gain_k = 0`
3. fusion hit, final miss → `gain_k = -1`
4. fusion miss, final miss → `gain_k = 0`

---

## 6) 為什麼改成 fusion@k vs final@k 會更好？

1. **同難度比較**：兩者都是 top-k，比較公平
2. **排除縮池偏差**：不再拿 top-20 跟 top-k 直接相減
3. **可直接回答核心問題**：reranker 是否比 fusion baseline 更會排序
4. **更適合 A/B**：不同 reranker type、candidate_pool、top_k 的比較更可信

---

## 7) 驗收標準（DoD）

1. 每題有 `fusion_k_hit / final_k_hit / rerank_gain_k`
2. summary 有 `avg_rerank_gain_k` 且可追蹤趨勢
3. leaderboard 使用新指標做排序依據之一
4. 舊指標保留但明確標記用途，不混淆 reranker 品質

---

## 8) 導入後的建議判讀

先看：
1. `avg_rerank_gain_k`（主）
2. `final_k_hit_rate`（主）
3. `accuracy_relaxed`（端到端）
4. `avg_rerank_latency_ms`（成本）

推薦選型準則：
- `avg_rerank_gain_k >= 0`
- `final_k_hit_rate` 不下降
- `accuracy_relaxed` 不下降
- latency 可接受

---

## 9) 預期收益

- 指標更貼近 reranker 真實能力
- 避免被「20→k 天然落差」誤導
- 讓後續 reranker 迭代（heuristic / cross-encoder / fallback）有可相信的比較基準

---

## 10) 實作狀態（2026-03-15）

已完成並落地於 `langchain_rag`：

- ✅ 每題新增欄位
  - `fusion_k_hit`
  - `final_k_hit`
  - `rerank_gain_k`
  - `pipeline_drop_from_20_to_k`（舊觀念改名）

- ✅ summary 新增/調整
  - `retrieval.fusion_k_hit_rate`
  - `retrieval.final_k_hit_rate`
  - `retrieval.avg_rerank_gain_k`（主指標）
  - `retrieval.pipeline_drop_from_20_to_k`
  - `retrieval.retrieval_recall_at_20`（保留）
  - `retrieval.avg_rerank_latency_ms`（保留）

- ✅ 實驗 runner 同步改版
  - leaderboard 排序改以 `avg_rerank_gain_k` 為必要條件
  - 匯出欄位新增 `fusion_k_hit_rate / final_k_hit_rate / avg_rerank_gain_k`

- ✅ 單元測試
  - 新增 `tests/test_rerank_gain_metrics.py`（四種最小案例）
  - 更新 `tests/test_experiments_runner.py` 以新指標驗證排序
