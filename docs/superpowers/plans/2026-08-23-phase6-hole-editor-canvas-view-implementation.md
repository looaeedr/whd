# Phase6 統一開孔編輯器 Canvas View 實作計畫

> **給代理執行者：** 必須使用 superpowers:executing-plans 或等效逐任務流程執行；每個行為先 RED 再 GREEN。

**目標：** 新增 `Phase6HoleEditorCanvasView`，把統一開孔編輯器的 Canvas transform、resolved cache、hit-test、selected overlay 與 redraw 從 `gui.py` 收斂到單一 View module。

**架構：** `Phase6HoleEditorSession` 繼續唯一擁有 feature transaction；`Phase6HoleEditorCanvasView` 唯一擁有 Canvas 顯示狀態；`gui.py` 只保留 Tk 組裝、domain adapter 與 event orchestration。Door/Indicator manufacturing preview 由 `draw_extra` callback 注入，不得讓 View import manufacturing owner。

**技術棧：** Python、Tkinter、pytest、Xvfb、既有 `ae_engine.sheetmetal_features`。

**規格：** `docs/superpowers/specs/2026-08-23-phase6-hole-editor-canvas-view-design.md`

## 全域限制

- 不改 `config.ini`。
- 不修改 `Phase6HoleEditorSession` transaction 語意。
- 不重寫任何 sheet-metal 幾何公式。
- 不讓新 View import `gui`、`manufacturing_api`、ProjectSession、SettingsService、DesignerWorkspace。
- Tk 測試一律使用 `xvfb-run -a python -m pytest`。

---

### 任務 1：建立純 Canvas View seam

**檔案：**
- 新增：`phase6_hole_editor_canvas_view.py`
- 新增：`tests/test_phase6_hole_editor_canvas_view.py`

**介面：**
- 產出 `HoleEditorCanvasFrame`
- 產出 `Phase6HoleEditorCanvasView.render()`
- 產出 `canvas_to_world()`、`hit_test()`、`hide_overlays()`

- [x] **步驟 1：寫 RED**

建立 FakeCanvas / FakeWidget，驗證 render 會建立 transform、hit-test 命中 resolved feature、無 selection 時 overlay 會 hide。

- [x] **步驟 2：執行 RED**

```bash
python -m pytest -q tests/test_phase6_hole_editor_canvas_view.py
```

預期：因 module 尚不存在失敗。

- [x] **步驟 3：最小 GREEN**

實作 frame、viewport transform、surface/finished boundary、resolved feature cache、selected crosshair、overlay placement、hit-test。

- [x] **步驟 4：執行 GREEN**

```bash
python -m pytest -q tests/test_phase6_hole_editor_canvas_view.py
```

預期：0 failure。

---

### 任務 2：Bridge/Tk Editor 接入 View

**檔案：**
- 修改：`gui.py`
- 修改：`tests/test_phase6_hole_editor_session.py`
- 修改：`tests/test_phase6_hole_editor_canvas_view.py`

**介面：**
- `_open_unified_hole_editor()` 建立一個 `Phase6HoleEditorCanvasView`
- `redraw()` 只組 `HoleEditorCanvasFrame` + extra callback 後呼叫 `view.render()`
- mouse events 只透過 `view.canvas_to_world()` / `view.hit_test()`

- [x] **步驟 1：寫 ownership RED**

AST 驗證 editor method 不得再定義 `transform_box`、`hide_overlays`、`place_reference_overlays`、`resolved_canvas_rect`、`hit_index`。

- [x] **步驟 2：執行 RED**

```bash
python -m pytest -q tests/test_phase6_hole_editor_canvas_view.py -k ownership
```

預期：現有 `gui.py` 仍擁有這些實作，因此失敗。

- [x] **步驟 3：最小 GREEN**

把 View implementation 移出 method；Door enclosure/indicator 仍由 Bridge 計算 extra bounds 並用 `draw_extra` callback 繪製。

- [x] **步驟 4：真 Tk 回歸**

新增 Canvas click/drag 測試；既有 delete→Undo→Cancel All 測試不得修改產品語意。

```bash
xvfb-run -a python -m pytest -q tests/test_phase6_hole_editor_canvas_view.py tests/test_phase6_hole_editor_session.py
```

預期：0 failure。

---

### 任務 3：Ownership 與相依性收斂

**檔案：**
- 修改：`tests/test_phase6_hole_editor_canvas_view.py`
- 修改：`gui.py`

- [x] **步驟 1：新增 ownership guard**

AST 驗證新 View 不 import manufacturing/project/settings/workspace owner，且不 mutate features；GUI editor 不重新 resolve hit-test geometry。

- [x] **步驟 2：執行聚焦回歸**

```bash
xvfb-run -a python -m pytest -q \
  tests/test_phase6_hole_editor_canvas_view.py \
  tests/test_phase6_hole_editor_session.py \
  tests/test_phase6_final_scene_view_ownership.py
```

預期：0 failure。

---

### 任務 4：完整資料鏈回歸與文件

**檔案：**
- 修改：`docs/superpowers/README.md`
- 新增：`docs/superpowers/verification/2026-08-23-phase6-hole-editor-canvas-view-verification.md`
- 修改：`使用說明書.md`
- 修改：`修改日誌/20260823.md`
- 修改：`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- 修改：`DELIVERY_README.md`

- [x] **步驟 1：執行語法驗證**

```bash
python -m py_compile gui.py phase6_hole_editor_canvas_view.py phase6_hole_editor_session.py
```

- [x] **步驟 2：執行原始完整 suite**

```bash
xvfb-run -a python -m pytest -q
```

預期：只允許既知 `/mnt/data/自訂.p6fold` 4 項失敗。

- [x] **步驟 3：排除既知外部 fixture 後跑 0-failure suite**

使用四個既知 node id `--deselect`，預期 0 failure。

- [x] **步驟 4：確認 `config.ini` SHA256**

必須維持：

`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`

- [x] **步驟 5：同步繁中文件並封 FULL/UPDATE**

FULL／UPDATE 必須使用相同 Asia/Taipei `YYYYMMDD_HHMMSS`；UPDATE 不得包含 `config.ini`。
