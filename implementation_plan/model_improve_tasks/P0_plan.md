# P0_plan.md — 先修評測器（高優先）細部計畫

> 目標：在不改動主要 RAG 推論流程之前，先把評測器修到「可反映真實能力」，避免因評分偏差導致錯誤優化方向。

---

## 1. 目前問題與根因

### 1.1 當前評分邏輯（摘要）

現行 `judge(pred, refused, gold)` 在可回答題的判定為：

- `normalize(gold) in normalize(pred)`

此做法簡單，但會錯失大量語義等價情況。

### 1.2 造成的觀測偏差

1. **格式等價誤判**
   - `4.25元` vs `4.25`
   - `16 年` vs `十六年`
2. **數值單位誤判**
   - 百分比、小數、科學記號、億/千元表記差異
3. **多子題被當單一字串比對**
   - 問題含 A + B，只答 A 時難精準給部分分數
4. **拒答指標不完整**
   - 僅有 precision，不足以看過度拒答或拒答不足

---

## 2. P0 範圍（In Scope / Out of Scope）

### In Scope

- 升級 `judge` 與評測統計邏輯
- 新增 strict / relaxed 雙軌指標
- 新增拒答 confusion matrix 與 F1
- 新增多子題完整率（completeness）
- 產出更可診斷的 `eval_summary.json`

### Out of Scope

- 不改 retrieval 策略（Hybrid / Rerank）
- 不改 LLM prompt 與生成流程
- 不改 chunking

---

## 3. 設計原則

1. **雙軌評分，避免「放寬即進步」錯覺**
   - `accuracy_strict`：接近舊規則，便於回溯比較
   - `accuracy_relaxed`：容忍語義等價與數值等價

2. **可解釋**
   - 每題附 `judge_reason`（例如 `numeric_equivalent`, `partial_coverage`）

3. **可追蹤**
   - 指標欄位固定化，方便 dashboard 或後續迭代比較

---

## 4. 詳細任務拆解

## Task P0-1：抽離評分器模組

### 目標
將評分邏輯從 `core.py`/`cli.py` 的內嵌函式中抽離成獨立 evaluator（方便測試與擴充）。

### 建議結構

- `src/langchain_rag_app/eval/`
  - `normalizers.py`
  - `judge.py`
  - `metrics.py`

### 產出

- `judge_answer(...)` 可回傳：
  - `is_correct_strict`
  - `is_correct_relaxed`
  - `coverage_score`（0~1）
  - `reason_codes`（list）

---

## Task P0-2：文字與數值正規化

### 目標
建立可重用 normalizer，降低格式噪音造成誤判。

### 功能需求

1. **文字層**
   - 全半形、標點、空白、大小寫統一
   - 中文數字轉阿拉伯數字（至少 0~100 常見範圍）

2. **數值層**
   - 擷取數字 + 單位（元、億元、千元、%、年）
   - 百分比/小數互轉容忍（如 0.12% vs 0.0012）
   - 科學記號容忍（`1.2E-3`）

3. **容忍區間**
   - 可設定 numeric tolerance（預設可為相對誤差 0.5%）

### 產出

- `normalize_text(s)`
- `extract_numeric_facts(s)` -> list of `{value, unit, type}`
- `numeric_equivalent(a, b, tolerance)`

---

## Task P0-3：多子題判定與部分分數

### 目標
針對 `A + B`、`比較 2023 與 2024` 等題型，避免「全對/全錯」過度簡化。

### 設計

1. 子題切分（rule-based）
   - 關鍵連接詞：`、` `與` `以及` `;` `；` `比較`
2. 子題覆蓋檢測
   - gold 每個要素是否在 pred 中被對應到
3. 分數
   - `coverage_score = hit_subparts / total_subparts`

### 產出

- 每題新增欄位：
  - `subparts_total`
  - `subparts_hit`
  - `coverage_score`

---

## Task P0-4：拒答指標完整化

