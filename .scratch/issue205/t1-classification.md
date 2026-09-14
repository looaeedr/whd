# #205 T1 — SAFE / REVIEW / HOLD + State Ownership Map

[當前角色：T1 實作者]

Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
T0 evidence: #204 / run `34806853791`

## Classification rules

- `SAFE` means semantic ownership is clear enough to proceed to T2 characterization; it does **not** authorize immediate movement.
- `REVIEW` means ownership/caller contract is still too broad or uncertain for T2 extraction coverage to be specified safely.
- `HOLD` means do not move in the current modularization wave. Dead/legacy/negative-guard symbols are not moved merely to reduce `gui.py` line count.
- AST/static evidence alone never establishes SAFE; classifications below include source/caller/test semantic reread.

## First-wave classification

### SAFE — `_corner_preview_canvas_point` (L150–L156)
Reason:
- pure coordinate projection from explicit `point/ox/oy/scale/span/flip_y` inputs;
- no `self`, global mutation, controller, project, manufacturing, persistence, or widget ownership;
- live use is corner-thumbnail drawing only;
- direct regression coverage exists in `tests/test_phase6_ui_state_regressions.py`.
T2 characterization requirement:
- top/bottom Y orientation, coordinate output, no state mutation.

### SAFE — `_corner_preview_flip_y_for_target` (L159–L161)
Reason:
- pure normalization of explicit target key;
- no state/global/widget ownership;
- direct regression asserts top variants True and bottom variants False.
T2 characterization requirement:
- exact target-key matrix including empty/unknown values.

### SAFE — `_project_toolbar_presentation` (L164–L179)
Reason:
- returns a presentation-only immutable-style dict/tuple contract;
- no callbacks, state mutation, settings mutation, project transaction, geometry or manufacturing ownership;
- `create_widgets()` consumes the spec while callbacks remain on `Phase6ApplicationHost`;
- direct foundation regression references the function.
T2 characterization requirement:
- exact action order/roles/title/subtitle/padding values; moving it must not move callback ownership.

### HOLD — `layout_reference_overlay_rects` (L278–L361)
Reason:
- syntactically pure, but T0 repo-wide search found no live production caller in current `gui.py`;
- moving an unproven/dead compatibility surface only to reduce line count violates move-by-responsibility and caller-proof-before-delete/move rules.
Next action:
- separate caller/dead-code proof if future work wants to revive/delete/extract it; not part of first move-only wave.

### HOLD — `_YMirroredPreviewTransform` (L367–L376)
Reason:
- no live production caller was found;
- `tests/test_endcap_head_mirror.py` monkeypatches it to *raise* and proves authoritative head corner-data must not mirror at render time;
- therefore it is a negative compatibility/legacy guard, not a current renderer abstraction.
Next action:
- keep in place unless a separate caller-proof/dead-code ticket authorizes deletion or compatibility relocation.

### HOLD — `render_structural_result` (L379–L404)
Reason:
- no live production caller in current `gui.py`;
- current 2D single-source regression explicitly forbids `draw_door` from using it; production rendering is from authoritative Final `DrawingScene` instead;
- moving it would preserve a stale alternative renderer seam without architectural benefit.
Next action:
- separate dead-code/compatibility proof if removal is desired.

### SAFE — `render_drawing_scene` (L407–L440), with mandatory T2 characterization
Reason:
- consumes an already-authoritative `DrawingScene` plus explicit Canvas transform;
- owns only presentation translation (primitive → Canvas coordinates, layer colors, BEND dash/width), not manufacturing geometry or state;
- does not read/write `self`, project state, workspace state, settings, DXF, or geometry inputs;
- live production callers span Fold Designer corner-data projection and Door/Base Plate/Indicator/BoxBody/EndCap 2D views, all passing authoritative scene/render data;
- current single-source regression requires `draw_door` to consume `_authoritative_render_data` + `render_drawing_scene` and forbids reconstruction through legacy structural helpers.
Risk:
- broad caller surface means this is SAFE only for T2 characterization, not immediate move.
T2 characterization requirement:
- Polyline/Line/Circle behavior, CUTTING/BEND/MARKING/BLIND_HOLE/DATUM colors, BEND dash, closed/open primitives, skip_layers, transform scaling, and representative authoritative caller equivalence.

