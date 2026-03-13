# model_improvement_overall.md

## 1) 背景與目標

本文件整理 `langchain_rag` 目前評測結果與後續優化路線，目標是在不破壞可解釋性（可附來源）的前提下，顯著提升：

- **整體正確率（Accuracy）**
- **拒答品質（Refusal Precision / Recall）**
- **多子題問題完整率（Completeness）**
- **數值題精準度（Numeric Fidelity）**

---

## 2) 現況摘要（來自 artifacts/eval_results.json + eval_summary.json）

- 題數：30
- Accuracy：0.1667（5/30）
- 拒答題數：2
- 拒答 precision：0.0
- citation coverage：1.0

### 2.1 觀察到的失敗類型

1. **評測規則過嚴，低估模型能力**
   - 現行 `judge()` 是字串包含（`normalize(gold) in normalize(pred)`）
   - 對於「表述等價但字串不同」會誤判為錯
   - 例：`16 年` vs `十六年`、`4.25元` vs `4.25`

2. **多子題問題回答不完整**
   - 例：同時問「總資產 + EPS」，只答一半

3. **拒答策略不穩定**
   - 有些「該拒答」題目直接猜答案（幻覺）
   - 有些「可回答」題目反而拒答（保守過頭）

4. **數值與年份類錯誤**
   - 典型錯誤：年份答錯、比例算錯、單位掉失

5. **策略/摘要題偏題**
   - 有時生成流暢但未對齊 gold 關鍵點

---

## 3) 優化總策略（優先順序）

> 核心原則：**先修量測，再修檢索，最後修生成與決策（拒答）**。

### P0 — 先修評測器（高優先）

在目前評測器不夠穩的情況下，直接優化 pipeline 容易「看不出真提升」。

#### 建議改進

- **數值正規化**
  - 支援百分比、小數、科學記號、千/萬/億單位轉換
- **語義等價容忍**
  - `16` / `十六`、`4.25` / `4.25元` 等視為等價
- **多子題拆分評分**
  - 對 `A + B` 題型計算 partial score
- **拒答指標分離**
  - 除 precision 外，補 recall/F1 與 confusion matrix

#### 交付物

- `eval_summary.json` 增加以下欄位：
  - `accuracy_strict`, `accuracy_relaxed`
  - `refusal_precision`, `refusal_recall`, `refusal_f1`
  - `completeness_score`（多子題覆蓋率）

---

### P1 — 檢索升級：Hybrid + Rerank（高優先）

目前主要採 dense retrieval + k=5。對年報這種「關鍵字強、數字密集」文本，建議改為混合檢索。

#### 建議架構

1. **第一階段召回（Recall）**
   - Dense（現有 embedding）+ BM25（keyword）
   - 合併候選（例如 top20）

2. **第二階段重排（Precision）**
   - Cross-encoder reranker 對 top20 重排
   - 取 top5 給生成模型

#### 預期收益

- 改善數值題、專有名詞題、年份題的召回
- 降低主詞錯配（題目問 A，取到 B）

---

### P2 — 問題分解（Multi-intent Query Planning）（中高優先）

針對「同時問多個欄位」與「比較題」，先拆再答。

#### 建議流程

1. 問題分類：
   - single-fact / multi-fact / compare / summarize
2. 若為 multi-fact/compare：
   - 生成子問題列表
   - 每個子問題獨立檢索與作答
3. 聚合器：
   - 合併子答案
   - 檢查每個子問題是否有證據

#### 預期收益

- 顯著改善「漏答」
- 提高答案結構完整性

---

### P3 — 拒答閘門（Evidence Sufficiency Gate）（高優先）

單靠 prompt 要求「不足就拒答」通常不穩定。需要在生成前後加入規則化 gate。

#### Gate 設計

1. **證據抽取**：先抽取支持答案的原文句（含頁碼）
2. **實體對齊**：檢查題目關鍵實體是否出現在證據中
3. **覆蓋度判定**：多子題是否全部有對應證據
4. **不通過則拒答**：輸出標準 refusal_text

#### 特別規則

- 若問題含外部公司/非年報範圍（如國泰金控）且檢索不到對應證據，強制拒答
- 若題目是預測/推論而資料源無明確描述，強制拒答

---

### P4 — Chunk 與文件結構優化（中優先）

現行設定：`chunk_size=1000`, `overlap=200`。

#### 建議方向

- 嘗試 2~3 組參數 A/B test：
  - 500/100
  - 700/120
  - 1000/200（baseline）
- 使用 heading-aware 切分（章節標題優先）
- 表格區塊避免跨段切碎

#### 評估方式

- 同一組題庫比較 strict/relaxed accuracy
- 對數值題、比較題分組看提升幅度

---

## 4) Prompt / 輸出層優化（配套）

### 4.1 輸出格式建議

改為更可評估的結構化欄位：

```json
{
  "answer": "...",
  "refusal": false,
  "reason": "...",
  "evidence": [
    {"quote": "...", "page": 123}
  ],
  "sub_answers": [
    {"question": "...", "answer": "...", "supported": true}
  ]
}
```

### 4.2 生成約束

- 數值題優先輸出「值 + 單位」
- 多子題必須逐點回答
- 若 evidence 為空，不可輸出確定語氣答案

---

## 5) 兩週落地計畫（建議）

## Week 1：量測與檢索

1. 修評測器（P0）
2. 加入 Hybrid retrieval（P1 第一階段）
3. 比較 baseline vs hybrid 的 retrieval recall / end-to-end accuracy

### 里程碑
- 產出新版 `eval_summary.json`
- 提供錯題類型分布（數值題/拒答題/多子題）

## Week 2：決策與完整性

1. 加 reranker（P1 第二階段）
2. 上線 query planning（P2）
3. 加 evidence gate（P3）
4. 進行 chunk ablation（P4）

### 里程碑
- refusal precision 與 recall 同時提升
- 多子題完整率可觀察上升

---

## 6) 驗收指標（KPI）

建議設定可追蹤目標：

- `accuracy_relaxed >= 0.45`
- `accuracy_strict >= 0.35`
- `refusal_precision >= 0.80`
- `refusal_recall >= 0.80`
- `completeness_score >= 0.85`

> 備註：KPI 會依題庫難度與評測器版本調整。

---

## 7) 風險與注意事項

1. **過度拒答風險**
   - gate 太嚴可能壓低可答題表現
   - 需同時監控 refusal recall/precision 平衡

2. **rerank 成本與延遲**
   - cross-encoder 會增加 latency
   - 可透過小模型或候選數控制（top20 -> top8）

3. **評測 drift**
   - 評測器升級後需保留 strict 指標，避免「只靠放寬規則看起來變好」

---

## 8) 建議先做的最小可行改善（MVP）

若要最小成本快速提升，優先順序如下：

1. **P0 評測器升級**（先校正尺）
2. **P1 Hybrid retrieval（不先上 rerank）**
3. **P3 Evidence gate（先做簡化版）**

這三步通常即可顯著改善：
- 該拒答不拒答
- 數值題召回不穩
- 評測誤判造成的錯誤觀感

---

## 9) 後續文件串接

- 本文件：總體策略（overall）
- 既有 `langchain_rag_upgrade_plan.md`：可延伸為「實作任務拆解版」
- 建議新增 `experiment_log.md`：記錄每輪設定、指標、結論，避免重複試錯
