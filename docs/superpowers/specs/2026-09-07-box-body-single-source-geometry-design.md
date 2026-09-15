# Phase6 箱身單一來源／單一幾何算法規格

- 日期：2026-09-07
- 目標分支：`cleanup/2d-3d-sync`
- 規格分支：`spec/box-body-single-source-20260907`
- 性質：實作前 Source of Truth／TDD 驗收規格
- 範圍：Box Body / 箱身的輸入、Fold Profile、2D、3D、DXF、GUI 尺寸顯示與 Save/Reload
- 不改製造規則本身；本輪只消除同一輸入被不同 caller 重算成不同幾何的 Source-of-Truth 漂移

## 1. 問題定義

箱身操作員輸入本來只有一套。現在的錯誤不是「使用者輸入有兩份」，而是**同一份輸入被多條 production 路徑用不同算法重新解讀**。

目前已確認至少存在：

1. `build_box_body_profile() → build_box_body_result_from_fold_profile()`
   - Phase6 新路徑。
   - 依 Cabinet Family 尺寸語意將 operator 尺寸轉成 material Fold Profile。
   - BEND 數量來自實際 topology。
2. `calculate_z_length()`
   - legacy 固定段數總料長公式。
   - 固定假設 `2*FW + W + 2*D - 6T + zl/zr + z_comp`。
3. `build_box_body_result()`
   - legacy 固定 D-W-D + 周邊固定 segment builder。
   - 對 `W/D` 固定減 `2T`，其他折段直接視為 material。
4. GUI / Bridge caller 依「有沒有 profile」決定走新算法或 legacy fallback。
5. 某些 GUI seam 會先自己建立一份 structural result，之後又再呼叫 authoritative render provider 重建一次。
6. Fold Designer 內部 `state.profiles_vault["箱身"]` 與主 GUI `Phase6WorkspaceController.box_body_profile` 都可持有箱身 profile；若 consumer 能直接讀任一份，就可能形成平行 authority。

因此目前可能出現：

```text
同一組 W/H/D/T/FW/zl...
        ↓
   caller A → Fold Profile 算法
   caller B → 固定 9 段算法
   caller C → cached/editor profile
        ↓
2D / 3D / DXF / 尺寸顯示不一致
```

本規格的目標不是再建立一個新 resolver，而是**把現有 canonical Fold Profile / Manufacturing boundary 真正變成唯一 production 幾何入口**。

---

## 2. 核心原則

### 2.1 一個輸入，不准多套 production 尺寸公式

操作員在主 GUI / Fold Designer 編輯的是同一份箱身狀態。

同一個語意欄位不得同時存在兩套 production 解讀：

- `W`
- `H`
- `D`
- `T`
- `FW`
- `zl1 / zl2 / zr1 / zr2`
- `z_comp`
- 箱身 Fold topology
- 箱身 structure state

允許不同 UI 編輯器呈現同一狀態，但**不允許任一 UI consumer 自己重新發明 structural blank 公式**。

### 2.2 Operator 尺寸與 Material Fold Profile 是不同「尺寸空間」，不是兩份來源

資料鏈固定為：

```text
Operator / Project canonical state
        ↓
Cabinet Family dimension semantics
        ↓
Canonical material Fold Profile
        ↓
Manufacturing geometry
        ↓
2D / 3D / DXF / blank dimensions
```

`Fold Profile.len` 是 material-space 尺寸。

Family policy 負責一次性處理 operator-space → material-space 的轉換。轉換完成後，下游只消費 material Fold Profile，**不得再回頭用 raw W/D/FW/zl... 自己補 T**。

### 2.3 受電箱尺寸語意

受電箱已確認：

```python
box_body_profile_uses_outside_dimensions() == True
```

因此受電箱 operator Box Body fold values 以包外語意進入 Family。

正式 material 尺寸轉換：

```text
material segment
= operator outside segment
- 實際相鄰 BEND 數 × T
```

「實際相鄰 BEND 數」必須由**當前 Fold topology**判定，不能用固定 9 段或固定 `2T`。

