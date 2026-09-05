# Door Layout Visual Remainder and Export Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace Door per-cell preview controls with an all-cells cabinet-oriented layout editor with automatic width/height remainder completion, and permanently mirror Door geometry left-right only at DXF export.

**Architecture:** Keep Door canonical geometry and GUI coordinates unchanged. Add pure partition/remainder helpers next to Door layout derivation, let `gui.py` own only Tk state and whole-layout visualization, and add a reusable horizontal DrawingScene transform used only by Door exporters immediately before `_save_scene_dxf`.

**Tech Stack:** Python 3, Tkinter, pytest, ezdxf, existing DrawingScene primitives.

## Global Constraints

- Global W/H/D semantics remain unchanged.
- Door FourSideFlange topology remains unchanged.
- Widths are horizontal; heights are vertical; all layout cells remain visible.
- The current generated remainder becomes fixed when edited, and a new positive remainder is appended.
- Zero/negative automatic remainder cells are never created; oversubscription is reported as invalid.
- Door GUI/canonical geometry is not mirrored.
- All Door DXF exports, single and multi-door, are horizontally mirrored exactly once at the final export boundary.
- Non-Door exporters are unchanged.
- Formal tests live in `tests/`; one-off/manual artifacts live in `tmp/`.

---

### Task 1: Pure partition remainder model

**Files:**
- Modify: `sheetmetal_part_adapters.py`
- Test: `tests/test_multi_door_layout.py`

**Interfaces:**
- Produces: `complete_partition(fixed_values, total)` returning `(completed_values, remainder_value, is_valid, excess)` with only positive generated remainders.
- Produces: pure behavior used by GUI width and per-column height state.

- [x] Write failing tests for `400 -> 400,600`, editing the auto 600 to fixed 400 -> `400,400,200`, deletion/recompute, exact fill, and oversubscription.
- [x] Run the targeted tests and confirm RED because the helper does not exist.
- [x] Implement the smallest pure helper satisfying the tests.
- [x] Run targeted tests and confirm GREEN.

### Task 2: Door editor automatic remainder state

**Files:**
- Modify: `gui.py`
- Test: `tests/test_multi_door_gui.py`

**Interfaces:**
- Door column model stores fixed/user values separately from one generated width/height remainder marker.
- Existing `get_door_layout_columns()` still returns numeric `(width, heights)` data compatible with `validate_door_layout_dimensions`.

- [x] Write failing Tk tests for auto width completion, promotion of edited auto width, independent per-column height completion, delete/recompute, and invalid oversubscription status.
- [x] Run targeted GUI tests under Xvfb and confirm RED.
- [x] Implement state synchronization and trace/commit behavior without manufacturing formulas in `gui.py`.
- [x] Run targeted GUI tests and confirm GREEN.

### Task 3: Whole-layout Door visualization

**Files:**
- Modify: `gui.py`
- Test: `tests/test_multi_door_gui.py`

**Interfaces:**
- `draw_door()` in multi-door mode draws the complete cabinet subdivision, not one unfolded Door.
- Width inputs/labels are horizontally associated with columns; height controls are vertically associated with segments.
- Clicking a cell updates selection for feature ownership without hiding other cells.

- [x] Write failing tests proving there are no `預覽` radiobuttons, all cells are represented on the Door canvas, and selecting one cell preserves all cell rectangles.
- [x] Run targeted GUI tests and confirm RED.
- [x] Rebuild Door layout controls and multi-door canvas drawing to match cabinet orientation.
- [x] Keep single-door `draw_door()` behavior unchanged.
- [x] Run targeted GUI tests and confirm GREEN.

### Task 4: Export-only horizontal scene transform

**Files:**
- Modify: `sheetmetal_drawing.py`
- Modify: `ae.py`
- Test: `tests/test_multi_door_layout.py`

**Interfaces:**
- Produces: `mirror_drawing_scene_x(scene, min_x, max_x)` (or equivalent scene-bounds convenience) transforming Polyline, Line, Circle, and Text positions while preserving layers/styles.
- `export_door_dxf()` and `export_stretched_door_dxf()` apply the transform exactly once immediately before `_save_scene_dxf()`.

- [x] Write failing tests that compare canonical Door scene coordinates with DXF output and prove x reflection for CUTTING, BEND, circles/features, DATUM/MARKING/CHECK while y is unchanged.
- [x] Write a failing regression proving non-Door export remains unmirrored.
- [x] Run targeted tests and confirm RED.
- [x] Implement the horizontal DrawingScene transform.
- [x] Apply it only in both Door exporter paths.
- [x] Run targeted tests and confirm GREEN.

### Task 5: Full regression and packaging

**Files:**
- Update: `README_MULTI_DOOR_TRIAL.md`
- Generate only manual artifacts under: `tmp/`

**Interfaces:**
- `pytest tests/` is the authoritative regression run.

- [x] Run `pytest tests/` and require all tests PASS.
- [x] Run `python -m py_compile` on the six project modules.
- [x] Under Xvfb, instantiate GUI and exercise the 1000→400→600→edit400→200 workflow for both width and height.
- [x] Export single Door and multi-door examples, read them back with ezdxf, and verify the horizontal mirror numerically.
- [x] Re-run the existing head/end-cap mirror regression.
- [x] Put generated DXFs/manual inspection files only under `tmp/`.
- [x] Rebuild `/mnt/data/multi_door_layout_trial.zip`.
