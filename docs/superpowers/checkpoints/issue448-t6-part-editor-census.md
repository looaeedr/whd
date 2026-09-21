# Issue #448 / T6 — Part Editor contract decomposition / owner decision

- Parent / Master: #441
- Issue: #448
- Role: T6 實作者
- Accepted predecessor / base: `9ccd3f51dbda0a9096c2ec964aa69c803ee09238`
- Work branch: `refactor/issue448-t6-part-editor-owner-20260921`
- Current X observation only: `acdfcfc66a46940798bff77df4b8e32bfc10b7ca`
- Preflight evidence: `docs/superpowers/checkpoints/issue448-t6-preflight-evidence.txt`

## Characterized root

`fold_designer_bridge.py::_fix11_activate_part` is ~220 lines, but line count is not the ownership decision. Its body is a composition/compatibility adapter spanning multiple already-existing deep owners.

## Contract decomposition

| Contract | Current owner / seam | Bridge responsibility |
|---|---|---|
| navigation identity + activation decision | `phase6_part_navigation.py` + `Phase6WorkspaceNavigationController` | resolve operator key, ask controller for activation plan, invoke begin/finish |
| save outgoing | `_fix11_save_current_part` routes canonical save semantics to DesignerWorkspace / domain helpers | order save before active identity changes; bridge reads live Tk editor values |
| profile persistence | `Phase6DesignerWorkspace` / `SharedWorkspaceState` | live editor overlay + compatibility adapter only |
| settings render | `Phase6SettingsPanel` via `_phase6_render_settings_context` | choose current context after activation |
| shared-content mount | `_phase6_mount_shared_content` | presentation-only direct-sibling mode mount |
| update intent | `gui_modules/application/command_router.py` scheduler | classify geometry-vs-display and submit one intent |
| physical-piece navigation | `phase6_part_navigation.py` + navigation-controller remembered child | compatibility projection of selected physical child to Tk label/selector |
| render handoff | final-scene renderer/view + update-intent executor | settle Tk viewport, then submit one authoritative render/update route |
| project save/reload payload | `Phase6DesignerWorkspace.snapshot/export_shared_snapshot` + `Phase6ProjectController` | collect live active editor overlay at persistence boundary |

## Existing owners already satisfy the deep seams

### Navigation/state owner

`Phase6WorkspaceNavigationController.plan_activation()` owns:
- presence validation;
- previous active identity;
- no-op detection;
- save-outgoing decision;
- begin/finish switching state;
- remembered BoxBody physical child.

It imports no Tk, renderer, manufacturing geometry, or bridge.

`Phase6DesignerWorkspace` owns:
- available / active / selected identity;
- switching flag;
- profile stash;
- physical derived-part presence;
- complete workspace snapshot;
- dirty/clean lifecycle.

### Update-intent owner

`gui_modules/application/command_router.py` owns the Fold Designer update scheduler:
- `submit_fold_designer_update_intent`;
- `flush_fold_designer_update_intents`;
- queued geometry/display rendering behavior.

The bridge submits a reason; it does not own the scheduler loop.

### Presentation owners

Settings, shared-content mount, renderer canvas visibility, bend-ui rebuild/refresh, and operator Tk variables are presentation/composition concerns and necessarily live at the application adapter seam.

## Deletion test for B — EXTRACT_PART_EDITOR_SESSION

Deleting a hypothetical `PartEditorSession` would push the same dependencies back into one caller. To implement the current activation behavior without depending on the full app, a new session would need ports/callbacks for at least:

- outgoing editor save;
- pending Tk `after` cancellation;
- shared-content mount;
- navigation plan/begin/finish;
- part selector label/buttons;
- BendUI profile/tab rebuild;
- W/H/D Tk projection;
- hole projection;
- settings render/mount;
- Matplotlib idle-draw suppression;
- Tk layout settling;
- drawing-edge controls;
- manufacturing-state signature;
- update-intent submit;
- persistent structure refresh;
- physical-piece selector refresh;
- content-switch refresh.

That interface is nearly the existing app/bridge surface. Complexity would not disappear behind a small interface; it would be re-described as 15+ callbacks. This is a shallow wrapper and fails the approved prohibition against “整塊 move-only 到新 class 但仍依賴完整 app/bridge surface”.

## Deletion test for A — DEEPEN_EXISTING_DESIGNER_WORKSPACE

`Phase6DesignerWorkspace` is intentionally a pure state owner. Moving Tk/BendUI/renderer/settings/update orchestration into it would:
- break its existing no-Tk/no-renderer/no-project-service contract;
- conflate pure workspace state with presentation;
- weaken its current deep interface and testability.

The stateful pieces that *do* belong there are already there: active/selected identities, switching, profiles, features, derived parts, snapshots, dirty/clean state.

Therefore A would not deepen the existing module; it would broaden its interface across unrelated tiers.

## Decision

`DECISION=C_KEEP_BRIDGE_COMPATIBILITY`

This is not “do nothing because the function is large”. It is an explicit owner decision:

1. preserve `_fix11_activate_part` as the application-level compatibility/composition adapter;
2. keep navigation/state decisions in `Phase6WorkspaceNavigationController` / `Phase6DesignerWorkspace`;
3. keep update scheduling in command_router;
4. keep project persistence payload authority in DesignerWorkspace + ProjectController;
5. keep settings/shared-content/render calls as narrow application adapter routing;
6. do not create `phase6_part_editor_session.py`;
7. do not move domain/profile formulas, physical-part identity, persistence, or render-intent authority back into bridge.

## Required machine evidence

Focused contracts must prove:

- Part identity drift = 0.
- Outgoing save occurs before active identity switches.
- No direct DesignerWorkspace mutators/assignments leak back into bridge activation.
- Profile save/reload remains owned by DesignerWorkspace snapshots.
- Explicit stale physical-child selection fails closed and never guesses a sibling.
- Shared-content switch remains presentation-only and exactly one direct surface.
- Activation submits exactly one update-intent route through command_router.
- `phase6_part_editor_session.py` does not exist under decision C.
- No project-persistence owner moves.
- No production geometry / DXF / config drift.

Next action: add #448 focused decision/behavior contracts, then remote headless + Xvfb A/B acceptance.
