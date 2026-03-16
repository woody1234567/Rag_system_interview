# RAG Web Demo (Nuxt Full-Stack)

這個專案是 Nuxt 全端 Web App，前端透過 Nuxt server routes（BFF）呼叫 FastAPI：
- Nuxt BFF API：`/api/rag/*`
- FastAPI 目標：`/healthz`, `/v1/rag/query`, `/v1/rag/index`

---

## 1) 本機開發

### 安裝
```bash
cd /root/.openclaw/workspace/projects/Fubon_interview/rag_demo/web_demo
pnpm install
```

### 設定 FastAPI 位址（重要）
建立 `.env`：
```env
NUXT_PUBLIC_FASTAPI_BASE_URL=http://127.0.0.1:8000
```

> 若 FastAPI 不在本機，改成你的 API URL（例如 `https://your-fastapi.example.com`）

### 啟動
```bash
pnpm dev
```

開啟：`http://localhost:3000`

---

## 2) 使用方式

進入首頁後可做三件事：

1. **Health 檢查**
   - 頁面會自動檢查 FastAPI 狀態（ok/down）

2. **RAG 問答**
   - 輸入問題後按「送出問題」
   - 可勾選 `include debug` 查看 `retrieval_debug`

3. **重建索引**
   - 按「重建索引」觸發 FastAPI `/v1/rag/index`

---

## 3) 測試與建置

### Unit Test
```bash
pnpm test
```

### Production Build
```bash
pnpm build
pnpm preview
```

---

## 4) 部署到 Vercel

## A. 前置條件
- 已有 Vercel 帳號
- FastAPI 需部署在可被 Vercel 存取的公開 HTTPS URL
- 確認 FastAPI endpoint 可用：
  - `GET /healthz`
  - `POST /v1/rag/query`
  - `POST /v1/rag/index`

## B. 用 Vercel Dashboard 部署（建議）
1. 把 `projects/Fubon_interview` 推到 GitHub
2. 到 Vercel → **Add New Project** → 匯入該 repo
3. 設定 **Root Directory** 為：
   - `rag_demo/web_demo`
4. Framework Preset 選 **Nuxt**（通常會自動偵測）
5. Build Command 保持預設（通常是 `pnpm build`）
6. 在 Environment Variables 新增：
   - `NUXT_PUBLIC_FASTAPI_BASE_URL=https://<your-fastapi-domain>`
7. 點 Deploy

## C. 用 Vercel CLI 部署
```bash
cd /root/.openclaw/workspace/projects/Fubon_interview/rag_demo/web_demo
npm i -g vercel
vercel login
vercel
```

部署時確認：
- Project root 是目前目錄（`web_demo`）
- 環境變數已設定 `NUXT_PUBLIC_FASTAPI_BASE_URL`

首次部署後，設定正式環境：
```bash
vercel env add NUXT_PUBLIC_FASTAPI_BASE_URL production
vercel --prod
```

---

## 5) 部署後檢查清單

1. 開啟 Vercel 網址，首頁可正常載入
2. 顯示 FastAPI 狀態為 `ok`
3. 問答可以成功回傳答案
4. 重建索引按鈕可正常觸發
5. Vercel Functions log 沒有 5xx 異常

---

## 6) 常見問題

- **顯示 `down` 或查詢失敗**
  - 檢查 `NUXT_PUBLIC_FASTAPI_BASE_URL` 是否正確
  - 確認 FastAPI 服務真的有開、且能從外網存取

- **Vercel 部署成功但 API 失敗**
  - 多半是 FastAPI URL 錯誤或 endpoint 路徑不一致
  - 先測：`https://your-fastapi-domain/healthz`

- **本機可以、線上不行**
  - 本機 `127.0.0.1` 只對本機有效，線上一定要改成公開網域

---

## 7) 目前 API 對應（Nuxt BFF）
- `POST /api/rag/query` → FastAPI `POST /v1/rag/query`
- `POST /api/rag/index` → FastAPI `POST /v1/rag/index`
- `GET /api/rag/health` → FastAPI `GET /healthz`