受電箱還有 Family topology：

- 沿用原箱身主折鏈。
- 移除 terminal `zr1`。
- fresh 預設 magnitude sequence：
  `24 / 24 / 29 / 350 / 800 / 350 / 29 / 18`
  對應
  `zl1 / zl2 / FW左 / D左 / W / D右 / FW右 / zr2`。

在 `T=2`、上述 fresh topology 下，canonical material Fold Profile 的 segment 長度必須為：

```text
22 / 20 / 25 / 346 / 796 / 346 / 25 / 16
```

總 material blank X span：

```text
1596 mm
```

這組 **1596 mm** 是本規格的 Receiving fresh regression oracle。

### 2.4 金庫型／其他 Family 不得被受電箱規則污染

本輪只收斂資料鏈，不把 Receiving 的 outside semantics 寫進 generic builder。

各 Family 仍由：

```python
cabinet_family_policy.box_body_profile_uses_outside_dimensions(...)
cabinet_family_policy.transform_box_body_profile(...)
```

決定轉換／topology。

generic manufacturing geometry 不得出現：

```python
if model == "受電箱":
    ...
```

類的尺寸補丁。

---

## 3. Canonical 所有權

### 3.1 Operator canonical state

主 GUI 的 model / dimension state 是操作員欄位的唯一 upstream source。

Fold Designer 可編輯相同語意，但每次有效 edit 必須 immediate live-sync 回 canonical state；不得形成關閉 3D 才提交的第二份 production draft。

### 3.2 Box Body Fold Profile canonical owner

committed / live production Box Body Fold Profile 的 owner 固定為：

```text
Phase6WorkspaceController.box_body_profile
```

`gui.BoxCalculatorGUI.fold_designer_box_body_profile` 只可作 controller alias，不得另存實體 profile。

Fold Designer：

```text
state.profiles_vault["箱身"]
```

只允許作**編輯器工作記憶體 / UI projection**：

- 開啟時從 canonical profile 載入。
- 使用者每次有效修改後立即 publish。
- publish 成功後 controller 內容即為新的 production canonical profile。
- manufacturing / 2D / DXF / assembly consumer 不得繞過 controller，直接把 `profiles_vault["箱身"]` 當 production Source of Truth。
- snapshot export 前必須先 flush/publish，輸出內容與 controller canonical profile 一致。

### 3.3 Project persistence

Save 只保存 canonical workspace profile。

Load 規則：

1. 新格式 project 有 `box_body_profile`：
   - restore 到 `Phase6WorkspaceController`。
   - UI scalars 由該 canonical state / reader 同步。
   - 不再由 legacy fixed formula 重建。
2. legacy project 沒有 `box_body_profile`：
   - 由 scalar + Family policy **遷移一次**成 canonical profile。
   - migration 成功後立刻進新資料鏈。
   - migration 失敗必須 fail closed，禁止 silent fallback 到 `calculate_z_length()` / `build_box_body_result()`。
3. fresh known-family switch：
   - 先套該 Family fresh defaults。
   - 再立即 materialize canonical profile。
   - 任何 2D/3D/尺寸顯示執行前，box body 必須已存在 canonical profile。

因此：**箱身存在時，初始化完成後「沒有 canonical profile」不是合法 production 狀態。**

---

## 4. 唯一 Manufacturing 幾何邊界

### 4.1 Public production boundary

正式 consumer 只能透過 `ae_engine.manufacturing_api` 取得箱身 manufacturing geometry。

一體式箱身：

```text
BoxBodyPartSpec
→ manufacturing_api.build_part_render_data()
→ PartRenderData
```

二件／三件式：

```text
BoxBodyPartSpec + same canonical Fold Profile + structure state
→ manufacturing_api.build_box_body_structure_render_data()
→ BoxBodyStructureRenderData.pieces[]
```

這兩條是不同**physical structure topology**，不是兩套 dimension Source of Truth。兩者必須共用同一份 canonical material Fold Profile，structure resolver 只能拆分／派生 physical pieces，不能重新解讀 raw W/D/FW。

