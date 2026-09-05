# Door Editor Indicator Box and Frame Guides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make each Door editor own its direct-indicator/indicator-box mode, keep the insert action reachable, move coordinate confirmation to the right, and render true enclosure-frame measurement guides using per-edge frame presence and configured gaps.

**Architecture:** Keep Door geometry canonical. Add a pure helper for enclosure reference offsets from `DoorFrameEdges`, `FW`, `T`, `gap_w`, and `gap_h`; both measurement math and editor rendering consume the helper. Extend per-door indicator state with an explicit mutually-exclusive mode (`none`, `indicator`, `indicator_box`) while preserving legacy `enabled` compatibility. GUI layout changes stay inside the unified hole editor.

**Tech Stack:** Python, Tkinter, pytest, ezdxf, existing sheetmetal geometry/features/drawing modules.

## Global Constraints

- Door GUI/internal geometry remains normal orientation; Door DXF mirrors only at export.
- End-cap head remains WYSIWYG after its one-time normalization.
- Multi-door cells retain independent feature/indicator state.
- `door_gap_w` and `door_gap_h` are configuration values, never hard-code `3.5` in new frame-reference logic.
- Missing frame edges omit only `FW + 2T`; gap still applies on that side.

---

### Task 1: Pure enclosure reference offsets

**Files:**
- Modify: `sheetmetal_features.py`
- Test: `tests/test_multi_door_layout.py`

**Interfaces:**
- Produces: `door_enclosure_reference_offsets(frame_edges, frame_width, thickness, gap_w, gap_h)` returning left/right/top/bottom offsets.
- Updates: `measure_door_indicator_position(...)` and `door_indicator_offset_for_position(...)` to accept `frame_edges`, `gap_w`, `gap_h`.

- [x] Write failing tests for complete four-edge and missing-right/missing-bottom cases.
- [x] Run focused tests and confirm RED.
- [x] Implement offsets and replace hard-coded `+3.5` measurement math.
- [x] Run focused tests and confirm GREEN.

### Task 2: Per-door indicator/indicator-box mode

**Files:**
- Modify: `gui.py`
- Modify: `ae.py` only if export adapter needs explicit per-cell indicator-hole parameters.
- Test: `tests/test_multi_door_gui.py`

**Interfaces:**
- Per-door state adds `mode: none|indicator|indicator_box` and preserves `enabled` as derived direct-indicator compatibility.
- `indicator_box` uses that door's layer/group values to derive its centered Door cutout.

- [x] Write failing tests showing two cells may independently select indicator-box and direct-indicator while each cell remains internally mutually exclusive.
- [x] Run focused tests and confirm RED.
- [x] Add radio-mode controls to the Door hole editor and commit state per cell.
- [x] Wire per-cell indicator-box opening into overview and multi-door DXF output.
- [x] Run focused tests and confirm GREEN.

### Task 3: Door editor layout fixes

**Files:**
- Modify: `gui.py`
- Test: `tests/test_multi_door_gui.py`

**Interfaces:**
- Left catalog area becomes scrollable or otherwise reserves a fixed bottom action bar so `插入` is always reachable.
- Coordinate-reference `確定` button lives on the right side of the floating coordinate panel.

- [x] Write failing widget-layout tests for reachable insert button and right-side confirm placement.
- [x] Run focused tests and confirm RED.
- [x] Restructure editor frames without changing feature editing behavior.
- [x] Run focused tests and confirm GREEN.

### Task 4: Enclosure-frame visualization in Door editor

**Files:**
- Modify: `gui.py`
- Test: `tests/test_multi_door_gui.py`

**Interfaces:**
- When `箱體定位距離` is enabled, editor draws an enclosure reference rectangle/edge guides based on per-side offsets and extends selected X/Y reference lines to those references.
- Uses cell `DoorFrameEdges`; no synthetic `FW+2T` on absent sides.

- [x] Write failing tests for guide bounds in four-edge and missing-right/bottom cells.
- [x] Run focused tests and confirm RED.
- [x] Render reference bounds and extend measurement guides.
- [x] Run focused tests and confirm GREEN.

### Task 5: Full regression and package

**Files:**
- Test: `tests/`
- Output: `/mnt/data/multi_door_layout_trial.zip`

- [x] Run `pytest -q tests`.
- [x] Run `python -m py_compile` over core modules.
- [x] Run a Tk/Xvfb smoke test opening a multi-door cell editor and checking mode/insert/reference widgets.
- [x] Package clean tree with formal tests only in `tests/`; temporary diagnostics in `tmp/`.
