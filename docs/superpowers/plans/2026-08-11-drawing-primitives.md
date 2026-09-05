# Drawing Primitive Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Move CHECK, STOCK, and DATUM primitive generation out of `ae.py` into a pure DXF-independent drawing layer so `ae.py` only serializes returned primitives.

**Architecture:** Add `sheetmetal_drawing.py` containing immutable drawing primitives plus pure builders for stock outlines, base-plate datum, and part-specific CHECK annotations. `ae.py` will map these primitives to ezdxf entities with one serializer and will stop deriving CHECK/STOCK/DATUM coordinates for migrated exporters.

**Tech Stack:** Python dataclasses, existing `Vec2`, pytest, ezdxf only at the exporter boundary.

## Global Constraints

- `sheetmetal_drawing.py` must not import `ezdxf`, `tkinter`, or Shapely.
- Preserve current layer names, colors, text, text sizes, attachment points, and STOCK enable/disable behavior.
- Preserve Base Plate DATUM geometry exactly.
- CHECK builders may format already-known dimensions but must not become a second structural geometry engine.
- Door indicator dimensions must consume the existing shared indicator position/guide result.
- CUTTING, BEND, MARKING, and feature resolution are out of scope.

---

### Task 1: Add pure drawing primitive model and generic STOCK builder

**Files:**
- Create: `sheetmetal_drawing.py`
- Create: `test_sheetmetal_drawing.py`

**Interfaces:**
- Produces: `PolylinePrimitive(points, layer, closed=False, color=None)`
- Produces: `LinePrimitive(p1, p2, layer, color=None)`
- Produces: `TextPrimitive(text, insert, layer, char_height, attachment_point, color=None)`
- Produces: `build_stock_outline(width, height) -> PolylinePrimitive`

- [x] Write failing tests importing the primitive classes and asserting `build_stock_outline(100, 50)` yields `(0,0) → (100,0) → (100,50) → (0,50) → (0,0)` on `STOCK`.
- [x] Run `pytest -q test_sheetmetal_drawing.py` and verify RED because `sheetmetal_drawing` does not exist.
- [x] Implement the immutable primitive dataclasses and generic stock builder.
- [x] Run `pytest -q test_sheetmetal_drawing.py` and verify GREEN.

### Task 2: Add Base Plate DATUM and CHECK builders

**Files:**
- Modify: `sheetmetal_drawing.py`
- Modify: `test_sheetmetal_drawing.py`

**Interfaces:**
- Produces: `build_base_plate_datum(w, h, shrink_left, shrink_bottom, bend) -> PolylinePrimitive`
- Produces: `build_base_plate_check(total_width, total_height, bend, shrink_top, shrink_bottom, shrink_left, shrink_right) -> tuple[TextPrimitive, ...]`

- [x] Add failing tests asserting the current datum origin `(-(shrink_left-bend), -(shrink_bottom-bend))`, exact W×H rectangle, CHECK text, insert `(total_width/2, total_height+50)`, height `30`, attachment `8`.
- [x] Run targeted tests and verify RED.
- [x] Implement the minimal builders using only supplied values.
- [x] Run targeted tests and verify GREEN.

### Task 3: Add CHECK builders for Door, Box Body, Indicator Box, and End Cap/Tail

**Files:**
- Modify: `sheetmetal_drawing.py`
- Modify: `test_sheetmetal_drawing.py`

**Interfaces:**
- Produces: `build_door_check(...)`
- Produces: `build_box_body_check(...)`
- Produces: `build_indicator_box_check(...)`
- Produces: `build_endcap_check(...)`
- Produces: optional dimension `LinePrimitive/TextPrimitive` from an existing `DoorIndicatorPosition`

- [x] Add failing tests for exact current CHECK text fragments and placement for each family.
- [x] Add failing test proving Door indicator dimension primitives use the passed `DoorIndicatorPosition` numbers verbatim.
- [x] Run targeted tests and verify RED.
- [x] Implement the builders without recomputing structural outlines or feature placement.
- [x] Run targeted tests and verify GREEN.

### Task 4: Add one DXF serializer for drawing primitives

**Files:**
- Modify: `ae.py`
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Consumes: `PolylinePrimitive | LinePrimitive | TextPrimitive`
- Produces: `_add_drawing_primitives_to_dxf(msp, primitives)`

- [x] Add failing fake-modelspace tests verifying each primitive maps to the existing ezdxf call and attributes without coordinate changes.
- [x] Run targeted integration tests and verify RED.
- [x] Implement the serializer with no geometry calculations.
- [x] Run targeted integration tests and verify GREEN.

### Task 5: Migrate direct exporters

**Files:**
- Modify: `ae.py`
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Door, Box Body, End Cap/Tail, Indicator Box, Base Plate use `build_stock_outline` and the relevant CHECK/DATUM builder.

- [x] Add source/integration tests asserting direct exporters call drawing builders and preserve current layer entities.
- [x] Run tests and verify RED.
- [x] Replace direct exporter STOCK point arrays, CHECK MTEXT/line calculations, and Base Plate DATUM calculations with drawing primitives.
- [x] Run tests and verify GREEN.

### Task 6: Migrate stretched exporters

**Files:**
- Modify: `ae.py`
- Modify: `test_ae_geometry_integration.py`

**Interfaces:**
- Stretched Door, Box Body, End Cap/Tail use the same generic stock and CHECK builders as direct exporters wherever the same annotation semantics apply.

- [x] Add failing source/integration tests proving stretched paths no longer construct their own STOCK arrays or CHECK annotation coordinates.
- [x] Run tests and verify RED.
- [x] Replace duplicated stretched STOCK/CHECK logic with drawing builders and serializer.
- [x] Run tests and verify GREEN.

### Task 7: Full regression and audit

**Files:**
- Modify only if verification exposes defects.

- [x] Run `pytest -q`.
- [x] Run `python -m py_compile ae.py gui.py sheetmetal_geometry.py sheetmetal_features.py sheetmetal_part_adapters.py sheetmetal_drawing.py`.
- [x] Generate and re-open representative Door, Box Body, Base Plate, Indicator Box, Head, and Tail DXFs.
- [x] Verify STOCK appears only when enabled, Base Plate DATUM remains present, CHECK remains present, and CUTTING/BEND counts do not regress.
- [x] Search `ae.py` to confirm migrated exporters no longer calculate Base Plate DATUM coordinates or manually build CHECK/STOCK point arrays.
