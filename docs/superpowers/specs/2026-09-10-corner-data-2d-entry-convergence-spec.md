# WHD 截角資料整合與 2D 入口收斂規格書

## 目標

收掉主視窗舊的獨立 2D Notebook 入口，將既有展開圖能力整合進 Fold Designer 的「板件選單」，新增「截角資料」模式。功能本體不重寫，只改入口與 View 組裝方式。

## 已確認 UX

- 板件選單保留「組合體」，新增「截角資料」。
- 點「截角資料」後，左側內容像目前組合體板件清單，列出 authoritative workspace 目前實際存在的所有正式板件。
- 點某板件後，Fold Designer 的同一圖區顯示該板件原本既有的 2D 展開圖；不得跳回舊 Notebook、不得另開第二套 2D 視窗。
- 原本 2D 的孔、尺寸、截角、BEND、標註與互動能力全部保留；「功能不變，只改入口」。
- 3D 有的正式板件，截角資料就有；兩者是同一份 authoritative state，不建立第二份 `2d_parts` / `corner_parts` 狀態。

## SSOT

```text
Project / Workspace authoritative state
    -> stable physical part identity
    -> PartSpec / Resolved Manufacturing Geometry
    -> authoritative PartRenderData / FinalScene
    -> 3D View
    -> Unfold View
```

禁止：

- 由 3D 畫面反推 2D 幾何；
- 在新入口重算第二份 manufacturing geometry；
- 用 UI label 當板件 identity；
- 用 validation / screenshot / expected value 回灌 production 幾何；
- widget-to-widget 同步冒充資料同步。

## 板件身份與動態拓撲

- 身份只能使用 stable authoritative part key，不使用顯示文字。
- 動態門、底板、中隔、indicator、inner door、multipart physical children 必須由 current workspace / resolved manufacturing output 投影。
- refresh 時保留仍合法的 selected stable key；若板件已不存在，必須丟棄 stale selection 並從 authoritative part list 重新 resolve。

### Multipart BoxBody

- operator 頂層仍可顯示單一「箱身」。
- 實體子板件維持 stable physical identity，例如 `box_body:left_side` / `box_body:back` / `box_body:right_side`。
- 進入箱身展圖時：若先前記住的 physical child 仍存在，沿用它；否則選 authoritative workspace order 的第一個 child。
- 不得用 aggregate `box_body` 偽造 multipart 單片展圖。

## View 邊界

「截角資料」是 UI mode，不是 manufacturing part，也不是新的幾何 owner。

mode switch / view destroy / view recreate / StringVar trace / selection callback 不得：

- 修改 manufacturing state；
- 重送 geometry；
- 改變 CornerType、Fold Profile、holes、part presence；
- 改變 Save/Reload payload。

雙 UI 過渡期同步方式固定為：

```text
authoritative state mutation
    -> invalidate
    -> legacy unfold View refresh
    -> new Fold Designer unfold View refresh
```

不是 legacy widget <-> new widget 互相抄值。

## 舊 2D Notebook 相依盤點

目前 `gui.py` 舊入口仍包含：

- `self.notebook`
- `self.tab_z`
- `self.tab_head`
- `self.tab_tail`
- `self.tab_door`
- `self.tab_base_plate`
- stable key -> tab selection glue
- `refresh_corner_type_panel()` / `draw_preview()` 等依 tab widget 的 callback 路徑

T5 前先遷移能力；T7 才可移除 legacy entry。禁止在 parity 尚未證明前提前刪除。

## Fold Designer 既有可複用骨架

`fold_designer_bridge.py` 已存在：

- `part_selector` / `part_var` / `part_choice_menu`
- `designer_workspace.available_parts`
- `_phase6_operator_part_selector_keys(...)`
- `_phase6_box_body_piece_keys(...)`
- `_phase6_activate_operator_part(...)`
- physical child -> same resolved aggregate manufacturing result 的 render-data sink
- 組合體左側板件列表與 topology refresh pattern

新功能應用 adapter / view-controller 層接入這些既有權威，不建立第二個 manufacturing solver。

## 驗收順序

1. T0：Baseline / Spec / Knowledge Gate。
2. T1：新增「截角資料」Navigation Mode。
3. T2：Authoritative Parts Projection。
4. T3：Selection Lifecycle + Multipart。
5. T4：Existing Authoritative Unfold View Adapter。
6. T5：Existing 2D Capability Migration。
7. T6：Dual-View Parity + Persistence。
8. T7：Remove Legacy 2D Entry + Dead-Code Gate。
9. T8：Final Combined Acceptance / Production Integration。

T7 之前禁止刪舊入口。

## 測試分層

- Controller / Adapter contract tests：stable identity、authoritative parts、selection lifecycle、render-data sink，不比較畫素。
- Tk headless interaction tests：切換 mode / part / multipart / dynamic add-remove。
- 小型 Xvfb smoke + 最終 Combined Acceptance。
- DXF / Save→Reload / physical-part acceptance 最終仍走 `驗證板件與DXF`。

## Dead-code Gate

T7 完成條件：

- 使用者已無可到達的舊 2D Notebook 入口；
- production navigation 不再依賴 `tab_z/tab_head/tab_tail/tab_door/tab_base_plate`；
- 無 dangling callback / stale tab selection glue；
- shared renderer/helper 若仍被新 View 使用可保留，不為了「刪舊 UI」誤刪共用能力。

## 修改流程硬規則

- 每次施工從最新 target 建新分支，不直接改 `cleanup/2d-3d-sync`。
- 每張票先 preflight / required references，再 RED-first contract，再最小 production change，再 QA。
- validation 只判斷對錯，永遠不能反向成為 production 計算來源。
- 新發現的規則/踩坑必須同步 Skill、AI knowledge/library、durable agent-readable docs 與驗收 evidence。
