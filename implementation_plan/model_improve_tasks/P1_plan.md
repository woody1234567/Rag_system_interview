# P1_plan.md — 檢索升級：Hybrid + Rerank（高優先）細部計畫

> 目標：在不大幅改動現有應用介面的前提下，將檢索層由單一 dense retrieval 升級為「Hybrid Recall + Rerank Precision」，提升召回率、降低主題錯配，並為後續 P2/P3 奠定穩定基礎。

---

## 1. P1 要解決的核心問題

根據目前 `eval_results.json` 的錯題型態，檢索層存在以下痛點：

1. **關鍵詞題召回不足**
   - 對專有名詞、章節標題、表格欄位名稱敏感度不足
2. **數值題主題錯配**
   - 抓到相關段落但不是正確公司/正確年度
3. **多子題問題 evidence 不完整**
   - top-k 內容不足以覆蓋每個子問題
4. **僅有 dense 相似度，缺少 lexical signal**
   - 年報類文件通常 keyword 很關鍵（欄位名、公司名、年份）

---

## 2. 範圍定義（In Scope / Out of Scope）

### In Scope

- 引入 Hybrid 檢索（Dense + BM25）
- 設計候選融合策略（RRF / weighted fusion）
- 導入第二階段 reranker（cross-encoder 或等價 rerank 模型）
- 增加檢索觀測指標（retrieval hit / recall@k / rerank gain）

### Out of Scope

- 不改最終回答 prompt（P2/P3 再做）
- 不改拒答 gate（P3）
- 不改資料切塊策略（P4）

---

## 3. 目標架構

## 3.1 雙階段檢索流程

1. **Stage A — Hybrid Recall（高召回）**
   - Dense retriever（現有 embedding + Chroma）
   - BM25 retriever（基於 chunk 文本）
   - 各自取 topN（例：N=20）

2. **Stage B — Rerank Precision（高精準）**
   - 合併候選後送入 reranker
   - 依 relevance score 重排
   - 取 topK（例：K=5）送給生成模型

## 3.2 建議參數（初始）

- `dense_top_n = 20`
- `bm25_top_n = 20`
- `fusion_method = rrf`（Reciprocal Rank Fusion）
- `rrf_k = 60`（可調）
- `rerank_top_k = 5`

---

## 4. 詳細任務拆解

## Task P1-1：Retrieval 抽象介面化

### 目標
先把現有 `get_retriever()` 擴充成可切換策略，避免後續在主流程到處加 if/else。

### 建議

- 新增 `retrieval_mode` 設定：
  - `dense_only`（baseline）
  - `hybrid_no_rerank`
  - `hybrid_rerank`
- 建立 retrieval pipeline 類別：
  - `retrieve(query) -> candidates`

### 交付物

- 統一資料結構：
  - `doc_id`, `page`, `content`, `dense_rank`, `bm25_rank`, `fusion_score`, `rerank_score`

---

## Task P1-2：加入 BM25 檢索器

### 目標
補上 lexical matching 能力，提升關鍵字與欄位詞命中。

### 設計

- 以 index 時的 chunks 建立 BM25 corpus
- query 執行 BM25 檢索取 topN
- 支援中文文本切詞策略（可先簡化為字元/空白規則，之後再升級）

### 注意

- BM25 與 Dense 回傳文件需可對齊（同 doc_id）
- chunk metadata（頁碼、來源）需完整保留

---

## Task P1-3：融合策略（Fusion）

### 目標
穩定整合 Dense / BM25 候選，不讓單一路徑主導。

### 建議方案

1. **RRF（優先）**
   - `score = Σ 1 / (k + rank_i)`
2. **Weighted score（備選）**
   - `score = w_dense * s_dense + w_bm25 * s_bm25`

### 初始建議

- 先用 RRF（對分數尺度不敏感）
- 融合後保留 topM（例：M=30）給 rerank

---

## Task P1-4：導入 Reranker

### 目標
在高召回候選中提升排序精準度，降低「看似相關但非答案段」的干擾。

### 流程

- 輸入：(query, candidate chunk)
- 輸出：relevance score
- 取 topK 作為最終 context

### 模型選擇（原則）

