# GUI Overlay / Guide Single-Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the remaining design/manufacturing coordinate formulas out of `gui.py` while keeping presentation-only Canvas styling local to the GUI.

**Architecture:** Physical holes/cutouts remain in `sheetmetal_features.py`; design-only world-space guides are added there as small immutable data objects. `ae.py` serializes resolved features to DXF, while `gui.py` renders the same resolved features/guides through `CanvasTransform` and keeps only presentation choices such as colors, fonts, and label placement.

**Tech Stack:** Python 3.11+, dataclasses, pytest, tkinter at GUI boundary only, ezdxf at DXF boundary only.

## Global Constraints

- No new per-part hard-coded main geometry.
- `sheetmetal_features.py` must not import tkinter or ezdxf.
- Existing Vault dimensions and behavior must remain unchanged.
- STOCK W/H labels may remain presentation-only in `gui.py` when derived directly from `StructuralGeometryResult`.
- DATUM coordinates must never be invented in `gui.py`.
- GUI must not silently fall back to duplicate coordinate formulas.

---

### Task 1: Add world-space guide types and end-cap guide resolver

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `test_sheetmetal_features.py`

**Interfaces:**
- Produces: `RectGuide(min_point: Vec2, max_point: Vec2, role: str)`
- Produces: `DimensionGuide(start: Vec2, end: Vec2, value: float, axis: str)`
- Produces: `resolve_endcap_finished_face_guide(width: float, depth: float, thickness: float) -> RectGuide`

- [ ] Add failing tests asserting the current Vault finished-face guide is `(2T, 2T)` to `(W-2T, D-T)` and rejects non-positive thickness.
- [ ] Run `pytest test_sheetmetal_features.py -q` and verify RED because the new symbols do not exist.
- [ ] Implement the immutable guide types and resolver with no GUI imports.
- [ ] Run `pytest test_sheetmetal_features.py -q` and verify GREEN.

### Task 2: Centralize Vault end-cap fixed features

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `test_sheetmetal_features.py`
- Modify: `ae.py`
- Modify: `gui.py`

**Interfaces:**
- Produces: `resolve_vault_endcap_fixed_features(...) -> tuple[ResolvedFeature, ...]`
- Consumes: `StructuralGeometryResult` end-cap dimensions/topology and Vault config values.

- [ ] Add failing tests for head/tail fixed features: two hanging circles, one square cutout, and tail-only bottom circle.
- [ ] Verify T=2 current coordinates and a T=1.5 case where thickness-dependent vertical placement remains consistent with the current formula.
- [ ] Run targeted tests and verify RED.
- [ ] Implement `resolve_vault_endcap_fixed_features` in `sheetmetal_features.py`.
- [ ] Refactor `ae.export_end_cap_dxf()` so fixed CUTTING features are serialized from the resolver only.
- [ ] Refactor `gui.draw_end_cap()` so the no-baseline preview renders the same resolved features only.
- [ ] Run targeted tests and verify GREEN.

### Task 3: Migrate the hole-editor guide rectangle

**Files:**
- Modify: `gui.py`
- Modify: `test_gui_structural_rendering.py`

**Interfaces:**
- Consumes: `resolve_endcap_finished_face_guide(...) -> RectGuide`

- [ ] Add a source-level/integration regression asserting the hole editor uses the resolver and no longer contains `bx_l=2*t_box`, `bx_r=w_box-2*t_box`, `by_b=2*t_box`, `by_t=d_box-t_box`.
- [ ] Verify RED.
- [ ] Replace the local guide calculation with the returned `RectGuide`, then render it through the existing `CanvasTransform`.
- [ ] Verify GREEN.

### Task 4: Make shared dimension guides explicit for Door Indicator

**Files:**
- Modify: `sheetmetal_features.py`
- Modify: `gui.py`
- Modify: `test_sheetmetal_features.py`

**Interfaces:**
- Extend the existing `DoorIndicatorLayout` with world-space `dimension_guides` or a helper `resolve_door_indicator_dimension_guides(layout, context)`.

- [ ] Add failing tests asserting current X/Y dimension values and endpoints are preserved.
- [ ] Verify RED.
- [ ] Implement the shared `DimensionGuide` output from the existing Door Indicator policy/layout.
- [ ] Refactor GUI dimension arrows/text to consume those guides; Canvas code only chooses label offsets/color/font.
- [ ] Verify GREEN.

### Task 5: Audit STOCK/DATUM and presentation-only overlays

**Files:**
- Modify: `gui.py` only if audit finds duplicated design geometry.
- Modify: `test_gui_structural_rendering.py`

**Interfaces:**
- STOCK preview bounds are exactly `(0,0)` to `(result.width,result.height)`.
- Generic W/H labels read `result.width/result.height` only.
- GUI has no independent DATUM coordinate construction.

- [ ] Add audit tests/search checks for duplicate manufacturing formulas in GUI.
- [ ] Confirm existing STOCK rectangles are derived only from structural result dimensions or equivalent authoritative blank dimensions.
- [ ] Confirm DATUM is not recomputed in GUI; if present, route it through a shared primitive source instead.
- [ ] Keep pure display grid, colors, fonts, padding, legends, and label pixel offsets in GUI.

### Task 6: Full verification

**Files:**
- Modify only if verification exposes a defect.

- [ ] Run `pytest -q`.
- [ ] Run `python -m py_compile ae.py gui.py sheetmetal_geometry.py sheetmetal_features.py sheetmetal_part_adapters.py`.
- [ ] Generate representative Door, Base Plate, Box Body, Indicator Box, End Cap/Tail DXFs and reload them with ezdxf.
- [ ] Search `gui.py` for the removed end-cap fixed-hole and hole-editor guide formulas.
- [ ] Search `ae.py` for duplicate Vault end-cap fixed-hole formulas outside config adaptation/serialization.