### 目標
把拒答能力從單一 precision 擴展為完整分類指標。

### 需計算

- TP（該拒答且有拒答）
- FP（不該拒答卻拒答）
- FN（該拒答卻未拒答）
- TN（不該拒答且未拒答）

### 指標

- `refusal_precision`
- `refusal_recall`
- `refusal_f1`
- `refusal_confusion_matrix`

---

## Task P0-5：評測輸出擴充

### 目標
讓 `eval_results.json` 與 `eval_summary.json` 可直接支援診斷與報告。

### eval_results.json（每題）新增欄位

- `is_correct_strict`
- `is_correct_relaxed`
- `coverage_score`
- `judge_reason_codes`

### eval_summary.json 新增欄位

- `accuracy_strict`
- `accuracy_relaxed`
- `avg_coverage_score`
- `refusal_precision`
- `refusal_recall`
- `refusal_f1`
- `refusal_confusion_matrix`

---

## Task P0-6：回歸測試（Evaluator Unit Tests）

### 目標
確保未來調整不破壞評分一致性。

### 最低測試集

1. 格式等價測試
   - `4.25` == `4.25元`
2. 百分比測試
   - `0.12%` == `1.2E-3`
3. 中文數字測試
   - `十六年` == `16 年`
4. 拒答判定測試
   - gold 為拒答型時，僅 `pred_refusal=True` 才算對
5. 多子題覆蓋測試
   - 2 子題中答 1 題時 `coverage_score=0.5`

---

## 6. 驗收標準（Definition of Done）

1. 不改 RAG pipeline 前提下，可輸出 strict/relaxed 雙軌結果
2. `eval_summary.json` 含完整拒答指標與 confusion matrix
3. 多子題 coverage 可量化
4. 單元測試覆蓋上述 5 類基礎情境
5. 新舊結果可對照（提供一次 baseline 對比）

---

## 7. 風險與緩解

1. **過度放寬導致指標灌水**
   - 緩解：保留 strict 指標作主追蹤，relaxed 僅作輔助解讀

2. **rule-based 子題切分不穩**
   - 緩解：先做保守規則；失敗案例記錄到後續 P1/P2

3. **數值單位規則複雜**
   - 緩解：先覆蓋本題庫常見單位（%、元、千元、億元、年）

---

## 8. 依賴與串接

- 先完成本計畫（P0）後，再執行：
  - P1（Hybrid + Rerank）
  - P2（Query Planning）
  - P3（Evidence Gate）

> 原則：沒有穩定評測器，就不要進入大規模模型優化。

---

## 9. 實作狀態（2026-03-13）

已在 `langchain_rag` 完成 P0 實作：

- ✅ P0-1：抽離評分器模組
  - 新增 `src/langchain_rag_app/eval/normalizers.py`
  - 新增 `src/langchain_rag_app/eval/judge.py`
  - 新增 `src/langchain_rag_app/eval/metrics.py`

- ✅ P0-2：文字與數值正規化
  - 中文數字（常見範圍）轉換
  - 百分比/科學記號/單位（元、千元、萬、億、年）處理
  - `numeric_equivalent()` 相對誤差容忍

- ✅ P0-3：多子題 coverage
  - rule-based 子題切分
  - 每題輸出 `coverage_score`

- ✅ P0-4：拒答指標完整化
  - 輸出 `refusal_precision / refusal_recall / refusal_f1`
  - 輸出 `refusal_confusion_matrix`

- ✅ P0-5：評測輸出擴充
  - 每題：`is_correct_strict`, `is_correct_relaxed`, `coverage_score`, `judge_reason_codes`
  - 總結：`accuracy_strict`, `accuracy_relaxed`, `avg_coverage_score` 等

- ✅ P0-6：回歸測試
  - 新增 `tests/test_evaluator.py`
  - 覆蓋：格式等價、百分比、中文數字、拒答、多子題覆蓋
