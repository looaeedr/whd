# 目前狀態補充：3D 獨立入口調整

2026-08-18 後續 UI 決定：保留平鋪板件按鈕與主工作區開孔；取消內嵌 `3D折彎` workspace mode，恢復左側 `開啟折彎 / 3D 設計` 獨立 Toplevel 入口。以下內容保留為 FIX14 原始實作歷史。

# Unified Part Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Integrate Phase6 panel/corner editing, the original 3D fold designer, and the Phase6 hole editor into one live-synchronized main-window workspace.

**Architecture:** `gui.py` owns one shared workspace selection (`part`, `mode`) and embeds the existing Phase6 part panels plus a `Phase6FoldDesignerApp` host. `fold_designer_bridge.py` remains the adapter around the byte-identical original renderer and exposes live-change callbacks plus a flat part selector API. The existing Phase6 hole editor gains an embedded host option while retaining its existing modal entry path for compatibility.

**Tech Stack:** Python 3, tkinter/ttk, matplotlib, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-unified-part-workspace-design.md`

## Global Constraints
- Do not modify `fold_designer_original.py`.
- Do not modify any `ae_engine/` file.
- Preserve FIX13 outside-dimension and BEND-line conversions.
- Do not create a second hole data model.
- No manual Apply is required for 3D edits.
- Config and baseline DXF files are not package payload.

---

### Task 1: Flat shared part and mode controls
**Files:** `gui.py`, `tests/test_original_fold_designer_gui_integration.py`
- [x] Add failing tests proving the main window has flat part buttons (no part Combobox) and three mode buttons.
- [x] Verify RED.
- [x] Add shared `active_workspace_part`, `workspace_mode`, part-button refresh, and mode-switch helpers around the existing right-side notebook.
- [x] Verify GREEN.

### Task 2: Embedded original 3D fold designer
**Files:** `fold_designer_bridge.py`, `gui.py`, `tests/test_original_fold_designer_bridge.py`, `tests/test_original_fold_designer_gui_integration.py`
- [x] Add failing tests for an embeddable root host and live callback after fold edits.
- [x] Verify RED.
- [x] Add a no-window host adapter, hide the bridge's old part Combobox, expose `set_live_change_callback()` and external `activate_part()` synchronization.
- [x] Embed one designer instance in the main workspace and live-apply snapshots back to Phase6 with recursion/debounce guards.
- [x] Verify GREEN.

### Task 3: Embedded Phase6 hole editor mode
**Files:** `gui.py`, `tests/test_multi_door_gui.py`, `tests/test_original_fold_designer_gui_integration.py`
- [x] Add failing tests that `開孔` mode targets the shared active part and does not instantiate the prototype HolesUI editor.
- [x] Verify RED.
- [x] Refactor `_open_unified_hole_editor()` to optionally build inside a supplied host frame while preserving the current modal path.
- [x] Wire workspace `開孔` to recreate the embedded editor for the active part from `surface_features`.
- [x] Verify GREEN.

### Task 4: Live shared-state round trip and regressions
**Files:** `gui.py`, `fold_designer_bridge.py`, `tests/test_original_fold_designer_gui_integration.py`
- [x] Add failing tests for 3D edit -> immediate Phase6 vars -> Corner geometry/cache invalidation without explicit Apply.
- [x] Verify RED.
- [x] Flush/synchronize on live callback, part change, and mode change; avoid feedback loops.
- [x] Verify FIX13 W-2T/D-T UI and W-4T/D-3T engine spans remain intact.
- [x] Run complete test suites, py_compile, file hashes, and clean-install verification.


## API 盤點

現行 API 邊界與多門接入方式請參考 `docs/superpowers/CURRENT_API_INVENTORY_20260818.md`。