### 4.2 Canonical integral geometry primitive

integral Box Body 的 structural blank 由：

```python
build_box_body_result_from_fold_profile(...)
```

消費 canonical material Fold Profile。

它不得重新做 Family outside/material 轉換。

### 4.3 合法 derived geometry

下列 helper 可以存在，因為它們是從 canonical geometry / semantic state **衍生**結果，不是第二份輸入來源：

- `box_body_height_from_corner_policies()`
- `box_body_vertical_offsets()`
- `formed_box_body_fw_widths(profile, T)`
- physical structure resolver
- face-local / assembly placement resolver
- material bounds / fold guides from FinalScene

條件是它們的輸入必須來自 canonical state/profile，不可再讀另一份 legacy raw formula。

---

## 5. Legacy API 分級

### 5.1 `calculate_z_length()`

定位改為：

> legacy compatibility helper only

production 禁止：

- `gui.update_calculations()`
- Fold Designer dimension projection
- 2D renderer
- 3D renderer
- DXF export
- Save/Reload validation

呼叫它決定箱身展開總寬。

保留函式本身僅為尚未遷移的外部 API / legacy tests 相容；若全 repo 後續確認零外部依賴，可另案刪除。

### 5.2 `build_box_body_result()`

定位改為：

> legacy scalar-to-fixed-chain compatibility builder

production consumer 在 canonical profile 已存在後不得呼叫它。

尤其禁止：

- GUI preview fallback
- Main calculation fallback
- hole editor structural surface
- baseline feature mapping拿它當 current manufacturing topology
- 3D / DXF fallback

### 5.3 `get_stretched_box_body_data()`

基準 DXF parser / compatibility feature mapper 可以保留，但：

- 不得把從 baseline DXF 反推的 `FW/zl1/zl2/zr...` 回寫為 current authoritative dimensions。
- 不得決定 current structural blank。
- current feature placement 若需 baseline reference，必須映射到 canonical current topology / face-local datum。
- baseline feature extraction 是 secondary feature mapping，不是 Box Body dimension Source of Truth。

---

## 6. GUI 規格

### 6.1 `update_calculations()`

箱身結果尺寸固定：

```text
canonical BoxBodyPartSpec
→ authoritative manufacturing render data
→ material bounds
→ 顯示展開寬／高
```

禁止：

```python
if profile:
    authoritative
else:
    calculate_z_length(...)
```

fresh app 也必須先 materialize canonical profile，而不是走 legacy fallback。

### 6.2 `draw_box_body()`

只能取得**一次 authoritative manufacturing result**。

禁止同一 redraw：

1. 先直接 `build_box_body_result...`
2. 再呼叫 `_authoritative_render_data(spec)`
3. 兩份結果各自供不同 hit-zone / canvas / dimensions 使用

2D material、BEND、face bounds、display dimensions 必須由同一份 authoritative result/topology 衍生。

### 6.3 Hole editor

箱身 face editor 可以使用形成後 face envelope，例如：

- W
- D
- BoxBodyFinishedHeight

作為 face-local editing datum。

但這種 formed-face 尺寸**不是 unfolded blank Source of Truth**。

禁止 hole editor 為了取得 surface 再建立一套 fixed 9-segment Box Body structural result。

目前 unreachable/dead `open_part_hole_editor(part_key=="box_body")` legacy branch 應移除，避免未來 refactor 意外復活第二算法。

### 6.4 Snapshot / `part_dimensions`

若 `part_dimensions["box_body"]` 保留，必須明確區分 dimension space：

- `FORMED_OUTSIDE`：W/H/D assembly envelope。
- `MATERIAL_BLANK`：只能由 authoritative render material bounds 取得。

不得把 `{"width": W, "height": H}` 當成 unfolded blank。

若現有 schema 無 dimension-space 欄位，本輪至少在使用處與測試中禁止混用；是否升級 schema 可另案，不為了本修正先擴大 project format。

---

## 7. Fold Designer Bridge 規格

