# GUI Overlay / Guide Single-Source Design

**Date:** 2026-08-11
**Scope:** Remaining GUI dimension text, auxiliary guides, STOCK/DATUM preview, and fixed manufacturing overlays.

## Goal

Finish separating presentation-only Canvas drawing from design/manufacturing geometry.

The GUI may choose colors, fonts, dash styles, padding, and label placement. It must not independently derive manufacturing feature coordinates, usable-face boundaries, or design dimensions that are also used by DXF/export logic.

## Classification

### Presentation-only: may stay in `gui.py`

- Canvas background grid.
- Preview padding and zoom/scale.
- Width/height text placement around the preview.
- Legend/info text and colors.
- STOCK visibility toggle and Canvas styling.
- Display of the structural result bounding rectangle when it is derived directly from `result.width/result.height`.

These do not become manufacturing data merely because they are drawn with coordinates.

### Design/manufacturing data: must leave `gui.py`

- End-cap fixed hanging holes, square opening, and tail bottom hole.
- Door-indicator positioning dimensions and interaction envelope.
- Base-plate mounting holes.
- Hole-editor finished-face / bend-safe guide rectangle.
- Any future DATUM geometry that is exported to DXF.

## Chosen Architecture

Do **not** create a second geometry engine.

Extend the existing pure modules with two concepts:

1. `sheetmetal_features.py` remains authoritative for physical holes/cutouts/marking features.
2. Add a small pure preview/design guide model for non-DXF guides that have design meaning.

Proposed types:

```python
@dataclass(frozen=True)
class RectGuide:
    min_point: Vec2
    max_point: Vec2
    role: str

@dataclass(frozen=True)
class DimensionGuide:
    start: Vec2
    end: Vec2
    value: float
    axis: str
```

These types contain world-space geometry only. They contain no Canvas color/font/tag information.

## End-cap Fixed Features

Move the current fixed feature formulas out of both `ae.py` and `gui.py` into one resolver:

```python
resolve_vault_endcap_fixed_features(
    result: StructuralGeometryResult,
    *,
    thickness: float,
    bottom_fold: float,
    frame_width: float,
    hanging_hole_radius: float,
    hanging_hole_offset_from_primary: float,
    hanging_hole_y_from_top_bend: float,
    square_hole_origin: Vec2,
    square_hole_size: Vec2,
    tail_bottom_hole_radius: float,
    tail_bottom_hole_y: float,
    is_tail: bool,
) -> tuple[ResolvedFeature, ...]
```

Both DXF export and GUI preview serialize/render the same resolved features.

This keeps vault-specific placement in a Vault feature policy, not in generic topology.

## Hole Editor Guide

The current GUI computes:

```text
left   = 2T
right  = W - 2T
bottom = 2T
top    = D - T
```

for the blue "折彎內部區域" rectangle.

That rectangle is a design-space guide, not just a Canvas decoration. Move it to:

```python
resolve_endcap_finished_face_guide(width, depth, thickness) -> RectGuide
```

The GUI only renders the returned world-space guide.

This phase preserves the current guide definition exactly; it does not reinterpret whether the rule is universally valid outside the current Vault workflow.

## STOCK

STOCK is a manufacturing/export layer but its current preview geometry is exactly the structural blank bounding rectangle.

Therefore:

```text
Preview STOCK rectangle = (0,0) .. (result.width,result.height)
```

No extra geometry model is needed unless future STOCK becomes larger than the structural blank.

DXF STOCK serialization remains in `ae.py` for now.

## DATUM

DATUM exported geometry must never be invented by `gui.py`.

If the GUI later previews DATUM, it must consume the same world-space DATUM primitives used by DXF.

This phase audits DATUM and adds no GUI DATUM preview if none currently exists.

## Dimension Text

Generic W/H preview labels are presentation-only:

```text
W = result.width
H = result.height
```

They may stay in `gui.py`.

Part-specific design dimensions (for example Door Indicator X/Y positioning) must come from a shared `DimensionGuide` / layout result and may not be recomputed in Canvas code.

## Error Handling

- Feature/guide resolvers validate non-negative dimensions and positive thickness where required.
- GUI receives already-resolved world geometry.
- Rendering failures must not silently fall back to duplicate coordinate formulas.

## Testing

Pure tests:

- Vault end-cap fixed feature coordinates match current T=2 behavior.
- T=1.5 uses the same policy correctly where thickness participates.
- Head vs tail feature count differs only by the tail bottom hole.
- End-cap finished-face guide matches current `2T / W-2T / 2T / D-T` behavior.
- Door indicator dimension guides remain unchanged.
- Base-plate mounting-hole resolver remains unchanged.

Integration tests:

- GUI and DXF use the same end-cap fixed feature resolver.
- No end-cap fixed-hole coordinate formulas remain in `gui.py`.
- No duplicated fixed-hole formulas remain in `ae.py` outside serialization/config adaptation.
- `pytest -q` and `py_compile` remain green.

## Non-Goals

- No Tkinter layout redesign.
- No CAM/kerf/over-cut logic.
- No change to existing Vault manufacturing dimensions.
- No attempt to generalize the Vault finished-face guide to all enclosure families.
- No new GUI DATUM visualization unless existing behavior already requires it.

## Success Criterion

After this phase:

```text
Structural geometry -> sheetmetal_geometry / part adapters
Physical features   -> sheetmetal_features
Design guides       -> pure world-space guide resolver
Canvas styling      -> gui.py only
DXF serialization   -> ae.py only
```

`gui.py` may place pixels, text, colors, and arrows, but it must not own manufacturing/design coordinate formulas.
