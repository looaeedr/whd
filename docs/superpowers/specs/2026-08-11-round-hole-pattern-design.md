# Round Hole Pattern Design

## Goal
Extend the unified hole editor with a dedicated round-hole arrangement workflow while keeping the existing nine-anchor positioning workflow intact. The last workflow whose Confirm button is pressed becomes authoritative when the two workflows conflict.

## Catalog layout
The left side of the unified editor shows two visible catalog lists sourced from the existing catalog loader:
- `一般開孔`: entries originating from `基準檔/開孔/開孔.csv`.
- `管孔清單`: entries originating from `基準檔/開孔/管孔尺寸清單.csv`.

Custom circle and custom rectangle controls remain separate from both lists. Double-clicking a non-custom catalog row enters insertion mode immediately; the Insert button remains available.

## Main reference overlay
X and Y edge-distance controls remain together near the selected reference crosshair and use a slightly smaller font than the current 16 pt presentation. Floating controls must not cover the selected feature footprint and must not overlap one another.

## Round-hole settings window
Selecting a circular placed feature exposes a separate round-hole settings window. It supports all directions:
- Left
- Right
- Up
- Down
- Both horizontal directions
- Both vertical directions

The window always displays both values:
- Center distance: distance between circle centers.
- Gap: shortest edge-to-edge distance between the two circular perimeters.

Exactly one representation is the current driver at a time, but both remain visible and synchronized. If the center-distance field is the driver, editing it recomputes gap. If the gap field is the driver, editing it recomputes center distance. For adjacent circles with radii `r1` and `r2`, `center_distance = gap + r1 + r2`.

## Fill and Refill
`Fill` starts from the current selected circle and adds as many legal circles as fit in the selected direction, using the chosen driving representation.

`Refill` is allowed to reposition the generated row/column instead of preserving the current selected-circle location. It uses the selected direction and the active center-distance/gap rule to maximize the usable run within the legal FeatureSurface/finished reference limits, without placing any feature outside the legal FeatureSurface.

Generated circles inherit the selected feature's processing semantic (CUTTING or BLIND_HOLE), diameter, and relevant catalog identity.

## Circular-neighbor alignment
When the reference neighbor is also circular, the round-hole settings window additionally offers:
- Center aligned
- Pipe top aligned
- Pipe bottom aligned

For horizontal arrangements, top/bottom alignment affects Y. Center aligned matches center Y; top aligned matches top perimeter Y; bottom aligned matches bottom perimeter Y. For vertical arrangements, the corresponding circular perimeter alignment is applied on the perpendicular axis consistently with the selected reference relationship.

## Conflict precedence
The main nine-anchor reference workflow and the round-hole arrangement workflow are independent edit modes with separate Confirm buttons.

- Pressing `確定定位` in the reference overlay makes the reference-position result authoritative at that moment.
- Pressing `確定` in the round-hole settings window makes the round-hole arrangement result authoritative at that moment.
- If their constraints conflict, whichever Confirm was pressed last wins; the other workflow's displayed values refresh from the resulting geometry instead of trying to enforce stale constraints.

Cancel in either workflow restores the state captured when that workflow began.

## Validation
All generated or moved circular features must pass the existing FeatureSurface containment rules. Invalid edits are rejected/restored rather than clipped or hard-coded.

## Tests
Add pure tests for center-distance/gap synchronization, mixed-diameter calculations, all fill directions, refill behavior, legal-boundary stopping, alignment modes, and last-confirm-wins state semantics. Add GUI source/interaction tests for separate pipe catalog visibility, round settings availability only for circles, both synchronized fields, Fill/Refill controls, and smaller non-overlapping reference inputs.
