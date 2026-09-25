---
whd_doc_role: REFERENCE
whd_contract: issue293-t5-editors-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #293 T5 — Editors / dialogs / modal workflow implementation plan

## Identity
- Parent: #287
- Task: #293 / T5
- Accepted predecessor: `#292 @ 2ee5f73183c08f5f6dee3c220f8d95c5f097c9af`
- Work branch: `refactor/issue293-gui-phase2-t5-editors-20260917`
- Design: `docs/superpowers/specs/2026-09-17-issue293-t5-editors-design.md`
- Scope reconciliation proof: run `35217734914`
- Production integration remains #296/T8 responsibility.

## Execution rule
Use TDD for each extraction slice: RED -> verify intended failure provenance -> minimal GREEN -> focused regression -> commit. T5 owns transient editor state only; committed project state, geometry authority, manufacturing formulas, T6 rendering/projection and T7 lifecycle/domain ownership remain with their existing owners. Do not move later-slice ownership to satisfy LOC. Validation judges correctness only and never becomes a production calculation source. No concrete Actions RUN ID means `RUN_NOT_CREATED`: fix trigger/ref/prerequisite immediately; poll only a concrete RUN.

## Task 1 — Structural gate reconciliation [LOCKED]
Machine contract: `tests/process/test_issue293_t5_scope_reconciliation.py`.

Accepted evidence from exact #292 predecessor:
- reconciliation run `35217734914`
- `gui.py = 7,453 LOC`
- CURRENT T0 T5/T5-shared symbols = 5
- over-generous removable LOC = `1,628`
- raw `4,000` requires `3,453` LOC removal
- zero-wiring best case = `5,825`
- raw-gate shortfall = `1,825`

Legal-budget reconciliation uses the same method as accepted T4:
- five delegates × 3 lines = 15
- import/wiring budget = 24
- theoretical root = `5,864`
- safety margin = 20
- reconciled T5 hard gate = **`gui.py <= 5,884`**

The Phase 2 final gate remains **`gui.py <= 2,500`**; T5 may not steal T6/T7 scope to accelerate it.

Before extraction, the machine contract, design, implementation plan and Issue #293 must all state the same `5,884` gate and proof provenance.

## Task 2 — Architecture / ownership RED
Add `tests/test_issue293_gui_phase2_t5_editors.py` before production editor package exists.

RED contract must prove:
- `gui_modules/editors/` does not yet exist;
- `_open_unified_hole_editor` is still a giant root implementation rather than a thin delegate;
- `ask_xy_dialog`, `open_part_hole_editor`, `open_hole_editor`, and editor hint routing remain rooted;
- no editor package may import `gui` or `compatibility/legacy_exports.py`;
- no second transient/committed hole store is allowed;
- existing `Phase6HoleEditorSession` and `Phase6HoleEditorCanvasView` remain required authorities;
- final architecture contract includes class <=800, callback/method <=150, no giant mixin, no circular import and root `gui.py <=5,884`.

Run this RED with the #293 scope-reconciliation contract. The new T5 assertions must fail only for intended missing/existing-root structure while the locked T5 scope proof remains GREEN.

## Task 3 — Generic dialog extraction
Characterize `ask_xy_dialog` first: defaults, invalid input behavior, confirm result, cancel/window-close/Escape behavior and transient-only state.

Create `gui_modules/editors/dialogs.py`. Move only modal presentation/input normalization. Preserve caller-visible result and cancellation semantics. Leave root only a thin delegate where the established caller contract requires it.

Run focused dialog tests and accepted relevant regressions before continuing.

## Task 4 — Hole editor orchestration and view seams
Characterize current `_open_unified_hole_editor` behavior before moving it: part/family routing, session baseline, modal lifecycle, list/catalog/status presentation, preview refresh, focus, confirm/cancel and geometry delegate calls.

