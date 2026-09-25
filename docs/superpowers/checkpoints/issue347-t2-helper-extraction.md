# Issue #347 T2 — Manufacturing helper extraction evidence

## Identity
- Master: #344
- Task: #347 / T2
- Predecessor: #346 accepted HEAD `52dca1add3f39663e178fce113b9fc77d361bd6a`
- Branch: `refactor/issue347-manufacturing-helpers-extraction-20260918`

## Move-only scope
New canonical owner: `phase6_manufacturing_geometry.py`

Moved as one canonical implementation:
- `_PHASE6_ASSEMBLY_PLACEMENTS`
- `_phase6_door_part_assembly_placement`
- `_phase6_assembly_placement_for_part`
- `_phase6_relief_polygon_coords`
- `_phase6_assembly_relief_clearance`
- `_phase6_current_cabinet_family`
- `_phase6_solution_is_committable`
- `_phase6_apply_resolved_cut_to_part`
- `_phase6_apply_resolved_cut_to_owner`
- `_phase6_side_wrap_target_corners`
- `_phase6_box_body_piece_solver_key`
- `_phase6_expand_box_body_fw_world_mid`
- `_phase6_shift_multistage_terminal_fold_world_mid`
- `_phase6_joint_relief_state_item_matches`
- `_phase6_cut_geometry_from_state_item`
- `_phase6_signature_canonical_value`
- `_phase6_manufacturing_state_signature`
- `_phase6_joint_registry_diagnostic_info`

Bridge now imports/re-exports these symbols from the new owner.

## Static ownership
T2 extraction contract proves:
- all moved symbols are defined by `phase6_manufacturing_geometry.py`
- none of them remains defined in `fold_designer_bridge.py`
- bridge re-export objects are identical to owner objects
- AST reverse imports from `phase6_manufacturing_geometry.py` to `fold_designer_bridge.py` = **0**

Bridge LOC:
- before T2: **10,849**
- after T2: **10,276**
- reduction: **573 lines**

## RED
RUN `35358233218`
- **2 FAIL**
- both expected `ModuleNotFoundError: No module named 'phase6_manufacturing_geometry'`
- proves extraction contract was RED before implementation

## Focused GREEN
RUN `35358356688`
- focused extraction contract: **2 PASS**

## T1-equivalent parity acceptance
RUN `35358447248`

- focused: **2 PASS**
- broader Headless: **140 PASS / 16 SKIP / 0 FAIL**
- broader Xvfb with exact T1 inherited RED nodes deselected: **154 PASS / 2 DESELECTED / 0 FAIL**

The two deselected node IDs are exactly the T1 failure contract in:
`config/issue346_t1_xvfb_failure_contract.json`

No new failure was introduced by T2.

## Phase boundary
Not moved in T2:
- `_phase6_build_joint_world_geometry` — T3
- `_phase6_resolve_explicit_joint_reliefs` — T4
- `_phase6_resolve_family_divider_reliefs` — remains for later manufacturing solver slice
- `_phase6_resolve_manufacturing_geometry` — T5
- `_phase6_make_assembly_scene_render_data` — remains bridge-owned scene adapter

## Conclusion
T2 accepted: low-coupling manufacturing helpers, placements, replay/cut helpers, cache-signature helpers, and shared pure helpers now have one canonical owner with zero reverse bridge import and T1-equivalent behavior.
