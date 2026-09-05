# GUI Interaction Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize remaining GUI feature interaction and mounting-hole coordinate rules in `sheetmetal_features.py` so GUI and DXF consume the same resolved geometry.

**Architecture:** Extend the existing pure feature engine with layout, bounds, hit-test, clamp, and dimension helpers. Keep `gui.py` as Canvas/event orchestration and `ae.py` as DXF serialization only.

**Tech Stack:** Python 3.11+, dataclasses, pytest, existing `sheetmetal_geometry.Vec2`, Tkinter only in GUI boundary, ezdxf only in DXF boundary.

## Global Constraints

- Preserve current Vault-type manufacturing geometry and user workflow.
- `sheetmetal_features.py` must not import tkinter or ezdxf.
- Canvas pixels are not manufacturing coordinates.
- Existing end-cap hole dictionaries remain compatible.
- No new CAM/kerf/over-cut behavior.

---

### Task 1: Door indicator resolved interaction layout

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `test_sheetmetal_features.py`

**Interfaces:**
- Produce: `WorldBounds`
- Produce: `DoorIndicatorLayout`
- Produce: `resolve_door_indicator_layout(context, layer_groups, offset)`
- Produce: layout `hit_test()`, `clamp_offset()`, dimension measurement and inverse-offset helpers.

- [ ] Write failing tests for interaction bounds, hit-test, clamp, X/Y dimension measurement, and reverse offset.
- [ ] Run tests and verify RED.
- [ ] Implement minimal pure layout helpers using the existing feature resolver.
- [ ] Run tests and verify GREEN.

### Task 2: End-cap feature world-space hit-test

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `test_sheetmetal_features.py`
- Modify: `gui.py`

**Interfaces:**
- Produce: `resolve_features_in_finished_face(width, height, features)`
- Produce: `hit_test_resolved_features(point, features, tolerance)`

- [ ] Write failing circle and rectangle hit-test tests.
- [ ] Verify RED.
- [ ] Implement finished-face resolution and extent-aware hit-test.
- [ ] Refactor `open_hole_editor()` to use world hit-test.
- [ ] Verify GREEN.

### Task 3: Base-plate mounting-hole resolver

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `test_sheetmetal_features.py`
- Modify: `gui.py`
- Modify: `ae.py`

**Interfaces:**
- Produce: `resolve_base_plate_mounting_holes(width, height, bend, edge_clearance=15.0, diameter=10.0)`

- [ ] Write failing exact-center test.
- [ ] Verify RED.
- [ ] Implement resolver.
- [ ] Replace GUI and DXF duplicated formulas with resolved circles.
- [ ] Verify GREEN.

### Task 4: Refactor door GUI interaction and dimensions

**Files:**
- Modify: `gui.py`
- Modify: `test_gui_structural_rendering.py`

**Interfaces:**
- Consume `DoorIndicatorLayout` only for interaction geometry.

- [ ] Write source-audit tests proving legacy indicator interaction formulas are absent from GUI handlers.
- [ ] Verify RED.
- [ ] Refactor press/drag/double-click/dimension rendering to use layout helpers and `CanvasTransform`.
- [ ] Verify GREEN.

### Task 5: Full verification and hard-code audit

**Files:**
- Modify only if regressions are found.

- [ ] Run `pytest -q`.
- [ ] Run `python -m py_compile ae.py gui.py sheetmetal_geometry.py sheetmetal_features.py sheetmetal_part_adapters.py`.
- [ ] Generate/read representative Door, End-cap, Base-plate DXFs when ezdxf is available.
- [ ] Search GUI for `offset_x_phys`, `offset_y_phys`, `W_active`, `H_active`, `cx_min = 191`, and base-plate `bend + 15.0` structural/feature duplication.
