# LangChain RAG Implementation

依 `implementation_plan/langchain_rag_upgrade_plan.md` 實作的 LangChain 版本 RAG。

## 功能
- `rag-index`: 建立 Chroma 向量索引
- `rag-query`: 單題查詢（含來源頁碼、拒答）
- `rag-eval`: 題庫批次評測（含 P1 Hybrid Retrieval）
  - `accuracy_strict`
  - `accuracy_relaxed`
  - `avg_coverage_score`（多子題完整率）
  - `refusal_precision / refusal_recall / refusal_f1`
  - `refusal_confusion_matrix`
  - `citation_coverage`

## 使用（改善後版本）

### 0) 進入專案
```bash
cd /root/.openclaw/workspace/projects/Fubon_interview/langchain_rag
```

### 1) 安裝依賴
```bash
uv sync
```

### 2) 設定 `.env`（只要做一次）
建立 `langchain_rag/.env`：

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

> 程式會自動載入 `.env`，不用手動 `export`。

### 3) 建立索引
```bash
uv run rag-index
```

成功後會看到 chunk 數量（JSON），並建立 Chroma 索引於：
- `langchain_rag/artifacts/chroma_db`

### 4) 單題測試
```bash
uv run rag-query --question "富邦金控 113 年度合併稅後淨利是多少？"
```

輸出欄位包含：
- `answer`
- `refusal`
- `reason`
- `sources`

### 5) 跑完整評測（P0 改善版）
```bash
uv run rag-eval
```

主要輸出檔案：
- `langchain_rag/artifacts/eval_results.json`
- `langchain_rag/artifacts/eval_summary.json`

`eval_summary.json` 會包含：
- `accuracy_strict`
- `accuracy_relaxed`
- `avg_coverage_score`
- `refusal_precision`
- `refusal_recall`
- `refusal_f1`
- `refusal_confusion_matrix`
- `citation_coverage`
- `retrieval.retrieval_recall_at_20`
- `retrieval.final_context_hit_rate`
- `retrieval.rerank_gain`

另外會輸出：
- `langchain_rag/artifacts/eval_retrieval_debug.json`
  - 每題 dense/bm25/fusion/rerank 的候選資訊，方便 debug。

## Reranker 切換
在 `config.json` 使用 `rerank.type`：
- `"heuristic"`：規則式重排（預設）
- `"cross_encoder"`：Cross-Encoder 重排（失敗時自動 fallback heuristic）
- `"none"`：跳過 rerank，直接使用 fused top-k

## 自動化參數實驗（experiments_plan）
- Grid 檔：`experiments/rerank_grid.json`
- Runner：`scripts/run_rerank_experiments.py`

執行：
```bash
uv run python scripts/run_rerank_experiments.py --project-dir . --top-n 3
```

輸出：
- `artifacts/experiments/<run_id>/leaderboard.csv`
- `artifacts/experiments/<run_id>/results.json`
- `artifacts/experiments/latest_summary.csv`

## Cross-system 評測（Baseline vs LangChain）
依 `implementation_plan/cross_system_eval.md`，可用同一套 judge/metrics 比較兩系統。

### 執行方式
在 `langchain_rag` 目錄下執行：

```bash
# 會先跑一次最新 langchain rag-eval，再做 cross-system 統一評測
uv run python ../scripts/run_cross_system_eval.py --project-root .. --run-langchain-eval
```

### 輸出檔案
- `../baseline_model/artifacts/eval_results.json`
- `../baseline_model/artifacts/eval_summary.json`
- `./artifacts/eval_results_unified.json`
- `./artifacts/eval_summary_unified.json`
- `../artifacts/cross_system/comparison_report.json`
- `../artifacts/cross_system/comparison_report.md`
- `../artifacts/cross_system/run_<timestamp>/...`（含 snapshot）

### 6) 跑單元測試
```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
```

## 常見問題

- 若出現 `OPENAI_API_KEY` 相關錯誤：請確認 `.env` 有設定且檔名正確。
- 若 `rag-query` / `rag-eval` 報索引不存在：先執行 `uv run rag-index`。
- 若要重建索引：清空 `langchain_rag/artifacts/chroma_db` 後重新 `rag-index`。
