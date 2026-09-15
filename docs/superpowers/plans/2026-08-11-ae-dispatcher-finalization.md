# AE Dispatcher Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `ae.py` into a thin scene dispatcher/writer without changing manufacturing output.

**Architecture:** Existing geometry/feature/drawing modules remain authoritative. `ae.py` composes `DrawingScene`, then a single helper creates the DXF document, serializes the scene, and saves it. Existing export APIs remain compatible and a canonical `export_part_dxf()` dispatcher is added.

**Tech Stack:** Python, pytest, ezdxf, existing sheetmetal modules.

## Global Constraints
- No geometry formula changes.
- No public exporter signature removal.
- No second serializer.
- Preserve layer/entity output.
- TDD before production changes.

---

### Task 1: Lock scene save behavior
- [ ] Add failing tests for `_save_scene_dxf` and exporter round-trip.
- [ ] Implement `_save_scene_dxf` using `setup_dxf_layers` + `_add_drawing_scene_to_dxf`.
- [ ] Verify tests pass.

### Task 2: Extract direct scene builders
- [ ] Add failing tests for `_build_door_scene`, `_build_box_body_scene`, `_build_end_cap_scene`, `_build_indicator_box_scene`, `_build_base_plate_scene` layer counts.
- [ ] Move existing scene assembly into those helpers without changing formulas.
- [ ] Make direct exporters thin wrappers.
- [ ] Verify regression tests.

### Task 3: Normalize stretched save path
- [ ] Make stretched exporters call `_save_scene_dxf` only.
- [ ] Verify stretched baseline round-trip.

### Task 4: Add canonical dispatcher
- [ ] Add failing dispatcher tests for supported aliases and invalid part type.
- [ ] Implement `export_part_dxf(part_type, filepath, **kwargs)` mapping to existing exporters.
- [ ] Verify existing public exporters remain callable.

### Task 5: Final verification
- [ ] Run full pytest.
- [ ] Run py_compile.
- [ ] Audit `ezdxf.new` and `doc.saveas` usage to ensure exporter paths use `_save_scene_dxf`.
- [ ] Run representative DXF round-trip.
