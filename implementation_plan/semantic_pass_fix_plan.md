# semantic_pass_fix_plan.md — 修復 Semantic Task Pass 為 0 的細部實作設計

> 目標：針對目前 `semantic_task_pass = 0` 的問題，修正兩個核心瓶頸：
> 1) **pass 規則過嚴**（LLM judge 分數高但 pass=false）
> 2) **聚合邏輯不合理**（multi_fact 的語義訊號被 aggregator 吃掉）

---

## 1) 現況診斷（依最新 eval）

### 1.1 觀測結果

- `summary_strategy` 共 3 題：
  - `llm_pass=true`：0
  - `rule_relaxed=true`：0
  - `final_label` 全為 `incorrect`

- `multi_fact` 共 5 題：
  - `llm_pass=true`：3
  - 但 `final_label=incorrect` 仍存在（如 q25）

- 代表：
  - **LLM pass 判準偏嚴**（例如 q24：0.9/0.8/0.9 仍 pass=false）
  - **aggregator 對 multi_fact 過度 rule-first**，語義訊號未被納入最終決策

---

## 2) 修復目標與驗收門檻

## 2.1 目標

1. 讓 LLM judge 的 `pass` 能合理反映語義品質
2. 讓 multi_fact 題型能使用語義層訊號進行最終判定
3. 讓 `semantic_task_pass` 不再被單一題型定義卡死

## 2.2 KPI（第一輪）

- `semantic_task_pass >= 0.30`
- `accuracy_relaxed` 下降不超過 `0.02`
- `refusal_f1` 不惡化

---

## 3) 設計原則

1. **Hard fact 不放寬**：數值、年份、拒答仍以 rule 為主
2. **Semantic task 分級判定**：摘要與多子題允許語義等價
3. **Faithfulness 保底**：語義放寬不可犧牲證據一致性
4. **可解釋輸出**：每題應能看出是 rule 或 llm 決定

---

## 4) 修復方案總覽

## A. 修正 LLM pass 規則（避免過嚴）

### 現況問題
LLM 回傳高分（0.9/0.8/0.9）仍 `pass=false`，表示「pass 由模型主觀布林決定」偏保守。

### 改進策略
新增程式端「再判定層」：`normalize_llm_pass()`

以分數計算決定 pass：

- `weighted = semantic*0.4 + completeness*0.4 + faithfulness*0.2`
- 若 `faithfulness < 0.6` → 強制 fail
- 否則 `weighted >= threshold` → pass

題型門檻：
- `summary_strategy`: threshold = 0.70
- `multi_fact`: threshold = 0.75，且 completeness >= 0.75

> 保留原始 `llm_judge.pass`，新增 `llm_judge.pass_calibrated` 供聚合器使用。

---

## B. 修正 Aggregator（納入 multi_fact 語義訊號）

### 現況問題
`multi_fact` 被歸類為 hard_types，導致 llm pass 幾乎無法影響 final label。

### 改進策略
調整 `aggregate_three_layers()`：

1. hard_types 只保留：
   - `hard_fact_numeric`
   - `hard_fact_entity`

2. semantic_types 擴充為：
   - `summary_strategy`
   - `multi_fact`

3. 新規則（semantic types）：
   - `rule_relaxed && llm_pass_calibrated` → `correct_semantic`
   - `llm_pass_calibrated && faithfulness>=0.8` → `correct_semantic`
   - `rule_relaxed || llm_pass_calibrated` → `partial`
   - else `incorrect`

> 注意：對 multi_fact 可加 safety guard（若 numeric mismatch 嚴重則不允許 correct_semantic）

---

## C. 修正 semantic_task_pass 指標定義

### 現況問題
`semantic_task_pass` 只看 `summary_strategy`，造成指標過度狹窄。

### 改進策略
在 `metrics.py` 調整：

- semantic tasks = `summary_strategy + multi_fact`
- pass 條件：`final_label in {correct_semantic, partial}`

