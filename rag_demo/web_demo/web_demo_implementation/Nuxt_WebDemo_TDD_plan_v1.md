# Nuxt Web Demo TDD Plan v1

## 目標
在 `rag_demo/web_demo` 使用 **Nuxt 全端框架**開發 RAG Web App，並串接 `rag_demo/api/FastAPI_implementation` 提供的 API。

本計畫採 **TDD（Test-Driven Development）**：
1. 先寫測試（Red）
2. 再實作最小功能讓測試通過（Green）
3. 再重構與補強（Refactor）

---

## 系統邊界與責任分工

### Nuxt（Web 全端）
- 前端 UI/UX（問答頁、索引按鈕、狀態顯示）
- Nuxt server routes（BFF）作為前端與 FastAPI 中介層
- 請求/回應資料正規化（避免前端直接依賴 FastAPI 細節）

### FastAPI（已建立）
- `POST /v1/rag/query`
- `POST /v1/rag/index`
- `GET /healthz` / `GET /readyz`
- 後續可補 `POST /v1/rag/eval`

---

## v1 交付範圍（先小步可用）

### 功能需求
1. 問答功能：輸入問題 → 顯示 answer/refusal/sources
2. 可選 Debug 模式：顯示 retrieval_debug（預設關）
3. 建索引功能：按鈕觸發 index API，顯示成功/失敗
4. 後端健康狀態：頁面載入時檢查 FastAPI health

### 非功能需求
- 明確錯誤訊息（timeout/network/backend error）
- API baseURL 可透過環境變數配置
- 測試可在本地一鍵執行

---

## 建議 Nuxt 結構

```text
web_demo/
  app/
    pages/
      index.vue
    components/
      RagQueryForm.vue
      RagAnswerCard.vue
      RagSystemStatus.vue
      RagIndexAction.vue
    composables/
      useRagApi.ts
      useRagState.ts
    server/
      api/
        rag/
          query.post.ts
          index.post.ts
          health.get.ts
    types/
      rag.ts
  tests/
    unit/
      composables/useRagApi.spec.ts
      server/rag.query.spec.ts
      server/rag.index.spec.ts
      components/RagQueryForm.spec.ts
      pages/index.spec.ts
  nuxt.config.ts
  vitest.config.ts
```

---

## TDD 分階段計畫

## Phase 0 — 測試基礎設施

### 先寫（Red）
- 建立 Vitest 設定（unit + nuxt environment）
- 建立測試 helper（mock `$fetch` / mock runtime config）

### 再做（Green）
- `pnpm test` 可執行
- 放一個 smoke test 通過

---

## Phase 1 — Server Route (BFF) query/index/health

### 先寫測試（Red）
1. `server/api/rag/query.post.ts`
   - 會把前端 payload 轉發到 FastAPI `/v1/rag/query`
   - 成功時回傳標準化物件
   - FastAPI 錯誤時轉成 Nuxt API error（含 code/message）
2. `server/api/rag/index.post.ts`
   - 轉發到 `/v1/rag/index`
   - 正確處理 409（index in progress）
3. `server/api/rag/health.get.ts`
   - 轉發 `/healthz`

### 再實作（Green）
- 寫最小 server routes 讓測試通過

### Refactor
- 共用 `server/utils/fastapiClient.ts`（統一 timeout/error mapping）

---

## Phase 2 — Composable API 層

### 先寫測試（Red）
- `useRagApi`：
  - `queryRag()` 成功/失敗
  - `buildIndex()` 成功/失敗
  - `checkHealth()` 成功/失敗

### 再實作（Green）
- 透過 Nuxt server routes 呼叫，不直接打 FastAPI

### Refactor
- 抽 `types/rag.ts` 型別

---

## Phase 3 — UI 元件與首頁

### 先寫測試（Red）
1. `RagQueryForm`
   - 輸入空字串不可送出
   - 送出時 emit query event
2. `RagAnswerCard`
   - 正確顯示 answer/refusal/sources
3. `RagIndexAction`
   - 點擊後呼叫 index action，顯示 loading/success/error
4. `pages/index`
   - 首次載入會檢查 health
   - 問答流程可完整走通（mock composable）

### 再實作（Green）
- 完成頁面互動與狀態管理

### Refactor
- 拆分顯示邏輯與商業邏輯

---

## Phase 4 — E2E（可選但建議）

### 先寫測試（Red）
- 以 Playwright 做一條主流程：
  - 打開首頁
  - 輸入問題
  - 看到回答

### 再實作（Green）
- 補齊 loading/error UI

---

## API 合約（Nuxt BFF 對前端）

### `POST /api/rag/query`
Request:
```json
{
  "question": "string",
  "question_type": "string?",
  "include_debug": false
}
```

Response:
```json
{
  "answer": "string",
  "refusal": false,
  "reason": "string",
  "sources": [1, 2],
  "gate": {},
  "retrieval_debug": null
}
```

### `POST /api/rag/index`
Response:
```json
{
  "chunks": 123,
  "status": "completed"
}
```

### `GET /api/rag/health`
Response:
```json
{
  "status": "ok"
}
```

---

## 風險與對策
1. **FastAPI 尚未啟動造成 Nuxt call 失敗**
   - 對策：health 狀態顯示 + 明確錯誤提示
2. **payload 過大（debug）**
   - 對策：UI 預設關閉 `include_debug`
3. **跨域/CORS 問題**
   - 對策：前端只打 Nuxt `/api/*`，由 BFF 轉發 FastAPI
4. **測試環境依賴重**
   - 對策：server/composable 測試優先 mock，減少外部依賴

---

## Done Definition（v1）
- [ ] Nuxt 頁面可完成一次問答流程
- [ ] 可觸發 index 並顯示結果
- [ ] 可顯示 backend 健康狀態
- [ ] 單元測試覆蓋 server routes + composables + 關鍵 UI
- [ ] 全部測試通過

---

## 下一步執行順序（我會照這順序做）
1. 先建測試框架與第一批 tests（server routes）
2. 實作 Nuxt BFF routes 讓測試 pass
3. 補 composables tests + implementation
4. 補 UI tests + implementation
5. 最後整體測試與小幅重構
