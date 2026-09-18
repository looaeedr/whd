---
whd_doc_role: REFERENCE
whd_contract: issue292-t4-part-panels-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #292 T4 — Physical-Part Panel Extraction Implementation Plan

## Identity
- Parent: #287
- Task: #292 / T4
- Accepted predecessor: `#291 @ cefb1a11c837a73508a6a2b09eac77ba38c798f6`
- Work branch: `refactor/issue292-gui-phase2-t4-panels-20260916`
- Design: `docs/superpowers/specs/2026-09-16-issue292-t4-part-panels-design.md`
- Production integration remains #296/T8 responsibility.

## Execution rule
Use TDD for every extraction slice: RED -> verify intended failure -> minimal GREEN -> focused regression -> commit. Never move T5/T6/T7/HOLD, manufacturing/DXF/project authority, or committed shadow state merely to satisfy a LOC target. For Actions, RUN=0 means fix the trigger/prerequisite immediately; poll only a concrete RUN.

## Task 1 — Structural gate reconciliation [LOCKED]
Machine contract: `tests/process/test_issue292_t4_scope_reconciliation.py`.

Valid raw-impossibility proof:
- RUN `35119606947`, job `104873722227`
- accepted `gui.py = 8,515 LOC`
- maximal over-generous T4 removable upper bound = `2,476 LOC`
- zero-wiring best case = `6,039 LOC`
- raw `5,500` gate therefore impossible even while over-crediting mixed `init_variables` and assuming zero wiring.

Legal-budget measurement:
- RUN `35119940754`, job `104874856272`
- 35 unambiguous presentation/input-normalization whole methods
- removable LOC `1,200`
- root delegate budget `105`
- import/wiring budget `24`
- theoretical root `7,444`
- safety margin `20`
- reconciled hard gate: **`gui.py <= 7,464`**

No extraction starts until the machine contract, issue and design all agree on `7,464` and a fresh QA run makes reconciliation GREEN.

## Task 2 — Architecture/ownership RED
Add `tests/test_issue292_gui_phase2_t4_part_panels.py`.

RED contract:
- `gui_modules/parts/panels/` with `common`, `assembly_corner`, `box_body`, `endcap`, `base_plate`, `door`, `divider`, `multipart`, `indicator_box` does not yet exist;
- moved panel implementations remain rooted in `gui.py`;
- legacy `gui_modules/part_panels.py` still needs caller reconciliation;
- no panel may import `gui` or compatibility exports or introduce committed shadow state;
- final contract enforces module/class/method gates and `gui.py <= 7,464`.

Run T4 RED and accepted T3 contract in the same validation context; T4 must RED for target structure while T3 stays GREEN.

## Task 3 — Shared presentation primitive / legacy helper census
Census every caller of `_phase6_logical_part_present`.
- Add `gui_modules/parts/panels/__init__.py` and `common.py`.
- Move the helper if callers are internal and delete `gui_modules/part_panels.py`.
- If a real external caller exists, keep only an explicit deprecated shim with caller inventory/removal issue/date.
- Assert one implementation only and preserve `door_c*`, `base_plate_c*`, `box_body:*` behavior.

## Task 4 — Assembly/corner panel
Add `assembly_corner.py`; move only widget construction, display formatting, input normalization and thin routing. Keep assembly/corner committed state and manufacturing interpretation in existing authority. Characterize defaults/FW/manual-corner controls first, observe RED, then move minimal code.

## Task 5 — Box-body/endcap/base-plate/divider panels
Add `box_body.py`, `endcap.py`, `base_plate.py`, `divider.py`.
- box body reuses T3 subtabs/physical identity;
- endcap preserves FW/default/presence UI;
- base plate preserves same/shrink behavior;
- divider preserves UI/defaults while flat/form/包外 and manufacturing rules stay outside panels.
For geometry-affecting inputs compare authoritative results before/after; never add panel formulas.

## Task 6 — Door/multipart/indicator panels
Add `door.py`, `multipart.py`, `indicator_box.py`.
- door: layout widgets, cell-selection presentation, input normalization, add/remove routing, inner-door UI, status refresh;
- no second `door_layout_columns`, `receiving_inner_doors`, scope/handle/feature/indicator committed store;
- multipart: presentation only, preserving top-level `箱身` and stable physical children;
- indicator: input/config routing only; drawing remains T6.

## Task 7 — Eligible Tk adapters / root duplicate removal
Census `init_variables` and move only part-specific Tk adapters/bindings to focused panel setup. Do not add generic `variables.py`; do not move committed/domain state. Remove moved root bodies or leave only established thin delegates. Re-run shadow-state/import/size/LOC contracts.

## Task 8 — Focused L0/L1/L2/L4 acceptance
L0: T4 architecture contract, T3 contract, import/circular/static-size scans, `gui.py <= 7,464`.

L1: exact defaults, enable/disable/presence, edit/commit/cancel routing, receiving/vault/multipart availability, SettingsService/WorkspaceController ownership.

L2: representative box-body/endcap/base-plate/door/divider inputs must produce the same authoritative manufacturing/resolved outputs as predecessor.

L4 Xvfb: receiving/vault transitions, multipart panel behavior, door layout/cell selection, base-plate same/shrink, endcap FW, divider defaults, indicator configuration, manual corners, affected short-window/scroll behavior.

Protected drift must remain zero for `config.ini`, `基準檔/**`, manufacturing `ae_engine/**`, `phase6_project_file.py`, project schema and baseline/reference artifacts.

## Task 9 — Full Headless/Xvfb acceptance
Create temporary QA branch/workflow from exact candidate HEAD. Run full Headless and Xvfb. For any RED, record exact FAILED nodeids and perform accepted-predecessor/candidate A/B before calling it inherited. Acceptance requires GREEN or candidate-only failure set = 0 with exact proof. Protected drift and candidate reconciliation must be GREEN.

## Task 10 — Cleanup / closure guard
Remove temporary QA workflows/helpers and verify cleanup has no unintended content drift. Fresh-read candidate HEAD and issue state.

Build terminal checkpoint bound to:
- issue `#292`
- branch `refactor/issue292-gui-phase2-t4-panels-20260916`
- fresh candidate HEAD

Invoke canonical `authorize-finalization`, then `verify-finalization-proof` at the closure boundary. Any missing/stale/mismatched proof fails closed. Only then close #292/completed and remote-read it back.

## No production integration
Do not update `cleanup/2d-3d-sync` in T4. #296/T8 owns final accepted-chain integration.