新增拆分指標：
- `semantic_task_pass_summary`
- `semantic_task_pass_multifact`
- `semantic_rule_conflict_rate`（llm pass 但 final incorrect）

---

## 5) 實作任務拆解

## SP-1：LLM judge 校準模組

新增函式：
- `calibrate_llm_pass(question_type, semantic_score, completeness_score, faithfulness_score)`

輸出：
- `pass_calibrated`
- `calibrated_reason`
- `weighted_score`

## SP-2：eval 結果欄位擴充

在 `eval_results.json` 每題新增：
- `llm_judge.pass_raw`
- `llm_judge.pass_calibrated`
- `llm_judge.weighted_score`
- `llm_judge.calibrated_reason`

## SP-3：aggregate_three_layers 改版

- 更新題型分組
- 使用 `pass_calibrated` 替代 `pass`
- 保留 hard-fact 嚴格策略

## SP-4：metrics 指標改版

- `semantic_task_pass` 納入 multi_fact
- 新增分題型 pass 指標與 conflict rate

## SP-5：回歸測試

最小測試案例：
1. summary 高分（0.9/0.8/0.9）應 pass_calibrated=true
2. faithfulness 低（<0.6）應 fail
3. multi_fact llm_pass=true 且 rule=false 可得 partial/correct_semantic
4. hard_fact 仍不可被語義層覆蓋

---

## 6) 風險與緩解

1. **語義放寬導致灌分**
   - 緩解：faithfulness hard floor + 保留 strict 指標

2. **multi_fact 過度寬鬆**
   - 緩解：若 numeric mismatch 類 reason code 出現，限制最高到 `partial`

3. **跨版本比較困難**
   - 緩解：保留舊欄位並標註 deprecated，提供 before/after 對照

---

## 7) 導入順序（建議 1~2 天）

## Day 1
- SP-1（pass calibration）
- SP-2（結果欄位擴充）
- SP-3（aggregator 改版）

## Day 2
- SP-4（metrics 改版）
- SP-5（測試 + 全量 eval）
- 產出對照報告（before vs after）

---

## 8) 驗收清單（DoD）

1. `semantic_task_pass` 不再固定為 0
2. 可觀測 `pass_raw` 與 `pass_calibrated` 差異
3. `semantic_rule_conflict_rate` 下降
4. `accuracy_relaxed` 與 `refusal_f1` 未顯著惡化
5. 多題型結果可被合理解釋（含 reason code）

---

## 9) 預期成果

- 修復語義層「有訊號但無法轉化成最終通過」問題
- 提升 summary/multi_fact 題型的評估公平性
- 讓後續 P2（query planning）與 P3（gate tuning）的成效能被準確量測

---

## 10) 實作狀態（2026-03-15）

已完成並落地於 `langchain_rag`：

- ✅ SP-1：LLM pass 校準層
  - 新增 `calibrate_llm_pass(...)`
  - 產出 `pass_calibrated`, `weighted_score`, `calibrated_reason`
  - 保留 `pass_raw`（原始 LLM pass）

- ✅ SP-2：結果欄位擴充
  - `llm_judge.pass_raw`
  - `llm_judge.pass_calibrated`
  - `llm_judge.weighted_score`
  - `llm_judge.calibrated_reason`

- ✅ SP-3：Aggregator 改版
  - hard types 只保留 `hard_fact_numeric`, `hard_fact_entity`
  - semantic types 納入 `summary_strategy`, `multi_fact`
  - semantic 聚合採 `pass_calibrated` + faithfulness guard

- ✅ SP-4：metrics 改版
  - `semantic_task_pass` 納入 `summary_strategy + multi_fact`
  - 新增：
    - `semantic_task_pass_summary`
    - `semantic_task_pass_multifact`
    - `semantic_rule_conflict_rate`

- ✅ SP-5：回歸測試
  - 更新 `tests/test_three_layer_eval.py`
  - 新增 `tests/test_semantic_pass_metrics.py`
