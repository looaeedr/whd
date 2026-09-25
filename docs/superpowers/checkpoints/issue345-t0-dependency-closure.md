# Issue #345 T0 — final move-set dependency closure evidence

## Identity

- Master: #344
- Task: #345 / T0
- Production base: `cleanup/2d-3d-sync`
- Live production HEAD locked at task start: `cfa1e0540ef3414913d4c5f402f4cf0fa5d727b1`
- Working branch: `refactor/issue345-manufacturing-preflight-20260918`
- AST gate commit: `572e772cc5ca29daddb276acbdae7f6720bdd91b`
- QA RUN: `35357314254`
- QA job: `105639717828`
- Result: **SUCCESS**

No production implementation file was modified in T0.

## Live bridge census

AST gate on the live base reports:

- `fold_designer_bridge.py`: 10,849 lines
- manufacturing cluster start: `_phase6_assembly_relief_clearance@6225`
- manufacturing cluster end: `_phase6_resolve_manufacturing_geometry@7791`
- final expanded move-set: 22 symbols

## Final expanded move-set

```text
_PHASE6_ASSEMBLY_PLACEMENTS
_phase6_apply_resolved_cut_to_owner
_phase6_apply_resolved_cut_to_part
_phase6_assembly_placement_for_part
_phase6_assembly_relief_clearance
_phase6_box_body_piece_solver_key
_phase6_build_joint_world_geometry
_phase6_current_cabinet_family
_phase6_cut_geometry_from_state_item
_phase6_door_part_assembly_placement
_phase6_expand_box_body_fw_world_mid
_phase6_joint_registry_diagnostic_info
_phase6_joint_relief_state_item_matches
_phase6_manufacturing_state_signature
_phase6_relief_polygon_coords
_phase6_resolve_explicit_joint_reliefs
_phase6_resolve_family_divider_reliefs
_phase6_resolve_manufacturing_geometry
_phase6_shift_multistage_terminal_fold_world_mid
_phase6_side_wrap_target_corners
_phase6_signature_canonical_value
_phase6_solution_is_committable
```

`_phase6_make_assembly_scene_render_data` is intentionally excluded: it remains a scene adapter in the bridge.

## AST free-variable / bridge-symbol closure

The machine gate found exactly five bridge-external symbols:

```text
_phase6_is_box_body_physical_piece_key
_phase6_mesh_profiles_for_part
_phase6_operator_finished_dimensions
_phase6_publish_live_state
_phase6_scene_query_payload_for_part
```

Classification:

### A — existing canonical owner

- `_phase6_is_box_body_physical_piece_key`
  - manufacturing owner must import `phase6_part_navigation.is_box_body_physical_piece_key`
  - the manufacturing call site is authorized to change identifier from the bridge wrapper name to the canonical name

### C — self-coupled shared bridge helpers

- `_phase6_mesh_profiles_for_part`
- `_phase6_operator_finished_dimensions`
- `_phase6_publish_live_state`
- `_phase6_scene_query_payload_for_part`

These remain bridge-owned and must be supplied to the manufacturing implementation through `Phase6FoldDesignerApp` bound-method wiring. The manufacturing module must not import the bridge.

Machine result:

```text
PASS: final move-set dependency closure is exactly A(1)+C(4); unknown=0
PASS: predicted phase6_manufacturing_geometry -> fold_designer_bridge imports = 0
```

Therefore:

- unknown / unclassified dependency count = **0**
- predicted reverse bridge import count = **0**

## Current class-wiring inventory

At the live T0 base:

- `Phase6FoldDesignerApp._phase6_publish_live_state = _phase6_publish_live_state` already exists.
- `_phase6_mesh_profiles_for_part` is not yet class-wired.
- `_phase6_operator_finished_dimensions` is not yet class-wired.
- `_phase6_scene_query_payload_for_part` is not yet class-wired.

The three missing bindings are expected T6 compatibility work, not a T0 dependency surprise.

## Shared caller inventory outside the move-set

The live scan found bridge callers that must remain valid after extraction:

- `_phase6_assembly_relief_clearance`
  - `_phase6_serialize_assembly_relief_state`
  - `_phase6_registry_validate_candidate_3d`
- `_phase6_current_cabinet_family`
  - `_phase6_registry_validate_candidate_3d`
  - `_phase6_status_projection`
  - `_phase6_query_assembly_render_data`
  - `_phase6_create_relief_promotion_candidates`
- `_phase6_solution_is_committable`
  - `_phase6_serialize_assembly_relief_state`
- `_phase6_manufacturing_state_signature`
  - `_phase6_show_assembly`
  - `_fix11_activate_part`
- `_phase6_resolve_manufacturing_geometry`
  - `_phase6_box_body_piece_render_data`
  - `_phase6_query_final_render_data`
  - `_phase6_query_assembly_render_data`
  - `_phase6_render_data_for_blank`
- `_phase6_relief_polygon_coords`
  - `_phase6_serialize_assembly_relief_state`
- `_PHASE6_ASSEMBLY_PLACEMENTS`
  - `_phase6_is_base_plate_part_key`
  - `_phase6_registry_validate_candidate_3d`

These symbols therefore require a single canonical implementation plus bridge-side import/re-export where needed; duplication is forbidden.

## T0 gate conclusion

T0 dependency closure is accepted for the live base:

1. the complete expanded move-set was analyzed, including non-contiguous B-class symbols;
2. no second-order dependency appeared;
3. every external bridge symbol is classified by the approved A/C rules;
4. the zero-reverse-import design is feasible without a Phase 2 API redesign;
5. no production source implementation drift occurred.

Next predecessor-gated task: #346 / T1 characterization baseline.