Bridge 只負責：

- canonical snapshot ↔ editor controls
- UI profile editing
- live publish
- project migration adapter
- display projection

Bridge 不得：

- 自己實作 Box Body blank width formula
- 依 segment count 寫 5/8/9 段特例
- 在 canonical profile 缺失時 silent fallback fixed-chain geometry
- 直接把 `state.profiles_vault["箱身"]` 交給 manufacturing/export，而沒有先 publish canonical state

`export_phase6_snapshot()` 前必須：

1. save editor。
2. read/validate current profile。
3. publish 到 canonical workspace。
4. snapshot 攜帶與 canonical owner 完全一致的 profile。

---

## 8. Family / Structure lifecycle

### 8.1 Fresh Receiving

固定資料流：

```text
使用者切「受電箱」
→ apply_family_defaults
→ Receiving transform removes zr1
→ build_box_body_profile
→ outside → material conversion by actual bends
→ workspace_controller.set_box_body_profile
→ build BoxBodyPartSpec
→ manufacturing render
→ 2D / 3D / DXF / dimensions
```

沒有任何 fixed 9-segment fallback。

### 8.2 Fresh Vault / Custom

同樣先建立 canonical profile，再進 manufacturing。

Family policy 可不同；production chain 不同的只能是 Family policy / physical structure policy，不能是 GUI caller 私有公式。

### 8.3 Live Family switch

無論 3D 是否已開：

```text
old family canonical state
→ family transaction
→ new family scalars/topology
→ rebuild canonical profile exactly once
→ publish
→ all consumers invalidate/re-render
```

不得殘留 old-family profile，也不得讓 Main GUI 與 Fold Designer 分別 rebuild 出兩份 profile。

### 8.4 3D Fold edit

```text
canonical profile
→ editor copy
→ user edit one segment / angle / add / remove
→ validate
→ immediate publish canonical profile
→ manufacturing re-render
→ 2D / 3D / DXF all observe same new state
```

刪折後 material compensation 必須按新實際 BEND adjacency 重新計算／保存，不得保留 stale `ui_len_add` 作 manufacturing oracle。

### 8.5 二件／三件式

structure state 決定 physical split；canonical Box Body Fold Profile 仍只有一份 upstream topology。

structure resolver 可以產生多片 material geometry，但不得：

- 另造一份 independent Box Body profile
- 重新用 raw W/D/FW 套 fixed material correction
- 用 exploded preview bounds 冒充單片 blank

每片 blank 直接量各自 authoritative physical piece material。

---

## 9. 必須移除的 production 分叉

本輪完成時，下列 production pattern 必須為零：

### 9.1 GUI 尺寸 fallback

```python
z_len = ae.calculate_z_length(...)
```

不得再出現在 active production calculation path。

### 9.2 GUI scalar structural fallback

```python
build_box_body_result(
    w=..., d=..., fw=..., ...
)
```

不得再作 current Box Body preview / current feature surface / current dimensions 的 authority。

### 9.3 profile-presence 決定算法

禁止：

```python
if spec.fold_profile:
    new_algorithm()
else:
    old_algorithm()
```

production initialization 必須保證 canonical profile 已存在；缺 profile 是 migration/error state，不是選擇另一套算法的正常條件。

### 9.4 consumer 重複 build

同一 consumer 不得先建 structural result，再建 authoritative PartRenderData。

### 9.5 baseline 反推 current dimensions

baseline DXF 可提供 fixed feature provenance；不得提供 current W/D/FW/z fold authoritative value。

---

## 10. 不變量

實作完成後必須全部成立：

