---
whd_doc_role: REFERENCE
whd_contract: gui-phase2-t0-responsibility-inventory
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #288 T0 — gui.py Responsibility Inventory

## Evidence identity

- Production baseline: `d72e81b5820b9cb54008a2dda9e96cdc673a9734`
- AST audit run: `34990930540` — SUCCESS
- AST artifact: `10405043174` (`issue288-t0-ast-inventory`)
- `gui.py` LOC: **9863**
- Top-level functions: **13**
- Classes: **6**
- Direct class methods: **254**
- Nested functions/callbacks: **82**

## T0 conclusion

`Phase6ApplicationHost` occupies **9119 lines / 237 direct methods**. The monolith is therefore an application-host responsibility problem, not a top-level-helper problem.

The worst hotspot is `_open_unified_hole_editor`: **1,333 lines / 57 nested functions**. T5 must decompose it into explicit editor view/controller/session seams; a whole-method file move is forbidden.

## Classification

- `MOVE_SAFE`: stateless/presentation responsibility may move after characterization.
- `MOVE_WITH_DEPENDENCY_CONTRACT`: preserve caller/state-owner contract before movement.
- `REVIEW`: mixed responsibility; split/prove contract first.
- `HOLD`: manufacturing/state/compatibility boundary; do not move until authority is proven.

## Top-level functions

| Symbol | Lines | Classification | Target | Reason |
|---|---:|---|---|---|
| `_endcap_profiles_for_assembly` | 178-202 (25) | HOLD | T7 manufacturing adapter/controller | assembly/fold semantic bridge |
| `_rects_overlap` | 267-271 (5) | MOVE_SAFE | T6 rendering/overlays | pure rectangle helper |
| `layout_reference_overlay_rects` | 274-357 (84) | MOVE_SAFE | T6 rendering/overlays | pure overlay layout |
| `render_structural_result` | 375-400 (26) | MOVE_SAFE | T6 rendering | renders resolved result |
| `render_secondary_scene` | 403-418 (16) | MOVE_SAFE | T6 rendering | scene presentation |
| `render_resolved_features` | 421-448 (28) | MOVE_SAFE | T6 rendering | resolved-feature presentation |
| `render_surface_user_features` | 451-455 (5) | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering | resolved-feature wrapper |
| `feature_surface_from_drawing_scene` | 458-461 (4) | REVIEW | T6 rendering/adapter | prove derived-only surface semantics |
| `_draw_phase6_annotation_projection` | 464-495 (32) | MOVE_SAFE | T6 rendering | annotation drawing |
| `_draw_phase6_corner_dimension_overlay` | 497-507 (11) | MOVE_SAFE | T6 rendering | dimension overlay drawing |
| `draw_hole_editor_hint` | 510-516 (7) | MOVE_SAFE | T5/T6 editor presentation | hint rendering |
| `_phase6_2d_material_viewport` | 519-546 (28) | MOVE_SAFE | T6 rendering/transforms | presentation viewport |
| `main` | 9837-9859 (23) | MOVE_WITH_DEPENDENCY_CONTRACT | T1 application bootstrap | startup/root orchestration |

## Classes

| Class | Lines | Direct methods | Classification | Target |
|---|---:|---:|---|---|
| `_YMirroredPreviewTransform` | 363-372 (10) | 2 | MOVE_SAFE | T6 rendering/transforms |
| `_Phase6UpdateScheduler` | 549-652 (104) | 9 | MOVE_WITH_DEPENDENCY_CONTRACT | T1 command routing |
| `_Phase6DerivedCacheOwner` | 655-690 (36) | 4 | REVIEW | T6/T7 derived-cache boundary |
| `Phase6ApplicationHost` | 693-9811 (9119) | 237 | REVIEW | T1–T7 decomposition |
| `BoxCalculatorGUI` | 9815-9820 (6) | 0 | HOLD | T7 compatibility lifecycle |
| `Phase6PrimaryApplication` | 9823-9834 (12) | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T1 application lifecycle |

## Phase6ApplicationHost exhaustive direct-method map

