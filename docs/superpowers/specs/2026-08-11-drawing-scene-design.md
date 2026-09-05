# DrawingScene Single-Serializer Design

**Date:** 2026-08-11

## Goal

Make every DXF-writing path in `ae.py` consume one pure `DrawingScene` so structural CUTTING/BEND, resolved features, and CHECK/STOCK/DATUM are serialized by one implementation.

## Boundaries

- `sheetmetal_geometry.py`: structural geometry only.
- `sheetmetal_features.py`: physical features / factory feature policy.
- `sheetmetal_part_adapters.py`: legacy parameters -> structural result.
- `sheetmetal_drawing.py`: drawing primitives + scene assembly.
- `ae.py`: DXF document/layer setup, dispatch, scene serialization, save.

No `ezdxf` dependency may enter `sheetmetal_drawing.py`.

## Scene API

Add pure primitives:

- existing `PolylinePrimitive`
- existing `LinePrimitive`
- new `CirclePrimitive`
- existing `TextPrimitive`

Add `DrawingScene`:

```python
@dataclass
class DrawingScene:
    primitives: list[DrawingPrimitive]

    def add(self, primitive): ...
    def extend(self, primitives): ...
```

Provide conversion helpers:

```python
structural_result_to_primitives(result)
resolved_features_to_primitives(features)
legacy_geom_to_primitives(geom)
```

`legacy_geom_to_primitives` is a compatibility bridge for stretched/baseline paths. It does not become a permanent geometry model.

## Serialization

`ae.py` has exactly one generic serializer:

```python
_add_drawing_scene_to_dxf(msp, scene)
```

It handles Polyline / Line / Circle / Text, including semantic layer color defaults for MARKING and explicit primitive colors.

No exporter should call `msp.add_lwpolyline`, `msp.add_line`, `msp.add_circle`, or `msp.add_mtext` for production drawing geometry outside this serializer.

Layer creation remains in `setup_dxf_layers()`.

## Direct Exporters

Each direct exporter builds a scene in this order:

1. optional STOCK
2. structural CUTTING/BEND converted from `StructuralGeometryResult`
3. resolved features
4. CHECK/DATUM drawing primitives
5. serialize scene
6. save

Order must not affect geometry semantics, but preserving current ordering simplifies DXF regression.

## Stretched Exporters

Existing `geom = {'polylines': ..., 'lines': ..., 'circles': ...}` remains as an internal baseline-mapping representation in this phase.

Before writing DXF:

```text
legacy geom
→ legacy_geom_to_primitives()
→ DrawingScene
→ common serializer
```

No stretched exporter may contain separate loops over `geom['polylines']`, `geom['lines']`, or `geom['circles']` after migration.

## Features

`ResolvedCircle` / `ResolvedRect` are converted to drawing primitives before serialization. `ae.py` no longer needs a dedicated feature serializer.

MARKING centerlines become `LinePrimitive`s in the same scene.

## Colors

Semantic defaults are centralized in scene conversion / serializer:

- `MARKING`: 211 when no explicit color is supplied.
- CUTTING feature primitives may retain color 3 to preserve current output.
- DATUM explicit color 6 remains supported.

Core structural CUTTING/BEND rely on configured DXF layer colors unless a primitive explicitly overrides color.

## Non-goals

- Do not replace baseline feature recognition.
- Do not change structural formulas.
- Do not change GUI behavior.
- Do not redesign DXF layers.
- Do not add CAM compensation.

## Verification

- All existing tests remain green.
- New tests cover scene aggregation and all four primitive types.
- DXF round-trip verifies representative Door, BoxBody, BasePlate, Indicator, Head, Tail output and layer counts.
- Source audit: production `msp.add_*` drawing calls exist only in `setup`/single serializer, not individual exporters.
