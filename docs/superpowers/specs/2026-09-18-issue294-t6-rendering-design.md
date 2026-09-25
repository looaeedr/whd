---
whd_doc_role: REFERENCE
whd_contract: issue294-t6-rendering-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #294 / T6 — 2D rendering, overlays, transforms, and interaction extraction design

## Identity
- Parent: #287
- Task: #294 / T6
- Accepted predecessor: `#293 @ e05204366146cf44d2c8cb2ad939f5f753aba030`
- Work branch: `refactor/issue294-gui-phase2-t6-rendering-20260918`
- Scope reconciliation proof: run `35290713319`
- Production integration remains #296 / T8 responsibility.

## Goal
Extract 2D canvas rendering, overlays, presentation transforms, hit-test selection, and zoom/pan-style interaction routing from `gui.py` while preserving the one-way authority chain:

`authoritative state/controller -> resolved geometry/projection -> rendering/presentation`.

T6 may consume resolved or projected geometry. It must never become a source of fold dimensions, outside dimensions, hole positions, notches, part presence, DXF truth, manufacturing dimensions, 3D placement, or project truth.

## CURRENT T0 authority
The Phase 2 T0 inventory assigns a live pure T6 slice containing 37 functions/classes/methods on the accepted #293 tree. Live AST census run `35290713319` measured:

- accepted predecessor `gui.py`: **5,876 LOC**
- pure T6 removable implementation: **1,302 LOC**
- shared T4/T6 REVIEW surface: **348 LOC**
- derived-cache REVIEW class: **36 LOC**
- raw issue gate `<=3,000` requires **2,876 LOC** removal

The same run found **zero missing T0 symbols**.

The unmatched render-like root names were only four small already-classified or routing symbols:
- `_draw_corner_type_icon` — accepted T4 presentation delegate
- `_draw_phase6_finished_dimension_summary` — accepted T4 presentation delegate
- `_route_indicator_canvas_configure` — 2-line routing glue
- `_sync_door_canvas_double_click_binding` — 7-line routing glue

They do not close the raw-gate gap and do not authorize stealing T7 authority.

## Structural-gate reconciliation
The issue's original `gui.py <= 3,000` gate is mathematically incompatible with the accepted T0 T6 responsibility split.

Machine proof run `35290713319` deliberately grants an over-generous zero-wiring removal budget:
- pure T6: 1,302
- all shared T4/T6 REVIEW: 348
- derived-cache REVIEW: 36
- total over-generous removable: **1,686**
- zero-wiring best case: `5,876 - 1,686 = 4,190`

Since **4,190 > 3,000**, the raw gate cannot be reached even if every shared/review line were illegally treated as free T6 removal.

The legal reconciliation budget therefore counts **pure T6 only** and uses the same conservative method accepted by T4/T5:
- baseline: 5,876
- legal pure T6 removable: 1,302
- 37 symbols × 3-line root delegate/re-export budget: 111
- import/wiring budget: 24
- theoretical root: `5,876 - 1,302 + 111 + 24 = 4,709`
- safety margin: 20
- reconciled T6 hard gate: **`gui.py <= 4,729`**

This reconciliation is T6-only. The Phase 2 final gate remains **`gui.py <= 2,500`** and is not weakened. T7 must complete its legal controller/manufacturing-adapter scope before #296/T8 performs final combined integration.

## Target structure
Use focused modules with one-way dependencies; do not create a new renderer monolith:

- `gui_modules/rendering/__init__.py` — explicit public presentation surface only.
- `gui_modules/rendering/canvas_2d.py` — resolved structural/feature/secondary-scene primitives.
- `gui_modules/rendering/overlays.py` — annotation, dimensions, reference overlays and material viewport presentation.
- `gui_modules/rendering/transforms.py` — view-only coordinate transforms and viewport helpers.
- `gui_modules/rendering/door_view.py` — door, multi-door, base-plate and indicator 2D rendering orchestration that consumes authoritative results.
- `gui_modules/rendering/box_body_view.py` — box-body/endcap 2D rendering and presentation-only face/piece selection.
- `gui_modules/rendering/interaction.py` — hit-test, press/drag/release/double-click routing with no committed-state authority.

The exact module split may become smaller if responsibilities remain coherent, but ordinary module <=1,500 lines, class <=800 lines, callback/method <=150 lines remain hard limits.

## Ownership boundaries

### T6 may own
- canvas primitives and visual styling;
- presentation-only transforms and viewport state;
- annotation/dimension/reference overlay layout;
- hit-test zones derived from authoritative projections;
- transient hover/selection/drag presentation;
- event unpacking and routing for canvas interaction;
- choosing which authoritative projection/result to draw.

### T6 must not own
- manufacturing formulas or fold/outside dimension calculation;
- part-spec construction or `manufacturing_api` policy authority;
- authoritative part presence or project/session state;
- hole/notch/feature manufacturing placement formulas;
- DXF export/reopen truth;
- 3D placement/collision authority;
- validation/golden expectations as production inputs.

`_authoritative_render_data`, part-spec builders, manufacturing adapters and policy/controller boundaries remain T7 or existing authoritative owners.

## Dependency rules
Allowed direction:

`gui.py/orchestrator -> gui_modules/rendering/* -> resolved/projection contracts`.

Rendering modules may import stable data types and pure presentation helpers, but may not import `gui` or `compatibility/legacy_exports.py`, and may not call a validation/test helper as a production source.

No rendering module may create a second authoritative state store. Shared 2D/3D state remains unchanged.

## Parity strategy
Each production slice follows RED -> intended failure provenance -> minimal GREEN -> focused regression -> commit.

Evidence layers:
- L0: import direction, duplicate renderer/source, circular-import, geometry-authority, state-owner and module/method size scans.
- L2: authoritative geometry inputs and outputs unchanged.
- L3: drawing primitives, overlays, transforms, dimensions and part 2D projections unchanged.
- L4: Xvfb hit-test, selection, drag, double-click, resize and relevant zoom/pan interaction parity.
- 2D/3D same-state evidence: renderer must observe existing authoritative state only.

Full Headless/Xvfb acceptance uses exact accepted-predecessor/candidate A/B for any RED. Candidate-only failures and signature mismatches must be zero before closure.

## Invariants
T6 may not modify:
- `config.ini`;
- `基準檔/**`;
- `ae_engine/**`;
- `phase6_project_file.py`;
- project schema, release/reference authority, or manufacturing golden sources.

Temporary QA workflows/helpers/checkpoints must be absent from the accepted clean candidate.

## Completion
T6 is accepted only when:
- all pure T6 implementation has one legal rendering/presentation location or a justified thin root delegate;
- rendering dependencies are one-way and no geometry authority moved;
- no duplicate renderer/state source remains;
- relevant L0/L2/L3/L4 parity is GREEN;
- reconciled root gate **`gui.py <= 4,729`** is GREEN;
- full A/B has candidate-only failures = 0 and signature mismatches = 0;
- cleanup/finalization proof is terminal.

The Phase 2 final **`<=2,500`** gate remains unchanged.
