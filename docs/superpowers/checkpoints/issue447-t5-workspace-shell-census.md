# Issue #447 / T5 — Workspace Shell deletion-test census

- Parent / Master: #441
- Issue: #447
- Role: T5 實作者
- Accepted predecessor / base: `b9fcf32b5aa652bf283be5ce5c3840aa4d197ed1`
- Work branch: `refactor/issue447-t5-workspace-shell-20260921`
- Current X observation only: `e8329ca2cca84c8c9aa85c9feddc1ee7c8692dbc`
- Preflight evidence: `docs/superpowers/checkpoints/issue447-t5-preflight-evidence.txt`

## Deletion-test target

Persistent shell candidates in `fold_designer_bridge.py`:

| Function | Current callers outside definition | Observation |
|---|---:|---|
| `_phase6_build_persistent_top_area` | 1 | single composition root from Fold Designer init |
| `_phase6_build_project_toolbar` | 1 | only called by persistent top area |
| `_phase6_build_transaction_buttons` | 1 | only called by persistent top area |
| `_phase6_build_global_persistent_controls` | 1 | only called by persistent top area |
| `_phase6_build_output_controls` | 1 | only called by persistent top area |
| `_phase6_build_visual_controls` | 1 | only called by persistent top area |
| `_phase6_install_keyboard_shortcuts` | 1 | only called by persistent top area |
| `_phase6_toggle_fullscreen` | 2 | one button route + one F11 adapter route |
| `_phase6_mount_shared_content` | 4 | existing canonical single-slot mode mounting seam |

The top-area builder already concentrates the shell layout. Deleting it does not reveal duplicated callers that can be collapsed; instead it forces its layout logic into the init caller or into a new wrapper with the same dependencies.

## Extraction cost

A new `phase6_workspace_shell.py` would need to accept/inject existing owners for:
- project load/save/save-as;
- Registry editor entry;
- DXF/output controls;
- Settings panel/global controls;
- visual controls;
- reset action;
- status projection;
- sticky structure-tree refresh;
- left workspace width/text scale;
- fullscreen state and root window operations;
- keyboard command routing;
- canvas/right-workspace packing.

Those dependencies are already authoritative elsewhere. Moving only Tk statements behind a new class/function would not remove those seams or their state; it would add a new composition layer that forwards them. That is a shallow wrapper, explicitly prohibited by #447.

## Shared-content protected contract

Current mode surfaces are direct siblings under `self.left`:
- `input_content_host`
- `assembly_parts_panel`
- `corner_data_panel`

`_phase6_mount_shared_content` maps exactly one of those direct siblings and `pack_forget()`s the others. It deliberately has no fixed outer content frame.

Therefore:
- `ACTIVE_MODE_SURFACE_COUNT=1`
- separate Assembly region = 0
- separate Corner Data region = 0
- visible wrapper around the shared slot = 0

Moving this seam into a new shell owner would not reduce state/callback complexity and would increase the risk of recreating the rejected “大框包小框” layout.

## Event/callback ownership

`_phase6_install_keyboard_shortcuts` has one bridge call site. The binding loop is already owned by `gui_modules/application/command_router.py::install_fold_designer_keyboard_shortcuts`, which installs:
- Ctrl+S route once per installer call;
- Ctrl+O route once per installer call;
- F11 route once per installer call.

No second workspace-shell binding loop exists.

Fullscreen state remains one bridge presentation state:
- button callback → `_phase6_toggle_fullscreen`
- F11 adapter → `_phase6_toggle_fullscreen`

There is no second fullscreen state owner.

Thus:
- duplicate event binding owner = 0
- callback multiplication from T5 = 0

## Persistence / domain boundary

The deletion-test changes no project persistence, manufacturing, geometry, physical-part identity, Registry, or AssemblyJoint owner. No `phase6_workspace_shell.py` is created.

## Decision

`DECISION=NO_EXTRACTION`

Reason: the current shell is already concentrated at one composition seam; extraction would be a forwarding/shallow wrapper rather than a deep module. The accepted action is to keep the current shell implementation in place and add regression contracts that prevent shell duplication or shared-content re-wrapping.

## Machine acceptance to add

1. no `phase6_workspace_shell.py` under this NO_EXTRACTION decision;
2. `_phase6_build_persistent_top_area` remains a single-caller composition root;
3. shell sub-builders remain single-caller;
4. keyboard installer remains a single bridge route to command_router;
5. shared-content surfaces remain direct siblings and runtime maps exactly one;
6. no project persistence owner moves.

Next action: add focused #447 ownership/deletion-test contracts and run headless + Xvfb acceptance.