| Lines | Symbol | LOC | Classification | Planned slice |
|---:|---|---:|---|---|
| 694-742 | `__init__` | 49 | REVIEW | T7 remaining controller — manual dependency review |
| 745-747 | `fold_designer_box_body_profile` | 3 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 750-751 | `fold_designer_box_body_profile` | 2 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 754-756 | `fold_designer_part_bundle` | 3 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 759-760 | `fold_designer_part_bundle` | 2 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 763-765 | `_phase6_existing_parts` | 3 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 768-769 | `_phase6_existing_parts` | 2 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 772-774 | `_fold_designer_last_part_key` | 3 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 777-778 | `_fold_designer_last_part_key` | 2 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 781-783 | `_phase6_loaded_project_path` | 3 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 786-787 | `_phase6_loaded_project_path` | 2 | HOLD | T7 compatibility — legacy property shim; real owner is delegated controller |
| 789-814 | `setup_styles` | 26 | MOVE_SAFE | T2 layout — theme/ttk presentation |
| 816-1045 | `init_variables` | 230 | REVIEW | T2/T4/T7 split — mixed Tk adapters + host-owned state; split, never move whole |
| 1047-1064 | `_setting_var_map` | 18 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1066-1076 | `_collect_main_setting_values` | 11 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1079-1095 | `_serialize_corner_selection` | 17 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1097-1104 | `_serialize_manual_corner_state` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1106-1118 | `_current_cabinet_type_name` | 13 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1121-1148 | `_baseline_model_choices` | 28 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1150-1155 | `_endcap_depth_comp_t_for_family` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1157-1160 | `_known_corner_state_for_current_family` | 4 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1162-1177 | `_enforce_known_model_corner_types` | 16 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1179-1212 | `_apply_manual_corner_snapshot` | 34 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1214-1267 | `_apply_fold_designer_live_settings` | 54 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1269-1282 | `_save_fold_designer_defaults` | 14 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1284-1286 | `_apply_fold_designer_live_corner_state` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1288-1302 | `_notify_fold_designer_corner_state` | 15 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1304-1318 | `_phase6_external_sync_envelope` | 15 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1320-1354 | `_on_main_setting_var_changed` | 35 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T7 state routing — settings/corner sync; preserve service/controller authority |
| 1357-1386 | `_fold_designer_secondary_scene_rows` | 30 | REVIEW | T7 controller boundary — baseline/render/cabinet policy bridge |
| 1388-1420 | `_query_fold_designer_baseline_data` | 33 | REVIEW | T7 controller boundary — baseline/render/cabinet policy bridge |
| 1422-1460 | `_apply_cabinet_family_endcap_policy` | 39 | REVIEW | T7 controller boundary — baseline/render/cabinet policy bridge |
| 1463-1484 | `_fold_designer_corner_policy_from_payload` | 22 | HOLD | T7 controller/adapter — manufacturing/render/project boundary |
| 1486-1515 | `_authoritative_render_data` | 30 | HOLD | T7 controller/adapter — manufacturing/render/project boundary |
| 1517-1533 | `_require_verified_baseline_sources_for_manufacturing` | 17 | HOLD | T7 controller/adapter — manufacturing/render/project boundary |
| 1535-1546 | `_export_authoritative_part` | 12 | HOLD | T7 controller/adapter — manufacturing/render/project boundary |
| 1549-1720 | `_fold_designer_part_spec_from_payload` | 172 | HOLD | T7 controller/adapter — manufacturing/render/project boundary |
| 1722-1796 | `_query_fold_designer_render_data` | 75 | HOLD | T7 controller/adapter — manufacturing/render/project boundary |
| 1798-1985 | `_make_original_fold_designer_snapshot` | 188 | HOLD | T7 controller/adapter — manufacturing/render/project boundary |
| 1988-1993 | `_fold_designer_number_text` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 1997-2024 | `_apply_existing_parts_from_fold_workspace` | 28 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2026-2123 | `_apply_phase6_project_snapshot` | 98 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2125-2158 | `_compose_phase6_project_snapshot_from_main_gui` | 34 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2160-2164 | `_capture_phase6_committed_snapshot` | 5 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2172-2248 | `_apply_original_fold_designer_snapshot` | 77 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2250-2304 | `_store_fold_designer_workspace` | 55 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2306-2448 | `_apply_fold_designer_live_snapshot` | 143 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2450-2457 | `_apply_fold_designer_corner_transaction` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2459-2480 | `_reload_current_baseline_features` | 22 | MOVE_WITH_DEPENDENCY_CONTRACT | T7 project/workspace controller — snapshot/transaction orchestration |
| 2482-2599 | `open_original_fold_designer` | 118 | MOVE_WITH_DEPENDENCY_CONTRACT | T1 application lifecycle — workspace window lifecycle |
| 2601-2633 | `_apply_ui_text_size_preference` | 33 | MOVE_WITH_DEPENDENCY_CONTRACT | T2/T4 presentation — UI preference/assembly routing |
| 2635-2636 | `on_ui_text_size_changed` | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T2/T4 presentation — UI preference/assembly routing |
| 2638-2664 | `_current_box_assembly_type` | 27 | MOVE_WITH_DEPENDENCY_CONTRACT | T2/T4 presentation — UI preference/assembly routing |
| 2666-2699 | `_set_box_assembly_type` | 34 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2701-2705 | `on_box_assembly_changed` | 5 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2707-2718 | `_effective_endcap_fw` | 12 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2720-2734 | `_sync_endcap_fw_controls` | 15 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2736-2743 | `_apply_endcap_fw_snapshot` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2745-2753 | `on_endcap_fw_follow_changed` | 9 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2755-2778 | `on_fw_selected` | 24 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2780-2787 | `_baseline_source_model` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2789-2794 | `_door_material_frame_width` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2796-2802 | `_sync_fold_designer_manual_corner_context` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2804-2817 | `_current_manual_corner_part_key` | 14 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2819-2838 | `_manual_corner_policy` | 20 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2840-2852 | `_box_body_corner_policies` | 13 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2854-2871 | `_phase6_resolved_finished_dimensions` | 18 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2873-2888 | `_draw_phase6_finished_dimension_summary` | 16 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2890-2903 | `_box_body_finished_height` | 14 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2926-2944 | `_fixed_corner_summary` | 19 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2946-2952 | `_corner_part_type_editable` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2954-2956 | `_corner_part_editable` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2958-2963 | `_corner_part_parameters_unlockable` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2965-2966 | `_manual_corner_parameters_unlocked` | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2968-2969 | `_manual_corner_parameters_editable` | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2971-2972 | `_reset_manual_corner_parameter_locks` | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2974-2983 | `toggle_manual_corner_parameter_lock` | 10 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 2986-3002 | `_corner_parameter_summary` | 17 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3004-3189 | `create_corner_type_panel` | 186 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3191-3231 | `_draw_corner_type_icon` | 41 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3233-3238 | `_pair_for_corner_target` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3240-3251 | `_normalize_manual_corner_target` | 12 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3253-3256 | `_manual_selection_for_target` | 4 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3258-3271 | `select_manual_corner` | 14 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3273-3290 | `on_manual_corner_pair_same_changed` | 18 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3292-3310 | `set_manual_corner_type` | 19 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3313-3315 | `_corner_number_text` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3317-3353 | `_selection_from_manual_corner_controls` | 37 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3355-3372 | `on_manual_corner_mode_changed` | 18 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3374-3390 | `on_manual_corner_parameter_changed` | 17 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3392-3422 | `_refresh_manual_corner_parameter_rows` | 31 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3424-3531 | `refresh_corner_type_panel` | 108 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 corner/part panels — panel + state-changing callbacks |
| 3533-3843 | `create_widgets` | 311 | REVIEW | T2 main layout — 311-line mixed layout/callback method; split by region |
| 3845-3849 | `on_base_plate_same_toggle` | 5 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3851-3857 | `sync_base_plate_shrink` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3859-3869 | `create_input_row` | 11 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3871-3882 | `create_result_row` | 12 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3884-3890 | `_phase6_current_existing_parts` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3892-3899 | `_phase6_set_part_presence` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3901-3944 | `_phase6_refresh_presence_ui` | 44 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3946-3948 | `create_separator` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 3950-4104 | `create_advanced_inputs` | 155 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4106-4116 | `create_sub_input` | 11 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4118-4127 | `toggle_advanced_panel` | 10 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4129-4177 | `setup_tab_z_ui` | 49 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4179-4288 | `_render_fold_designer_corner_data_view` | 110 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4290-4294 | `_attach_part_hole_entrypoint` | 5 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4296-4355 | `setup_tab_endcap_ui` | 60 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4357-4369 | `setup_tab_base_plate_ui` | 13 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4372-4374 | `_door_layout_number_text` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 part panels — input/presence/tab presentation |
| 4376-4388 | `_new_door_layout_column` | 13 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4390-4404 | `set_door_layout_columns` | 15 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4406-4415 | `_ensure_door_layout_default` | 10 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4418-4425 | `_parse_layout_value` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4427-4438 | `_recompute_column_height_remainder` | 12 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4440-4491 | `_recompute_door_layout_remainders` | 52 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4493-4508 | `get_door_layout_columns` | 16 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4510-4519 | `get_door_layout_cells` | 10 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4522-4523 | `_door_layout_cell_key` | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4525-4533 | `get_selected_door_layout_cell` | 9 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4535-4566 | `select_door_layout_cell` | 32 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4568-4574 | `_sync_door_canvas_double_click_binding` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4576-4585 | `toggle_multi_door_layout` | 10 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4587-4595 | `_reject_door_layout_dimension` | 9 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4597-4629 | `commit_door_layout_width` | 33 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4631-4670 | `commit_door_layout_height` | 40 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4672-4677 | `add_door_layout_column` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4679-4696 | `_remap_door_layout_owned_data` | 18 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4698-4715 | `remove_door_layout_column` | 18 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4717-4722 | `add_door_layout_height` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4724-4738 | `remove_door_layout_height` | 15 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4740-4747 | `_on_door_layout_value_changed` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4749-4754 | `_on_total_door_dimension_changed` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4756-4769 | `_request_phase6_update` | 14 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4771-4776 | `_flush_phase6_authoritative_state` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4778-4779 | `_on_main_geometry_var_changed` | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4782-4792 | `_receiving_inner_door_stable_id_for_cell` | 11 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4794-4799 | `_receiving_inner_door_enabled` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4801-4813 | `_receiving_inner_door_inward_offset` | 13 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4815-4833 | `_set_receiving_inner_door_inward_offset` | 19 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4835-4857 | `_commit_receiving_inner_door_inward_offset` | 23 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4859-4885 | `_set_receiving_inner_door_enabled` | 27 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4887-4909 | `_commit_receiving_inner_door_checkbox` | 23 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4911-4936 | `refresh_door_layout_status` | 26 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 4938-5056 | `rebuild_door_layout_ui` | 119 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 5058-5160 | `setup_tab_door_ui` | 103 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 5162-5203 | `setup_tab_indicator_box_ui` | 42 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 door/multipart panels — door-layout UI + routing |
| 5205-5207 | `on_layers_count_changed` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5209-5234 | `rebuild_layers_config_ui` | 26 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5238-5297 | `draw_indicator_box` | 60 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 5299-5331 | `_normalize_door_indicator_state` | 33 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5333-5342 | `_door_layout_indicator_state_for_key` | 10 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5344-5352 | `_destroy_door_layout_entry_widgets` | 9 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5354-5365 | `_door_layout_entry_menu` | 12 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5373-5382 | `_door_layout_cell_result` | 10 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5384-5427 | `_door_layout_cell_resolved_features` | 44 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5429-5455 | `_door_layout_baseline_scene` | 27 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5457-5531 | `open_door_indicator_component_editor` | 75 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5533-5587 | `open_door_layout_cell_editor` | 55 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 5589-5738 | `draw_door_layout_overview` | 150 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 5740-5826 | `_draw_door_layout_dividers_and_frames` | 87 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 5828-6021 | `draw_door` | 194 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 6023-6107 | `draw_base_plate` | 85 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 6109-6115 | `_disable_all_door_indicators` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6117-6125 | `_disable_indicator_box_for_door_indicator` | 9 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6127-6134 | `on_indicator_box_toggle` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6136-6140 | `on_door_indicator_toggle` | 5 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6142-6144 | `on_door_layers_count_changed` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6146-6171 | `rebuild_door_layers_config_ui` | 26 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6173-6175 | `reset_door_indicator_offset_x` | 3 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6177-6181 | `reset_door_indicator_offset_y` | 5 | MOVE_WITH_DEPENDENCY_CONTRACT | T4/T6 door UI — door/indicator UI split |
| 6183-6190 | `_door_layout_cell_at_canvas_point` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 6192-6228 | `on_door_canvas_press` | 37 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 6230-6247 | `on_door_canvas_drag` | 18 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 6249-6250 | `on_door_canvas_release` | 2 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 6252-6259 | `on_door_canvas_double_click` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D presentation/interaction |
| 6261-6314 | `ask_xy_dialog` | 54 | MOVE_WITH_DEPENDENCY_CONTRACT | T5 editors/dialogs — modal workflow |
| 6316-6356 | `on_double_click_indicator` | 41 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 indicator panel — indicator UI routing |
| 6358-6364 | `_indicator_small_door_size_chain_label` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 indicator panel — indicator UI routing |
| 6366-6387 | `setup_tab_indicator_door_ui` | 22 | MOVE_WITH_DEPENDENCY_CONTRACT | T4 indicator panel — indicator UI routing |
| 6389-6445 | `draw_indicator_door` | 57 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering — 2D presentation |
| 6447-6456 | `_inherit_known_corner_state_into_custom` | 10 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6458-6495 | `_capture_cabinet_family_runtime` | 38 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6497-6529 | `_restore_cabinet_family_runtime` | 33 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6531-6609 | `_apply_cabinet_family_for_current_model` | 79 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6612-6699 | `on_baseline_changed` | 88 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6701-6716 | `bind_live_updates` | 16 | MOVE_WITH_DEPENDENCY_CONTRACT | T1 command routing — scheduler/orchestrator seam |
| 6719-6752 | `get_float_values` | 34 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6754-6778 | `_active_indicator_box_groups_for_results` | 25 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6780-6794 | `_has_any_indicator_box` | 15 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6796-6800 | `_clear_indicator_box_result_values` | 5 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6802-6844 | `_refresh_indicator_box_result_values` | 43 | REVIEW | T7 application/domain controller — cabinet runtime + calculation result routing |
| 6846-6977 | `update_calculations` | 132 | HOLD | root/T7 orchestration — central calculation orchestrator; not a view helper |
| 6980-6990 | `draw_preview` | 11 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 6995-7000 | `_box_body_face_at_canvas_point` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7002-7016 | `select_box_body_face` | 15 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7018-7044 | `on_box_body_canvas_press` | 27 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7046-7065 | `_box_body_baseline_faces` | 20 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7067-7073 | `_box_body_face_baseline_scene` | 7 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7075-7107 | `open_box_body_face_editor` | 33 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7110-7118 | `_box_body_piece_label` | 9 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7121-7126 | `_box_body_piece_face_key` | 6 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7128-7194 | `_refresh_box_body_piece_tabs_2d` | 67 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7196-7211 | `_on_box_body_piece_2d_tab_changed` | 16 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7213-7220 | `on_box_body_piece_double_click` | 8 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7222-7274 | `_draw_box_body_piece_preview` | 53 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7276-7382 | `draw_box_body` | 107 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7384-7441 | `draw_end_cap` | 58 | MOVE_WITH_DEPENDENCY_CONTRACT | T6 rendering/interaction — 2D render/selection entrypoints |
| 7443-7445 | `_manufacturing_context` | 3 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7447-7487 | `_box_body_part_spec_from_values` | 41 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7489-7496 | `_box_body_part_spec` | 8 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7498-7571 | `_end_cap_part_spec_from_values` | 74 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7574-7584 | `_phase6_relief_profile_signature` | 11 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7586-7701 | `_resolved_committed_assembly_relief_cuts` | 116 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7703-7727 | `_end_cap_part_spec` | 25 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7729-7754 | `_door_part_spec_from_values` | 26 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7756-7770 | `_single_door_part_spec` | 15 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7772-7796 | `_door_layout_part_spec` | 25 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7798-7810 | `_validate_indicator_state_fit` | 13 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7812-7818 | `_validate_single_door_indicator_fit` | 7 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7820-7825 | `_validate_door_layout_indicator_fit` | 6 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7827-7839 | `_base_plate_part_spec_from_values` | 13 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7841-7847 | `_base_plate_part_spec` | 7 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7849-7854 | `_indicator_box_part_spec_from_values` | 6 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7856-7861 | `_indicator_box_part_spec` | 6 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7863-7882 | `_indicator_door_part_spec_from_values` | 20 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7884-7888 | `_indicator_door_part_spec` | 5 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7890-7976 | `_indicator_component_editor_contexts` | 87 | HOLD | T7 manufacturing adapter/controller — part-spec/manufacturing boundary; never view/render |
| 7978-7989 | `export_multi_door_layout_dxfs` | 12 | REVIEW | T7 project/export/state adapters — DXF/export or state snapshot boundary |
| 7991-8022 | `export_multi_door_indicator_box_parts` | 32 | REVIEW | T7 project/export/state adapters — DXF/export or state snapshot boundary |
| 8024-8185 | `export_selected_dxf` | 162 | REVIEW | T7 project/export/state adapters — DXF/export or state snapshot boundary |
| 8188-8214 | `_single_door_indicator_state_snapshot` | 27 | REVIEW | T7 project/export/state adapters — DXF/export or state snapshot boundary |
| 8216-8232 | `_apply_single_door_indicator_state` | 17 | REVIEW | T7 project/export/state adapters — DXF/export or state snapshot boundary |
| 8234-8241 | `_apply_multi_door_indicator_state` | 8 | REVIEW | T7 project/export/state adapters — DXF/export or state snapshot boundary |
| 8243-8456 | `open_part_hole_editor` | 214 | MOVE_WITH_DEPENDENCY_CONTRACT | T5 editors/dialogs — hole editor workflow; transient state only |
| 8458-9790 | `_open_unified_hole_editor` | 1333 | MOVE_WITH_DEPENDENCY_CONTRACT | T5 editors/dialogs — hole editor workflow; transient state only |
| 9792-9811 | `open_hole_editor` | 20 | MOVE_WITH_DEPENDENCY_CONTRACT | T5 editors/dialogs — hole editor workflow; transient state only |

