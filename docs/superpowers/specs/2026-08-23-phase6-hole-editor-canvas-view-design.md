# Phase6 統一開孔編輯器 Canvas View 設計規格

## 目標

把 `gui.py::_open_unified_hole_editor()` 內仍混雜的 Canvas 顯示與座標互動責任收斂成 `Phase6HoleEditorCanvasView`，讓統一開孔編輯器形成三層明確 seam：

1. `Phase6HoleEditorSession`：開孔交易、Undo、context、Confirm/Cancel。
2. `Phase6HoleEditorCanvasView`：Canvas transform、resolved feature 顯示、選取十字、浮動參考框、hit-test。
3. `gui.py`：Tk 組裝、domain adapter、messagebox、Door/Indicator extension 與幾何命令調度。

## 不在本輪範圍

- 不更改 `Phase6HoleEditorSession` 的交易語意。
- 不重寫 `feature_is_within_surface()`、`move_feature_within_surface()`、`reference_distances()`、圓孔排列等 sheet-metal 幾何。
- 不搬 Door 指示燈盒／小門 manufacturing 幾何進 View。
- 不改開孔 catalog、確認／取消按鈕操作方式或 UI 配色。
- 不修改 `config.ini`。

## Source of Truth

### 開孔草稿

唯一 owner 仍是 `Phase6HoleEditorSession`。View 只能讀取 caller 傳入的 feature list 與 selected index，不得修改 feature list。

### 製造幾何

仍由 `ae_engine.sheetmetal_features` 與 manufacturing owner 提供。View 可呼叫純解析／hit-test helper，但不得建立第二套孔位幾何公式。

### Canvas 顯示狀態

`Phase6HoleEditorCanvasView` 唯一擁有目前：

- `CanvasTransform`
- 最近一次 resolved features
- overlay widget placement / hide 狀態

`gui.py` 不再維護 `transform_box` 或自行重新 resolve 一份 hit-test 幾何。

## Module Interface

新增 `phase6_hole_editor_canvas_view.py`：

```python
@dataclass(frozen=True)
class HoleEditorCanvasFrame:
    surface: object
    features: Sequence[object]
    width: float
    height: float
    reference_guide: object
    selected_index: int
    reference_distances: object | None = None
    measure_guide: object | None = None
    baseline_scene: object | None = None
    extra_bounds: tuple[float, float, float, float] | None = None
    insert_label: str | None = None
    error_text: str | None = None
    draw_extra: Callable[[object, CanvasTransform, int, int], None] | None = None
```

```python
class Phase6HoleEditorCanvasView:
    def render(self, frame: HoleEditorCanvasFrame) -> None: ...
    def canvas_to_world(self, x: float, y: float) -> Vec2 | None: ...
    def hit_test(self, x: float, y: float) -> int | None: ...
    def hide_overlays(self) -> None: ...
```

Constructor 只接受 Canvas 與穩定的 View dependency：grid renderer、baseline renderer、resolved-feature renderer、X/Y/reference overlay widgets。這些依賴只在建立 View 時注入一次。

## Render 流程

`render(frame)` 必須依序：

1. 清空 Canvas 並取得尺寸。
2. 計算 surface / finished reference / optional `extra_bounds` 的共同 viewport。
3. 建立並保存唯一 `CanvasTransform`。
4. 畫 grid、surface outline、baseline scene、finished boundary 與 W/H 尺寸。
5. 透過既有 `resolve_surface_features()` 解析 caller feature list，保存 resolved cache，再繪製。
6. 執行 `draw_extra` extension（Door indicator、indicator box 等仍由 Bridge 提供）。
7. 若有 error text，畫錯誤訊息。
8. 若 selected index 有效，畫十字基準、選取點並依 `reference_distances` 放置浮動 X/Y/reference widgets；否則隱藏 overlays。
9. 若有 `insert_label`，顯示插入模式提示。

## Hit-test / Mouse Coordinate

- `canvas_to_world()` 只能使用最近一次 render 建立的 transform；尚未 render 時回傳 `None`。
- `hit_test()` 只能使用最近一次 render 的 resolved cache，不得再次呼叫 `resolve_surface_features()`。
- tolerance 維持 `8 px / scale` 的既有語意。

這可避免 GUI 在 redraw 與 hit-test 各自解析一份 features，造成顯示與點擊命中不一致。

## Overlay 規則

原 `layout_axis_reference_overlay_rects()`、`resolved_canvas_rect()`、`hide_overlays()`、`place_reference_overlays()` 移入 View implementation。

浮動 widget 是 View adapter 的一部分，因此可直接呼叫 Tk widget 的 `place()/place_forget()/winfo_req*()`；但 View 不得建立或修改 feature/domain state。

## Bridge 保留責任

`gui.py` 仍負責：

- 建立 Tk widget。
- 建立 `Phase6HoleEditorSession`。
- 取得 `active_reference_guide()` 與 `reference_distances()`。
- Door enclosure/indicator 的額外 bounds 與額外繪製 callback。
- Canvas event → Session action / geometry command 的調度。
- messagebox、catalog、圓孔排列視窗、Confirm/Cancel。

Canvas event 改為：

```text
Tk event
  → canvas_view.canvas_to_world()/hit_test()
  → geometry command / HoleEditorSession
  → canvas_view.render(frame)
```

## Ownership Guard

`phase6_hole_editor_canvas_view.py`：

- 可以 import `tkinter` 與 `ae_engine.sheetmetal_features` 顯示／解析 helper。
- 不得 import `gui`、`manufacturing_api`、ProjectSession、SettingsService、DesignerWorkspace。
- 不得呼叫 feature list 的 append/remove/item assignment。

`gui.py::_open_unified_hole_editor()`：

- 不得再宣告 `transform_box`。
- 不得再定義 `hide_overlays`、`place_reference_overlays`、`resolved_canvas_rect`、`hit_index`。
- Canvas mouse callback 必須透過 `canvas_view` 做座標與 hit-test。

## 測試

### 純 View / Fake Canvas

1. render 建立 transform，world↔canvas 可逆。
2. hit-test 使用最近 resolved cache 並命中正確 feature。
3. selected overlay 在有效 selection 時顯示，無 selection 時 hide。
4. extra bounds 會納入 viewport。
5. View 不修改 feature list。
6. ownership import guard。

### 真 Tk

維持既有統一開孔 editor 回歸，並新增：

- 真 Canvas click 可透過新 View hit-test 選到既有孔。
- drag 後 Session feature 有更新，Cancel All 恢復原值。
- delete → Undo → Cancel All 仍完整成立。

## 成功條件

- `_open_unified_hole_editor()` 不再自行持有 Canvas transform / resolved hit-test cache / overlay placement。
- 統一開孔 editor 的交易與操作行為不變。
- 完整 suite 除既知 `/mnt/data/自訂.p6fold` 4 項外 0 failure。
- `config.ini` SHA256 不變。