1. 箱身操作員同一欄位只有一個 canonical value。
2. Box Body material Fold Profile 只有一個 committed/live production owner。
3. Receiving operator outside → material compensation 只在 canonical profile materialization / edit normalization 邊界做一次。
4. manufacturing consumer 不直接重新解讀 raw Receiving FW/W/D/z folds。
5. fresh Box Body 初始化結束後 canonical profile 一定存在。
6. `calculate_z_length()` 零 production caller。
7. `build_box_body_result()` 零 current manufacturing GUI/Bridge caller；只允許明確 legacy compatibility path。
8. Main 2D、Fold Designer 3D、DXF export、尺寸顯示的 blank bounds 來自同一 manufacturing result。
9. arbitrary Fold Chain add/remove 後，BEND 數、blank width、3D fold 一起變，不受固定 segment count 限制。
10. Receiving fresh profile 不含 `zr1`。
11. project Save/Reload 後 canonical profile identity / lengths / angles 不漂移。
12. Main GUI 與 Fold Designer 不可各自持有可供 production consumer 讀取的不同 box-body profile。
13. multi-piece structure 的每片 material 仍由同一 canonical profile + structure state 派生。
14. `config.ini` 不因測試／live sync 被修改。
15. generic Box Body engine 不新增 Receiving-specific hardcode。

---

## 11. TDD / 驗收 seam

本規格核准後，以下 seam 視為已確認，可直接用於 RED→GREEN。

### S1 — Receiving canonical material profile

輸入：

```text
model=受電箱
W=800
H=1600
D=350
T=2
FW=29
zl1 magnitude=24
zl2=24
zr2=18
Receiving topology removes zr1
```

期望 material profile：

```text
22 / 20 / 25 / 346 / 796 / 346 / 25 / 16
```

期望 total material X span：

```text
1596
```

### S2 — Fresh Main GUI 不得走 legacy total-width fallback

fresh Receiving 尚未開 Fold Designer 時：

- workspace 已有 canonical Box Body profile。
- Main GUI 箱身展開寬從 authoritative render material bounds 得到 1596。
- monkeypatch / guard `ae.calculate_z_length()` 為 raise 時，fresh Receiving 主 GUI仍可完成計算。

這條直接證明 production 不再依賴 legacy fallback。

### S3 — Main 2D == Manufacturing

同一 BoxBodyPartSpec：

```text
Main 2D CUTTING material bounds
==
manufacturing_api authoritative material bounds
```

不得有第二次 scalar rebuild。

### S4 — 3D == 2D == DXF

同一 canonical profile：

```text
Main 2D material bounds
==
single-part 3D source material bounds
==
DXF CUTTING bbox
```

BEND count / positions 同源。

### S5 — arbitrary topology

至少驗：

- 刪除一個可選外折。
- 新增外折。
- 5 段以上與 9 段以外的合法 topology。

每次修改後：

- material X span 按 actual segments 改變。
- 2D/3D/DXF 同步。
- `calculate_z_length()` 結果即使不同，也不得影響 production output。

### S6 — Receiving `zr1` guard

fresh、live family switch、Save/Reload：

```text
Receiving canonical box_body_profile
```

均不得重新出現 terminal `zr1`。

### S7 — Vault guard

Vault 現有 canonical fold/profile fixture 必須維持現有 verified dimensions/topology。

不得因為移除 Receiving fallback 而把 Receiving outside conversion套到 Vault。

### S8 — project migration

legacy project 無 `box_body_profile`：

- load 時只 migration 一次。
- migration 後 controller profile 存在。
- 2D/3D/DXF 只走 canonical profile。
- 下一次 Save 寫入 canonical profile。

corrupt profile：

- 明確 error / fail closed。
- 不 silent fallback fixed 9-segment formula。

### S9 — profile owner parity

任一 Fold Designer edit 後：

```text
editor exported profile
==
workspace_controller.box_body_profile()
==
project snapshot box_body_profile
```

以 normalized signature 比較 lengths / angles / semantic keys。

### S10 — multi-piece Receiving

Receiving fixed `THREE_PIECE_SIDE_BACK_SPLIT`：

- structure resolver 只消費 canonical profile + structure state。
- left/back/right physical pieces 的 unfolded material 由各自 authoritative result量得。
- 組裝 formed W/H/D 保持 family contract。
- 不得另跑 fixed 9-segment scalar builder。

### S11 — config invariant

每輪 QA：

