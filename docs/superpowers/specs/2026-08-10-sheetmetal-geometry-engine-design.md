# 2D Sheet-Metal Geometry Engine Design

Date: 2026-08-10

## Goal

Replace panel-type-specific CUTTING point assembly with a reusable 2D sheet-metal geometry engine. The engine must derive corner geometry from bend/flange topology and generate relief polygons that are subtracted from a base blank. Manufacturing-specific assembly rules remain explicit rules layered on top of generic geometry; they must not be hidden in hard-coded perimeter coordinates.

The first regression case is the existing end-cap/tail geometry in `ae.py.pre_corner_relief`. The previous parity-only implementation is explicitly not a correctness target.

## Why this change

The current end-cap exporter computes notch dimensions inside `export_end_cap_dxf()` and directly assembles a 16-point stepped outline. That works only while each corner shape is known in advance. As more sheet-metal types are added, this forces one-off point sequences and repeated manual formula work.

FreeCAD SheetMetal is used as an architectural reference, not copied as a 3D dependency. The reusable ideas are: resolve theoretical corner intersections, represent bend/flange adjacency explicitly, and generate relief/cut geometry from those relationships. FreeCAD's 3D Part/OCC solids, GUI, and K-factor-based unfold placement are out of scope for the first 2D engine.

## Scope of v1

### In scope

1. Pure-Python 2D geometry primitives for bend lines, flanges, corners, and relief polygons.
2. Infinite-line intersection and line extension helpers with tolerance handling.
3. A topology model that can describe one-, two-, or later multi-fold chains without naming a panel type.
4. Relief rules that return polygons/rectangles in a local corner coordinate system.
5. Polygon subtraction to produce the final CUTTING outline.
6. One manufacturing rule for the confirmed end-cap/tail insertion geometry, implemented as a rule rather than as a 16-point perimeter.
7. Regression tests for T=2.0 and T=1.5, asymmetric left/right fold lengths, and independently overridden left/right clearances.
8. Existing BEND, holes, CHECK, STOCK and unrelated exporters remain behaviorally unchanged unless their coordinates depend on the corrected CUTTING geometry.

### Out of scope

1. Full 3D sheet-metal modeling.
2. OpenCascade/FreeCAD runtime dependency.
3. Automatic inference of assembly intent from arbitrary DXF alone.
4. General K-factor/unfold replacement.
5. Rewriting all panel types in one pass.

## Architecture

Create a focused module `sheetmetal_geometry.py`.

### Data objects

#### `Vec2`
A lightweight immutable 2D point/vector representation. Tuples may be accepted at public boundaries, but engine internals use explicit vector helpers.

#### `BendLine`
Fields:
- `name`
- `p1`, `p2`
- `side` or normal/orientation metadata when known

Responsibilities:
- direction vector
- normalized direction
- theoretical infinite-line intersection with another bend
- optional finite segment bounds for validation

#### `Flange`
Fields:
- `name`
- `bend`
- `length`
- `parent`
- `child_bends`
- optional insertion/assembly role metadata

A flange is a geometric/topological entity, not a panel-type label.

#### `Corner`
Fields:
- `name`
- participating bends/flanges
- theoretical corner point
- local orthogonal axes (`u`, `v`)
- quadrant/material-side information

Responsibilities:
- convert local relief offsets to world coordinates
- validate that the selected bends are non-parallel and geometrically coherent

#### `ReliefPolygon`
Fields:
- polygon geometry
- rule name
- source corner
- metadata describing calculated dimensions

The polygon is the only artifact passed to the outline subtraction stage.

### Topology

Represent fold chains explicitly, e.g. the end-cap top edge:

`panel -> top_bend_1 -> top_flange_1 (ytop1) -> top_bend_2 -> top_flange_2 (FW)`

Left/right/bottom edges may each have independent single-fold chains. The model allows more chain nodes later without changing the corner engine.

The v1 topology builder may be constructed from known exporter dimensions. Automatic extraction from arbitrary DXF is a later stage.

## Geometry flow

1. Build the unnotched base blank polygon from the calculated flat width/depth.
2. Build bend lines from existing flat-pattern dimensions.
3. Resolve theoretical corner intersections from bend lines.
4. Build `Corner` objects and local axes.
5. Evaluate relief rules against each corner/topology context.
6. Each matching rule returns one or more relief polygons.
7. Union all relief polygons.
8. Subtract the union from the base blank using Shapely.
9. Validate result: non-empty, valid, one expected exterior for the end-cap regression case, no self-intersections, positive area.
10. Convert resulting exterior coordinates to DXF CUTTING polyline.

## Rule system

Rules must answer two questions separately:

1. **When does this rule apply?** — topology/assembly condition.
2. **What material is removed?** — relief polygon from physical dimensions.

No rule is allowed to directly return a full panel perimeter.

### Generic rules planned

- simple single-fold corner relief
- fold-chain corner relief
- junction/gap relief
- assembly/insertion relief

Only the assembly rule needed by the current end-cap is required in v1; the interfaces are designed so the other rules can be added without changing `OutlineBuilder`.

## End-cap/tail assembly rule: first regression rule

This rule captures the manufacturing behavior confirmed in discussion, but does not name a specific panel type internally.