## State Ownership Map

| State / responsibility | Authoritative owner | GUI role | 2D consumer | 3D consumer | Persistence | T1 rule |
|---|---|---|---|---|---|---|
| Project committed/draft transaction, project path, load/save ordering | `Phase6ProjectController` → `ProjectSession` | `Phase6ApplicationHost` supplies/receives snapshots and commands | snapshot consumer only | designer transaction consumer only | `.p6fold` via controller read/write | no second project store in `gui_modules` |
| Committed workspace: physical presence, active part, part profiles, BoxBody profile/structure, placements/features | `Phase6WorkspaceController` → `SharedWorkspaceState` | orchestrates controller calls and UI projection | reads current workspace/physical child | reads same committed workspace; draft committed back through controller | included in project snapshot | no `state.py` clone; no widget-backed truth |
| Committed runtime settings | `SettingsService` | widgets edit/project committed values through existing settings flow | reads committed effective values | same settings authority; designer may have transaction-local draft | `config.ini` is persisted next-start defaults, not second runtime owner | no settings duplication in layout/panel modules |
| Manufacturing geometry / material / DrawingScene / physical render data | `ae_engine.manufacturing_api` + PartSpec/RenderData/FinalScene contracts | builds PartSpec/context and requests authoritative render data | consumes `render_data.scene/material` | consumes same manufacturing result/contracts | project stores inputs/state, not validation-derived geometry | renderer must never reconstruct CUTTING/CornerType/holes from UI/test data |
| Authoritative render cache | `_Phase6DerivedCacheOwner` used by `Phase6ApplicationHost._authoritative_render_data` | cache orchestration only | shared exact render object | shared exact render object where applicable | not persisted | extraction cannot create a second render cache/source |
| GUI update ordering / dirty flush | `_Phase6UpdateScheduler` | `Phase6ApplicationHost` routes mutations through scheduler | refresh after authoritative flush | sync/refresh after authoritative flush | flush before save/export boundaries | no Event Bus replacing explicit ordering in initial split |
| UI widget variables / layout / callbacks | `Phase6ApplicationHost` during initial modularization | current orchestrator and widget owner | presentation projection | presentation/control projection | only through explicit snapshot/controller flow | panels may later emit explicit callbacks/commands; they do not own domain state |
| 2D Canvas presentation | current `Phase6ApplicationHost` methods + top-level presentation helpers | consumes authoritative render/state | yes | no authority | none | may be extracted only as presentation, never as 2D authoritative state |
| 3D workspace presentation/draft UI | existing Fold Designer/3D modules under project/workspace transaction boundary | opens/commits/cancels through host/controller | no authority | yes | draft commits through canonical snapshot flow | no parallel state store in `gui_modules` |

## Explicit no-go ownership moves

T1 does **not** authorize moving or duplicating:
- `project_controller` / `ProjectSession` state into `gui_modules/state.py`;
- `workspace_controller` / `SharedWorkspaceState` into a new Store;
- `SettingsService` committed runtime state into widgets/panels;
- `_authoritative_render_data` or manufacturing geometry into `drawing.py`;
- `_Phase6UpdateScheduler` ordering into a PubSub/Event Bus;
- physical part identity into selector strings or display labels;
- Save→Reload, DXF, validation expected, screenshots, or golden fixtures into production calculation authority.

## T1 conclusion

First T2 characterization wave is authorized only for:
1. `_corner_preview_canvas_point`
2. `_corner_preview_flip_y_for_target`
3. `_project_toolbar_presentation`
4. `render_drawing_scene`

HOLD in current wave:
1. `layout_reference_overlay_rects`
2. `_YMirroredPreviewTransform`
3. `render_structural_result`

No production symbol has moved and no production behavior has changed in T1.
