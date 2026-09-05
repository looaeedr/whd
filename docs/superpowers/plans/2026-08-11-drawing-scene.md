# DrawingScene Single-Serializer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all structural, feature, CHECK, STOCK and DATUM output through one pure DrawingScene and one DXF serializer.

**Architecture:** `sheetmetal_drawing.py` owns drawing primitives, scene aggregation, and pure conversion from structural/results/features/legacy baseline geometry. `ae.py` owns one `DrawingScene -> ezdxf` serializer plus document/layer creation and save operations.

**Tech Stack:** Python 3, dataclasses, pytest, ezdxf at serialization boundary only.

## Global Constraints

- `sheetmetal_drawing.py` must not import ezdxf or tkinter.
- Structural formulas remain in geometry/adapters; feature placement remains in feature resolver.
- Baseline mapping behavior is preserved.
- No production per-exporter `msp.add_line/add_lwpolyline/add_circle/add_mtext` loops remain after migration.

---

### Task 1: Scene Model and Circle Primitive

**Files:**
- Modify: `sheetmetal_drawing.py`
- Test: `test_sheetmetal_drawing.py`

**Interfaces:**
- Produces `CirclePrimitive(center: Vec2, radius: float, layer: str, color: int|None = None)`.
- Produces `DrawingScene(primitives=list[DrawingPrimitive])` with `add()` and `extend()`.

- [ ] Write failing tests for CirclePrimitive and scene ordering.
- [ ] Run tests and verify RED because symbols do not exist.
- [ ] Implement minimal dataclasses and methods.
- [ ] Run tests and verify GREEN.

### Task 2: Pure Converters

**Files:**
- Modify: `sheetmetal_drawing.py`
- Test: `test_sheetmetal_drawing.py`

**Interfaces:**
- `structural_result_to_primitives(result)` returns CUTTING polyline + BEND lines.
- `resolved_features_to_primitives(features)` returns circle/rect/centerline primitives.
- `legacy_geom_to_primitives(geom)` converts legacy `polylines/lines/circles` tuples.

- [ ] Write failing tests for exact layer/point/radius conversion.
- [ ] Verify RED.
- [ ] Implement minimal pure converters without ezdxf.
- [ ] Verify GREEN.

### Task 3: Single Scene Serializer

**Files:**
- Modify: `ae.py`
- Test: `test_ae_geometry_integration.py`

**Interfaces:**
- `_add_drawing_scene_to_dxf(msp, scene)` handles all four primitive types.

- [ ] Write failing fake-modelspace serializer test including MARKING default color.
- [ ] Verify RED because serializer does not exist.
- [ ] Implement serializer.
- [ ] Verify GREEN.

### Task 4: Migrate Direct Exporters

**Files:**
- Modify: `ae.py`
- Test: existing exporter integration tests

**Interfaces:**
- Door, BoxBody, EndCap, BasePlate, Indicator all assemble DrawingScene then serialize once.

- [ ] Add/adjust regression test asserting representative direct exporters still produce expected layer entity counts.
- [ ] Verify baseline before refactor.
- [ ] Replace direct CUTTING/BEND/features/drawing primitive serialization with scene assembly.
- [ ] Run direct exporter tests and verify GREEN.

### Task 5: Migrate Stretched Exporters

**Files:**
- Modify: `ae.py`
- Test: existing stretched/integration tests

**Interfaces:**
- Stretched EndCap/Door/BoxBody/Indicator use `legacy_geom_to_primitives()` and common serializer.

- [ ] Add regression test for legacy geom conversion with MARKING circle/line.
- [ ] Verify RED for missing common path where applicable.
- [ ] Replace local `geom` write loops with DrawingScene conversion/serialization.
- [ ] Verify GREEN.

### Task 6: Remove Old Serializers and Audit

**Files:**
- Modify: `ae.py`

- [ ] Remove `_add_drawing_primitives_to_dxf` and `_add_resolved_features_to_dxf` after all callers migrate.
- [ ] Run `pytest -q`.
- [ ] Run `python -m py_compile ae.py gui.py sheetmetal_geometry.py sheetmetal_features.py sheetmetal_part_adapters.py sheetmetal_drawing.py`.
- [ ] Search `ae.py` for `msp.add_lwpolyline`, `msp.add_line`, `msp.add_circle`, `msp.add_mtext`; confirm production calls are confined to one serializer.
- [ ] Generate/read representative DXFs and verify expected layers/entity counts.