- 先選可本地/穩定推論的 rerank 模型
- 若延遲過高，可限制 rerank 候選數（例如 30 -> 12）

### 交付物

- `rerank_score` 寫入中間結果（便於診斷）

---

## Task P1-5：Retrieval Debug Artifact

### 目標
讓每題「為何取到這些 chunk」可觀測。

### 新增輸出檔（建議）

- `artifacts/eval_retrieval_debug.json`

每題至少包含：
- query
- dense_top
- bm25_top
- fusion_top
- rerank_top
- 最終提供給 LLM 的 docs（頁碼 + 摘要）

---

## Task P1-6：檢索層指標化

### 目標
把 end-to-end accuracy 拆解成可定位的 retrieval KPI。

### 建議 KPI

- `retrieval_recall_at_20`（gold evidence 是否在候選）
- `final_context_hit_rate`（topK 是否含 gold evidence）
- `rerank_gain`（rerank 前後 hit 提升）
- `entity_mismatch_rate`（實體錯配率）

---

## 5. 實作步驟（建議順序）

## Phase 1：Hybrid without rerank（先上線）

1. 完成 BM25 + Fusion
2. 保持生成流程不變
3. 跑一次完整 eval 比較 baseline

**期望結果**：召回相關 evidence 的題數提升

## Phase 2：加上 rerank（再精煉）

1. 在融合候選後加 reranker
2. 做 topK/延遲權衡
3. 觀察錯題是否從「主題錯配」轉為「生成錯誤」

**期望結果**：precision 提升、錯誤來源更集中

---

## 6. 設定檔擴充建議（config.json）

建議新增：

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
    "top_k": 5,
    "candidate_pool": 30,
    "model": "<your_reranker_model>"
  }
}
```

---

## 7. 驗收標準（Definition of Done）

1. 可在不改 CLI 使用方式下切換 `dense_only` / `hybrid` / `hybrid_rerank`
2. `eval_retrieval_debug.json` 可追溯每題檢索路徑
3. retrieval KPI 可輸出並納入 summary
4. 相較 baseline：
   - `accuracy_relaxed` 有可觀提升，或
   - 至少 `final_context_hit_rate` 顯著提升

---

## 8. 風險與緩解

1. **延遲增加**（Hybrid + rerank）
   - 緩解：降低 candidate_pool、只對疑難題 rerank
2. **BM25 中文效果不穩**
   - 緩解：先做簡單詞法，後續再引入更好的 tokenizer
3. **融合後候選過多造成噪音**
   - 緩解：增加實體過濾（公司名/年份必須匹配）

---

## 9. 建議實驗矩陣（最小版）

A/B 三組即可先看方向：

1. `dense_only`（baseline）
2. `hybrid_no_rerank`（dense+bm25+rrf）
3. `hybrid_rerank`（2 + rerank）

每組追蹤：
- strict / relaxed accuracy
- refusal 指標（確認不因檢索升級而惡化）
- retrieval KPI（hit rate、rerank gain）

---

## 10. 與後續計畫的銜接

- **P2（Query Planning）**：基於 P1 提供更完整候選，提升多子題覆蓋
- **P3（Evidence Gate）**：利用 rerank 後高置信 evidence 做拒答判斷
- **P4（Chunk 優化）**：若 P1 後仍有召回瓶頸，再優化切塊

> 原則：先把檢索命中率拉上來，再處理生成與拒答策略，迭代效率最高。

---

## 11. 實作狀態（2026-03-14）

已完成並落地於 `langchain_rag`：

- ✅ P1-1：Retrieval 抽象介面化（`retrieval_mode` 可切換）
- ✅ P1-2：加入 BM25（`BM25Index`）
- ✅ P1-3：融合策略（RRF）
- ✅ P1-4：Rerank（heuristic reranker，保留 `rerank_score`）
- ✅ P1-5：Retrieval debug artifact
  - 產出 `artifacts/eval_retrieval_debug.json`
- ✅ P1-6：檢索 KPI
  - `retrieval_recall_at_20`
  - `final_context_hit_rate`
  - `rerank_gain`

### 測試狀態
- 單元測試通過（共 15 tests）
- 新增 retrieval 測試：`tests/test_retrieval_pipeline.py`
