# GUI Hole / Feature Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make GUI hole preview and DXF output consume one authoritative resolved feature geometry path.

**Architecture:** Add a pure `sheetmetal_features.py` model/resolver layer between design intent and render/serialization. End-cap user holes, door indicator/nameplate patterns, and baseline-mapped circles are normalized into resolved features; GUI only maps resolved world coordinates to Canvas pixels, and `ae.py` only serializes resolved features.

**Tech Stack:** Python 3.11+, dataclasses, pytest, tkinter at GUI boundary, ezdxf at DXF boundary; no ezdxf/tkinter dependency in `sheetmetal_features.py`.

## Global Constraints

- Preserve current end-cap X/Y input meaning in finished-face coordinates.
- `sheetmetal_features.py` must not import `tkinter` or `ezdxf`.
- Structural assembly relief stays in `sheetmetal_geometry.py`.
- CAM kerf / over-cut / slit compensation remains out of this feature engine.
- GUI pixels are presentation only and are never persisted as feature coordinates.
- Existing hole types and user workflows remain available.

---

### Task 1: Pure feature model and CanvasTransform

**Files:**
- Create: `sheetmetal_features.py`
- Create: `test_sheetmetal_features.py`

**Interfaces:**
- Produces: `FeatureAnchor`, `CircleFeature`, `RectFeature`, `ResolvedCircle`, `ResolvedRect`, `CanvasTransform`
- Produces: `CanvasTransform.world_to_canvas(Vec2)` and `canvas_to_world(x, y)`

- [x] Write tests for feature dataclasses, layer semantics, and world/canvas round-trip.
- [x] Run the tests and confirm RED due to missing module/classes.
- [x] Implement the minimal pure model and transform.
- [x] Run the tests and confirm GREEN.

### Task 2: End-cap finished-face resolver

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `test_sheetmetal_features.py`

**Interfaces:**
- Produces: `EndCapFeatureContext`
- Produces: `legacy_hole_to_feature(hole)`
- Produces: `resolve_endcap_features(context, features)`

- [x] Write regression tests matching the current `_add_user_holes_to_dxf()` linear mapping for T=2 and T=1.5.
- [x] Add asymmetric left/right fold coverage.
- [x] Confirm RED.
- [x] Implement the finished-face → unfolded mapping once in the feature resolver.
- [x] Confirm GREEN.

### Task 3: Make ae.py a resolved-feature serializer for end-cap holes

**Files:**
- Modify: `ae.py`
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Consumes: `resolve_endcap_features(...)`
- Produces: `_add_resolved_features_to_dxf(msp, resolved_features)`

- [x] Write integration tests for circle, pipe MARKING, AS/VS CUTTING, and rectangle serialization.
- [x] Confirm RED against the new serializer API.
- [x] Refactor `_add_user_holes_to_dxf()` to convert legacy dictionaries, resolve once, and serialize resolved features.
- [x] Confirm GREEN.

### Task 4: End-cap hole editor uses shared transform/resolution

**Files:**
- Modify: `gui.py`
- Modify: `test_sheetmetal_features.py`

**Interfaces:**
- Consumes: `CanvasTransform`, `legacy_hole_to_feature`, `resolve_endcap_features`

- [x] Add transform tests that reproduce the hole-editor scale/origin behavior.
- [x] Confirm RED if helper behavior is missing.
- [x] Replace local `c2p` / reverse-coordinate formulas in `open_hole_editor()` with `CanvasTransform`.
- [x] Render/hit-test holes through feature conversion instead of duplicating shape semantics.
- [x] Confirm GREEN and compile GUI.

### Task 5: Normalize baseline mapped circles

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `ae.py`
- Modify: `test_sheetmetal_features.py`

**Interfaces:**
- Produces: `resolved_circles_from_baseline(mapped_circles)`

- [x] Write tests preserving mapped center/radius/layer exactly.
- [x] Confirm RED.
- [x] Add normalization without changing baseline mapping math.
- [x] Use normalized results at DXF/GUI consumption boundaries where practical.
- [x] Confirm GREEN.

### Task 6: Door indicator/nameplate feature resolver

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `ae.py`
- Modify: `gui.py`
- Modify: `test_sheetmetal_features.py`
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Produces: `DoorIndicatorContext`
- Produces: `resolve_door_indicator_features(context, layer_groups, offset)`

- [x] Write pure regressions for one-group and multi-group layouts including CUTTING and MARKING features.
- [x] Write offset regression proving a single offset changes both preview/export geometry.
- [x] Confirm RED.
- [x] Move repeated-hole placement formulas into the resolver.
- [x] Make direct door DXF use resolved features.
- [x] Make door GUI preview draw the same resolved features.
- [x] Confirm GREEN.

### Task 7: Full verification and duplicate-formula audit

**Files:**
- Modify only if verification exposes defects.

- [x] Run `pytest -q`.
- [x] Run `python -m py_compile ae.py gui.py sheetmetal_geometry.py sheetmetal_features.py`.
- [x] Search GUI/DXF code for duplicate door indicator placement formulas (`133.5`, `191.0`, `171.0`, `90.0`) and keep placement authority in `sheetmetal_features.py`.
- [x] Confirm end-cap hole mapping formula exists only in the resolver.
- [x] Produce representative DXFs and re-read them when ezdxf is available.
