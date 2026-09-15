# GUI Hole / Feature Engine Design

**Date:** 2026-08-10  
**Scope:** WHD `new-engine`, current manufacturing baseline is the Vault/Safe-type enclosure family.

## Goal

Make GUI hole preview and DXF hole output consume the same resolved feature geometry, while preserving the current user workflows.

The GUI must stop owning manufacturing coordinates. Canvas pixels are presentation only.

## Current Sources Found

The current code has three structural feature sources:

1. **End-cap user holes**
   - `head_holes` / `tail_holes`
   - circle, rectangle, pipe blind hole, AS, VS
   - edited in `open_hole_editor()`
   - currently stores raw `{x, y, type, params}` dictionaries in finished/projection coordinates
   - `ae._add_user_holes_to_dxf()` performs a separate finished-face → unfolded mapping

2. **Door indicator/nameplate/marking features**
   - GUI preview calculates hole coordinates itself
   - `ae.py` also calculates/export them
   - drag offsets are maintained independently in GUI state

3. **Baseline-mapped features**
   - `get_mapped_circles_from_baseline()`
   - already derives placement from the current StripFoldChain / bend anchors
   - should remain supported, but its output should be normalized into the same feature result model

## Chosen Architecture

Use a new pure module:

```text
sheetmetal_features.py
```

It must not import `tkinter` or `ezdxf`.

### Core data types

```python
FeatureAnchor
CircleFeature
RectFeature
ResolvedCircle
ResolvedRect
FeaturePattern
```

A feature stores design intent, not Canvas pixels.

Example:

```python
CircleFeature(
    diameter=22.0,
    anchor=FeatureAnchor.PANEL_CENTER,
    offset=Vec2(100.0, -50.0),
    layer="CUTTING",
)
```

### Coordinate spaces

Explicitly separate:

```text
Finished Face Space
Unfolded Geometry Space
Canvas Pixel Space
```

Rules:

- Feature placement data is defined in Finished Face Space where appropriate.
- Resolver maps Finished Face → Unfolded coordinates.
- Canvas renderer maps Unfolded coordinates → pixels.
- Canvas pixel coordinates are never persisted as feature data.

### World/canvas transform

Create one reusable transform object/helper:

```python
CanvasTransform.world_to_canvas(Vec2) -> tuple[float, float]
CanvasTransform.canvas_to_world(x, y) -> Vec2
```

All GUI outline, bends, holes, hit-testing, drag offsets, and dimension overlays should eventually use it.

## Feature Resolver

`sheetmetal_features.py` owns placement rules.

Proposed interface:

```python
resolve_features(part_geometry, features) -> list[ResolvedFeature]
```

For end-cap finished-face holes, provide a dedicated mapping context using the actual structural geometry/bend boundaries rather than repeating formulas in `gui.py` and `ae.py`.

For baseline circles, wrap existing mapped coordinates as `ResolvedCircle` instead of rewriting the baseline algorithm in this phase.

## DXF Boundary

`ae.py` receives resolved features and serializes them:

```text
ResolvedCircle(CUTTING) -> add_circle
ResolvedCircle(MARKING) -> add_circle / optional cross line
ResolvedRect(CUTTING)   -> lwpolyline
```

`ae.py` must not recalculate placement geometry after resolution.

## GUI Boundary

`gui.py`:

1. builds/edits Feature definitions,
2. requests resolved features,
3. renders `ResolvedFeature` through `CanvasTransform`,
4. performs hit-testing using the resolved world coordinates.

Existing GUI workflows remain:

- double-click end-cap to edit holes,
- current list editor,
- door indicator drag,
- baseline feature preview.

This phase changes their geometry source, not the user's workflow.

## Anchor Strategy

Phase 1 supports a small, stable set:

```text
ABSOLUTE_FINISHED_FACE
PANEL_CENTER
TOP_LEFT
TOP_RIGHT
BOTTOM_LEFT
BOTTOM_RIGHT
```

Do not add large semantic anchor catalogs yet.

Existing end-cap user holes are migrated initially as `ABSOLUTE_FINISHED_FACE` so current saved/entered X/Y behavior remains unchanged.

Door indicator group can use `PANEL_CENTER + offset`.

## Patterns

Do not explode repeated design intent into independent hard-coded GUI coordinates.

Introduce lightweight:

```python
LinearPattern
GridPattern
```

only where the existing door indicator/nameplate logic already represents repeated patterns. Do not migrate unrelated feature generation in this phase.

## Layer / Manufacturing Semantics

The feature module may carry semantic output layer names:

- `CUTTING`
- `MARKING`

It must not perform DXF serialization.

Important boundary:

Structural assembly relief remains in `sheetmetal_geometry.py`.

Feature engine handles:
- holes,
- rectangular cutouts,
- blind/marking holes,
- user-defined openings,
- repeated hole patterns.

CAM-only kerf, over-cut, slit compensation, or machine-specific relief remains outside both geometry modules.

## Migration Order

1. Add pure feature model + tests.
2. Add finished-face/unfolded resolver for end-cap holes.
3. Refactor `_add_user_holes_to_dxf()` to serialize resolved features only.
4. Refactor `open_hole_editor()` preview/hit-test to use the same resolved features.
5. Add shared `CanvasTransform`; migrate end-cap hole editor first.
6. Normalize baseline-mapped circles to `ResolvedFeature`.
7. Move door indicator/nameplate repeated-hole geometry into feature resolver.
8. Replace door GUI preview hole calculations with resolved features.
9. Expand shared CanvasTransform to structural preview drawing after feature path is stable.

## Compatibility Rules

- Existing end-cap X/Y inputs keep their current finished/projection coordinate meaning.
- Existing pipe-hole blind marking remains `MARKING`.
- Existing AS/VS/circle holes remain `CUTTING`.
- Existing rectangular holes remain `CUTTING`.
- Existing baseline mapping behavior is preserved before refactoring its internals.
- No GUI interaction behavior is intentionally removed in this phase.

## Tests

Pure tests must cover:

- circle/rectangle feature resolution,
- finished-face → unfolded mapping,
- T=2 and T=1.5,
- asymmetric end-cap left/right folds,
- anchors and offsets,
- world↔canvas round-trip,
- pattern expansion,
- CUTTING vs MARKING semantics.

Integration tests must verify:

- GUI-side resolved hole coordinates equal DXF-side resolved coordinates,
- end-cap existing hole cases preserve expected output,
- baseline mapped circles remain at the same unfolded coordinates,
- door indicator drag changes feature offset once and both preview/export consume it.

## Non-Goals

This phase does not:

- redesign the Tkinter layout,
- replace baseline feature recognition,
- introduce CAM kerf/over-cut compensation,
- rewrite structural `sheetmetal_geometry.py`,
- add arbitrary new hole types not already needed by the project.

## Success Criterion

There is exactly one authoritative path for hole placement:

```text
Feature Definition
→ Feature Resolver
→ ResolvedFeature
   ├─ GUI Preview
   └─ DXF Writer
```

No production hole coordinate formula should need to be duplicated in `gui.py` and `ae.py`.
