# Hole Editor CAD Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the unified hole editor screen-safe and CAD-like: board dimensions on-canvas, reference inputs following the selected reference crosshair, immediate distance edits, visible rotation, per-hole confirm/cancel, whole-editor confirm/cancel, and Esc cancellation.

**Architecture:** Keep manufacturing geometry and FeatureSurface APIs unchanged. `gui.py` owns only Tk layout, transaction snapshots, and event wiring; all hole movement continues through `reference_distances()` and `move_feature_by_reference_distance()`. The editor mutates the existing feature list live for preview, but snapshots allow per-hole and whole-editor rollback.

**Tech Stack:** Python 3.11, Tkinter, existing sheetmetal feature/resolver APIs, pytest.

## Global Constraints
- Every hole footprint remains fully inside its FeatureSurface.
- All part types continue using `_open_unified_hole_editor()`.
- No new manufacturing-coordinate formulas in GUI.
- No `套用` buttons for reference distances.
- `Esc` cancels insertion first, then current reference edit, then the whole editor.

---

### Task 1: Screen-safe editor shell
**Files:** Modify `gui.py`; Test `test_hole_editor_overlay_contract.py`
- [ ] Add failing source contract for adaptive screen geometry, no fixed 1320x780, and fixed whole-editor confirm/cancel controls.
- [ ] Run targeted test and confirm RED.
- [ ] Implement adaptive geometry and two-column layout.
- [ ] Run targeted test and confirm GREEN.

### Task 2: On-canvas board dimensions and reference overlay
**Files:** Modify `gui.py`; Test `test_hole_editor_overlay_contract.py`
- [ ] Add failing contract for W/H dimension labels and canvas overlay reference controls.
- [ ] Run targeted test and confirm RED.
- [ ] Draw board W/H dimensions and position reference Entry widgets around the selected crosshair.
- [ ] Add reference-anchor selector and per-hole 確定/取消 beside the crosshair.
- [ ] Run targeted test and confirm GREEN.

### Task 3: Immediate edits, rotation, and transactional cancel
**Files:** Modify `gui.py`; Test `test_hole_editor_overlay_contract.py`
- [ ] Add failing contracts for no `套用`, immediate Return/FocusOut update, visible rotation control, per-hole snapshot restore, editor snapshot restore, and Escape state order.
- [ ] Run targeted test and confirm RED.
- [ ] Implement immediate edit callbacks through `move_feature_by_reference_distance()` only.
- [ ] Implement selected-hole rotation with FeatureSurface validation.
- [ ] Implement per-hole confirm/cancel and whole-editor confirm/cancel snapshots.
- [ ] Implement Escape: cancel insert → cancel current hole edit → cancel whole editor.
- [ ] Run targeted test and confirm GREEN.

### Task 4: Regression verification
**Files:** Existing test suite
- [ ] Run full pytest suite.
- [ ] Run py_compile on core modules.
- [ ] Initialize GUI in virtual display and open unified editor.
- [ ] Verify no old right-side Apply controls remain.