Create:
- `gui_modules/editors/hole_editor.py` for orchestration and authoritative-host routing;
- `gui_modules/editors/hole_editor_view.py` for modal widgets/bindings/presentation.

Reuse existing `Phase6HoleEditorSession` and `Phase6HoleEditorCanvasView`; do not copy their state or formulas. The editor package receives explicit collaborators instead of importing `gui`.

## Task 5 — Decompose nested callbacks
The predecessor `_open_unified_hole_editor` contains 57 nested callbacks. Convert them into explicit responsibility methods/handlers. Do not transplant the 1,333-line method into a new giant function/class.

Hard gates during decomposition:
- ordinary GUI module <=1,500 lines unless formally justified;
- ordinary class <=800 lines;
- ordinary callback/method <=150 lines;
- no giant mixin;
- no committed state shadow;
- geometry/manufacturing queries remain delegated to existing owners.

After each coherent slice: focused GREEN + regression + commit.

## Task 6 — Root routing and T0 symbol completion
Reconcile all five CURRENT T0 T5/T5-shared symbols:
- `draw_hole_editor_hint`
- `ask_xy_dialog`
- `open_part_hole_editor`
- `_open_unified_hole_editor`
- `open_hole_editor`

Root bodies must be removed or reduced to established thin delegates. No later-slice method is credited to T5. Re-run scope, import, duplicate-state and structural gates. `gui.py` must be **<=5,884 LOC**.

## Task 7 — Focused L0/L1/L2/L4 acceptance
L0: scope reconciliation, T5 architecture contract, accepted T4 contract, import/circular/static-size scans, no compatibility import, no duplicate implementation/state, root `gui.py <=5,884`.

L1: open/session routing, draft edits, selection, current undo/redo semantics, cancel/window-close/Escape no committed mutation, confirm one authoritative commit, receiving/vault/multipart/physical-part routes.

L2: representative geometry-affecting editor actions must yield identical authoritative outputs to the accepted predecessor. No formula may be moved into or invented by the editor merely to pass validation.

L4 Xvfb: modal lifecycle/focus, list/catalog/status, preview, selection, zoom/pan/context interaction where currently exposed, confirm/cancel/Escape and affected short-window behavior.

Protected drift remains zero for `config.ini`, `基準檔/**`, `ae_engine/**`, `phase6_project_file.py`, project schema and reference/release artifacts.

## Task 8 — Full Headless/Xvfb acceptance
Create temporary QA branch/workflow from the exact candidate HEAD. Run full Headless and Xvfb. For every RED, record exact failed nodeids/signatures and run accepted-predecessor/candidate A/B before classifying inherited. Acceptance requires candidate-only failures = 0 and signature mismatches = 0, plus structural/protected-invariant GREEN.

## Task 9 — Cleanup / closure guard
Remove temporary #293 workflows/helpers/checkpoints from the accepted candidate and prove tested->cleaned drift contains only approved hygiene deletions. Preserve evidence artifacts.

Fresh-read canonical #293 branch/head and Issue state. Build a terminal checkpoint bound to:
- issue `#293`
- branch `refactor/issue293-gui-phase2-t5-editors-20260917`
- fresh clean candidate HEAD

Use the current canonical production finalization guard authority out-of-tree if the #293 lineage predates that guard version. Invoke `assert-finalizable`, `authorize-finalization`, and `verify-finalization-proof`; fresh-lock owner/guard refs immediately before close. Then close #293 with `state_reason=completed` and remote-read `closed/completed`.

Before remote branch deletion, fresh-fetch all OPEN PRs and protect both `head.ref` and `base.ref` through `tools/branch_cleanup_ref_guard.py`. Keep the canonical accepted #293 branch for #294 lineage.

## No production integration
Do not update `cleanup/2d-3d-sync` in T5. #296/T8 owns final combined acceptance, the unchanged Phase 2 `gui.py <=2,500` gate, cleanup/drift audit and non-force production integration.
