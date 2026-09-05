# All-Part Sheet-Metal Topology Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Migrate Door, Indicator Box, Base Plate, Box Body, and their stretched paths onto reusable topology/builders so CUTTING and BEND are no longer hand-coded per part type.

**Architecture:** Extend `sheetmetal_geometry.py` with two reusable topology families: `FourSideFlangeGeometry` for four-sided folded panels and `StripFoldChain` for one-dimensional multi-bend blanks. Part-specific code only supplies dimensions and relief policies; all exterior generation and bend clipping live in the geometry module. Baseline DXF mapping remains responsible only for secondary features.

**Tech Stack:** Python 3.11+, dataclasses, Shapely, pytest, ezdxf only at exporter boundary.

## Global Constraints

- Do not key geometry rules by panel/part name.
- Preserve current T=2 output unless a current literal is demonstrably a thickness-dependent hard-code (Indicator Box 47/49 is such a case).
- Direct and stretched versions of the same part must share the same structural geometry builder.
- CUTTING/BEND structural geometry must be testable without importing ezdxf.
- No hard-coded perimeter vertex lists remain in migrated exporters.
- Existing End Cap assembly relief remains a regression case and must not regress.

---

### Task 1: Add generic FourSideFlange geometry

**Files:**
- Modify: `sheetmetal_geometry.py`
- Create: `test_four_side_flange_geometry.py`

**Interfaces:**
- Produces: `FourSideFlangeGeometry`
- Produces: `RectCornerReliefPolicy`
- Produces: `build_four_side_outline(geometry, policy) -> list[Vec2]`
- Produces: `build_four_side_bend_segments(geometry, policy) -> list[BendLine]`

- [x] Write failing tests for asymmetric left/right/top/bottom folds.
- [x] Verify RED.
- [x] Implement rectangle-minus-four-corner-reliefs builder with Shapely.
- [x] Implement material-clipped four bend segments.
- [x] Verify GREEN for symmetric and asymmetric cases.
- [x] Verify current end-cap tests remain green.

### Task 2: Migrate Door direct geometry

**Files:**
- Modify: `ae.py` (`export_door_dxf`)
- Modify: `test_ae_geometry_integration.py`
- Add/modify: `test_four_side_flange_geometry.py`

**Interfaces:**
- Door policy:
  - bottom-left X = `fold_left - T`
  - bottom-right X = `fold_right - T`
  - top-left X = `fold_left - T`
  - top-right X = `fold_right - T`
  - bottom Y = `fold_bottom`
  - top Y = `fold_top`

- [x] Write failing pure-geometry regression for current default Door points.
- [x] Verify RED.
- [x] Replace `cutting_points` 12-point literal with `build_four_side_outline`.
- [x] Replace four hand-coded BEND lines with `build_four_side_bend_segments`.
- [x] Update CHECK text to use policy-derived dimensions.
- [x] Verify GREEN.

### Task 3: Migrate stretched Door onto the same builder

**Files:**
- Modify: `ae.py` (`get_stretched_door_data`)
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Consumes the exact same Door `FourSideFlangeGeometry + RectCornerReliefPolicy` as Task 2.
- Baseline mapper may append holes, circles, MARKING, and non-structural local CUTTING only.

- [x] Write failing test asserting direct Door and stretched Door structural outline equality for equivalent dimensions.
- [x] Verify RED.
- [x] Remove duplicated structural outline/BEND construction from `get_stretched_door_data`.
- [x] Feed engine points/segments into `geom`.
- [x] Verify GREEN.

### Task 4: Migrate Indicator Box and remove 47/49 structural hard-code

**Files:**
- Modify: `ae.py` (`get_indicator_box_data`)
- Modify: `config.ini` only if a configurable fold size is introduced
- Create/modify: `test_indicator_box_geometry.py`

**Interfaces:**
- `indicator_fold = 49.0` remains current default.
- Use Door-style policy:
  - corner X = `indicator_fold - T`
  - corner Y = `indicator_fold`

