# Unified Hole Editor & Reference Positioning Design

## Goal
Unify Head, Tail, Door, Box Body, Base Plate, Indicator Box, and Indicator Door onto one hole editor and one placement model.

## Entry points
- Double-click any supported panel canvas opens the same hole editor.
- Right-click no longer opens a hole editor.
- Door double-click is reclaimed for hole editing; indicator configuration remains available from its checkbox/fields.
- The old Head/Tail editor UI is removed; only legacy data conversion remains.

## Catalog and insertion
- The left catalog remains visible and reads only `基準檔/開孔/開孔.csv` and `基準檔/開孔/管孔尺寸清單.csv`.
- Catalog selection remains selected after insertion.
- Selecting an item does not immediately place it. The user presses `插入`, then clicks the panel to place one or more holes.
- Add `自訂圓孔` and `自訂方孔`; each has only a `盲孔` checkbox. Unchecked means CUTTING, checked means BLIND_HOLE.
- The created-hole list is always visible.
- Double-clicking a created-hole row toggles the entire inserted feature between CUTTING and BLIND_HOLE. There is no DXF-profile exception: the user's latest decision wins for the inserted feature.

## Nine reference anchors
The positioning reference is one of exactly nine anchors:
- 中心
- 中上
- 中下
- 中左
- 中右
- 左上
- 左下
- 右上
- 右下

The selected anchor defines the point on the current feature through which the horizontal and vertical crosshair reference lines pass. Other features are compared using the same anchor position on those features.

## Edge direction
For explicit side anchors, the side encoded by the anchor determines the panel edge used for the corresponding axis.

For `中心`:
- X uses the nearest of left/right panel edges; equal distance chooses left.
- Y uses the nearest of top/bottom panel edges; equal distance chooses bottom.

For middle anchors that do not specify one axis side:
- `中上` / `中下`: X uses the nearest left/right edge; tie chooses left.
- `中左` / `中右`: Y uses the nearest top/bottom edge; tie chooses bottom.

## Neighbor-hole reference
Neighbor selection is axis-specific and uses the active reference crosshair:
- X neighbor: compare other features' same-anchor points by perpendicular distance to the current feature's horizontal reference line. Lowest perpendicular distance wins; ties use along-X distance.
- Y neighbor: compare other features' same-anchor points by perpendicular distance to the current feature's vertical reference line. Lowest perpendicular distance wins; ties use along-Y distance.
- The selected edge direction restricts candidates to that side of the current feature. If no candidate exists on that side, show no neighbor distance.

## Distance fields
Show four large editable fields:
- X 到邊框
- X 到鄰近孔
- Y 到邊框
- Y 到鄰近孔

Labels dynamically name the chosen side, e.g. `X 到左邊框`, `X 到左側鄰近孔`.

Editing an edge-distance field moves the current feature along that axis and recomputes the neighbor value. Editing a neighbor-distance field moves the feature relative to the currently selected neighbor and recomputes the edge distance. All moves are validated against FeatureSurface full-footprint containment.

## Right-click on inserted features
Right-clicking an inserted feature no longer opens an editor. It opens a reference-anchor menu with the nine anchors and a `十字基準線` visibility toggle. The same anchor can also be selected from a visible dropdown/list in the editor.

## Visual behavior
- Crosshair lines pass through the selected feature anchor.
- Selected catalog text remains visible.
- Selected inserted hole is highlighted.
- Primary numeric inputs use larger fonts (about 15-16 pt) and taller rows/buttons.

## Data architecture
- All parts use `surface_features[part_key]` as the semantic feature list.
- Head/Tail keep compatibility adapters syncing to `head_holes` / `tail_holes` only at the boundary.
- GUI stores no canvas-pixel manufacturing data.
- FeatureSurface containment remains authoritative for legality.
- GUI and DXF consume the same semantic feature geometry.

## Testing
- Reference anchor point correctness for all nine anchors.
- Center edge tie-break: X left, Y bottom.
- Neighbor ranking: perpendicular-to-reference-line first, along-axis second, candidate restricted to selected side.
- Distance-field round trips and boundary rejection.
- Created-hole double-click process toggle CUTTING <-> BLIND_HOLE including profile features.
- All supported canvases double-click into unified editor; no right-click-open bindings remain.
- Head/Tail legacy storage still syncs and exports.
