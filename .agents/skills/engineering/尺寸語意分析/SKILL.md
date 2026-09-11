---
name: 尺寸語意分析
description: 當工作需要追蹤 WHD 數值運算中的尺寸語意，尤其要分清料尺寸、包外、flat、formed、FW、T、datum、截角與 collision envelope，並找出同為 mm 卻語意不相容的混用時使用；此 Skill 只做分析與驗證，不建立 production 公式 authority。
---

# 尺寸語意分析

`尺寸語意分析` 用來抓一類很難靠「單位都是 mm」發現的錯：**物理單位相同，但工程語意不同。**

例如 `29 mm` 的 FW 包外與 `29 mm` 的 flat 料尺寸，數字和 unit 都相同，卻不是可互換的量。若沒有獨立、已核准的 conversion authority，就不能直接相加、相減、比較或代入同一 formula。

本 Skill **只能做分析與驗證**。任何 finding 都**不能回灌 production**；不能因為 mismatch 看起來差 `2 mm` 就發明 `+2` offset 或新 formula。真正 Source of Truth 仍來自使用者核准規格、canonical domain spec、Registry、正式 UI/input definition 與 production authority。

## 1. WHD semantic dimension vocabulary

基礎物理單位可以仍是 `mm`，但分析時至少區分以下 semantic dimensions：

| Semantic dimension | 意義 |
| --- | --- |
| `{material_length}` | 料尺寸／flat material 上的實際長度 |
| `{formed_outside_length}` | 成形後包外尺寸 |
| `{FW_formed}` | FW 對應的 formed physical face / 3D 輸入語意 |
| `{sheet_thickness}` | 板厚 T；`2T` 是兩層厚度占用，不等於任意補償量 |
| `{flat_relief_length}` | 2D flat 截角／避讓上的長度 |
| `{collision_envelope}` | 3D 組立或 collision 判定的 physical envelope |
| `{datum_offset}` | 相對基準點／基準面的 offset，不是絕對尺寸 |

必要時可以增加局部 derived semantic dimension，但新增 vocabulary 也必須有 authority，不得靠命名猜測。

## 2. 同為 mm 仍可能不相容

傳統 dimensional analysis 會把兩個 `mm` 視為同維度；WHD 不能只做到這裡。

```text
29 mm {FW_formed}
29 mm {material_length}
```

兩者數值相同、unit 相同，**語意仍不同**。要互換必須存在明確 conversion：例如由已核准展開/成形規則、厚度、折彎方向與基準面定義得到的轉換。

沒有 conversion authority 時：

- 不得因數字相等就當等價；
- 不得因差值剛好是 `T` 或 `2T` 就猜 compensation；
- 不得用 validation result 倒推出轉換公式；
- 不得把 3D collision envelope 直接當 2D flat relief dimension。

## 3. 基本 semantic algebra

### 3.1 Addition / subtraction

相加、相減預設要求相容 semantic dimension：

```text
{material_length} + {material_length} -> {material_length}
{formed_outside_length} - {formed_outside_length} -> {formed_outside_length}
{material_length} + {formed_outside_length} -> MISMATCH
```

只有存在明確 conversion authority 時，才先轉到共同語意再運算。

### 3.2 Multiplication / division

dimensionless count / ratio 可以作用於尺寸，但要確認 ratio 真的是 `{1}`。例如 `2 * T` 可以得到 thickness occupancy；它不代表任何地方看到 `2 mm` 都能解釋成 `T` 補償。

### 3.3 Comparison / assignment / return

以下也要檢查 semantic compatibility：

- assignment：RHS semantic dimension 要符合 LHS contract；
- function arg / return：caller 與 callee 的尺寸語意要一致；
- conditional branches：不同 return path 不可一邊回 flat、一邊回 formed；
- equality / tolerance compare：比較前必須先確認 semantic basis 相同。

## 4. WHD 常見 mismatch 類型

### 4.1 flat bbox 當 formed 3D package

2D 展開的 bbox 是 `{material_length}` / flat topology 的結果；3D 包外是 `{formed_outside_length}`。直接拿 flat bbox 當 3D package dimension 是語意錯誤，即使數字偶爾相等。

### 4.2 FW 被誤當成任意 fold segment

FW 是正式 3D input / physical face 語意 `{FW_formed}`。不能因某段折長數字相近就把它當 FW，也不能把「FW 都同一個面」改寫成不同面上的 local segment。

### 4.3 T / 2T 被誤當經驗補償

`T` 是 `{sheet_thickness}`。`W - 2T` 的 `2T` 有具體 physical occupancy；不能從 validation 差值看到 2 mm，就反推 production 要 `+T` 或 `-T`。

