# reranker_revised_v1.md — Cross-Encoder Reranker 導入與可切換架構細部計畫

> 目的：解決目前 heuristic reranker 出現負增益（`rerank_gain < 0`）問題，導入第二種 reranking 路徑（Cross-Encoder），並透過 `config.json` 讓系統可選擇 reranker 類型，支援可控 A/B 實驗與逐步上線。

---

## 1) 背景與問題

目前 `langchain_rag` 的 rerank 流程為固定 heuristic：
- 使用 `fusion_score + token overlap + year_bonus` 計分
- 未讀取 `rerank.model` 進行實際模型切換

已觀測到：
- `retrieval_recall_at_20` 尚可
- 但 `final_context_hit_rate` 偏低
- 且 `rerank_gain` 出現負值

推論：現行 heuristic 在部分題型（多子題/摘要題/細節數值題）排序能力不足，會把更關鍵的 evidence 擠出 top-k。

---

## 2) 目標

1. 導入 **Cross-Encoder reranker**（第二條可用路徑）
2. 保留現有 heuristic 作為 fallback
3. 讓 `config.json` 可切換 reranker type
4. 產出可比較的實驗結果（accuracy / hit rate / latency）

---

## 3) 範圍（In Scope / Out of Scope）

### In Scope
- reranker 模組化（strategy/router）
- cross-encoder 實作與 lazy load
- config 驅動 reranker 選擇
- 評測輸出增加 reranker 觀測欄位

### Out of Scope
- 不改 chunking（P4）
- 不改拒答 gate（P3）
- 不改 LLM answer prompt

---

## 4) 目標架構

## 4.1 檢索主流程（維持）

1. Dense retrieve
2. BM25 retrieve
3. RRF fusion
4. Reranker（可切換）
5. 取 top_k 給 LLM

## 4.2 Reranker 策略層

新增策略介面：
- `heuristic`
- `cross_encoder`
- `none`（直接用 fused top-k）

由 `config.json` 的 `rerank.type` 決定。

---

## 5) config.json 設計（提案）

```json
{
  "retrieval_mode": "hybrid_rerank",
  "dense_top_n": 20,
  "bm25_top_n": 20,
  "fusion": {
    "method": "rrf",
    "rrf_k": 60
  },
  "rerank": {
    "enabled": true,
    "type": "heuristic",
    "top_k": 5,
    "candidate_pool": 30,
    "heuristic": {
      "year_bonus": 0.1
    },
    "cross_encoder": {
      "model_name": "BAAI/bge-reranker-v2-m3",
      "batch_size": 16,
      "max_length": 512,
      "device": "cpu"
    }
  }
}
```

### 切換方式
- `"type": "heuristic"`：現有行為
- `"type": "cross_encoder"`：使用新 reranker
- `"type": "none"`：跳過 rerank（等效 hybrid_no_rerank）

---

## 6) 實作任務拆解

## Task R1：Reranker 路由器（必要）

### 目標
把 `heuristic_rerank(...)` 單一路徑改成「策略分派」。

### 建議
- 新增 `rerank_candidates(query, candidates, cfg)`
- 內部依 `cfg["rerank"]["type"]` dispatch

### 交付
- 支援 `heuristic/cross_encoder/none`

---

## Task R2：Cross-Encoder Reranker 實作（核心）

### 目標
新增 `cross_encoder_rerank(...)`，以 `(query, doc)` 相關性分數重排。

### 技術路徑（建議）
- 套件：`sentence-transformers`
- 類別：`CrossEncoder`
- 輸入：`[(query, candidate.content), ...]`
- 輸出：每個 candidate 的 `rerank_score`

### 模型建議（初版）
- `BAAI/bge-reranker-v2-m3`（優先，穩定且常見）

### 交付
- `rerank_score` 寫回 candidate
- 排序後取 `top_k`

---

## Task R3：模型載入與效能控制（必要）

### 目標
避免每題重載模型，控制延遲與記憶體。

### 建議
- lazy singleton cache：首次使用才載入
- `batch_size` 可調
- `candidate_pool` 上限保護（例如 <= 100）

### 交付
- 可在 CPU 穩定執行
- 可在 config 中調整效能參數

