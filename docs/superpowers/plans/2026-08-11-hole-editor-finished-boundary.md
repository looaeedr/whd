# Hole Editor Finished Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the unified hole editor use assembled/finished dimensions as its user-facing reference, support fast catalog double-click insertion, collision-free on-canvas reference controls, and full-screen editing.

**Architecture:** Keep `FeatureSurface` as the hard manufacturing containment boundary. Add an independent rectangular `RectGuide` used only for user-facing finished dimensions and edge-distance reference math. The GUI derives that guide from the existing authoritative part formulas, draws it as a dashed Finished Boundary, and passes it to pure reference-distance helpers; hole geometry/export stays unchanged.

**Tech Stack:** Python 3, Tkinter, Shapely, pytest.

## Global Constraints

- Blank/outline geometry and DXF export remain unchanged.
- Full feature footprint must remain inside `FeatureSurface` after every move/rotation.
- User-facing edge distance is measured from the finished/assembled reference guide, not the bend line or blank outline.
- Center anchor tie-break remains X→left and Y→bottom.
- Neighbor selection remains same-anchor, minimum perpendicular distance to the selected reference line first, along-axis distance second.
- Catalog items except `＋ 自訂圓孔` and `＋ 自訂方孔` enter insertion mode on double-click; the Insert button remains available.
- F11 toggles full-screen; the visible full-screen button performs the same action; Esc keeps the existing layered cancellation semantics.

---

### Task 1: Finished reference-frame math

**Files:**
- Modify: `sheetmetal_features.py`
- Test: `test_unified_hole_reference.py`

**Interfaces:**
- Consumes: existing `FeatureSurface`, `RectGuide`, `reference_distances`, `move_feature_by_reference_distance`.
- Produces: optional `reference_guide: RectGuide | None` argument on `reference_edge_directions`, `reference_distances`, and `move_feature_by_reference_distance`.

- [ ] **Step 1: Write failing tests** proving edge distances and inverse movement use a supplied `RectGuide`, while neighbor ranking and containment still use existing feature/surface rules.
- [ ] **Step 2: Run targeted tests and confirm RED** because the current functions do not accept `reference_guide`.
- [ ] **Step 3: Implement minimal guide-aware edge helpers**: rectangle edges come from `reference_guide`; no guide preserves current polygon-edge behavior.
- [ ] **Step 4: Run targeted tests and confirm GREEN**.

### Task 2: Part-specific finished/assembled guides

**Files:**
- Modify: `sheetmetal_part_adapters.py`
- Test: `test_sheetmetal_part_adapters.py`

**Interfaces:**
- Produces: `build_finished_reference_guide(part_key, result, *, finished_width, finished_height, thickness=0.0, left_fold=0.0, right_fold=0.0, top_fold=0.0, bottom_fold=0.0) -> RectGuide`.

- [ ] **Step 1: Write failing tests** for door, base plate, indicator box/door, box-body front face, and endcap assembled guide dimensions.
- [ ] **Step 2: Verify RED** because the helper is absent.
- [ ] **Step 3: Implement only formula-to-guide mapping**, centered/offset in unfolded world coordinates using existing topology/fold data.
- [ ] **Step 4: Verify GREEN**.

### Task 3: Unified editor interaction and layout

**Files:**
- Modify: `gui.py`
- Test: `test_hole_editor_overlay_contract.py`
- Test: `test_hole_catalog_gui_contract.py`

**Interfaces:**
- `_open_unified_hole_editor(..., reference_guide=None)` uses finished guide for dimensions/reference math.
- `catalog_list` double-click calls insertion mode only for non-custom catalog rows.
- `place_reference_overlays()` lays out four entry boxes outside the selected hole footprint and resolves pairwise collisions.

- [ ] **Step 1: Write failing source/behavior contract tests** for catalog double-click insertion, F11/full-screen button, dashed finished boundary, no-overlap layout helper, and passing `reference_guide` into distance/move calls.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Implement full-screen toggle** with a visible button, F11 binding, and normal geometry restore.
- [ ] **Step 4: Implement catalog double-click** that selects the row and enters insert mode unless it is a custom row.
- [ ] **Step 5: Replace fixed overlay offsets** with footprint-aware candidate placement and rectangle collision rejection/clamping.
- [ ] **Step 6: Draw Finished Boundary as dashed line and dimension it outside the shape**; retain the solid FeatureSurface outline and bends/geometry semantics.
- [ ] **Step 7: Use finished guide in edge-distance field refresh and editing**.
- [ ] **Step 8: Run targeted tests and confirm GREEN**.

### Task 4: Wire authoritative finished dimensions per part

**Files:**
- Modify: `gui.py`
- Test: `test_all_panel_hole_surface_contract.py`

**Interfaces:**
- `open_part_hole_editor()` and `open_hole_editor()` compute/pass the correct finished guide without changing feature containment surfaces.

- [ ] **Step 1: Write failing contracts** for each supported part passing `reference_guide`.
- [ ] **Step 2: Verify RED**.
- [ ] **Step 3: Wire door finished size, base plate finished top size, indicator box assembled size, indicator door finished size, box-body front assembled face, and endcap W×D reference guide**.
- [ ] **Step 4: Verify GREEN**.

### Task 5: Regression and live GUI verification

**Files:**
- Modify only if a real regression is found.

- [ ] **Step 1: Run `pytest -q`** and require zero failures.
- [ ] **Step 2: Run `python -m py_compile`** on core modules.
- [ ] **Step 3: Under Xvfb, initialize the app and open the editor**; verify F11 toggling, visible toolbar/footer, finished W/H dimension text, and overlay widgets stay outside a representative large hole.
- [ ] **Step 4: Package a fresh ZIP and patch against `whd-corner-hole-editor-cad-overlay.zip`**.

## Self-Review

- Spec coverage: double-click catalog insertion, non-overlapping overlay controls, full-screen, finished dimensions, dashed guide, edge-distance semantics, and no geometry/export regression are each assigned to a task.
- Placeholder scan: no TBD/TODO/"similar to" steps.
- Type consistency: all guide-aware APIs use `RectGuide | None`; GUI passes the same guide to display and movement math.