### 4.4 datum offset 當絕對位置／尺寸

`{datum_offset}` 必須和它所屬 datum 一起解讀。局部 offset 不可直接拿去和 global absolute coordinate 比較。

### 4.5 flat relief 與 collision envelope 混用

2D 截角是 `{flat_relief_length}`，驗證對象可能是 3D `{collision_envelope}`。兩者可以經 authoritative backprojection / conversion 互相驗證，但 collision finding **只能判定對錯**，不能自己成為新的截角公式。

## 5. 四階段分析流程

這個流程借用 upstream dimensional-analysis 的 scan → vocabulary → propagation → validation 思路，但 WHD 不接受其強制 `full-auto` / Task-subagent 假設。

### Phase 1 — Scan

找出會產生或傳遞尺寸語意的：

- input / UI fields；
- geometry calculations；
- helper / adapter boundaries；
- serialize / Save→Reload；
- DXF / 2D↔3D projection；
- collision / placement / datum calculations。

先列 scope，不急著改碼。

### Phase 2 — Vocabulary grounding

從使用者規格、UI 定義、canonical Registry / domain docs / Source of Truth 建立 semantic vocabulary。變數名稱只能當線索，不是 authority。

標記 certainty：

- `CERTAIN`：有明確 authority；
- `INFERRED`：由已知 interface / formula 可合理推得，但仍需驗證；
- `UNKNOWN`：沒有足夠 authority，禁止硬猜。

### Phase 3 — Propagation

沿 expression、assignment、call boundary、return path 傳遞 semantic dimension；記錄 explicit conversion。

如果遇到 helper 名稱像 `normalize`, `outside`, `width`，一定追到真正 contract；不得只靠名字判斷。

### Phase 4 — Validation

把 finding 分成：

1. `CONFIRMED_MISMATCH`：明確混用不相容 dimensions。
2. `AUTHORIZED_CONVERSION`：已由 canonical authority 明確轉換，無問題。
3. `AMBIGUOUS_AUTHORITY`：規格不足，不能判定公式對錯。
4. `VALIDATION_ONLY_FINDING`：collision/probe/test 暴露疑點，但不得升格成 production 規則。

## 6. capability-adaptive 執行；不得假裝 subagent

Upstream `dimensional-analysis` 要求固定 `full-auto`，並用 `Task` 啟動 scanner / discoverer / annotator / propagator / validator subagent。這個前提在 WHD **不成立**。

每次先做 capability detection：

- 如果 runtime 真的有可驗證的 subagent / parallel-agent 能力，而且專案允許，可把互相獨立的 scan / review 工作分批執行。
- 如果沒有，**同一執行者**必須按 Phase 1→4 逐階段完成。
- **不得假裝**已派 subagent、不得等待不存在的 agent 回報、不得因沒有 full-auto orchestration 就停工。
- 是否有 capability 只影響 execution mechanics，不影響 analysis authority。

## 7. Authority 防火牆

`尺寸語意分析` 是 validator，不是 formula generator。

允許：

- 指出 `{formed_outside_length}` 被傳給要求 `{material_length}` 的參數；
- 指出兩條 return path semantic dimension 不一致；
- 指出缺少明確 conversion authority；
- 根據既有 authority 驗證 `W - 2T` 之類公式是否維度/語意一致。

禁止：

- 從實測差值決定 `offset = 2`；
- 從 collision fringe 決定新 `formula`；
- 從 test expected / DXF probe / current output 反推 canonical dimension；
- 看到數字「剛好吻合」就升格成 Source of Truth。

**分析與驗證結果不能回灌 production。** 若 finding 指向 production bug，回到使用者／canonical spec／Registry 釐清真正規則，再依 TDD 修正。

## 8. 報告格式

每個 finding 至少列：

```text
path / symbol:
observed semantic dimension:
expected semantic dimension:
physical unit:
authority:
conversion (if any):
classification:
evidence:
next action:
```

Unknown 就寫 UNKNOWN；不要腦補。

## 9. 來源與 WHD 適配

輸入來源：`trailofbits/skills@321ccfe628eca0d314b0ee4eaffcdd8a05639aaf` 的 `dimensional-analysis` Skill，以及 `dimension-algebra.md`、`common-dimensions.md`、`bug-patterns.md`。

WHD 保留 semantic algebra、跨 call-boundary propagation、mismatch classification；把 DeFi token/decimal vocabulary 換成鈑金工程語意，並移除強制 full-auto / fake subagent 前提。最終 authority 永遠是 WHD canonical Source of Truth，而不是分析器本身。
