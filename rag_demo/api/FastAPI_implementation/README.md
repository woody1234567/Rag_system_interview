# FastAPI implementation (v1)

這個專案已改為使用 **uv** 進行套件與虛擬環境管理。

## 1) 初始化 / 安裝依賴

```bash
cd /root/.openclaw/workspace/projects/Fubon_interview/rag_demo/api/FastAPI_implementation
uv sync --dev
```

> `uv sync` 會依 `pyproject.toml`（與 lock 檔）建立 `.venv` 並安裝依賴。

## 2) 啟動 API

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## 3) 執行測試

```bash
uv run pytest -q
```

## 4) 常用 uv 指令

- 新增執行依賴：
  ```bash
  uv add <package>
  ```
- 新增開發依賴：
  ```bash
  uv add --dev <package>
  ```
- 更新 lock：
  ```bash
  uv lock
  ```
- 同步環境（依 lock）：
  ```bash
  uv sync --dev
  ```