Inputs:
- thickness `T`
- top first fold `ytop1`
- top second fold/frame width `FW`
- left fold `yl1`
- right fold `yr1`
- bottom fold `ybottom1`
- top secondary X clearance, default `0.5T`, common with optional per-side override
- top secondary insertion depth, default `2T`, common with optional per-side override
- bottom clearance, default `0.5T`, common with optional per-side override

Confirmed geometry:

### Top primary relief
- left width: `abs(yl1) + FW`
- right width: `abs(yr1) + FW`
- height: `ytop1 + FW - T`

Purpose: retain `1T` material relationship needed for a flush front after assembly.

### Top secondary relief
- left width from the left fold side: `abs(yl1) + left_secondary_extra`, default extra `0.5T`
- right width from the right fold side: `abs(yr1) + right_secondary_extra`, default extra `0.5T`
- insertion-relief height: default `2T`
- rectangular, directly connected below the primary relief, then reconnects to the original side-fold edge

Purpose: allow the left/right end-cap flanges to pass the box body's upper sheet thickness in the depth direction.

### Bottom relief
- left width: `abs(yl1) + left_bottom_extra`, default extra `0.5T`
- right width: `abs(yr1) + right_bottom_extra`, default extra `0.5T`
- height: `ybottom1 + bottom_extra` (common default `0.5T`; per-side X overrides do not change Y unless a dedicated Y override is supplied later)
- single rectangular stage only

Purpose: assembly clearance; no upper-style retaining/secondary stage.

### Symmetry
Left/right defaults are symmetric but all X-clearance and secondary-depth values can be independently overridden. Left/right fold lengths are inherently independent.

## Configuration migration

Do not silently reinterpret the existing INI keys in place because `bottom_gap=0.5` currently means an absolute 0.5 mm while the new manufacturing default is `0.5T`.

Add new explicit factor-based keys, for example:

```ini
[RELIEF]
top_secondary_x_factor = 0.5
top_secondary_depth_factor = 2.0
bottom_x_factor = 0.5
bottom_y_factor = 0.5
```

Optional side-specific override keys remain absent by default; when absent, the common factor is used.

Legacy `[NOTCH]` keys remain readable for compatibility during migration, but new geometry uses the new relief configuration. A deprecation comment/warning may be added without breaking startup.

## Integration with `ae.py`

`export_end_cap_dxf()` remains responsible for:
- resolving user/config dimensions
- calculating total flat width/depth
- creating the DXF document/layers
- drawing BEND, holes, STOCK, CHECK
- writing output

It will no longer assemble CUTTING as a literal point list.

Instead it will:

1. create an end-cap topology description from dimensions;
2. call the geometry engine to build the final outline polygon;
3. convert the polygon exterior to a DXF lightweight polyline.

`zl1/zr1` must not participate in the top end-cap primary relief formula. They may remain in the public function signature temporarily for backward compatibility, then be deprecated separately.

## Error handling and validation

The engine raises specific geometry errors for:
- parallel/non-intersecting theoretical bend definitions where an intersection is required
- zero/negative thickness
- negative fold lengths after normalization
- relief polygon outside the blank beyond tolerance
- relief removing the whole blank
- invalid or multi-part output where a single exterior is required

Tolerance defaults are centralized; no ad-hoc `1e-9` parity guard is used as a correctness criterion.

If Shapely repairs are needed, use the existing project's `make_valid`/`buffer(0)` strategy only after preserving the original error context. Silent repair is not the first step.

## Testing strategy

Tests are geometry-first and independent of ezdxf where possible.

### Primitive tests
- horizontal/vertical intersection
- arbitrary-angle intersection
- parallel lines rejected
- local/world coordinate transforms

### End-cap rule tests
- current common case: `T=2`, `ytop1=16`, `FW=25`, `yl1=yr1=15`
- thickness scaling: `T=1.5`
- asymmetric folds: e.g. left 15/right 20
- shared relief factors
- independent left/right overrides
- top primary relief uses `yl1/yr1`, never `zl1/zr1`
- top secondary relief is fold length + clearance, not fold length - clearance
- bottom clearance scales with T

### Outline tests
- polygon valid
- expected notch step count/topology for the regression case
- no self-intersections
- bend lines stay inside intended material regions
- DXF CUTTING polyline is closed

### Non-regression
Existing calculations and unrelated exporters are imported and exercised with smoke tests where practical. The old 16-point coordinates are not treated as golden output because some legacy formulas are known to be wrong.

## Migration sequence

1. Add pure geometry module + tests.
2. Add end-cap topology builder + assembly relief rule.
3. Validate numerical geometry against the confirmed manufacturing formulas.
4. Switch only end-cap/tail CUTTING generation to the engine.
5. Keep a feature flag or easy rollback path for one migration cycle if needed.
6. Once stable, migrate the next sheet-metal type by topology/rule, not by adding another perimeter builder.

## Success criteria

- End-cap/tail CUTTING no longer contains a manually assembled 16-point perimeter.
- Current confirmed end-cap geometry is generated from topology + relief polygons.
- Changing T from 2.0 to 1.5 automatically scales factor-based clearances.
- Left/right fold lengths and relief overrides can differ without new code branches.
- A second sheet-metal type can be added by constructing topology and selecting/adding a relief rule, without modifying the outline builder.
- No FreeCAD runtime dependency is introduced.
