# rag_system_design.md

## 專案目標

建立一個可驗證、可評估、可控幻覺的富邦年報 RAG 系統，能針對題庫問題提供：
1. 明確答案
2. 可追溯來源（頁碼/段落）
3. 無證據時的安全拒答

---

## 一、系統設計總覽

採用「檢索優先 + 證據約束生成」架構：

1. **Document Processing Layer**
   - 解析 PDF（含文字、表格）
   - 正規化內容（數字、標點、換行）
   - 保留 metadata：`page`, `section`, `chunk_id`

2. **Indexing & Retrieval Layer**
   - Chunk 建立（語意切分 + 頁碼對齊）
   - Embedding 向量化
   - Vector DB 建立索引
   - Hybrid retrieval（向量 + 關鍵字，必要時）

3. **Reasoning & Answer Layer**
   - Top-k 證據召回
   - （可選）Cross-encoder rerank
   - LLM 依證據回答 + 輸出來源引用
   - 低證據信心時啟用拒答策略

4. **Evaluation & Guardrail Layer**
   - 題庫自動評測（30 題）
   - 指標：Accuracy / 拒答正確率 / 引用完整度
   - 幻覺檢測標記與錯誤分類分析

---

## 二、資料處理與前處理規格

## 2.1 輸入資料
- 年報 PDF（主要知識來源）
- 題庫 Excel（測試與標準答案）

## 2.2 文字前處理
- 移除無意義換行、頁眉頁腳噪音
- 統一全形半形符號
- 金額單位標準化（億/千元等）
- 數字格式正規化（1,508.2 / 1508.2 / 1.5082e3 類型比對）

## 2.3 Chunking 策略
- 以章節語意切分為主，頁碼邊界為輔
- 目標 chunk 大小：約 300~700 tokens
- overlap：50~100 tokens（避免關鍵資訊被切斷）
- metadata 最低要求：
  - `doc_name`
  - `page_start`, `page_end`
  - `section_title`
  - `chunk_text`

---

## 三、檢索策略設計

## 3.1 Baseline
- Dense retrieval（embedding + cosine similarity）
- Top-k = 5（初始值，可調）

## 3.2 強化方案（加分方向）
- Hybrid retrieval：BM25 + Dense 融合
- Reranker：交叉編碼器重排前 20 筆候選，取前 5 筆
- Query rewriting：
  - 同義詞展開（淨利=稅後淨利）
  - 年份對齊（113年度=2024年）

## 3.3 多跳檢索（對前後關聯題）
- 第一步取主題上下文（例如子公司策略）
- 第二步針對子問題拆解召回（人壽/銀行/證券）
- 合併證據後再回答

---

## 四、生成與回答格式

## 4.1 回答原則
- 僅根據召回證據作答
- 必須附來源頁碼
- 不允許無來源數字

## 4.2 回答模板（建議）
- `answer`: 最終答案
- `evidence`: 引用段落摘要
- `source_pages`: [頁碼列表]
- `confidence`: high / medium / low

## 4.3 拒答策略（核心）
觸發任一條件即拒答：
1. Top-k 相關度整體低於門檻
2. 關鍵欄位（數字/主詞）無法在證據中定位
3. 題目屬外部資訊（如非富邦年報揭露）

拒答回覆標準：
- 「根據目前提供之富邦 113 年報資料，無法找到直接可驗證的答案，因此不進行推論。」

---

## 五、評測設計（對齊面試要求）

## 5.1 測試集
- 使用附件 30 題完整題庫
- 題型標記：基本 / 加分 / 困難

## 5.2 評分指標
1. **Accuracy（主指標）**
   - 正確題數 / 全部題數
2. **Refusal Precision（拒答精準）**
   - 應拒答題中，正確拒答比例
3. **Citation Coverage（引用覆蓋）**
   - 有附來源且可對應答案的比例
4. **Hallucination Rate（幻覺率）**
   - 無依據回答題數 / 全部題數

## 5.3 自動比對規則
- 文字比對：標準化後 exact / 包含比對
- 數值比對：允許格式差異（如千分位、科學記號）
- 頁碼比對：答案來源是否落在標準頁碼範圍附近

## 5.4 錯誤分類
- Retrieval Error（檢索不到）
- Reasoning Error（檢索到但回答錯）
- Citation Error（答案對但引用不完整）
- Hallucination（無證據編造）

---

## 六、里程碑與交付節奏

## Milestone 1：Baseline 可跑（Day 1~2）
- PDF 解析 + chunk + indexing
- 基本問答流程可跑
- 先完成 30 題批次推論

## Milestone 2：評測與拒答（Day 3~4）
- 建立 scoring script（Accuracy/拒答率）
- 上線 evidence threshold
- 針對第 28、29 題做拒答驗證

## Milestone 3：優化與加分（Day 5~6）
- 加入 hybrid retrieval / reranker
- 強化多跳題與計算題
- 產出錯誤分析與改善前後對比

## Milestone 4：面試交付（Day 7）
- 簡報化系統設計
- 結果表格（各題表現 + 指標）
- 幻覺案例展示（錯誤→修正）

---

## 七、建議輸出文件（後續可新增）

- `implementation_plan/rag_system_design.md`（本檔）
- `implementation_plan/langchain_rag_upgrade_plan.md`（LangChain + LLM 升級規劃）
- `implementation_plan/evaluation_protocol.md`
- `implementation_plan/hallucination_policy.md`
- `implementation_plan/experiment_log.md`

---

## 八、風險與應對

1. **PDF 表格抽取錯位**
   - 應對：表格區塊單獨解析 + 數值欄位正規化
2. **跨頁題召回不足**
   - 應對：多跳檢索 + rerank
3. **數值題格式不一致導致誤判**
   - 應對：數值比較函式（單位換算 + 容差）
4. **模型過度自信導致幻覺**
   - 應對：低信心強制拒答 + 引用硬限制

---

## 九、完成定義（Definition of Done）

- 系統可穩定執行 30 題批次測試
- Accuracy 可量化呈現，且有題級別結果
- 幻覺題（至少 28/29）可正確拒答
- 回答皆可附來源頁碼
- 可清楚說明方法設計、限制與改進路線
