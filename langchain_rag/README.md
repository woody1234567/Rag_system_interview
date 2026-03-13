# LangChain RAG Implementation

依 `implementation_plan/langchain_rag_upgrade_plan.md` 實作的 LangChain 版本 RAG。

## 功能
- `rag-index`: 建立 Chroma 向量索引
- `rag-query`: 單題查詢（含來源頁碼、拒答）
- `rag-eval`: 題庫批次評測（P0 評測器）
  - `accuracy_strict`
  - `accuracy_relaxed`
  - `avg_coverage_score`（多子題完整率）
  - `refusal_precision / refusal_recall / refusal_f1`
  - `refusal_confusion_matrix`
  - `citation_coverage`

## 使用
```bash
cd langchain_rag
uv sync

# 建索引
uv run rag-index

# 單題查詢
uv run rag-query --question "富邦金控 113 年度合併稅後淨利是多少？"

# 批次評測
uv run rag-eval

# P0 evaluator 單元測試
uv run python -m unittest discover -s tests -p 'test_*.py'
```

## 環境變數（自動讀取 .env）
在 `langchain_rag/.env` 放入：

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

程式會自動讀取 `.env`，不需要每次手動 `export`。
