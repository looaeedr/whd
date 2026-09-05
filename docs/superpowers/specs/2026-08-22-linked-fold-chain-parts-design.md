# Linked Fold Chain / Optional Parts Design

## Approved behavior

- Box-body Fold Chain is authoritative and supports arbitrary practical topology; tests cover up to 20 segments without segment-count branches.
- Editing box-body topology must update the head/tail mating fold topology immediately while preserving head/tail native orientation, holes, CornerType and retain geometry.
- Confirm commits the Fold Chain and existing-part set back to the main GUI; 2D/final manufacturing geometry must consume the committed Fold Chain, not reconstruct the legacy nine-segment chain.
- Cancel/X discards the whole draft.
- Optional parts can be removed and later added back. Box body remains mandatory.
- .p6fold saves/restores the authoritative Fold Chain and exact existing-part set. Derived head/tail profiles may be stored diagnostically but are rebuilt from box-body mating topology on load.

## Mating topology rule

The box body retains one W core and two D cores. The material before the left D and after the right D is the front-edge folding chain. The canonical Phase6 keys provide semantic anchors; unkeyed user-added folds in the outer chain are preserved in order. Head uses the derived front chain before its D core; tail uses the same chain after its D core in native reverse order. The opposite end-cap flap remains its own end-cap parameter. This is topology-driven and independent of total segment count.

## 2D manufacturing rule

BoxBodyPartSpec carries the authoritative profile. Scene generation builds CUTTING width and BEND positions directly from that profile; baseline/fixed features remain owned by AE and are mapped using the semantic D-W-D anchors. Export uses the same final scene path when a custom profile is present.
