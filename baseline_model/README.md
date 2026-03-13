# Baseline RAG Model (Fubon Interview)

這是依照 `implementation_plan/rag_system_design.md` 實作的 **baseline 版本**。

## Baseline 特性
- PDF -> page-level text extraction（需 `pypdf`）
- Chunking（固定字元長度 + overlap）
- 純 Python（stdlib）TF-IDF 檢索
- 證據門檻 + 拒答機制
- 讀取題庫 Excel（`.xlsx`）並批次評測
- 產出 Accuracy / 拒答正確率 / 幻覺率 / 引用覆蓋

## 目錄
- `config.json`：路徑與參數
- `rag_pipeline.py`：核心流程（抽取、索引、檢索、回答、評測）
- `run_baseline.py`：CLI 入口

## 使用方式

1) 建議在專案根目錄建立虛擬環境並安裝 `pypdf`：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pypdf
```

2) 在 `projects/Fubon_interview` 下執行：

```bash
python3 baseline_model/run_baseline.py build
python3 baseline_model/run_baseline.py eval
```

3) 產物位置（預設）
- `baseline_model/artifacts/pages.jsonl`
- `baseline_model/artifacts/chunks.jsonl`
- `baseline_model/artifacts/eval_results.jsonl`
- `baseline_model/artifacts/eval_summary.json`

## 說明
- 這是 baseline：優先可運作、可驗證、可拒答。
- 下一步可再加入：hybrid retrieval / reranker / multi-hop。