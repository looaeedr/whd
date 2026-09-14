# #204 T0 Dependency Inventory Summary

[當前角色：T0 實作者]

## Locked baseline

- production: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
- analyzed branch head: `53ca41119a10d9280e1ec6c7f39cf3ef5ac4c720`
- remote evidence run: `34806853791` — GREEN
- artifact: `issue204-t0-analysis` / `10333386357`

## AST inventory

- `gui.py`: **10,068 lines**
- imports: **35**
- top-level symbols: **23**
- class methods: **262**
- function/method bodies analyzed: **363**
- module globals assigned: **1**
- primary host: `Phase6ApplicationHost` L733–L10015
- compatibility shells at tail: `BoxCalculatorGUI` L10019–L10024, `Phase6PrimaryApplication` L10027–L10038

The full artifact contains per-function `self` reads/writes, name reads/writes, attributes, calls, same-file call index, and repo-wide symbol references.

## Coupling hotspots

These are inventory findings only; **no SAFE/REVIEW/HOLD classification is made in T0**.

- `init_variables` L856–L1085: 132 `self` writes; highest state-ownership concentration.
- `create_widgets` L3650–L3960: 72 `self` reads / 22 writes; high layout/controller coupling.
- `create_corner_type_panel` L3121–L3306: 42 reads / 26 writes.
- `_make_original_fold_designer_snapshot` L1838–L2025: 48 reads; persistence/state aggregation seam.
- `_apply_fold_designer_live_snapshot` L2423–L2565: 18 reads / 15 writes; live-sync/state mutation seam.
- `export_selected_dxf` L8228–L8389: 36 reads; export/manufacturing boundary.
- `update_calculations` L7040–L7171: 28 reads; authoritative render/calculation boundary.
- `_apply_phase6_project_snapshot` L2081–L2178: 17 reads / 8 writes; project restore seam.

## First-wave candidate evidence

### `_corner_preview_canvas_point` L150–L156
- no `self` reads/writes
- same-file callers: `_draw_corner_type_icon`, nested `pt`
- repo references include `tests/test_phase6_ui_state_regressions.py`
- T0 makes no extraction decision.

### `_corner_preview_flip_y_for_target` L159–L161
- no `self` reads/writes
- same-file caller: `refresh_corner_type_panel`
- explicit UI regression references in `tests/test_phase6_ui_state_regressions.py`

### `_project_toolbar_presentation` L164–L179
- no `self` reads/writes
- same-file caller: `create_widgets`
- regression references in `tests/test_issue123_ui_foundation.py`

### `layout_reference_overlay_rects` L278–L361
- no `self` reads/writes
- same-file AST call index reports no caller
- repo-wide references include handoff/backups; T1 must distinguish live production/test callers from historical evidence before any move.

### `_YMirroredPreviewTransform` L367–L376
- class candidate, therefore not represented in function-definition slice
- repo-wide regression reference: `tests/test_endcap_head_mirror.py`
- T1 must inspect constructor/attribute contract before classification.

### `render_structural_result` L379–L404
- no `self` reads/writes
- same-file AST call index reports no caller
- regression reference: `tests/test_phase6_3d_single_source_renderer.py`
- absence of same-file callers is not proof of dead code or SAFE extraction.

### `render_drawing_scene` L407–L440
- no `self` reads/writes
- same-file callers include `render_secondary_scene`, Fold Designer corner-data view, Door, Base Plate, Indicator Door, Box Body, End Cap rendering paths.
- wide repo reference surface; requires T1 semantic review before any move.

## T0 conclusions

1. `gui.py` is not safely splittable by line-count or class-size alone.
2. State ownership is highly concentrated in `Phase6ApplicationHost`; initial extraction must avoid duplicating that state.
3. Several top-level drawing/presentation helpers are syntactically independent of `self`, but static independence is **not** sufficient to classify SAFE.
4. Repo-wide references contain production, tests, backups, logs, and historical docs; T1 must classify caller authority rather than count matches mechanically.
5. No production behavior, geometry, DXF formula, state ownership, UI workflow, or persistence schema was changed in T0.

Next gate: #205 must perform human semantic reread + SAFE/REVIEW/HOLD + State Ownership Map. No move-only extraction is authorized yet.