- [x] Write failing T=2 regression proving current 47/49 outline is preserved.
- [x] Write failing T=1.5 test expecting X=47.5, not fixed 47.
- [x] Verify RED.
- [x] Replace structural 12-point literal and four BEND literals with FourSideFlange builder.
- [x] Keep light/nameplate/marking hole logic unchanged.
- [x] Verify GREEN.

### Task 5: Migrate Base Plate using a different policy on the same topology

**Files:**
- Modify: `ae.py` (`export_base_plate_dxf`)
- Create/modify: `test_base_plate_geometry.py`

**Interfaces:**
- Four folds all use `bend`.
- Corner policy uses full flange depth:
  - corner X = `bend`
  - corner Y = `bend`

- [x] Write failing default regression for current Base Plate 12-point shape.
- [x] Verify RED.
- [x] Replace perimeter literal with FourSideFlange builder.
- [x] Replace hand-coded BEND lines with engine segments.
- [x] Keep holes/DATUM/CHECK separate from structure.
- [x] Verify GREEN.

### Task 6: Add generic StripFoldChain geometry

**Files:**
- Modify: `sheetmetal_geometry.py`
- Create: `test_strip_fold_chain.py`

**Interfaces:**
- Produces: `FoldSegment(name, length, compensation=0.0)`
- Produces: `StripFoldChain(segments, height)`
- Produces: `build_strip_outline(chain) -> list[Vec2]`
- Produces: `build_strip_bend_segments(chain) -> list[BendLine]`

- [x] Write failing test for a nine-segment chain producing eight bends.
- [x] Write failing asymmetric chain test.
- [x] Verify RED.
- [x] Implement cumulative segment/bend position generation.
- [x] Verify GREEN.

### Task 7: Migrate Box Body direct exporter

**Files:**
- Modify: `ae.py` (`export_box_body_dxf`)
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Construct segments from:
  - `abs(zl1)`
  - `zl2`
  - `FW`
  - `D - 2T`
  - `W - 2T`
  - `D - 2T`
  - `FW`
  - `zr2`
  - `abs(zr1)`
- Preserve current `z_comp / 9` behavior as per-segment compensation policy initially.

- [x] Write failing regression matching current total length and x1..x8 bend positions.
- [x] Verify RED.
- [x] Replace x1..x8 manual accumulation with StripFoldChain.
- [x] Replace rectangle literal with strip outline builder.
- [x] Verify GREEN.

### Task 8: Migrate stretched Box Body

**Files:**
- Modify: `ae.py` (`get_stretched_box_body_data`)
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Structural CUTTING/BEND comes from StripFoldChain.
- Existing baseline mapping uses the generated bend anchors for feature mapping.

- [x] Write failing test asserting direct and stretched box structural bends agree for an eight-bend baseline.
- [x] Verify RED.
- [x] Replace duplicated structural rectangle/bend assembly with StripFoldChain result.
- [x] Keep baseline hole/marking mapping separate.
- [x] Verify GREEN.

### Task 9: Centralize structural geometry adapters in ae.py

**Files:**
- Modify: `ae.py`
- Modify: all geometry integration tests

**Interfaces:**
- Add focused adapter functions:
  - `_make_door_geometry(...)`
  - `_make_indicator_box_geometry(...)`
  - `_make_base_plate_geometry(...)`
  - `_make_box_body_chain(...)`
  - existing `_make_endcap_geometry(...)` or equivalent

- [x] Write tests that adapter results are independent of exporter/DXF creation.
- [x] Verify RED.
- [x] Move part-dimension translation into adapters.
- [x] Keep exporter functions limited to writing returned primitives.
- [x] Verify GREEN.

### Task 10: Full regression and hard-code audit

**Files:**
- Modify only if verification exposes defects.

**Verification:**
- [x] Run `pytest -q`.
- [x] Run `python -m py_compile ae.py gui.py sheetmetal_geometry.py`.
- [x] Search `ae.py` for structural literals:
  - Door/BasePlate/Indicator 12-point `cutting_points` must be gone.
  - Indicator structural `47.0`/`49.0` must be gone except default/config values.
  - Box Body `x1 ... x8` structural bend generation must be gone.
- [x] Confirm End Cap tests remain green.
- [x] Confirm geometry tests run without importing ezdxf.
