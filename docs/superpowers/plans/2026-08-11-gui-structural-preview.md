# GUI Structural Preview Single-Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make GUI structural previews and DXF exporters consume the same pure structural geometry results for all currently migrated Vault/Safe-type parts.

**Architecture:** Add `sheetmetal_part_adapters.py` as the pure shared translation layer from legacy/UI dimensions to `sheetmetal_geometry.py` topology builders. Both `ae.py` and `gui.py` consume `StructuralGeometryResult`; GUI keeps only Canvas rendering and UI overlays, while DXF keeps only serialization and secondary feature mapping.

**Tech Stack:** Python 3.11+, dataclasses, Shapely through `sheetmetal_geometry.py`, Tkinter Canvas in `gui.py`, ezdxf only in `ae.py`, pytest.

## Global Constraints

- `sheetmetal_geometry.py` remains free of `tkinter` and `ezdxf`.
- `sheetmetal_part_adapters.py` is pure and performs no Canvas or DXF operations.
- `gui.py` must not derive production CUTTING/BEND coordinates after migration.
- `ae.py` must not independently derive structural coordinates that are already produced by shared adapters.
- Baseline DXF contributes only secondary features; main CUTTING/BEND comes from the shared structural result.
- Preserve current GUI tabs, colors, dimensions, STOCK overlays, drag behavior, and feature previews.
- Preserve validated Vault/Safe-type factory rules, including corrected End Cap relief formulas.
- All production-code behavior changes follow TDD.

---

### Task 1: Shared Structural Result and Part Adapters

**Files:**
- Create: `sheetmetal_part_adapters.py`
- Create: `test_sheetmetal_part_adapters.py`

**Interfaces:**
- Produces: `StructuralGeometryResult(outline, bends, width, height)`
- Produces: `build_box_body_result(...)`
- Produces: `build_door_result(...)`
- Produces: `build_base_plate_result(...)`
- Produces: `build_indicator_box_result(...)`
- Produces: `build_endcap_result(...)`

- [x] Write failing tests comparing adapter results to existing `sheetmetal_geometry` builders for box body, door, base plate, indicator box, and end cap.
- [x] Run `pytest -q test_sheetmetal_part_adapters.py` and verify RED because the module does not exist.
- [x] Implement the minimal pure adapters using existing topology classes/builders and no GUI/DXF imports.
- [x] Run `pytest -q test_sheetmetal_part_adapters.py` and verify GREEN.
- [x] Run existing geometry tests to ensure no regression.

### Task 2: Migrate DXF Structural Exporters to Shared Adapters

**Files:**
- Modify: `ae.py`
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Consumes the five adapter functions from Task 1.
- Exporters serialize `result.outline` to CUTTING and `result.bends` to BEND.

- [x] Write failing integration assertions that `ae.py` structural helper/export paths use adapter-equivalent output.
- [x] Verify RED before changing production code.
- [x] Replace duplicated structural construction in the relevant direct exporters with shared adapter calls.
- [x] Preserve holes/MARKING/DATUM/STOCK/CHECK behavior unchanged.
- [x] Verify GREEN with `pytest -q test_ae_geometry_integration.py`.

### Task 3: Add Generic GUI Structural Renderer

**Files:**
- Modify: `gui.py`
- Create: `test_gui_structural_rendering.py`

**Interfaces:**
- Produces: `_render_structural_result(canvas, result, transform, tags=None)` or equivalent focused helper.
- Consumes: `StructuralGeometryResult`, `CanvasTransform`.

- [x] Write a failing fake-Canvas test proving the renderer draws the supplied outline and bend coordinates without deriving new geometry.
- [x] Verify RED.
- [x] Implement the minimal renderer using `CanvasTransform.world_to_canvas`.
- [x] Verify GREEN.

### Task 4: Migrate Box Body GUI Preview

**Files:**
- Modify: `gui.py` (`draw_box_body`)
- Modify: `test_gui_structural_rendering.py`

**Interfaces:**
- Consumes: `build_box_body_result(...)`.
- Baseline circles remain a secondary overlay.

- [x] Write failing source/integration assertions that `draw_box_body` no longer contains `bx1...bx8` manufacturing calculations.
- [x] Verify RED.
- [x] Replace manual rectangle and eight bend calculations with the shared result and generic renderer.
- [x] Keep STOCK, dimensions, info text, and baseline circles.
- [x] Verify GREEN.

### Task 5: Migrate Door GUI Preview

**Files:**
- Modify: `gui.py` (`draw_door`)
- Modify: `test_gui_structural_rendering.py`

**Interfaces:**
- Consumes: `build_door_result(...)`.
- Door feature resolver remains the source for indicator/nameplate holes.

- [x] Write failing assertions that the non-baseline 12-point CUTTING fallback and four manual BEND lines are absent.
- [x] Verify RED.
- [x] Render shared door structural result in both direct and baseline preview modes.
- [x] Preserve indicator feature rendering, dimension overlays, and drag metadata.
- [x] Verify GREEN.

### Task 6: Migrate Base Plate and Indicator Box GUI Previews

**Files:**
- Modify: `gui.py` (`draw_base_plate`, `draw_indicator_box`)
- Modify: `test_gui_structural_rendering.py`

**Interfaces:**
- Consumes: `build_base_plate_result(...)`, `build_indicator_box_result(...)`.

- [x] Write failing assertions for removal of Base Plate 12-point structural list and manual four BEND lines.
- [x] Verify RED.
- [x] Use shared results for structural CUTTING/BEND.
- [x] Preserve Base Plate comparison rectangle, four functional hole previews, shrink controls, and Indicator secondary features.
- [x] Verify GREEN.

### Task 7: Migrate End Cap / Tail GUI Preview

**Files:**
- Modify: `gui.py` (`draw_end_cap`)
- Modify: `test_gui_structural_rendering.py`

**Interfaces:**
- Consumes: `build_endcap_result(...)` with the same `ReliefConfig` used by DXF.
- Baseline mapping remains secondary feature overlay only.

- [x] Write a failing regression assertion that the old non-baseline notch formulas and hand-built stepped CUTTING list are still present before migration.
- [x] Verify RED.
- [x] Replace structural preview with the shared End Cap result.
- [x] Preserve built-in holes, user holes, labels, STOCK, and baseline secondary features.
- [x] Verify corrected Vault relief dimensions match DXF preview geometry.
- [x] Verify GREEN.

### Task 8: Structural Duplication Audit and Full Verification

**Files:**
- Modify only if verification finds defects.

- [x] Run `pytest -q`.
- [x] Run `python -m py_compile ae.py gui.py sheetmetal_geometry.py sheetmetal_features.py sheetmetal_part_adapters.py`.
- [x] Search `gui.py` for structural hard-code signatures: `bx1`, `bx2`, 12/16-point structural lists, old End Cap `zl1/zr1 + fw + t`, and old `side_fold - 0.5T` formulas.
- [x] Generate representative Door, Base Plate, Box Body, Indicator Box, and End Cap DXFs and reopen them with ezdxf when available.
- [x] Confirm GUI-facing adapter results and DXF-facing adapter results are the same objects/data for equivalent parameters.
