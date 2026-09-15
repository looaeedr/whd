# Hole Catalog / Blind Hole / Rotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load ordinary and blind hole catalogs from `基準檔/開孔/`, add directional rotation/profile holes, and preserve FeatureSurface legality through GUI and DXF.

**Architecture:** `hole_catalog.py` owns CSV/DXF catalog parsing and returns pure definitions. `sheetmetal_features.py` owns semantic feature rotation, footprint validation, and resolution. `sheetmetal_drawing.py` maps resolved geometry to semantic layers; `ae.py` only creates DXF layers and serializes scenes; `gui.py` selects definitions and places features.

**Tech Stack:** Python 3, csv, dataclasses, Shapely, ezdxf at catalog/DXF boundaries, Tkinter, pytest.

## Global Constraints
- `管孔尺寸清單.csv` lives under `基準檔/開孔/` and means BLIND_HOLE.
- `開孔.csv` means CUTTING.
- One numeric size = circle; two numeric sizes = rectangle; filename = profile DXF.
- BLIND_HOLE is Color 1 / CONTINUOUS; MARKING stays engraving/marking only.
- Rotation choices are 90/180/270/360; 360 is geometrically equivalent to 0.
- Full rotated footprint must remain inside FeatureSurface.
- GUI and DXF consume the same resolved features.

---

### Task 1: Startup regression and resource move
**Files:** Modify `gui.py`; move catalog CSV; test `test_gui_startup_contract.py`.
**Interfaces:** GUI startup contains no out-of-scope `canvas/cw` hint call; catalog paths use `ae.get_resource_path`.
- [ ] Write a failing source regression for the stray startup call.
- [ ] Verify RED.
- [ ] Remove only the stray call and relocate the pipe CSV into `基準檔/開孔/`.
- [ ] Verify GREEN.

### Task 2: HoleCatalog parser
**Files:** Create `hole_catalog.py`; create `test_hole_catalog.py`.
**Interfaces:** `HoleDefinition`, `load_hole_catalog(base_dir)`, `load_pipe_catalog(base_dir)`, `load_profile_points(path)`.
- [ ] Test one-number circle, two-number rectangle, filename profile, UTF-8 BOM, and pipe BLIND_HOLE semantics.
- [ ] Verify RED because module does not exist.
- [ ] Implement minimal parser and DXF profile loader.
- [ ] Verify GREEN.

### Task 3: Rotatable profile features and containment
**Files:** Modify `sheetmetal_features.py`; tests in `test_sheetmetal_features.py` and `test_feature_surface.py`.
**Interfaces:** `ProfileFeature`, `ResolvedProfile`; Rect/Profile `rotation_deg`; `feature_from_hole_definition(...)` adapter.
- [ ] Test 90-degree rectangle dimensions, 180/270 profile points, 360 identity, and rotated boundary rejection.
- [ ] Verify RED.
- [ ] Implement rotation around feature center and rotated Shapely footprint.
- [ ] Verify GREEN.

### Task 4: BLIND_HOLE DrawingScene/DXF semantics
**Files:** Modify `sheetmetal_drawing.py`, `ae.py`; tests `test_sheetmetal_drawing.py`, `test_ae_geometry_integration.py`.
**Interfaces:** BLIND_HOLE primitives default Color 1; setup creates BLIND_HOLE layer Color 1 / CONTINUOUS; pipe centerline uses DATUM rather than MARKING.
- [ ] Write failing layer/color/primitive tests.
- [ ] Verify RED.
- [ ] Implement semantic mapping and layer setup.
- [ ] Verify GREEN.

### Task 5: GUI catalog and rotation integration
**Files:** Modify `gui.py`; test `test_hole_catalog_gui_contract.py`.
**Interfaces:** Catalog chooser builds Features through shared adapter; directional entries expose 90/180/270/360; pipe entries produce BLIND_HOLE.
- [ ] Write failing source/behavior contract tests.
- [ ] Verify RED.
- [ ] Integrate catalog into generic and end-cap editors without duplicating geometry rules.
- [ ] Verify GREEN.

### Task 6: Full verification
**Files:** all touched modules/tests.
- [ ] Run full pytest suite.
- [ ] Run py_compile for six core modules plus `hole_catalog.py`.
- [ ] Round-trip one CUTTING circle, one rotated rectangular/profile CUTTING hole, and one BLIND_HOLE pipe feature through DXF.
- [ ] Audit that MARKING is not used for pipe holes.
