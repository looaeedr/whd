# Generic FeatureSurface / HoleRegion Design

## Goal
Any valid sheet-metal panel outline may become a hole-capable `FeatureSurface`. Hole legality is determined by the complete feature footprint, not by its center point or part name.

## Core model
`FeatureSurface(surface_id, outline, polygon, allow_features)` stores the authoritative polygon in feature-world coordinates. The engine contains no allow-list for Head, Tail, Door, Base Plate, Box Body, or Indicator parts.

## Boundary rule
A circle is represented by its actual radius footprint and a rectangle by its full rectangle footprint. A feature is legal only when `surface.polygon.covers(feature_footprint)` is true. Boundary tangency is allowed; any material outside the surface is rejected.

## Interaction rule
Placement validates before insertion. Dragging uses immutable `move_feature_within_surface`; an invalid move returns the previous feature so the object stops at its last legal position. Exact X/Y edits, semantic-anchor edits, and patterns use the same validation path.

## Surfaces
- Head/Tail keep the existing finished-face coordinate system and use the blue finished-face frame as their FeatureSurface.
- Box Body, Door, Base Plate use the authoritative `StructuralGeometryResult.outline` directly.
- Indicator Box / Indicator Door use the authoritative primary closed CUTTING polyline already present in their DrawingScene.

## GUI
Head/Tail retain their dedicated editor. Other major panels use a common simplified editor opened by right-click: select feature type, click, drag, exact X/Y, delete. Main previews render the same user features in orange.

## DXF
Direct Door/Box/Base/Indicator builders accept the same generic user Feature objects, validate them against the authoritative surface, resolve to world-space primitives, and serialize through DrawingScene. Stretched Door also validates against its primary CUTTING surface. End-cap exporters independently validate finished-face user holes before mapping to unfolded coordinates.

## Non-goals
No full sketch constraint solver, no CAM kerf/overcut compensation, no duplicated per-part boundary formulas, no Canvas-pixel persistence.
