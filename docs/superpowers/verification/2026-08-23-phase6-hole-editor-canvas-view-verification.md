# Phase6 統一開孔編輯器 Canvas View 驗證報告

## 範圍

本輪新增 `Phase6HoleEditorCanvasView`，只收斂統一開孔編輯器的 Canvas transform、resolved cache、hit-test、selected crosshair 與浮動 reference overlay。HoleEditorSession、sheet-metal 幾何與 manufacturing owner 不變。

## TDD 證據

### RED

新增 `tests/test_phase6_hole_editor_canvas_view.py` 後，首次執行得到 4 failure：

- module `phase6_hole_editor_canvas_view` 不存在。
- `gui.py` 仍定義 `hide_overlays / place_reference_overlays / resolved_canvas_rect / hit_index`。

### GREEN

- View 純責任：3 passed。
- View + HoleEditorSession ownership／真 Tk：21 passed。
- 關聯 Project/FinalScene/renderer/linked profile：104 passed、2 skipped、4 deselected。

## 行為驗證

真 Tk 測試實際執行：

```text
開啟統一開孔 editor
→ Canvas 點中既有孔
→ B1 drag 移動孔位
→ Session feature 確實變更
→ 取消全部
→ 原始 feature 完整恢復
```

既有 delete → Undo → Cancel All 回歸也持續通過。

## Ownership 驗證

`gui.py::_open_unified_hole_editor()`：

- 不再有 `transform_box`。
- 不再定義 `hide_overlays / place_reference_overlays / resolved_canvas_rect / hit_index`。
- 不再引用 `resolve_surface_features / hit_test_resolved_features / CanvasTransform`。

`phase6_hole_editor_canvas_view.py`：

- 不 import `gui`。
- 不 import `ae_engine.manufacturing_api`。
- 不依賴 ProjectSession、SettingsService 或 DesignerWorkspace。
- feature mutation 仍由 `Phase6HoleEditorSession` 負責。

## 完整回歸

原始完整 suite：

`354 passed, 2 skipped, 4 failed`

4 個 failure 全部仍為既知外部 fixture `/mnt/data/自訂.p6fold` 不存在：

1. `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
2. `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
3. `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
4. `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

明確排除以上 4 項：

`354 passed, 2 skipped, 4 deselected, 0 failure`

## 結構結果

- `_open_unified_hole_editor()`：1431 行 → 1333 行。
- 巢狀函式：61 → 57。
- 新 `phase6_hole_editor_canvas_view.py`：Canvas/Tk View 深模組。

本輪的成功指標不是單純減行，而是 redraw 與 hit-test 共用同一 transform/resolved cache，GUI 不再擁有第二套 Canvas 顯示狀態。

## config.ini

未修改。最終 SHA256 必須維持：

`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`
