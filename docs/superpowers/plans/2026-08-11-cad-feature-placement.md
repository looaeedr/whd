# CAD-style Feature Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Let head/tail users place, drag, re-anchor, dimension, and pattern holes directly on the finished-face preview without typing X/Y first.

**Architecture:** Add pure placement helpers to `sheetmetal_features.py`; `gui.py` converts Canvas events to world coordinates and delegates all placement math to those helpers. Existing `head_holes` / `tail_holes` dictionaries remain the persistence compatibility boundary, while authoritative placement during editing uses `Feature` definitions.

**Tech Stack:** Python 3, dataclasses, Tkinter Canvas, pytest, existing `sheetmetal_features.py` / `CanvasTransform`.

## Global Constraints

- Do not add tkinter or ezdxf dependencies to `sheetmetal_features.py`.
- Do not change finished-face -> unfolded mapping or DXF layer semantics.
- Preserve existing hole types: 圓形, 方形, 管孔, AS, VS.
- Existing `head_holes` / `tail_holes` dictionaries must load and export at identical absolute positions.
- Canvas pixels are presentation-only; all placement state is millimetre world-space.
- Phase 1 clamps feature centers only; no radius/half-size edge-clearance enforcement.
- No full sketch constraint solver.

---

### Task 1: Pure placement model and anchor selection

**Files:**
- Modify: `sheetmetal_features.py`
- Test: `test_sheetmetal_features.py`

**Interfaces:**
- Produces: `FeaturePlacement`, `PlacementGuideSet`, `choose_feature_anchor`, `placement_from_finished_point`, `feature_finished_point`, `reanchor_feature`, `move_feature_to_finished_point`, `build_feature_placement_guides`.

- [x] Write failing tests for center/corner anchor selection, round-trip placement, re-anchor preserving world center, move preserving feature shape/layer/type, and guide values.
- [x] Run targeted tests and verify RED because APIs are missing.
- [x] Implement minimal pure placement APIs using `_anchor_point()` and immutable dataclass replacement.
- [x] Run targeted tests and verify GREEN.

### Task 2: Pattern expansion and legacy compatibility

**Files:**
- Modify: `sheetmetal_features.py`
- Test: `test_sheetmetal_features.py`

**Interfaces:**
- Produces: `feature_to_legacy_hole`, `expand_linear_pattern`, `expand_grid_pattern`.

- [x] Write failing tests for horizontal/vertical linear patterns, grid patterns, negative pitch, and legacy hole round-trip absolute position.
- [x] Run targeted tests and verify RED.
- [x] Implement minimal pattern expansion and compatibility serializer.
- [x] Run targeted tests and verify GREEN.

### Task 3: CAD-style click placement, selection, drag and numeric anchor editing

**Files:**
- Modify: `gui.py:open_hole_editor`
- Test: `test_gui_structural_rendering.py`

**Interfaces:**
- Consumes: Task 1/2 placement APIs.
- Produces: editor-local `feature_list` authoritative state synchronized to legacy `hole_list` only through `feature_to_legacy_hole`.

- [x] Add source-level failing tests requiring placement helpers, drag bindings, Anchor combobox, and no GUI anchor-coordinate formulas.
- [x] Run targeted tests and verify RED.
- [x] On editor open convert legacy hole dictionaries to `feature_list`.
- [x] Change canvas click: hit-test selects; otherwise click on finished-face guide places selected type via `placement_from_finished_point`.
- [x] Add press/motion/release drag path using `move_feature_to_finished_point` and guide clamp.
- [x] Render placement guides for selected feature.
- [x] Add Anchor selector and X/Y offset fields; re-anchor with `reanchor_feature`, preserving absolute center.
- [x] Synchronize authoritative features back to `hole_list` after edits so existing preview/DXF paths remain unchanged.
- [x] Keep existing list selection/delete/clear and old coordinate controls as compatibility editing path.
- [x] Run targeted GUI/source tests and existing feature tests.

### Task 4: Pattern controls and regression verification

**Files:**
- Modify: `gui.py:open_hole_editor`
- Test: `test_gui_structural_rendering.py`, `test_ae_geometry_integration.py`

**Interfaces:**
- Consumes: `expand_linear_pattern`, `expand_grid_pattern`.

- [x] Add source-level failing tests that pattern controls call pure expansion helpers.
- [x] Add minimal Linear/Grid controls operating on the selected source feature and replacing/appending generated Feature definitions.
- [x] Run targeted tests.
- [x] Run full pytest suite.
- [x] Run `py_compile` for core modules.
- [x] Export representative head/tail with legacy and newly placed holes and re-read DXF; verify layer/type/count.
- [x] Audit `gui.py` for anchor geometry / pattern coordinate formulas and canvas-pixel persistence.
