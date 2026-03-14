# P0_plan_revised_v1.md — 修正 relaxed 誤判過寬（numeric_equivalent bug）

> 目的：針對目前 `relaxed` 判分中「錯誤數值仍被判定為等價」的問題（例如 2040 vs 2050 仍通過），提出可落地的修補方案，避免評測指標被灌水、誤導後續優化方向。

---

## 1) 問題定義與影響

## 1.1 目前症狀

在 `eval_results.json` 可觀察到：
- 某些題目 `judge_reason_codes` 顯示 `numeric_equivalent`
- 但實際數值不相等（如年份錯誤）仍被 `is_correct_relaxed=true`

代表現有 `numeric_equivalent` 規則在至少一種情境下過寬。

## 1.2 風險

1. **指標失真**：`accuracy_relaxed` 被高估。
2. **錯誤決策**：團隊以為模型進步，實際可能答錯核心數值。
3. **後續優化偏移**：會把檢索/生成問題誤判成已解決。

---

## 2) 修補目標（Revision Scope）

本次只修 P0 評測器，不改推論流程。

### In Scope
- 修正 `numeric_equivalent` 判定邏輯
- 引入「數值類型感知」與「單位一致/可換算」規則
- 新增高風險題型保守判定（年份、比率、金額）
- 補齊單元測試與回歸測試

### Out of Scope
- 不改 retrieval / rerank
- 不改 answer generation prompt
- 不改 chunking

---

## 3) 根因假設（供實作前驗證）

建議先確認下列可能原因（至少一項成立）：

1. **純字串式數值偵測**導致「有數字就視為近似」
2. **容差設計全域化**，年份題也套用過大的 tolerance
3. **單位未綁定**，導致不同語意值被視為同類
4. **多數值題只比對到其中一個值**（partial hit 被當全對）

---

## 4) 修補策略（核心設計）

## 4.1 數值型別化（Typed Numeric Facts）

先抽取並標記數值型別，再決定比較規則。

建議型別：
- `year`（年份）
- `percentage`（百分比/比率）
- `currency_amount`（金額，含元/千元/億元）
- `count`（件數、人數、年數）
- `generic_number`（無法判別時）

每筆 fact 例：
```json
{
  "value": 2040,
  "unit": "year",
  "type": "year",
  "raw": "2040 年"
}
```

## 4.2 型別化容差規則（Type-specific Tolerance）

### A) 年份 (`year`)
- **嚴格相等（tolerance = 0）**
- `2040 != 2050` 必須判錯

### B) 百分比 (`percentage`)
- 支援表示法轉換：`0.12%` ↔ `0.0012`
- 建議容差：
  - 絕對誤差 `<= 0.0005`（若以比例值表示）
  - 或百分點誤差 `<= 0.05pp`（擇一統一）

### C) 金額 (`currency_amount`)
- 單位需可換算（元/千元/萬元/億元）
- 先正規化成最小單位（建議元）再比較
- 建議容差：
  - 相對誤差 `<= 0.1%`（或依題庫調整）

### D) 件數/人數/年數 (`count`)
- 預設嚴格相等
- 中文數字需先正規化（十六=16）

## 4.3 單位一致性守門（Unit Guard）

若兩側型別一致但單位不可換算，直接判不等價。

例如：
- `141.05%` vs `141.05 元` → 不等價
- `819,364,441`（無單位） vs `819,364,441 千元` → 須標記為「資訊不足，不直接等價」

> 針對缺單位情境，建議走「保守策略」：不直接 numeric_equivalent，除非題型規則允許。

## 4.4 多數值覆蓋規則（All-required Matching）

若 gold 含多個關鍵數值（如 A 與 B）：
- 必須達成 **all required facts matched** 才可 `relaxed_match`
- 僅匹配部分時：
  - `coverage_score < 1.0`
  - `is_correct_relaxed = false`
  - reason: `partial_numeric_match`

## 4.5 reason code 精細化

新增或調整 reason codes：
- `numeric_equivalent_strict_type`
- `numeric_mismatch_year`
- `numeric_mismatch_unit`
- `numeric_mismatch_tolerance`
- `partial_numeric_match`
- `missing_unit_guard`

---

## 5) 實作任務拆解（P0-R1 ~ P0-R6）

## P0-R1：重構 numeric parser

- 實作 `extract_typed_numeric_facts(text)`
- 支援：中文數字、科學記號、百分比、常見金額單位
- 產出結構化 fact list

## P0-R2：建立 type-aware comparator

- `compare_numeric_fact(gold_fact, pred_fact, policy)`
- 依 type 套對應 tolerance 與 unit conversion

## P0-R3：加入 unit guard 與保守策略

- 針對缺單位值採保守判定
- 提供可配置開關：
  - `allow_unitless_currency_match=false`（預設）

## P0-R4：多數值 all-match 機制

- gold 多數值時，逐一比對並要求全數命中
- 命中不足只給 coverage，不給 relaxed correct

## P0-R5：評測輸出擴充

在每題結果新增：
- `numeric_match_detail`（可選）
- `failed_numeric_facts`
- `judge_reason_codes`（新 code）

## P0-R6：單測與回歸測試

最小必測案例：
1. `2040` vs `2050`（年份）=> false
2. `0.12%` vs `1.2E-3` => true
3. `4.25元` vs `4.25`（金額缺單位）=> 依 policy，預設 false
4. `13件、27件` vs `13件` => partial，relaxed false
5. `16年` vs `十六年` => true

---

## 6) 配置建議（可放 config）

```json
{
  "eval": {
    "numeric_policy": {
      "year_tolerance": 0,
      "percentage_mode": "ratio",
      "percentage_abs_tolerance": 0.0005,
      "currency_rel_tolerance": 0.001,
      "count_tolerance": 0,
      "allow_unitless_currency_match": false,
      "require_all_numeric_facts": true
    }
  }
}
```

---

## 7) 驗收標準（Definition of Done）

1. 年份錯誤不再被判 `numeric_equivalent`
2. `relaxed` 不再因單位缺失而大量誤判
3. 多數值題需全數命中才算 relaxed correct
4. 回歸測試通過，且至少涵蓋上述 5 類案例
5. 重新評測後，`accuracy_relaxed` 若下降可接受（代表灌水消除）

---

## 8) 重新評測後的判讀原則

若修補後 `accuracy_relaxed` 下降，應解讀為：
- 評測器更誠實，而非模型退步。

建議同時檢視：
- `numeric_mismatch_*` 類 reason code 數量
- 多子題 `coverage_score`
- strict/relaxed 差距是否回到合理區間

---

## 9) 預期成果

完成本修補後，P0 的「量測可信度」會顯著提升：
- 能可靠反映數值題真實表現
- 避免把明顯錯誤（如年份錯）判成正確
- 為 P1（Hybrid + Rerank）提供乾淨、可信的比較基線
