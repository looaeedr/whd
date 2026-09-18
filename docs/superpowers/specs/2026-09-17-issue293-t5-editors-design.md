---
whd_doc_role: REFERENCE
whd_contract: issue293-t5-editors-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #293 / T5 — Editors, dialogs, and modal workflow extraction design

## Identity
- Parent: #287
- Task: #293 / T5
- Accepted predecessor: `#292 @ 2ee5f73183c08f5f6dee3c220f8d95c5f097c9af`
- Work branch: `refactor/issue293-gui-phase2-t5-editors-20260917`
- Scope reconciliation proof: run `35217734914`
- Production integration remains #296 / T8 responsibility.

## Goal
Extract editor/dialog/modal presentation and transient editor workflow from `gui.py` without creating a second committed state, second geometry authority, giant editor module, or compatibility dependency. T5 owns transient editor UI/session orchestration only. Commit remains a delegate into the existing authoritative state/controller boundary; cancel must leave committed state unchanged.

## CURRENT authority and scope
The Phase 2 T0 responsibility inventory is authoritative for slice ownership. Its explicit T5 or T5/T6 rows on the accepted #292 predecessor are:

- `draw_hole_editor_hint` — 7 LOC — T5/T6 editor presentation
- `ask_xy_dialog` — 54 LOC — T5 editors/dialogs
- `open_part_hole_editor` — 214 LOC — T5 editors/dialogs
- `_open_unified_hole_editor` — 1,333 LOC — T5 editors/dialogs
- `open_hole_editor` — 20 LOC — T5 editors/dialogs

The T0 state-owner map explicitly limits T5 to **transient editor state only**. Existing `Phase6HoleEditorSession` remains the staged editor-session authority for draft holes, selection, dirty/baseline state and commit/cancel semantics. Existing `Phase6HoleEditorCanvasView` remains the canvas/view coordinate and redraw seam. T5 must reuse those seams rather than duplicate them.

Issue examples such as `corner_editor.py`, `notch_editor.py`, or `parameter_editor.py` are illustrative names, not permission to steal later-slice responsibilities. Actual extraction follows the CURRENT T0 inventory and current source ownership.

## Structural-gate reconciliation
The issue's original raw `gui.py <= 4,000` T5 gate conflicts with the already accepted T0 responsibility split.

Machine proof run `35217734914` measured the exact accepted predecessor:

- predecessor `gui.py`: **7,453 LOC**
- over-generous sum of every T0 T5/T5-shared symbol above: **1,628 LOC**
- raw 4,000 gate would require removing **3,453 LOC**
- even assuming all 1,628 T5 lines disappear from root with **zero** delegate/import/wiring cost, best possible root is **5,825 LOC**
- raw-gate shortfall remains **1,825 LOC**

Therefore `<=4,000` cannot be reached inside legal T5 scope without stealing T6/T7 ownership.

Use the same reconciliation budgeting method already accepted for T4:

- baseline: 7,453
- legal T5 removable budget: 1,628
- five root symbols × 3-line delegate budget: 15
- import/wiring budget: 24
- safety margin: 20
- theoretical root: `7,453 - 1,628 + 15 + 24 = 5,864`
- reconciled T5 hard gate: **`gui.py <= 5,884`**

This reconciliation is T5-only. The Phase 2 final gate **remains `gui.py <= 2,500`** and is owned by #296/T8 after T6/T7 complete their own legal responsibilities.

## Target module structure
Create a focused editor package rather than moving one 1,333-line function wholesale:

- `gui_modules/editors/__init__.py` — explicit public editor routing surface only.
- `gui_modules/editors/dialogs.py` — generic modal dialog presentation such as XY input; transient Tk variables only.
- `gui_modules/editors/hole_editor.py` — editor orchestration/controller-facing routing: construct session/view, route user intent, commit/cancel through existing authority.
- `gui_modules/editors/hole_editor_view.py` — modal window/widget construction, binding, list/catalog/status controls, focus/lifecycle and presentation handlers.

If a class or method would violate Phase 2 structural limits, split it by responsibility instead of creating a giant mixin/module. No editor class may become a replacement monolith.

## Ownership boundaries
### T5 may own
- transient Tk widgets/variables;
- modal window lifecycle and focus;
- event unpacking and input normalization;
- staged editor-session routing;
- preview/list/status presentation;
- selection and transient UI state;
- commit/cancel button routing.

### T5 must not own
- committed project/part state;
- manufacturing interpretation;
- DXF authority;
- 2D/3D authoritative geometry;
- renderer/projection authority assigned to T6;
- lifecycle/domain-controller responsibilities assigned to T7;
- duplicate copies of `Phase6HoleEditorSession` or `Phase6HoleEditorCanvasView` state.

All geometry-affecting operations continue calling current authoritative host/controller/model functions. Validation is only used to judge parity, never as a production calculation source.

## Modal transaction contract
Opening an editor snapshots/stages through the existing session boundary. Editing may change transient draft state and preview only. `Cancel`, window-close, and `Escape` must not mutate committed state. `Confirm/Commit` normalizes user input and delegates the final transaction to the existing authoritative owner. No editor method may directly manufacture a second committed hole/corner/notch store.

## Root contract
After extraction, the T0 T5 root entry points may remain only as established thin compatibility-free delegates where callers still require their names. `_open_unified_hole_editor` must not retain the giant implementation body. `gui.py` must satisfy **<= 5,884 LOC** at T5 acceptance.

## Acceptance
L0 requires import direction, no circular import, no `compatibility/legacy_exports.py`, no duplicate implementation/state, class/method structural gates, exact T0 ownership and `gui.py <= 5,884`.

L1 requires transient-session parity: open, draft edits, selection, undo/redo where currently exposed, cancel/close/Escape no committed mutation, confirm exactly one authoritative commit, and current family/part routing.

L2 requires representative hole/corner/notch/parameter-affecting editor actions to produce the same authoritative resolved outputs as the accepted predecessor. The editor itself must not add formulas.

L4 requires Xvfb modal behavior, focus/close/Escape, preview/list/catalog interaction, selection and confirm/cancel behavior.

Full Headless/Xvfb acceptance must use exact candidate-vs-accepted-predecessor A/B for any RED. `config.ini`, `基準檔/**`, manufacturing `ae_engine/**`, `phase6_project_file.py`, schemas and release/reference artifacts remain protected.

## No production integration
T5 does not update `cleanup/2d-3d-sync`. It leaves a clean accepted #293 candidate for #294/T6. #296/T8 owns the final accepted-chain integration and the unchanged Phase 2 `gui.py <= 2,500` completion gate.
