# Issue #292 T4 — Physical-Part Panel Extraction Design

## Identity and lineage

- Parent: #287
- Task: #292 / T4
- Accepted predecessor: `#291 @ cefb1a11c837a73508a6a2b09eac77ba38c798f6`
- Work branch: `refactor/issue292-gui-phase2-t4-panels-20260916`
- Current production observed before T4 start: `cleanup/2d-3d-sync @ 8ccf1a9404a641ed892ab63e6f2c0e01ee80d6d9`
- Production intentionally does not yet contain accepted T1–T3 extraction; #291 design assigns final production integration to #296/T8. T4 therefore continues from the accepted predecessor chain, not from the older production tree.

## Goal

Move physical-part input-panel presentation and UI glue out of `gui.py` into focused modules under `gui_modules/parts/panels/`, without creating a second settings/state/geometry authority and without replacing the monolith with a new giant panel module.

T4 owns widget construction, Tk adapter state, input collection/normalization, presentation refresh, and thin routing. Committed state mutation, manufacturing calculations, project persistence, rendering authority, and editor session logic remain with their existing authoritative owners or later Phase 2 slices.

## Chosen package structure

```text
gui_modules/parts/
  selector.py              # accepted T3
  subtabs.py               # accepted T3
  panels/
    __init__.py
    common.py              # truly shared row/widget helpers only
    assembly_corner.py     # corner/assembly/endcap-FW presentation + routing
    box_body.py            # box-body input/result panel presentation
    endcap.py              # head/tail/endcap panel presentation
    base_plate.py          # base-plate panel presentation
    door.py                # door layout/input panel presentation + routing
    divider.py             # divider input panel presentation
    multipart.py           # multipart-specific panel presentation only
    indicator_box.py       # indicator-box / indicator-door panel presentation
```

There is deliberately no `all_parts.py`, no giant mixin, and no generic committed `state.py` inside the panel package.

## Existing `gui_modules/part_panels.py`

The accepted predecessor still contains `gui_modules/part_panels.py`, which currently exposes the stateless `_phase6_logical_part_present()` projection helper.

Before movement, T4 must census all callers.

- If only internal current callers exist, move the helper to the most appropriate focused module (`panels/common.py` or existing T3 selector presentation) and update callers; remove the old file.
- If a real external/legacy caller exists, retain only a thin deprecated compatibility shim with caller inventory and explicit removal issue/date.
- The old module may not retain a duplicate implementation after cutover.

## Authority boundaries

### Settings

Authoritative committed runtime settings remain owned by `SettingsService`.

```text
Tk variable / panel widget
  -> normalize
  -> host/controller command seam
  -> SettingsService
  -> committed snapshot
```

Panel modules may create or bind Tk variables but may not own a second committed settings dictionary or persist settings directly.

### Workspace / physical identity

`Phase6WorkspaceController` remains authoritative for `existing_parts`, `active_part`, box-body structure/profile, part profiles, placements, part features, and part-face features.

```text
panel event
  -> normalize requested user action
  -> route/dispatch
  -> Phase6WorkspaceController / existing host command seam
```

Panels may not mirror `active_part` or `existing_parts` as authoritative backing state.

### Host-owned committed clusters

T0 classified these as `HOST_COMMITTED_STATE_REVIEW` and T4 must not copy them into panels:

- assembly/corner: `assembly_joint_state`, `assembly_relief_state`, `endcap_fw_state`, `endcap_bottom_wrap_state`, `manual_corner_state`, pair/lock/override state;
- door/multipart: `door_layout_columns`, `receiving_inner_doors`, `door_layout_scope`, `door_layout_handle_edges`, per-cell feature/indicator maps;
- surface/face feature state.

T4 may move presentation and callback routing around these values, but authoritative ownership remains in the existing host/controller seam until T7 establishes any new focused owner.

### Manufacturing / geometry

Panels must not calculate or rederive finished dimensions, fold geometry, hole geometry, DXF coordinates, placements, or manufacturing part specs.

Allowed flow:

```text
panel input -> command/controller -> authoritative calculation -> resolved result -> panel/render presentation
```

Forbidden flow:

```text
panel -> local manufacturing formula -> new geometry truth
```

### Project / persistence

