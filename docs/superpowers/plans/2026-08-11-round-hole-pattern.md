# Round Hole Pattern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated circular-hole arrangement workflow with separate pipe catalog visibility, synchronized center/gap distances, fill/refill, circular alignment, and last-confirm-wins conflict handling.

**Architecture:** Put circle-spacing and pattern-generation rules in pure helpers inside `sheetmetal_features.py`; keep `FeatureSurface` as the sole legality boundary. `gui.py` only renders the two catalogs, opens the round-hole settings window, previews pure results, and commits/cancels transactional edits.

**Tech Stack:** Python, Tkinter, Shapely, pytest.

## Global Constraints
- Main positioning remains based on the existing nine reference anchors and Finished Boundary reference guide.
- `一般開孔` comes from `開孔.csv`; `管孔清單` comes from `管孔尺寸清單.csv`.
- Center distance and gap are both visible; one is the driver and the other is derived.
- `center_distance = gap + r1 + r2` for circular neighbors.
- Fill preserves the selected circle as the seed; Refill may reposition the run.
- Every generated feature must pass existing FeatureSurface containment.
- Last pressed Confirm button wins when reference positioning and round arrangement conflict.

---

### Task 1: Pure circular spacing helpers
**Files:**
- Modify: `sheetmetal_features.py`
- Test: `tests/test_round_hole_pattern.py`

**Interfaces:**
- Produces: `circle_center_distance_from_gap(gap, diameter_a, diameter_b) -> float`
- Produces: `circle_gap_from_center_distance(center_distance, diameter_a, diameter_b) -> float`
- Produces: `circle_alignment_coordinate(feature, alignment) -> float`

- [ ] Write failing tests for equal/mixed diameters and center/top/bottom alignment.
- [ ] Run `pytest tests/test_round_hole_pattern.py -q` and verify RED.
- [ ] Implement minimal pure helpers.
- [ ] Re-run targeted tests and verify GREEN.

### Task 2: Fill/refill pattern generation
**Files:**
- Modify: `sheetmetal_features.py`
- Test: `tests/test_round_hole_pattern.py`

**Interfaces:**
- Produces: `generate_round_fill(seed, surface, *, direction, driver, value, alignment, neighbors) -> tuple[HoleFeature, ...]`
- Produces: `generate_round_refill(seed, surface, *, direction, driver, value, alignment, neighbors) -> tuple[HoleFeature, ...]`

- [ ] Add failing tests for left/right/up/down/both-horizontal/both-vertical, edge stopping, and refill repositioning.
- [ ] Verify RED.
- [ ] Implement minimal generators using feature footprints and `FeatureSurface.contains_feature`.
- [ ] Verify GREEN.

### Task 3: Separate visible catalogs
**Files:**
- Modify: `gui.py`
- Test: `tests/test_round_hole_pattern_gui.py`

**Interfaces:**
- Consumes existing catalog entries with source metadata.
- Produces separate `一般開孔` and `管孔清單` Listboxes while retaining custom controls and double-click insertion.

- [ ] Add failing GUI/source tests for both list headings and pipe entries appearing in the pipe list.
- [ ] Verify RED.
- [ ] Implement split list presentation and shared insertion callbacks.
- [ ] Verify GREEN.

### Task 4: Round-hole settings UI and synchronized values
**Files:**
- Modify: `gui.py`
- Test: `tests/test_round_hole_pattern_gui.py`

**Interfaces:**
- Produces `_open_round_hole_settings(...)` for circular features only.
- Uses Task 1 spacing helpers.

- [ ] Add failing tests for all six directions, both visible value fields, driver selection, alignment options, Fill/Refill, Confirm/Cancel.
- [ ] Verify RED.
- [ ] Implement the transactional round settings window.
- [ ] Verify GREEN.

### Task 5: Conflict precedence and main overlay cleanup
**Files:**
- Modify: `gui.py`
- Test: `tests/test_round_hole_pattern_gui.py`

**Interfaces:**
- Main reference Confirm commits current reference geometry and refreshes round-window values.
- Round Confirm commits pattern geometry and refreshes reference overlay values.

- [ ] Add failing tests that last Confirm wins and Cancel restores workflow-entry state.
- [ ] Add failing test that X/Y edge inputs are grouped, use smaller font, and floating boxes avoid feature bbox/one another.
- [ ] Verify RED.
- [ ] Implement commit epochs/state snapshots and overlay layout adjustment.
- [ ] Verify GREEN.

### Task 6: Full verification
**Files:**
- Test all project tests.

- [ ] Run `pytest -q` and require zero failures.
- [ ] Run `python -m py_compile` for core modules.
- [ ] Open unified editor under Xvfb, verify both catalog panes and round settings window, and verify F11 still works.
- [ ] Package full ZIP and patch relative to `whd-corner-hole-editor-finished-boundary.zip`.
