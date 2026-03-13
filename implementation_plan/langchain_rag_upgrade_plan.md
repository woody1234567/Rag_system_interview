# LangChain RAG 升級規劃（從 baseline 到可交付版本）

## 背景

目前 `baseline_model` 已完成可執行流程（抽取/檢索/評測），但尚未導入 LLM 進行答案整合與證據約束生成，因此在題庫準確率與拒答品質上仍不足。

本文件目的：基於專案內 skills 與現有設計，規劃一版 **LangChain-based RAG** 升級路線。

---

## 一、已在專案中找到的相關 skills（`projects/Fubon_interview/.agents/skills`）

與本任務直接相關：

1. `langchain-rag`（最核心）
   - 提供完整 RAG 流程範式：Load → Split → Embed → Store → Retrieve → Generate
   - 建議元件：`PyPDFLoader`、`RecursiveCharacterTextSplitter`、`OpenAIEmbeddings`、`Chroma/FAISS`

2. `langchain-fundamentals`
   - 適合建立可維護的 LCEL / chain 結構

3. `langchain-dependencies`
   - 協助整理相依套件與版本策略

4. `langchain-middleware`
   - 可擴充 guardrail / logging / routing（進階）

5. `langgraph-*`（非第一階段必要）
   - 若後續要做多步推理流程圖與可回溯流程，可再引入

---

## 二、升級目標（對齊面試評分）

1. 導入 LLM 生成，但強制「證據約束」
2. 回答必附頁碼來源
3. 應拒答題（例如 28、29）要穩定拒答
4. 評測指標完整：Accuracy、Refusal Precision、Citation Coverage、Hallucination Rate

---

## 三、架構提案（LangChain 版本）

## 3.1 Index Pipeline

- Loader：`PyPDFLoader`（保留 page metadata）
- Splitter：`RecursiveCharacterTextSplitter`
  - `chunk_size`: 1000（初始）
  - `chunk_overlap`: 200（初始）
- Embedding：`OpenAIEmbeddings(text-embedding-3-small)`
- VectorStore：
  - 先用 `Chroma(persist_directory=...)`（開發友善）
  - 若要高效本地可切 `FAISS`

## 3.2 Retrieval Pipeline

- Retriever：`vectorstore.as_retriever(search_kwargs={"k": 5})`
- 可選增強：`search_type="mmr"` 以改善內容多樣性與跨頁訊息覆蓋
- 針對跨頁題可提高 `fetch_k` 後重排

## 3.3 Generation Pipeline

- LLM：`ChatOpenAI`（模型可配置）
- Prompt 規則：
  1) 只能根據 context 回答
  2) 找不到證據要明確拒答
  3) 回傳 JSON 結構（answer / sources / confidence / refusal）

建議輸出結構：
```json
{
  "answer": "...",
  "sources": [7, 12],
  "confidence": "high|medium|low",
  "refusal": false,
  "reason": "..."
}
```

---

## 四、幻覺防護設計（LangChain 版）

## 4.1 檢索門檻
- 若 top-k 相似度整體偏低 -> 直接拒答

## 4.2 證據完整性檢查
- 題目若要求數字，context 需含可對應數值；否則拒答

## 4.3 回答後驗證（post-check）
- 檢查答案中的關鍵數值/名詞是否能在來源 chunk 對齊
- 對不上即改為拒答或降置信度

## 4.4 幻覺題特例
- 題號 28、29 設為測試關鍵案例
- 需明確回覆資料不足，不做外推

---

## 五、實作拆解（建議檔案結構）

在 `baseline_model` 下新增 `langchain_rag/`：

- `langchain_rag/index.py`：建索引
- `langchain_rag/query.py`：單題查詢
- `langchain_rag/eval.py`：題庫評測
- `langchain_rag/prompts.py`：系統 prompt 與輸出格式
- `langchain_rag/config.py`：模型、k 值、門檻參數

並保留舊版 `rag_pipeline.py` 當 baseline 對照。

---

## 六、依賴規劃（uv）

第一階段最小集合：
- `langchain`
- `langchain-openai`
- `langchain-community`
- `langchain-text-splitters`
- `langchain-chroma`
- `pypdf`

若切 FAISS：
- `faiss-cpu`（視環境可用性）

---

## 七、評測計畫（對照 baseline）

1. 同一份 30 題題庫跑 baseline 與 langchain 版
2. 比較：
   - Accuracy
   - 拒答精準率（尤其 28/29）
   - 引用可驗證率
3. 產出錯誤分類：
   - 檢索錯
   - 生成錯
   - 拒答錯
   - 幻覺

---

## 八、里程碑（建議）

- M1（半天）：完成 langchain indexing + retrieval
- M2（半天）：接上 LLM 回答與結構化輸出
- M3（半天）：完成 eval script 與指標輸出
- M4（半天）：針對拒答題與跨頁題調參

---

## 九、成功定義

- 相較 baseline，Accuracy 有顯著提升
- 題號 28/29 可穩定拒答
- 每題回答具來源頁碼
- 可在面試中解釋設計取捨（為何選 Chroma、為何用 RCT splitter、為何設拒答門檻）