Project save/load, committed/draft transaction lifecycle, project path, payload ordering, and schema remain under `Phase6ProjectController` / `ProjectSession` and T7 scope.

### Editors / rendering

- Hole/editor session decomposition remains #293/T5.
- Drawing/overlay/render ownership remains #294/T6.
- T4 may attach an existing editor entrypoint or request a redraw but may not absorb editor/session or rendering implementation.

## Dependency direction

Allowed:

```text
gui.py / host orchestrator
  -> gui_modules.parts.panels.*
  -> explicit command/controller/service seam
```

Forbidden:

```text
gui_modules/** -> gui.py
gui_modules/** -> compatibility/legacy_exports.py
panel module -> project persistence implementation
panel module -> manufacturing/DXF authority as owner
panel module -> second authoritative state store
```

Panel modules may accept the host or explicit callbacks as a dependency during T4, but any callback must remain a thin route into existing authority. No panel module may import root `gui.py` to recover host methods.

## Callback contract

Every moved callback must reduce to:

```text
Event Unpacking -> Input Normalization -> Route / Dispatch
```

A callback that performs substantial state mutation, geometry calculation, persistence, or multi-domain orchestration is not eligible for direct movement. Split the presentation/routing portion and leave the authority/orchestration seam with the current owner or later T7.

## T4 responsibility groups

### Shared panel primitives

Eligible shared primitives include row creation, labels, entry widgets, separators, result-row presentation, packing/show-hide helpers, and generic enable/disable presentation when they do not encode domain policy.

`common.py` must stay small and presentation-only; domain-specific logic belongs to the relevant physical-part module.

### Assembly / corner presentation

Move eligible presentation and routing around:

- box assembly selector presentation;
- endcap FW follow/selection controls;
- manual corner type/parameter widgets;
- corner summaries/icons;
- lock/unlock presentation.

Do not move host-owned committed corner state ownership or manufacturing corner interpretation into this module.

### Box body

Move box-body panel/widget construction and input/result presentation. Existing T3 physical-subtab identity/navigation remains in `parts/subtabs.py`; T4 must integrate with it rather than duplicate it.

### Endcap

Move head/tail/endcap-specific input panel and presentation. Baseline/model source authority and fold/manufacturing calculations stay outside the panel.

### Base plate

Move base-plate input panel, same-toggle/shrink presentation, and routing. Dynamic physical base-plate identity and committed workspace state remain authoritative elsewhere.

### Door

Move door input/layout widgets, per-cell selection presentation, edit/commit/cancel UI routing, receiving inner-door controls, and status refresh.

Door layout committed structures remain host/controller-owned for T4 unless a pre-existing authoritative controller is already proven. T4 must not invent a second `door_layout_columns` owner.

### Divider

Move divider-specific input panel and presentation only. Divider geometry, formed/outer-vs-flat semantics, corner calculations, and manufacturing/DXF rules remain authoritative outside the panel.

### Multipart

Move only multipart-specific input-panel presentation that is not already T3 navigation. Stable physical identities remain unchanged; top-level `箱身` remains a logical selector while child physical identity remains authoritative.

### Indicator box / indicator door

Move input/configuration widgets and state-normalization/routing presentation. Actual 2D drawing belongs to T6 and may only be called through existing render seams.

## `init_variables` split rule

T0 classified `init_variables` as mixed T2/T4/T7 responsibility. T4 must not move the 230-line method wholesale.

Instead:

1. identify Tk adapters used solely by a physical-part panel;
2. move only their creation/binding into that panel's setup path or a focused helper colocated with the part;
3. leave host-owned committed domain values and cross-domain orchestration in the root/T7 seam;
4. prove no new committed shadow state is created.

A new generic `variables.py` containing all part state is forbidden because it would recreate the monolith and obscure ownership.

## Structural constraints

Hard gates from #292 / #287:

- `gui.py <= 5,500` lines at T4 acceptance;
- normal GUI module `<= 1,500` lines;
- normal GUI class `<= 800` lines;
- normal method/callback `<= 150` lines;
- no giant mixin;
- no duplicate implementation in `gui.py` after cutover;
- no circular import;
- new modules may not depend on compatibility exports.

