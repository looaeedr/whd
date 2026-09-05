# Unified Hole Editor & Reference Positioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split Head/Tail and generic hole editors with one editor supporting nine-anchor reference lines, neighbor-based positioning, explicit insertion, process toggling, and large readable controls.

**Architecture:** Put reference/neighbor math in `sheetmetal_features.py`, independent from Tkinter. Make `gui.py` a single editor over `surface_features[part_key]`, with Head/Tail legacy sync adapters only at the boundary. Keep `FeatureSurface` as the legality authority and reuse the existing catalog/feature conversion pipeline.

**Tech Stack:** Python 3.11, Tkinter/ttk, Shapely, ezdxf, pytest.

## Global Constraints
- Only `基準檔/開孔/開孔.csv` and `基準檔/開孔/管孔尺寸清單.csv` feed the catalog.
- No Canvas pixel coordinates are persisted as manufacturing data.
- Unchecked custom hole means CUTTING; checked means BLIND_HOLE.
- User double-click toggle overrides process for an inserted feature, including DXF profiles.
- All feature footprints must stay fully inside FeatureSurface.
- No part-specific positioning math in GUI.

---

### Task 1: Pure nine-anchor reference model
**Files:**
- Modify: `sheetmetal_features.py`
- Test: `test_unified_hole_reference.py`

**Interfaces:**
- Produces: `ReferenceAnchor`, `feature_reference_point(feature, anchor, width, height)`, `reference_edge_directions(...)`, `find_reference_neighbor(...)`, `reference_distances(...)`, `move_feature_by_reference_distance(...)`.

- [ ] Write failing tests for all nine anchor points, center tie-break, neighbor perpendicular ranking, and edge/neighbor move round-trips.
- [ ] Run tests and verify RED.
- [ ] Implement minimal pure geometry helpers.
- [ ] Run tests and verify GREEN.

### Task 2: Process override for inserted features
**Files:**
- Modify: `sheetmetal_features.py`, `sheetmetal_drawing.py`
- Test: `test_unified_hole_process_toggle.py`

**Interfaces:**
- Produces: `feature_with_process(feature, process)` that applies CUTTING or BLIND_HOLE to circle/rect/profile inserted features.

- [ ] Write failing tests including multi-layer profile override.
- [ ] Verify RED.
- [ ] Implement process override and primitive emission using the override.
- [ ] Verify GREEN.

### Task 3: One unified editor for every panel
**Files:**
- Modify: `gui.py`
- Test: `test_unified_hole_editor_contract.py`

**Interfaces:**
- Consumes Tasks 1-2.
- Produces: one `_open_unified_hole_editor(part_key, ...)`; `open_hole_editor()` becomes Head/Tail compatibility routing only or is removed.

- [ ] Write failing source/behavior tests for double-click entry on all supported canvases, no right-click-open, persistent catalog selection, Insert button, created-hole list double-click process toggle, nine-anchor menu/dropdown, large input font.
- [ ] Verify RED.
- [ ] Refactor generic editor into unified editor and route Head/Tail through it with legacy sync callbacks.
- [ ] Verify GREEN.

### Task 4: Reference UI interaction
**Files:**
- Modify: `gui.py`
- Test: `test_unified_hole_editor_reference_ui.py`

**Interfaces:**
- Uses pure reference helpers from Task 1.

- [ ] Write failing tests for dynamic labels, right-click anchor menu, crosshair visibility, edge/neighbor field synchronization, and boundary rejection.
- [ ] Verify RED.
- [ ] Implement interaction and rendering.
- [ ] Verify GREEN.

### Task 5: Regression and real GUI/DXF verification
**Files:**
- Update relevant tests only where old editor behavior is intentionally replaced.

- [ ] Run full pytest suite.
- [ ] Run `py_compile` on core modules.
- [ ] Initialize Tk GUI and call preview paths.
- [ ] Exercise Head/Tail legacy sync and Door/Base/Box/Indicator semantic feature storage.
- [ ] Export CUTTING and BLIND_HOLE examples and re-open DXF to verify layers.
