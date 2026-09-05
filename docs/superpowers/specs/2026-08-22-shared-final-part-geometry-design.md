# Shared Final Part Geometry Design

## Goal
Eliminate geometry drift between the 2D/corner/opening preview and Phase6 3D. A part's final manufacturing geometry is built once from one canonical PartSpec path and exposed as PartRenderData(scene, material). 2D and 3D are consumers only.

## Architecture
1. GUI owns the canonical conversion from current/draft part state to PartSpec.
2. GUI owns one authoritative PartRenderData cache keyed by the canonical PartSpec + ManufacturingContext.
3. Existing main-GUI PartSpec helpers and the Fold Designer callback use the same canonical builder; the Fold Designer callback must not duplicate Door/EndCap/etc construction formulas.
4. 2D geometry drawing for supported parts uses PartRenderData.scene for CUTTING/BEND/MARKING/BLIND_HOLE instead of rebuilding/merging structural, baseline and feature geometry separately.
5. 3D consumes the exact PartRenderData.scene and PartRenderData.material returned by the same GUI provider. It may fold/triangulate material and project operation graphics, but it must not resolve baseline, holes or corner semantics.

## Draft editing
The Fold Designer can have uncommitted settings. Its payload is treated as draft state only. The GUI canonical PartSpec builder accepts that state and produces a normal PartSpec using the same field mapping as committed state. This preserves live 3D editing without a second manufacturing implementation.

## Cache and invalidation
The authoritative render cache stores immutable PartRenderData. Any settings/feature/corner mutation clears it. Identical committed or draft PartSpecs reuse the same object. Cache size remains bounded.

## Door requirement
A Door baseline handle opening, fixed hole, user hole, indicator opening and CornerType cut must all exist in the same final DrawingScene/material. If 2D shows a CUTTING contour, 3D receives the same material with that contour removed.

## Testing
- Source guard: Fold Designer render callback contains no direct PartSpec constructors.
- Canonical spec equivalence: committed Door state and equivalent draft payload build equal DoorPartSpec values.
- Shared render identity: equal PartSpec/context queries return the same cached PartRenderData object.
- 2D Door preview renders the authoritative final scene rather than separately overlaying baseline + user features.
- Existing handle-opening regression remains green.
- Full pytest and py_compile pass from the packaged ZIP.

## Non-goals
- No change to manufacturing dimensions, CornerType formulas, baseline files or fold_designer_original.py.
- No redesign of GUI layout.
- No new hole classification rules in 3D.