If the accepted predecessor's legal T4 responsibility is insufficient to reach the raw 5,500-line gate without stealing T5/T6/T7/HOLD scope, T4 must run an exact AST reconciliation and update the issue with a measured responsibility-derived gate before production extraction continues. Whitespace/comment compression or stealing later-slice responsibility is forbidden.

## RED contract first

Before production extraction, add a focused structural test such as `tests/test_issue292_gui_phase2_t4_part_panels.py` that is RED on exact accepted predecessor `cefb1a11...` because:

- `gui_modules/parts/panels/` does not yet exist;
- physical-part panel builders/callbacks remain rooted in `gui.py`;
- the old `gui_modules/part_panels.py` still exists as the legacy shared location;
- architecture/import/size contracts are not yet satisfied.

The RED must be caused by target structure/ownership requirements, not missing dependencies or test harness errors.

## Behavior and parity evidence

### L0 — architecture

- new panel package exists and responsibilities are split by physical part;
- no `import gui` / `from gui import ...` inside `gui_modules/**`;
- no new-module dependency on `compatibility/legacy_exports.py`;
- no duplicate moved implementations left in root;
- no new authoritative state backing fields in panels;
- module/class/method size gates.

### L1 — model/state parity

- exact defaults preserved;
- enable/disable and presence state preserved;
- edit/commit/cancel behavior preserved;
- receiving/vault/multipart availability preserved;
- stable physical-part identity preserved;
- SettingsService / WorkspaceController ownership preserved.

### L2 — geometry-affecting input parity

For panel inputs that affect manufacturing output, compare authoritative results before/after without moving the calculations into panels. Relevant door/base-plate/endcap/divider/box-body cases must match.

### L4 — Xvfb UI parity

Cover at minimum:

- receiving and vault family transitions;
- multipart child panel availability;
- door layout edits and cell selection;
- base plate same/shrink controls;
- endcap FW controls;
- divider panel availability/defaults;
- indicator-box configuration;
- corner/manual controls;
- short-window/scroll usability where the moved panel participates.

Any suite red must be exact baseline/candidate A/B classified before exclusion.

## Protected invariants

T4 must not modify authoritative protected artifacts merely to pass tests, including:

- `config.ini`;
- `基準檔/**`;
- `ae_engine/**` manufacturing authority unless a separately proven non-panel prerequisite is explicitly accepted;
- `phase6_project_file.py` / project schema;
- baseline DXF definitions;
- golden/reference expectations as a workaround.

## Implementation order after design approval

1. Fresh accepted-predecessor readback and branch identity check.
2. Exact T4 responsibility/LOC reconciliation against `cefb1a11...`.
3. RED architecture/ownership contract.
4. Caller census for legacy `gui_modules/part_panels.py`.
5. Extract shared presentation primitives only.
6. Extract assembly/corner presentation.
7. Extract box-body/endcap/base-plate/divider panels.
8. Extract door/multipart/indicator-box panels.
9. Split eligible `init_variables` Tk adapters by physical-part owner.
10. Remove duplicate root implementations / resolve legacy helper shim.
11. Focused L0/L1/L2/L4 GREEN.
12. Full Headless/Xvfb with exact inherited-red A/B classification where needed.
13. Protected drift + candidate reconciliation.
14. Remove temporary QA workflows/helpers.
15. Invoke owning finalization guard and close #292 only after current proof passes.

## Acceptance

#292 is accepted only when:

- lineage is rooted at accepted `#291 @ cefb1a11...`;
- each physical-part panel has a focused owner module under `gui_modules/parts/panels/`;
- shared helpers are truly shared and presentation-only;
- no panel owns a second committed settings/workspace/domain store;
- no manufacturing/geometry/DXF/project authority moved into panels;
- no duplicate implementation remains in `gui.py`;
- structural size gates are satisfied or a responsibility-derived reconciliation is formally proven before extraction;
- focused and cross-part regressions are GREEN, or only exact A/B-proven inherited baseline reds remain;
- protected invariants are GREEN;
- temporary QA artifacts are removed;
- owning checkpoint + actual finalization guard invocation proof is current before closure.

Production `cleanup/2d-3d-sync` is not integrated by T4. Final accepted-chain integration remains #296/T8 responsibility.