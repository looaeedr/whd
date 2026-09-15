# Manufacturing Policy Boundary Design

## Goal
Remove the remaining automatic-split dependency on `modules.ae` so automatic bridges only translate source recognition into stable manufacturing contracts.

## Approved direction
Phase 3 already moved all automatic DXF export calls behind `manufacturing_api.generate_part()`. Phase 4 moves the remaining Factory Policy and geometry-derived helper knowledge behind the same boundary.

### Recommended approach: typed policy + API helpers
Add a portable `ManufacturingPolicy` dataclass to `contracts.py` and allow `ManufacturingContext` to carry an explicit policy. `manufacturing_api.resolve_policy()` supplies policy values from the wrapped AE engine when the caller does not inject one. Automatic bridges may consume the typed policy through the API, but may not import `ae`.

The API also owns manufacturing-derived operations that should not be duplicated in bridges:
- Door finished-face size for a `DoorPartSpec`.
- Indicator-box mounting-opening Feature for a layout at a finished-face center.
- Door indicator desired finished-face center → AE indicator offset.
- Indicator small-door `DoorPartSpec` construction.

This keeps automatic bridges responsible only for ownership, source geometry, semantic replacement selection, and finished-face Feature extraction.

## Rejected alternatives
1. **Raw dict of constants passed into bridges** — smaller patch, but loses type safety and recreates undocumented magic keys.
2. **Copy AE defaults/formulas into automatic bridges** — removes the import but duplicates Factory Policy, making future AE updates unsafe again.

## Contracts
`ManufacturingPolicy` contains the defaults currently read from AE:
- `default_thickness`
- `frame_width`
- `door_gap_w`, `door_gap_h`
- `door_fold_left`, `door_fold_right`, `door_fold_top`, `door_fold_bottom`
- `indicator_box_fold`
- `indicator_small_door_fold`

`ManufacturingContext.policy` is optional. When absent, `manufacturing_api.resolve_policy(context)` reads the wrapped AE defaults once at the API boundary.

## Data flow
```text
finalized info_data / source DXF
        ↓
automatic_* bridge
  - ownership
  - finished-face extraction
  - replacement semantics
        ↓
ManufacturingContext + ManufacturingPolicy
PartSpec + finished-face Feature
        ↓
manufacturing_api
  - finished-face dimensions
  - indicator-box manufacturing helpers
  - legacy AE compatibility
        ↓
AE Core / DXF
```

## Compatibility
- GUI continues to use `feature_space="legacy_unfolded"` during migration.
- Automatic Door/EndCap stay on finished-face Feature semantics.
- Existing baseline behavior, source logging, snapshots, replacement CSV semantics, and missing small-door baseline behavior do not change.
- `contracts.py` and `manufacturing_api.py` remain byte-identical between AE root and split-project `modules/`.

## Success criteria
1. `automatic_door_bridge.py` and `automatic_endcap_bridge.py` contain no `from modules import ae`, `import ae`, or `ae.` references.
2. No Factory Policy constants/formulas are duplicated in automatic bridges.
3. Automatic Door, EndCap, direct indicator, indicator box, and indicator small-door regressions remain green.
4. Real baseline DXF smoke remains readable.
5. Overlaying the update package onto the Phase 3 split full package requires no manual merge and does not include live replacement CSV/log files.