---

## Task R4：依賴管理（必要）

### 目標
補齊 cross-encoder 所需套件。

### 建議新增依賴
- `sentence-transformers`
- （視環境）`torch`

### 交付
- 更新 `pyproject.toml`
- 能在專案環境正常安裝與執行

---

## Task R5：Debug 與指標擴充（高優先）

### 目標
讓 reranker 的效果可觀測、可比較。

### eval_results 每題新增（或確認保留）
- `reranker_type`
- `candidate_pool_size`
- `rerank_top`（已有）
- `final_context_hit`

### eval_summary 新增（或確認保留）
- `rerank_gain`
- `final_context_hit_rate`
- `avg_rerank_latency_ms`（新增）

---

## Task R6：回退機制（建議）

### 目標
降低 reranker 排錯風險。

### 建議策略（保底）
- final docs = `rerank top (k-2)` + `fusion top 2`（去重）
- 若 rerank 分數過低或異常，回退 fused top-k

---

## 7) 實驗設計（A/B）

## 實驗組
1. `hybrid_no_rerank`（對照）
2. `hybrid_rerank + heuristic`
3. `hybrid_rerank + cross_encoder`
4. （可選）cross_encoder + fallback 保底

## 固定條件
- 相同題庫（30題）
- 相同 LLM/embedding model
- 相同 chunk/index

## 比較指標
- `accuracy_strict`
- `accuracy_relaxed`
- `retrieval.final_context_hit_rate`
- `retrieval.rerank_gain`
- `refusal_f1`
- `avg_rerank_latency_ms`

---

## 8) 驗收標準（Definition of Done）

1. config 可切換 reranker type
2. cross-encoder 可正常執行且輸出 rerank score
3. 能跑完整 `rag-eval`
4. 與 heuristic 對照可得到可解釋的增減結果
5. 至少一組設定使 `rerank_gain` 從負值改善到 >= 0

---

## 9) 風險與緩解

1. **延遲上升**（cross-encoder 常見）
   - 緩解：調小 candidate_pool、加 batch、CPU/GPU 分流

2. **環境依賴重量增加**（torch）
   - 緩解：先 CPU 版本，必要時拆 optional extra

3. **多語/中文表現不穩**
   - 緩解：先用中英兼容模型（bge-reranker-v2-m3）

4. **reranker 過擬合某題型**
   - 緩解：保留 fallback，做按題型路由（後續版）

---

## 10) 推薦導入順序

### Phase 1（低風險）
- 完成路由 + cross_encoder 實作
- 先不上線，僅離線 eval 比較

### Phase 2（受控啟用）
- `type=cross_encoder` 跑全量題庫
- 若 gain 未改善，啟用 fallback 保底策略

### Phase 3（穩定化）
- 根據題型切換 reranker（hard_fact 用保守策略，summary/multi_fact 用 cross_encoder）

---

## 11) 預期成果

- reranker 從「可能拖累」變成「可量化優化元件」
- 可透過 config 低成本切換策略
- 為後續 P2（query planning）與 P3（拒答 gate）提供更高品質 context

---

## 12) 實作狀態（2026-03-14）

已完成並落地於 `langchain_rag`：

- ✅ R1：Reranker router
  - 新增 `rerank_candidates(query, candidates, cfg)`
  - 支援 `heuristic` / `cross_encoder` / `none`

- ✅ R2：Cross-Encoder reranker
  - 新增 `cross_encoder_rerank(...)`
  - lazy import `sentence_transformers.CrossEncoder`
  - `cross_encoder` 不可用時自動 fallback 到 heuristic

- ✅ R3：效能控制
  - candidate pool 上限保護
  - rerank latency 量測（ms）

- ✅ R5：觀測欄位
  - 每題：`reranker_type`, `candidate_pool_size`, `avg_rerank_latency_ms`
  - summary：`retrieval.avg_rerank_latency_ms`

- ✅ R6：回退機制
  - `rerank top (k-2) + fusion top 2` 去重保底策略

- ✅ 測試
  - 新增 `tests/test_reranker_router.py`
  - 全部單元測試通過（18 tests）
