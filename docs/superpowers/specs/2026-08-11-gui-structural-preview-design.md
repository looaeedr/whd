# GUI Structural Preview Single-Source Design

**Date:** 2026-08-11
**Scope:** V5 `new-engine`; current validated manufacturing baseline is the Vault/Safe-type enclosure family.

## Goal

Make GUI structural previews render the same geometry result used by DXF export. Remove duplicated CUTTING/BEND coordinate derivation from `gui.py`.

## Chosen Architecture

Introduce a shared pure adapter module:

```text
sheetmetal_part_adapters.py
```

It converts legacy/UI parameter names into the existing generic topology builders in `sheetmetal_geometry.py` and returns one neutral result:

```python
StructuralGeometryResult(
    outline: tuple[Vec2, ...],
    bends: tuple[BendLine, ...],
    width: float,
    height: float,
)
```

Both `ae.py` and `gui.py` consume these adapters. This prevents GUI from duplicating `ae.py` parameter translation while keeping `sheetmetal_geometry.py` free of part-name/factory orchestration.

## Layer Boundaries

### `sheetmetal_geometry.py`

Pure topology/boolean engine only. No `tkinter`, no `ezdxf`, no GUI rendering.

### `sheetmetal_part_adapters.py`

Pure parameter-to-topology translation. Imports only pure geometry/config values passed as arguments. Provides adapters for:

- box body / StripFoldChain
- door / FourSideFlange
- base plate / FourSideFlange
- indicator box / FourSideFlange
- end cap / EndCapGeometry + ReliefConfig

No Canvas or DXF operations.

### `ae.py`

DXF serialization and existing secondary-feature mapping. Structural exporters consume `StructuralGeometryResult` rather than independently rebuilding outline/BEND geometry.

### `gui.py`

Canvas presentation only. It receives `StructuralGeometryResult`, computes a `CanvasTransform`, and renders outline/bends. It may still draw UI-only overlays such as dimensions, stock comparison rectangles, labels, drag handles, or secondary feature previews.

## Shared GUI Renderer

Add focused GUI helpers:

```python
_draw_structural_outline(canvas, result, transform, tags=None)
_draw_structural_bends(canvas, result, transform, tags=None)
```

These helpers do not calculate manufacturing coordinates.

## Migration Targets

### Box Body

Remove manual rectangle and `bx1...bx8` calculations from `draw_box_body()`. Use shared box-body adapter. Baseline feature circles remain a secondary overlay.

### Door

Remove fallback 12-point CUTTING and four manual BEND lines from `draw_door()`. Direct and baseline modes obtain structural geometry from the same shared door adapter; baseline mapping remains for secondary features only.

### Base Plate

Remove 12-point `bend × bend` outline and four manual BEND lines from `draw_base_plate()`. Preserve UI-only shrink control overlays, box comparison rectangle, dimensions, and four fixed functional hole previews as secondary features.

### Indicator Box

Replace any structural `CUTTING/BEND` preview source with the same indicator-box adapter used by DXF. Existing hole/nameplate/feature preview remains separate.

### End Cap / Tail

Remove the old non-baseline 16/17-point formula and manual BEND lines from `draw_end_cap()`. Use the same EndCapGeometry + ReliefConfig result as DXF, including the corrected Vault factory rules. Baseline mode also uses the same structural result; only baseline secondary entities remain mapped/overlaid.

## Baseline Rule

A baseline DXF may contribute secondary features, but must not override main structural CUTTING/BEND. Direct and stretched previews must derive structure from the same adapter result.

## Rendering Coordinates

All structural rendering uses the existing shared `CanvasTransform` from `sheetmetal_features.py`:

```text
Geometry mm coordinates
→ CanvasTransform
→ pixels
```

No per-draw-function `offset_x + x*scale` / `offset_y - y*scale` manufacturing conversion should remain once migrated.

## Compatibility

- Keep current GUI tabs and controls.
- Keep existing colors and line styles.
- Keep STOCK toggle behavior.
- Keep dimension/annotation overlays.
- Keep door indicator drag workflow.
- Keep baseline feature mapping behavior.
- Do not introduce CAM kerf/over-cut logic.

## Tests

Pure adapter tests verify that shared results match existing geometry builders for T=2 and T=1.5, asymmetric folds, and current Vault defaults.

GUI helper tests use a fake Canvas/transform where practical to verify that rendering consumes result coordinates without recomputing them.

Integration tests verify direct structural results used by GUI adapters equal those used by DXF exporters for box body, door, base plate, indicator box, and end cap.

## Success Criterion

For every migrated structural part:

```text
Parameters
→ shared Part Adapter
→ StructuralGeometryResult
   ├─ GUI renderer
   └─ DXF exporter
```

No production CUTTING/BEND coordinate formula remains duplicated in `gui.py`.
