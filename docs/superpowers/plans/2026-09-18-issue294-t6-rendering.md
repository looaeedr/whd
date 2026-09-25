---
whd_doc_role: REFERENCE
whd_contract: issue294-t6-rendering-plan
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #294 T6 — 2D rendering / overlay / interaction extraction implementation plan

## Identity
- Parent: #287
- Task: #294 / T6
- Accepted predecessor: `#293 @ e05204366146cf44d2c8cb2ad939f5f753aba030`
- Work branch: `refactor/issue294-gui-phase2-t6-rendering-20260918`
- Design: `docs/superpowers/specs/2026-09-18-issue294-t6-rendering-design.md`
- Scope reconciliation proof: run `35290713319`
- Production integration remains #296/T8 responsibility.

## Execution rule
Every extraction slice uses RED -> verify intended failure provenance -> minimal GREEN -> focused regression -> commit. T6 owns 2D presentation, overlays, view transforms and interaction routing only. It consumes existing authoritative resolved/projection data and must not become a second geometry/manufacturing/project-state authority.

No concrete Actions RUN ID means `RUN_NOT_CREATED`: fix trigger/ref/prerequisite immediately; poll only a concrete RUN.

## Task 1 — Structural gate reconciliation [LOCKED]
Machine contract: `tests/process/test_issue294_t6_scope_reconciliation.py`.

Live AST census run `35290713319` on the exact accepted #293 predecessor proved:
- `gui.py = 5,876 LOC`
- raw `<=3,000` requires 2,876 LOC removal
- pure T6 legal implementation = 1,302 LOC
- shared T4/T6 REVIEW = 348 LOC
- derived-cache REVIEW = 36 LOC
- even over-generous zero-wiring removal of all 1,686 lines leaves `4,190 LOC`
- raw gate is therefore impossible within legal T6 ownership

Legal-budget reconciliation, using the same method accepted by T4/T5:
- 37 pure T6 symbols × 3-line delegate/re-export budget = 111
- import/wiring budget = 24
- theoretical root = `4,709`
- safety margin = 20
- reconciled T6 hard gate = **`gui.py <= 4,729`**

The Phase 2 final gate remains **`gui.py <= 2,500`**. T6 may not steal T7 controller/manufacturing-adapter ownership to accelerate it.

Before extraction, the scope contract, design, plan and Issue #294 must all state the same 4,729 gate and machine-proof provenance.

## Task 2 — Architecture / ownership RED
Add `tests/test_issue294_gui_phase2_t6_rendering.py` before the new rendering package exists.

RED must prove the intended missing/current structure:
- `gui_modules/rendering/` is not yet the current owner of T6 implementation;
- current root T6 functions/methods remain real implementations rather than thin delegates;
- renderer modules may not import `gui` or `compatibility/legacy_exports.py`;
- renderer modules may not own or rebuild manufacturing geometry, part specs, project state or 3D placement;
- `_authoritative_render_data` and manufacturing/part-spec cluster stay outside rendering;
- no second renderer/projection/state source is introduced;
- ordinary module <=1,500, class <=800, method/callback <=150;
- root hard gate is 4,729.

Run architecture RED with the locked scope-reconciliation contract. The scope proof must stay GREEN while the new architecture assertions fail only for intended missing/existing-root structure.

## Task 3 — Pure shared canvas helpers
Characterize current output before moving:
- `_rects_overlap`
- `layout_reference_overlay_rects`
- `render_structural_result`
- `render_secondary_scene`
- `render_resolved_features`
- `render_surface_user_features`
- `feature_surface_from_drawing_scene`
- `_draw_phase6_annotation_projection`
- `_draw_phase6_corner_dimension_overlay`
- `_phase6_2d_material_viewport`
- `_YMirroredPreviewTransform`

Create focused `gui_modules/rendering/canvas_2d.py`, `overlays.py` and `transforms.py` seams. Preserve exact primitive/layer/text/viewport behavior. These modules consume resolved/projection data only.

## Task 4 — Indicator / door / base-plate 2D presentation
Characterize and extract:
- `draw_indicator_box`
- `draw_indicator_door`
- `draw_door_layout_overview`
- `_draw_door_layout_dividers_and_frames`
- `draw_door`
- `draw_base_plate`

