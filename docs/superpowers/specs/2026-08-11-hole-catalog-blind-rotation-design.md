# Hole Catalog / Blind Hole / Rotation Design

## Goal
Drive user hole choices from `基準檔/開孔/` while preserving manufacturing semantics: ordinary holes cut through on CUTTING, pipe holes are blind holes on BLIND_HOLE, and profile holes may rotate by 90/180/270/360 degrees.

## Files and catalog
- Move `基準檔/管孔尺寸清單.csv` to `基準檔/開孔/管孔尺寸清單.csv`.
- Read `基準檔/開孔/開孔.csv` as the ordinary CUTTING catalog.
- A row with one numeric size means a circular CUTTING hole.
- A row with two numeric sizes means a rectangular CUTTING hole.
- A row whose size is a filename means load that DXF from the same `基準檔/開孔/` directory and use its CUTTING profile as the hole geometry.
- Pipe catalog entries are always BLIND_HOLE, never MARKING.

## Processing layers
- CUTTING: through-cut hole geometry.
- BLIND_HOLE: blind-hole geometry, Color 1, CONTINUOUS.
- DATUM remains the semantic layer for center/reference lines.
- MARKING remains engraving/marking only.

## Feature model
Add profile feature support and an explicit `rotation_deg` on directional features. Rotation is normalized to 0/90/180/270 where user-facing 360 means 0. Circle and pipe-hole geometry may retain rotation data but UI disables rotation because it has no geometric effect.

## Boundary validation
FeatureSurface containment uses the fully rotated footprint. A profile or rectangle is legal only when its rotated footprint is fully covered by the owning surface polygon.

## GUI
- Fix the stray `draw_hole_editor_hint(canvas, cw, ...)` call in `update_calculations()` that prevents startup.
- Hole chooser lists ordinary CUTTING catalog entries and blind pipe entries with clear labels.
- Directional holes expose 90/180/270/360 rotation.
- Existing free-size circle/rectangle workflows remain available for compatibility.

## DXF profile loading
The catalog loader reads closed CUTTING LWPOLYLINE/POLYLINE geometry from the referenced profile DXF, normalizes it around its geometric bounding-box center, and rejects missing/empty/invalid profiles with a clear error. No Canvas pixels enter manufacturing data.
