# Drawing Primitive Layer Design

**Date:** 2026-08-11
**Scope:** Move CHECK / STOCK / DATUM generation out of `ae.py` while keeping DXF serialization in `ae.py`.

## Goal

Make `ae.py` a serialization boundary rather than a geometry/annotation calculator.

The new flow is:

```text
StructuralGeometryResult / Feature Policy / Part Parameters
                    ↓
            sheetmetal_drawing.py
                    ↓
        DrawingPrimitive objects
                    ↓
                 ae.py
                    ↓
                 ezdxf
```

## Boundary

`sheetmetal_drawing.py` must not import `ezdxf`, `tkinter`, or Shapely.

It may consume `Vec2`, structural results, part topology, and feature-policy measurement results.

## Primitive Types

```python
@dataclass(frozen=True)
class PolylinePrimitive:
    points: tuple[Vec2, ...]
    layer: str
    closed: bool = False
    color: int | None = None

@dataclass(frozen=True)
class LinePrimitive:
    p1: Vec2
    p2: Vec2
    layer: str
    color: int | None = None

@dataclass(frozen=True)
class TextPrimitive:
    text: str
    insert: Vec2
    layer: str
    char_height: float
    attachment_point: int
    color: int | None = None
```

These are semantic drawing outputs, not DXF entities.

## STOCK

STOCK is an auxiliary blank outline, not manufacturing geometry.

Use one generic builder:

```python
build_stock_outline(width, height) -> PolylinePrimitive
```

The dimensions must come from the authoritative structural result / adapter output. `ae.py` must not independently reconstruct stock dimensions.

## DATUM

DATUM is a design/reference primitive.

Current required case is Base Plate: the finished box W×H rectangle positioned relative to the unfolded blank.

Move the current formula:

```text
box_l = -(shrink_left - bend)
box_b = -(shrink_bottom - bend)
```

into:

```python
build_base_plate_datum(...)
```

`ae.py` receives only the returned primitive.

If GUI later displays DATUM, it must render the same primitive.

## CHECK

CHECK text and dimension lines are drawing annotations, not structural geometry.

Create part-focused builders because the text content is intentionally part-specific:

```python
build_door_check(...)
build_box_body_check(...)
build_endcap_check(...)
build_indicator_box_check(...)
build_base_plate_check(...)
```

Each returns drawing primitives only.

Door indicator X/Y dimension lines must consume the existing `DoorIndicatorPosition` / `DimensionGuide` result instead of repeating coordinate calculations.

CHECK builders may format confirmed part dimensions, fold sizes, and relief dimensions. They must not become a second structural geometry engine.

## DXF Serialization

Add one serializer in `ae.py`:

```python
_add_drawing_primitives_to_dxf(msp, primitives)
```

Mapping:

- `PolylinePrimitive` → `add_lwpolyline`
- `LinePrimitive` → `add_line`
- `TextPrimitive` → `add_mtext`

No coordinate derivation is allowed in this serializer.

## Migration Scope

Migrate all currently generated CHECK/STOCK/DATUM primitives in these direct exporters:

- Door
- Box Body
- End Cap / Tail
- Indicator Box
- Base Plate

Also migrate stretched Door / Box Body / End Cap CHECK/STOCK where they currently regenerate the same annotation/stock logic.

Do not redesign MARKING, CUTTING, BEND, or feature resolution in this phase.

## Compatibility

- Preserve current layer names, colors, text, text size, and attachment points.
- Preserve current STOCK enable/disable behavior.
- Preserve current Base Plate DATUM geometry exactly.
- Preserve current CHECK information and placement unless the old code duplicated a coordinate calculation already represented by a shared guide/policy.

## Testing

Pure tests must verify:

- stock rectangle coordinates,
- base-plate datum coordinates,
- CHECK text content for each part family,
- Door indicator dimension primitives consume the shared position/guide result,
- primitives contain no ezdxf objects.

Integration tests must verify representative DXFs retain:

- STOCK when enabled,
- DATUM for Base Plate,
- CHECK MTEXT and dimension lines,
- existing CUTTING/BEND counts.

## Success Criteria

1. `ae.py` no longer constructs CHECK text/line geometry for migrated exporters.
2. `ae.py` no longer constructs STOCK point arrays for migrated exporters.
3. Base Plate DATUM coordinates are not calculated in `ae.py`.
4. `sheetmetal_drawing.py` is pure Python and DXF-independent.
5. Full regression remains green.