Keep formula/state providers outside rendering. If a render method currently mixes result acquisition with drawing, split acquisition into host/controller routing and pass only authoritative result/projection to the rendering function.

Focused evidence must cover single door, multi-door, indicator-box/small-door presence, baseline scene projection, blind/cutting layers and finished-dimension annotation parity.

## Task 5 — Door canvas interaction routing
Characterize and extract:
- `_door_layout_cell_at_canvas_point`
- `on_door_canvas_press`
- `on_door_canvas_drag`
- `on_door_canvas_release`
- `on_door_canvas_double_click`

Interaction may own transient drag/click timing and presentation selection only. Authoritative selection/state mutations must route to the existing owner. Preserve double-click and cell hit-test semantics.

## Task 6 — Box-body / endcap 2D presentation and face/piece interaction
Characterize and extract:
- `draw_preview`
- `_box_body_face_at_canvas_point`
- `select_box_body_face`
- `on_box_body_canvas_press`
- `_box_body_baseline_faces`
- `_box_body_face_baseline_scene`
- `open_box_body_face_editor`
- `_box_body_piece_label`
- `_box_body_piece_face_key`
- `_refresh_box_body_piece_tabs_2d`
- `_on_box_body_piece_2d_tab_changed`
- `on_box_body_piece_double_click`
- `_draw_box_body_piece_preview`
- `draw_box_body`
- `draw_end_cap`

Do not move `_authoritative_render_data`, part-spec creation, manufacturing policy, collision/3D placement or project persistence into these modules.

## Task 7 — Shared REVIEW boundaries
Audit the 348 LOC T4/T6 shared surface and the 36 LOC derived-cache class separately.

Default is **do not count them toward T6 structural credit**. Move only a shared presentation fragment when ownership is proven and committed-state/control semantics remain with the accepted owner. Any such move requires dedicated characterization RED and focused GREEN.

Do not use shared/review rows merely to lower LOC.

## Task 8 — Focused T6 acceptance
Build explicit L0/L2/L3/L4 mapping.

L0:
- rendering package import direction;
- no import of `gui` or compatibility legacy exports;
- no duplicate renderer/projection implementation;
- no geometry/manufacturing/project-state owner;
- circular import scan;
- module/class/method size gates;
- root `gui.py <=4,729`.

L2:
- exact authoritative inputs/results consumed by renderer remain identical;
- 2D/3D same-state paths keep the same authoritative state.

L3:
- drawing primitives/layers;
- dimensions/annotation/reference overlays;
- viewport/transform behavior;
- box body/endcap/door/base plate/indicator projections.

L4 Xvfb:
- hit-test and selection;
- press/drag/release/double-click;
- resize and relevant zoom/pan;
- piece/face tab interaction;
- short-window presentation where applicable.

Protected invariants remain unchanged.

## Task 9 — Full Headless/Xvfb acceptance
Create temporary QA branch/workflow from the exact candidate HEAD. Run full Headless and Xvfb. For every RED, record exact nodeids/signatures and run accepted-predecessor/candidate A/B before classifying inherited.

Acceptance requires:
- candidate-only failures = 0;
- signature mismatches = 0;
- structural/protected invariants GREEN.

Use deterministic signature conditions when failure message ordering could otherwise vary.

## Task 10 — Cleanup / closure guard
Remove temporary #294 workflows/helpers/checkpoints from the accepted candidate and prove tested -> cleaned drift contains only approved hygiene deletions.

Fresh-read canonical #294 branch/head and Issue state. Build terminal checkpoint bound to:
- issue `#294`
- branch `refactor/issue294-gui-phase2-t6-rendering-20260918`
- fresh clean candidate HEAD

Use current production finalization guard authority out-of-tree if the #294 lineage predates that guard version. Invoke `assert-finalizable`, `authorize-finalization`, and `verify-finalization-proof`; fresh-lock owner/guard refs immediately before close.

Before remote branch deletion, fresh-fetch all OPEN PRs and protect both `head.ref` and `base.ref` through `tools/branch_cleanup_ref_guard.py`. Preserve the canonical accepted #294 branch for #295 lineage.

Close #294 only after remote readback can prove `closed/completed`.

## No production integration
Do not update `cleanup/2d-3d-sync` in T6. #296/T8 owns final combined acceptance, unchanged Phase 2 `gui.py <=2,500` gate, cleanup/drift audit and non-force production integration.
