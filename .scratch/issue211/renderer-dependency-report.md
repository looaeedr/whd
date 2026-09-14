# #211 / T7 Renderer Dependency Ownership Report

Accepted parent: `2e354528791eec4307f039c805bed4b743b3c265`
Audit head: `1c53f7ac3e419454856ab34176afbde94cd85833`
Audit run: `34836595570` — terminal SUCCESS

## Authority map

### Manufacturing/state owners — HOLD
- `Phase6WorkspaceController`: physical-part presence / active physical identity / committed workspace state.
- `Phase6ProjectController`: project transaction and persistence ordering.
- `Phase6ApplicationHost._authoritative_render_data`: authoritative manufacturing render-data query/cache boundary; not a renderer extraction candidate.
- PartSpec builders, ManufacturingContext, relief resolvers, snapshot/apply/store/sync methods: manufacturing/state/persistence authority; never move merely to reduce `gui.py`.

### Existing 3D renderer owner — KEEP
- `phase6_final_scene_view.py::Phase6FinalSceneView` is already the deep 3D view module.
- Its module contract consumes already-resolved `PartRenderData` / Fold Profile and must not build PartSpec, rebuild CUTTING, parse CornerType, or call the manufacturing engine again.
- `AssemblySceneRenderData.assembly_parts` retains authoritative assembly geometry; `visible_part_keys` / `visible_box_body_piece_keys` are render-only filters.
- Therefore T7 must NOT introduce a second `gui_modules/render_3d.py` merely for symmetry. 3D first-cut = KEEP existing owner; validate its boundary and callers.

### 2D mixed methods — HOLD until dependency-contract split
- `_render_fold_designer_corner_data_view`: drawing + event binding + navigation/editor callbacks.
- `draw_indicator_box`, `draw_door`, `draw_base_plate`, `draw_indicator_door`, `draw_box_body`, `draw_end_cap`: each queries authoritative specs/render data/state and draws in the same method.
- `draw_door_layout_overview`: widget construction/selection/input windows + drawing.
- `_draw_door_layout_dividers_and_frames`: derives assembly topology/placement and draws; cannot become a renderer until resolved data is passed in explicitly in a separate refactor.
- `draw_preview`, `update_calculations`, update scheduler: orchestration, not renderer ownership.

### SAFE Move-Only 2D first cut
1. `_draw_layout_resolved_features(canvas, resolved, blank_w, blank_h, bounds, tag)`
   - static; 0 app-state reads/writes;
   - consumes already-resolved feature objects and emits Canvas primitives only.
2. `_draw_layout_baseline_secondary(canvas, scene, blank_w, blank_h, bounds, tag)`
   - static; 0 app-state reads/writes;
   - consumes an already-built drawing scene and emits Canvas primitives only.
3. `draw_grid(self, canvas, w, h, tags=None)`
   - 0 app-state reads/writes; emits background grid Canvas lines only.
   - preserve the historical bound-method calling contract by moving the function with its `self` parameter unchanged, then aliasing it back onto `Phase6ApplicationHost`.

Target for first cut: `gui_modules/render_2d.py` only.
No `gui_modules/render_3d.py` in this cut.

## Synchronization / identity / visibility contract
- canonical state/manufacturing result flows outward to 2D and 3D; neither renderer writes manufacturing state.
- physical-part identity comes from workspace/resolved manufacturing output; UI labels/tree/tab indices are projections only.
- visibility is render-only and cannot change physical existence, geometry, placement, collision datum, Registry selection, or persistence.
- validation/screenshot/bbox/probe results are evidence only and cannot become production geometry inputs.

## Gate decision
`T7_DEPENDENCY_GATE = GREEN_FOR_STAGED_2D_HELPER_MOVE_ONLY`

Everything not listed in SAFE remains HOLD/REVIEW. This gate does not authorize geometry, state, persistence, 3D-owner, or interaction refactors.
