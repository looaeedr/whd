# Shared Final Part Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make 2D/corner/opening preview and Phase6 3D consume the same authoritative `PartRenderData` generated from one canonical GUI PartSpec path.

**Architecture:** GUI owns canonical state→PartSpec conversion and a bounded `PartRenderData` cache. Both committed preview and Fold Designer draft render requests go through this boundary; 3D only consumes `scene` and `material`. Door 2D drawing switches its actual CUTTING/BEND/MARKING geometry to the same final scene.

**Tech Stack:** Python, Tkinter, Shapely, Matplotlib, pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-shared-final-part-geometry-design.md`

## Global Constraints
- Do not change manufacturing dimensions, CornerType formulas or baseline files.
- `fold_designer_original.py` must remain byte-identical.
- 3D must not parse baseline, classify holes or calculate CornerType geometry.
- Draft Fold Designer edits must still update live 3D before transaction confirm.
- Cache must be invalidated on existing settings/feature/corner mutations.

---

### Task 1: Lock the canonical render boundary

**Files:**
- Modify: `tests/test_phase6_3d_single_source_renderer.py`
- Modify: `gui.py`

**Interfaces:**
- Produces: `BoxCalculatorGUI._fold_designer_part_spec_from_payload(part_key, payload)`
- Produces: `BoxCalculatorGUI._authoritative_render_data(spec, context)`
- Consumes: existing `_box_body_part_spec`, `_end_cap_part_spec`, `_single_door_part_spec`, `_door_layout_part_spec` semantics.

- [x] Write a source-guard test asserting `_query_fold_designer_render_data` contains no direct `DoorPartSpec(` / `BoxBodyPartSpec(` / `EndCapPartSpec(` / `BasePlatePartSpec(` / `IndicatorBoxPartSpec(` constructors.
- [x] Write a cache test using equal immutable specs to assert repeated `_authoritative_render_data` calls return the same `PartRenderData` object and call `manufacturing_api.build_part_render_data` once.
- [x] Run focused tests and verify RED.
- [x] Extract the current payload→spec logic into `_fold_designer_part_spec_from_payload` and make `_query_fold_designer_render_data` call only that builder + `_authoritative_render_data`.
- [x] Add bounded-cache key normalization for unhashable feature mappings using a stable `repr(spec)` + context tuple.
- [x] Run focused tests and verify GREEN.

### Task 2: Make committed and draft Door specs identical

**Files:**
- Modify: `tests/test_phase6_3d_single_source_renderer.py`
- Modify: `gui.py`

**Interfaces:**
- Consumes: `_fold_designer_part_spec_from_payload`.
- Produces: one shared Door field mapping for committed GUI state and Fold Designer draft state.

- [x] Add a regression test that creates an equivalent committed Door state and Fold Designer payload (baseline model, gaps, four folds, user features, indicator mode/offset, CornerType) and asserts the resulting `DoorPartSpec` values are equal.
- [x] Run the test and verify RED against duplicated mapping.
- [x] Factor Door spec construction into a helper accepting normalized values and reuse it from `_single_door_part_spec` and `_fold_designer_part_spec_from_payload`.
- [x] Repeat the same pattern for EndCap/BasePlate/Indicator parts where existing field mappings differ, without changing formulas.
- [x] Run focused tests and verify GREEN.

### Task 3: Make Door 2D consume final manufacturing scene

**Files:**
- Modify: `tests/test_phase6_3d_single_source_renderer.py`
- Modify: `gui.py`

**Interfaces:**
- Consumes: `_single_door_part_spec`, `_authoritative_render_data`.
- 2D output: `render_drawing_scene(canvas, render_data.scene, transform, skip_layers=("CHECK", "STOCK"))`.

- [x] Add a test that monkeypatches `_authoritative_render_data` with a sentinel final scene containing a CUTTING handle profile and asserts `draw_door` renders that final scene instead of separately calling baseline overlay/user-feature geometry builders.
- [x] Run test and verify RED.
- [x] In single-Door `draw_door`, build the canonical Door spec once, obtain authoritative render data once, derive blank bounds from `material.bounds`, and render `render_data.scene` for manufacturing geometry.
- [x] Preserve dimension annotations, indicator measurement guides, editor hints and STOCK overlay as UI-only layers.
- [x] Do not call `render_secondary_scene` or `render_surface_user_features` for the single-Door manufacturing geometry path.
- [x] Run Door preview + baseline handle regression tests and verify GREEN.

### Task 4: Verify 3D receives exactly the same final Door geometry

**Files:**
- Modify: `tests/test_phase6_3d_single_source_renderer.py`
- Existing: `tests/test_phase6_baseline_operation_alignment.py`
- Existing: `tests/test_phase6_3d_cutting_mesh.py`

**Interfaces:**
- Consumes: cached authoritative `PartRenderData`.

- [x] Add a test querying the same Door spec through the 2D authoritative provider and Fold Designer callback and assert object identity plus equal material bounds/area.
- [x] Add/retain a handle-line-profile test proving the final material has the handle opening removed.
- [x] Run focused suite and verify GREEN.

### Task 5: Package verification

**Files:**
- Modify: `修改日誌/20260822.md`
- Modify: `DELIVERY_README.md`
- Preserve: `fold_designer_original.py`

- [x] Run `python -m py_compile gui.py fold_designer_bridge.py ae_engine/manufacturing_api.py ae_engine/ae.py`.
- [x] Run `xvfb-run -a env PYTHONPATH=. pytest -q`.
- [x] Compare SHA256 of `fold_designer_original.py` against the input ZIP copy.
- [x] Update delivery notes with the single Final Part Geometry data flow and test counts.
- [x] Create `PHASE6_SHARED_FINAL_PART_GEOMETRY_20260822.zip`.
- [x] Extract the ZIP to a clean directory and rerun full pytest + py_compile there.
