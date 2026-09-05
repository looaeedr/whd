# CAD-style Feature Placement Design

## Goal

Replace coordinate-first end-cap hole editing with a CAD-style placement workflow while preserving the existing Feature/Resolver/DrawingScene architecture and all existing hole types.

The primary workflow becomes:

`choose hole type -> click finished face -> auto anchor -> resolved preview -> drag or edit dimensions -> optional pattern -> DXF`

GUI pixels remain presentation-only. Manufacturing geometry remains owned by `sheetmetal_features.py` and consumed by GUI and DXF through the existing shared resolver path.

## Scope

Phase 1 targets the existing head/tail hole editor only. The reusable placement APIs must be generic enough for later reuse by door/base/other panels, but this phase does not migrate those editors.

Existing hole types remain supported:

- 圓形
- 方形
- 管孔
- AS
- VS

Existing persisted `head_holes` / `tail_holes` dictionaries remain readable and writable. No file-format migration is required in this phase.

## Interaction Model

### Placement mode

Selecting a hole type arms placement mode. A click on the valid finished-face area creates one feature at the clicked world position.

The clicked point is converted through `CanvasTransform.canvas_to_world()` and clamped to the valid finished-face guide before placement.

### Automatic anchor selection

For every new or dragged feature, the placement controller selects the closest useful anchor from:

- `PANEL_CENTER`
- `TOP_LEFT`
- `TOP_RIGHT`
- `BOTTOM_LEFT`
- `BOTTOM_RIGHT`

`ABSOLUTE_FINISHED_FACE` remains supported for legacy data, but new point-placed holes prefer a semantic anchor.

Anchor selection uses normalized world-space distance and a deterministic tie-break order. It does not depend on canvas zoom.

The stored design intent is:

`Feature(anchor=<semantic anchor>, offset=<world-mm offset>)`

The GUI may still persist the existing absolute `x/y` dictionary for compatibility, but it must derive that compatibility representation from the authoritative Feature placement result rather than calculate a second placement formula.

### Smart guides

When placing or dragging, the GUI shows:

- current anchor label
- horizontal distance from the anchor/reference side
- vertical distance from the anchor/reference side
- optional alignment guide through panel center when within snap tolerance

Guides are display data. Their world-space endpoints and values are created by pure feature-placement helpers, not by canvas formulas.

### Selection and dragging

Existing world-space feature hit-testing remains authoritative.

Mouse press on a feature selects it. Mouse drag converts the cursor to world coordinates, clamps it to the finished-face guide, then updates the feature placement through the placement controller. The same resolved Feature is immediately re-rendered.

Dragging never stores pixels.

### Numeric editing

The right-side editor exposes:

- Anchor selector
- X offset / horizontal distance
- Y offset / vertical distance
- feature size parameters

Changing Anchor preserves the feature's current absolute world center, recalculating only its offset relative to the new anchor.

Changing an offset updates the same Feature definition used by preview and DXF.

### Pattern

Phase 1 supports two patterns:

- Linear: horizontal or vertical, count + pitch
- Grid: rows + columns + X/Y pitch

The source feature is the first pattern member. Pattern expansion is pure feature logic and produces multiple Feature definitions before resolution.

Pattern generation does not create a new geometry engine and does not store canvas coordinates.

## Pure Placement API

Add to `sheetmetal_features.py`:

- `FeaturePlacement` — semantic anchor + offset + absolute finished-face point
- `PlacementGuideSet` — anchor and dimension/alignment guides
- `choose_feature_anchor(point, width, height) -> FeatureAnchor`
- `placement_from_finished_point(point, width, height, preferred_anchor=None) -> FeaturePlacement`
- `reanchor_feature(feature, new_anchor, width, height) -> Feature`
- `move_feature_to_finished_point(feature, point, width, height) -> Feature`
- `build_feature_placement_guides(feature, width, height) -> PlacementGuideSet`
- `expand_linear_pattern(feature, count, pitch, axis) -> tuple[Feature, ...]`
- `expand_grid_pattern(feature, rows, columns, pitch_x, pitch_y) -> tuple[Feature, ...]`

All functions are pure and have no tkinter/ezdxf dependency.

## GUI Boundary

`gui.py::open_hole_editor()` owns only:

- toolbar/widgets
- mouse/key events
- world/pixel transform
- rendering resolved features and placement guides
- converting current Feature back to the legacy hole dictionary at compatibility boundaries

It must not own anchor geometry or pattern coordinate formulas.

A small editor-local state may contain:

- active placement type
- selected feature index
- drag state
- pattern settings

## Compatibility

- Existing saved `x/y` positions load at identical positions.
- Pipe blind holes remain `MARKING` with centerline.
- AS/VS/circle remain `CUTTING` circles.
- Rectangular holes remain `CUTTING` rectangles.
- Finished-face -> unfolded mapping is unchanged.
- DXF serialization is unchanged.
- Existing listbox-based selection and deletion remain available.
- Existing exact numeric coordinate entry remains available as a compatibility/editing path, but is no longer the primary placement workflow.

## Validation and Clamping

A placed feature center is clamped to the valid finished-face `RectGuide`.

Phase 1 clamps the center only, matching current semantics. It does not attempt automatic edge-clearance enforcement based on hole radius/rectangle half-size; that is a later manufacturing-validation policy if required.

Invalid numeric input leaves the current feature unchanged and uses the existing GUI validation/error path.

Pattern count must be >= 1. Pitch values may be positive or negative so direction is expressible without a second coordinate system.

## Tests

Pure tests:

- anchor selection at center and four corners
- anchor choice invariant to canvas scale (world-only function)
- placement from point reconstructs identical absolute point
- re-anchoring preserves absolute center
- moving a feature updates offset but preserves feature type/layer/size
- guide values/endpoints for all anchor families
- linear pattern expansion horizontal/vertical
- grid expansion row/column counts and pitch
- legacy feature -> semantic placement -> absolute point compatibility

GUI/source tests:

- `open_hole_editor()` uses placement helpers rather than anchor formulas
- click placement routes through canvas-to-world then placement helper
- drag path routes through placement helper
- pattern UI calls pure pattern helpers
- no persistence of canvas pixel coordinates

Regression:

- complete existing suite stays green
- head/tail legacy hole export remains identical in layer/type/count
- DXF round-trip for representative head and tail

## Non-goals

- Full sketch constraint solver
- Coincident/parallel/perpendicular/tangent constraints
- Arbitrary reference-to-reference constraints
- CAM clearance/kerf validation
- Changing DXF layer semantics
- Migrating every other part editor in the same phase

## Success Criteria

The end-cap user can create a hole without typing X/Y first: select type, click the face, then drag or edit semantic dimensions.

There is exactly one placement calculation path:

`Canvas event -> world point -> FeaturePlacement -> Feature -> Resolver -> GUI/DXF`

No manufacturing coordinate is derived from canvas pixels, and no second GUI-only hole placement formula is introduced.