## Nested functions/callbacks

| Parent | Nested symbol | Lines | LOC |
|---|---|---:|---:|
| `layout_reference_overlay_rects` | `rect_for` | 288-290 | 3 |
| `layout_reference_overlay_rects` | `fits` | 292-296 | 5 |
| `layout_reference_overlay_rects` | `choose` | 298-320 | 23 |
| `Phase6ApplicationHost._fold_designer_part_spec_from_payload` | `payload_policy` | 1601-1611 | 11 |
| `Phase6ApplicationHost._make_original_fold_designer_snapshot` | `number` | 1799-1803 | 5 |
| `Phase6ApplicationHost.open_original_fold_designer` | `destroy_designer_window` | 2516-2536 | 21 |
| `Phase6ApplicationHost.open_original_fold_designer` | `close_designer` | 2538-2554 | 17 |
| `Phase6ApplicationHost.open_original_fold_designer` | `load_project_from_designer` | 2556-2558 | 3 |
| `Phase6ApplicationHost.open_original_fold_designer` | `save_project_from_designer` | 2560-2563 | 4 |
| `Phase6ApplicationHost.open_original_fold_designer` | `project_path_changed` | 2565-2567 | 3 |
| `Phase6ApplicationHost._draw_corner_type_icon` | `pt` | 3208-3211 | 4 |
| `Phase6ApplicationHost.create_widgets` | `on_frame_configure` | 3632-3633 | 2 |
| `Phase6ApplicationHost.create_widgets` | `on_canvas_resize` | 3634-3635 | 2 |
| `Phase6ApplicationHost.create_widgets` | `on_mousewheel` | 3636-3637 | 2 |
| `Phase6ApplicationHost.create_widgets` | `make_chk` | 3745-3753 | 9 |
| `Phase6ApplicationHost.create_advanced_inputs` | `make_grid_input` | 4052-4063 | 12 |
| `Phase6ApplicationHost._set_receiving_inner_door_enabled` | `sort_key` | 4877-4882 | 6 |
| `Phase6ApplicationHost._draw_door_layout_dividers_and_frames` | `world_to_canvas` | 5747-5751 | 5 |
| `Phase6ApplicationHost.draw_base_plate` | `to_canvas` | 6070-6071 | 2 |
| `Phase6ApplicationHost.ask_xy_dialog` | `on_ok` | 6289-6296 | 8 |
| `Phase6ApplicationHost.ask_xy_dialog` | `on_cancel` | 6298-6299 | 2 |
| `Phase6ApplicationHost._box_body_part_spec_from_values` | `resolved_ybottom` | 7452-7458 | 7 |
| `Phase6ApplicationHost.export_selected_dxf` | `run_part` | 8079-8085 | 7 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `set_indicator_page_visible` | 8565-8578 | 14 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `request_indicator_redraw` | 8580-8586 | 7 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_box_distance_toggle` | 8588-8590 | 3 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `collect_indicator_state` | 8592-8622 | 31 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `rebuild_indicator_group_controls` | 8660-8674 | 15 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `small_row` | 8733-8737 | 5 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `toggle_fullscreen` | 8779-8805 | 27 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `validate_current_indicator_fit` | 8828-8855 | 28 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `add_group_entry` | 8888-8896 | 9 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `sync_all` | 8934-8937 | 4 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `feature_display` | 8939-8947 | 9 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `refresh_created` | 8949-8955 | 7 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `active_reference_guide` | 8960-8971 | 12 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `refresh_reference_fields` | 8973-9002 | 30 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `redraw` | 9004-9124 | 121 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `draw_extra` | 9034-9107 | 74 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_catalog_select` | 9128-9139 | 12 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `make_feature` | 9141-9157 | 17 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `set_insert_mode` | 9159-9166 | 8 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_catalog_double_click` | 9170-9184 | 15 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `commit_active_edit` | 9186-9190 | 5 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `undo_last_action` | 9192-9198 | 7 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `cancel_active_edit` | 9200-9209 | 10 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `begin_edit` | 9211-9224 | 14 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `select_feature` | 9226-9227 | 2 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_canvas_down` | 9229-9248 | 20 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_canvas_drag` | 9250-9260 | 11 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_canvas_up` | 9262-9265 | 4 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `set_reference_anchor` | 9267-9275 | 9 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_canvas_right` | 9277-9288 | 12 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_created_select` | 9290-9293 | 4 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `toggle_created_process` | 9295-9308 | 14 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `delete_selected` | 9310-9317 | 8 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `apply_reference_value` | 9321-9353 | 33 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `schedule_reference_value` | 9355-9362 | 8 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `rotate_selected` | 9369-9382 | 14 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `open_round_hole_settings` | 9387-9606 | 220 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `same_diameter_gap_from_center` | 9420-9421 | 2 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `same_diameter_center_from_gap` | 9423-9424 | 2 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `sync_from_center` | 9426-9438 | 13 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `sync_from_gap` | 9440-9452 | 13 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `driver_value` | 9518-9527 | 10 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `aligned_seed` | 9529-9537 | 9 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `apply_pattern` | 9539-9566 | 28 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `close_round_window` | 9575-9582 | 8 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `cancel_round` | 9584-9587 | 4 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `confirm_round` | 9589-9593 | 5 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `_baseline_status_color` | 9610-9611 | 2 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `_switch_editor_context` | 9613-9642 | 30 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `_selected_indicator_component_key` | 9644-9650 | 7 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `_refresh_indicator_component_contexts` | 9652-9691 | 40 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `_on_editor_page_changed` | 9693-9704 | 12 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `_on_indicator_component_page_changed` | 9706-9709 | 4 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `confirm_reference_edit` | 9721-9726 | 6 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `confirm_all` | 9732-9747 | 16 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `cancel_all` | 9749-9757 | 9 |
| `Phase6ApplicationHost._open_unified_hole_editor` | `on_escape` | 9762-9770 | 9 |
| `Phase6ApplicationHost.open_hole_editor` | `sync_legacy` | 9805-9806 | 2 |
| `main` | `open_project_after_startup` | 9852-9856 | 5 |

## Required extraction order

1. T1 lifecycle + scheduler/command routing.
2. T2 root layout/style split; never move `create_widgets` whole.
3. T3 selector/navigation over WorkspaceController state.
4. T4 part panels; split `init_variables` by owner vs Tk adapter.
5. T5 editor/dialog decomposition, led by the 1,333-line unified hole editor.
6. T6 rendering/overlay/interaction consuming resolved data only.
7. T7 project/visibility/controllers + HOLD/REVIEW manufacturing and compatibility boundaries.
8. T8 combined structural/functional/drift acceptance.

## T0 gate

- Meaningful top-level/class/direct-method/nested-callback structure: **mapped**.
- Every >150-line function/method: **classified by the exhaustive table and slice rules**.
- Every >800-line class: **classified** (`Phase6ApplicationHost`).
- Manufacturing-boundary methods are HOLD/REVIEW, not treated as view helpers.
- No production extraction performed during T0.
- **Responsibility inventory gate: GREEN.**