```text
config.ini SHA256 before == after
```

canonical hash 仍應為目前 branch 的既有值，除非另案明確變更設定。

---

## 12. Remote QA Gate

因本輪涉及 Fold Profile、2D/3D、manufacturing、DXF，一律視為高風險 geometry change。

最少：

1. focused RED/GREEN：S1 / S2 / S3。
2. Box Body core Fold ownership regression。
3. Receiving fresh family / family switch regression。
4. arbitrary topology regression。
5. Box Body structure multi-piece regression。
6. 2D / single-part 3D / assembly 3D consistency。
7. DXF bbox parity。
8. Save/Reload。
9. Head/Tail / assembly integrity affected regression。
10. `config.ini` invariant。
11. 至少一份真實 3D visual artifact，由開發端自行檢視。
12. remote run 必須監控到 terminal state；one-shot workflow 完成後移除並遠端反讀確認。

---

## 13. 實作順序

### Phase A — state/materialization

1. fresh Box Body initialization 強制建立 canonical profile。
2. legacy project 缺 profile 時一次 migration。
3. canonical owner 固定到 WorkspaceController。
4. Designer edit immediate publish owner parity。

### Phase B — remove duplicate calculation callers

1. `update_calculations()` 移除 `calculate_z_length()` fallback。
2. `draw_box_body()` 移除 local structural rebuild，改只消費 authoritative render。
3. 移除 unreachable hole-editor scalar Box Body branch。
4. Fold Designer dimension projection 改量 canonical manufacturing geometry，需要 material blank 時不得用 W/H metadata。

### Phase C — baseline / secondary features

1. baseline feature mapping 不再以 current legacy 9-segment result作 authority。
2. baseline features 映射到 canonical current topology / face-local datum。
3. 確認 current dimensions 不會被 baseline parser 反推覆蓋。

### Phase D — compatibility isolation

1. 對 `calculate_z_length()`、`build_box_body_result()` 加清楚 legacy contract。
2. production source scan 確認無 active caller。
3. legacy tests若仍需保留，必須明示 compatibility，不得拿它們當 current manufacturing oracle。

### Phase E — full gate

跑本規格第 12 節全部 gate，完成 docs / pitfalls / change log / durable QA state，再整合 target。

---

## 14. 非目標

本輪不做：

- 不改使用者已確認的箱身製造尺寸。
- 不新增第二個 Box Body resolver。
- 不重寫 Corner / Relief registry。
- 不改 Receiving 固定三件式側背分離規則。
- 不改二件／三件式已確認結構尺寸規格。
- 不重新設計 Door / EndCap / Base Plate。
- 不因清 legacy API 而破壞尚未確認的外部 public compatibility；先隔離 production caller，API 刪除另案。
- 不把 formed face W/H/D 與 unfolded blank width/height 混成同一欄位語意。
- 不用「畫面看起來一樣」代替 material bounds / topology / DXF / Save-Reload 驗收。

---

## 15. 完成定義

只有全部成立才算完成：

- [ ] fresh / load / live-switch 後 Box Body canonical profile 永遠存在。
- [ ] Receiving fresh material profile為 `22/20/25/346/796/346/25/16`，total X = `1596`。
- [ ] production `calculate_z_length()` caller = 0。
- [ ] production current Box Body `build_box_body_result()` scalar fallback caller = 0。
- [ ] Main 2D 不自行重建另一份 structural geometry。
- [ ] Fold Designer 不持有可繞過 controller 的 production profile authority。
- [ ] 2D / 3D / DXF / dimensions 同一 canonical manufacturing result。
- [ ] arbitrary topology 不受固定 segment count 影響。
- [ ] Receiving `zr1` 不會在 lifecycle 中復活。
- [ ] multi-piece physical pieces 同源。
- [ ] Save/Reload profile round-trip一致。
- [ ] Vault regression無退化。
- [ ] config invariant通過。
- [ ] remote QA terminal GREEN，one-shot workflow已清。
- [ ] production source scan 無第二套 Box Body blank公式。
