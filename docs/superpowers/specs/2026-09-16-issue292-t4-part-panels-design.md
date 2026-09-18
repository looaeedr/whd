---
whd_doc_role: REFERENCE
whd_contract: issue292-t4-part-panels-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #292 T4 — Physical-Part Panel Extraction Design

## Identity
- Parent: #287
- Task: #292 / T4
- Accepted predecessor: `#291 @ cefb1a11c837a73508a6a2b09eac77ba38c798f6`
- Work branch: `refactor/issue292-gui-phase2-t4-panels-20260916`
- Final production integration remains #296/T8 responsibility.

## Goal
Extract physical-part input-panel presentation and UI glue from `gui.py` into focused modules without creating second settings/state/geometry authority or a replacement monolith.

## Package structure
```text
gui_modules/parts/
  selector.py
  subtabs.py
  panels/
    __init__.py
    common.py
    assembly_corner.py
    box_body.py
    endcap.py
    base_plate.py
    door.py
    divider.py
    multipart.py
    indicator_box.py
```
No `all_parts.py`, giant mixin, or generic committed `state.py` is allowed.

## Authority boundaries
- `SettingsService` remains the committed runtime-settings owner.
- `Phase6WorkspaceController` remains authoritative for physical presence, active part, profiles, placements and features.
- `Phase6ProjectController` / `ProjectSession` retain persistence and project transaction authority.
- Host-owned committed assembly/corner and door/multipart clusters remain in their current authoritative seam until T7 unless an already-proven owner exists.
- Panels may own Tk/widget adapter state only.
- Manufacturing dimensions, fold/hole/DXF/placement calculations remain outside panels.
- T5 owns editor/dialog decomposition; T6 owns rendering/interaction; T7 owns remaining controller/HOLD/REVIEW boundaries.

Allowed flow:
```text
panel event -> normalize -> route/dispatch -> authoritative owner -> resolved result -> presentation
```

Forbidden:
```text
gui_modules/** -> gui.py
gui_modules/** -> compatibility/legacy_exports.py
panel -> local manufacturing formula / project persistence / second committed state store
```

## Legacy `gui_modules/part_panels.py`
Census every caller of `_phase6_logical_part_present()` before movement. If only current internal callers remain, move the helper to the focused package and delete the old file. If a real external caller exists, retain only a thin deprecated shim with caller inventory and removal issue/date. Duplicate implementation is forbidden.

## Responsibility groups
- `common.py`: truly shared row/widget/packing helpers only.
- `assembly_corner.py`: assembly selector, endcap-FW and manual-corner presentation/routing only.
- `box_body.py`: box-body input/result presentation; reuse T3 subtabs/identity.
- `endcap.py`: endcap input presentation; no baseline/manufacturing authority.
- `base_plate.py`: same/shrink input presentation/routing; no physical-state authority.
- `door.py`: layout widgets, cell-selection presentation, input normalization and inner-door UI routing; no second door-layout store.
- `divider.py`: divider input presentation only; no flat/formed/包外 geometry logic.
- `multipart.py`: multipart-specific panel presentation only; T3 retains navigation/identity.
- `indicator_box.py`: indicator input/configuration UI only; drawing remains T6.

## `init_variables`
`init_variables` is mixed T2/T4/T7 responsibility and must not move wholesale. Only part-specific Tk adapters may move, while committed/domain state stays in the authoritative host/controller seam. A generic `variables.py` is forbidden.

## Structural gate reconciliation
The original `gui.py <= 5,500` gate is impossible from the accepted #291 predecessor without stealing later-slice scope.

Fail-closed proof RUN `35119606947`, job `104873722227`:
- accepted `gui.py = 8,515 LOC`
- maximal over-generous T4 removable upper bound = `2,476 LOC`
- this bound already credits all mixed `init_variables` and assumes zero wiring
- zero-wiring best case = `6,039 LOC` > `5,500`

Legal-budget measurement RUN `35119940754`, job `104874856272`:
- unambiguous presentation/input-normalization methods = `35`
- removable LOC = `1,200`
- root delegate budget = `105`
- import/wiring budget = `24`
- theoretical root = `7,444`
- safety margin = `20`

Reconciled hard gate:
```text
gui.py <= 7,464 lines
```

The gate gives no LOC credit for mixed committed-state mutation, `init_variables`, T5/T6/T7/HOLD scope, manufacturing/DXF/project authority, or whitespace/comment compression.

Other gates:
- GUI module <= 1,500 lines
- class <= 800 lines
- method/callback <= 150 lines
- no giant mixin, duplicate implementation, circular import, or compatibility dependency

## TDD
Before extraction, `tests/test_issue292_gui_phase2_t4_part_panels.py` must be RED on the accepted predecessor because `gui_modules/parts/panels/` does not exist and panel implementations remain rooted in `gui.py`. The accepted T3 contract must remain GREEN in the same validation context.

Every slice follows RED -> minimal GREEN -> focused regression -> commit. Production code may not precede a correctly observed RED.

## Evidence
L0: package split, import direction, no duplicate/shadow authority, size gates and `gui.py <= 7,464`.

L1: exact defaults, enable/disable/presence, edit/commit/cancel routing, receiving/vault/multipart parity, stable physical identity, state-owner parity.

L2: geometry-affecting inputs compare authoritative before/after outputs; panel-local formulas are forbidden.

L4 Xvfb: family transitions, multipart availability, door layout/cell edits, base-plate same/shrink, endcap FW, divider defaults, indicator configuration, manual corner controls, and affected short-window/scroll behavior.

Any residual RED requires exact accepted-predecessor/candidate A/B proof before classification as inherited.

## Protected invariants
Do not modify `config.ini`, `基準檔/**`, manufacturing authority in `ae_engine/**`, project schema/`phase6_project_file.py`, baseline DXF, or golden/reference expectations to make tests pass.

## Acceptance
#292 is accepted only when:
- lineage remains rooted at accepted #291;
- each physical-part panel has a focused owner module;
- no second committed state/geometry authority exists;
- no duplicate implementation remains in `gui.py`;
- `gui.py <= 7,464` and module/class/method gates pass;
- focused and cross-part regressions are GREEN or only exact A/B-proven inherited reds remain;
- protected invariants pass;
- temporary QA artifacts are cleaned;
- fresh owning checkpoint plus actual finalization-guard invocation proof passes before closure.

T4 does not integrate `cleanup/2d-3d-sync`; #296/T8 owns final accepted-chain integration.
