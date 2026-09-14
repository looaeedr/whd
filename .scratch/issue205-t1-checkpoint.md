# #205 / T1 Checkpoint

- Parent: #203
- Depends on: #204 CLOSED / completed
- Task: T1 — SAFE/REVIEW/HOLD classification + state ownership map
- Current role: T1 實作者
- Production baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
- Work branch: `refactor/issue205-state-ownership-20260914`

## Completed
- production refetched; no drift since T0 baseline;
- fresh T1 branch created from exact production SHA;
- T1-specific preflight evidence recorded;
- human semantic reread completed for first-wave candidates, live callers, negative guards, project/workspace/settings/manufacturing ownership seams;
- classification written to `.scratch/issue205/t1-classification.md`;
- State Ownership Map written; no new Store/Event Bus/state owner introduced;
- no production symbol moved; no production behavior/source modified.

## Current classification
SAFE for T2 characterization:
- `_corner_preview_canvas_point`
- `_corner_preview_flip_y_for_target`
- `_project_toolbar_presentation`
- `render_drawing_scene` (broad caller surface; characterization mandatory)

HOLD in current wave:
- `layout_reference_overlay_rects` (no live production caller proven)
- `_YMirroredPreviewTransform` (negative legacy/compat guard; current regression forbids render-time use)
- `render_structural_result` (no live production caller; current single-source renderer contract forbids fallback use)

## Pending
- run T1 remote preflight/source-contract gate;
- capture terminal run + artifact evidence;
- remove temporary QA workflow;
- tested→cleaned and production→cleaned drift audit;
- total-control review and #205 closure;
- only after #205 closes may #206/T2 begin.

## Resume intention
Create evidence-only PR-triggered T1 gate, actively monitor to terminal, classify any RED from bounded logs, clean temporary QA workflow, drift audit, then transfer to total-control review.
