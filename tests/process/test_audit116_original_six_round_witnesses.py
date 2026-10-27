"""Mandatory original 116-item six-round regression identity/coverage integrity.

This *process* check protects original source-scoped regression functions
after the abandoned audit branch diverged. It does not certify Windows UAT,
real operator observations, original manufacturer output or 116/116 signoff.
Actual functionality must still pass the same canonical Product CI run.
Baseline: whd commit 5702703c95c9f216f62c1553288de49a9cba8b61.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.product_ci_regression import PYTEST_PATHS

ROOT = Path(__file__).resolve().parents[2]
# Original test functions and minimum executable assert/raises witnesses,
# measured from immutable round-six baseline commit 5702703c.
ORIGINAL_TEST_WITNESSES = {
  "tests/test_deep_audit_14_bugs_regression.py": {
    "test_bug1_main_sync_fingerprint_updates_after_fold_designer_live_settings": [
      4,
      0
    ],
    "test_bug2_multi_door_hole_edits_in_2d_override_stale_surface_features": [
      2,
      0
    ],
    "test_bug3_custom_part_only_change_syncs_surface_features": [
      3,
      0
    ],
    "test_bug4_receiving_multi_bay_projection_does_not_leak_bay0_door_state": [
      3,
      0
    ],
    "test_bug5_translated_scene_preserves_text_primitive_semantic_id": [
      3,
      0
    ],
    "test_bug6_material_from_cutting_components_promotes_outer_linework_over_inner_polyline": [
      2,
      0
    ],
    "test_bug7_scene_with_replaced_primary_cutting_preserves_inner_closed_polyline_holes": [
      1,
      0
    ],
    "test_bug8_text_region_respects_mtext_attachment_points": [
      4,
      0
    ],
    "test_bug9_displaced_callout_leader_is_included_in_obstacle_line_regions": [
      2,
      0
    ],
    "test_bug10_existing_conflict_geometry_handles_short_polyline_and_material_epsilon": [
      2,
      0
    ],
    "test_bug11_derived_physical_part_key_includes_fixing_plate_nfb_layer_and_nfb_pad": [
      5,
      0
    ],
    "test_bug12_and_bug13_registry_diagnostics_panel_form_and_source_round_trip": [
      10,
      0
    ],
    "test_bug14_phase6_bending_ui_remove_pairs_by_phase6_key": [
      4,
      0
    ]
  },
  "tests/test_deep_audit_round2_bugfixes.py": {
    "test_r2_1_and_r2_6_derived_keys_and_custom_parts_preserved_on_bootstrap_and_refresh": [
      5,
      0
    ],
    "test_r2_1_commit_box_body_right_side_syncs_zr1_and_uses_settings_thickness": [
      2,
      0
    ],
    "test_r2_2_save_current_part_custom_part_saves_bend_ui_and_outside_compensation": [
      3,
      0
    ],
    "test_r2_3_workspace_controller_quantity_mode_feature_sync_and_snapshot": [
      3,
      0
    ],
    "test_r2_4_custom_part_only_change_first_feature_on_custom_part": [
      1,
      0
    ],
    "test_r2_5_project_controller_quantity_mode_and_workspace_export": [
      6,
      0
    ],
    "test_r2_7_and_r2_8_hole_editor_sync_and_multi_door_indicator_state_trigger_update": [
      2,
      0
    ],
    "test_r2_9_remap_door_layout_owned_data_remaps_handle_edges_inner_doors_and_surface_features": [
      5,
      0
    ],
    "test_r2_10_render_snapshots_passes_model_name_and_frame_width_to_derive_box_body_dividers": [
      2,
      0
    ],
    "test_r2_12_receiving_inner_door_frames_top_only_and_half_back_panel_requires_multi_door": [
      3,
      2
    ],
    "test_r2_13_and_r2_14_receiving_layout_and_switch_layout_validation_and_projection": [
      4,
      4
    ],
    "test_r2_15_and_r2_16_quantity_feature_errors_and_validate_setting_tuple_normalization": [
      4,
      0
    ],
    "test_r2_17_clip_axis_bend_geometry_collection_and_round_refill_local_span": [
      4,
      0
    ],
    "test_r2_18_mirror_drawing_scene_x_reflects_check_text_attachment_point": [
      2,
      0
    ]
  },
  "tests/test_deep_audit_round3_bugfixes.py": {
    "test_r3_1_receiving_mode_session_preserves_inner_door_candidates": [
      5,
      0
    ],
    "test_r3_2_materialize_project_snapshot_does_not_leak_bay1_door_state_to_bay2": [
      4,
      0
    ],
    "test_r3_3_endcap_world_relief_solver_passes_preserve_core_origin": [
      2,
      0
    ],
    "test_r3_4_certified_relief_family_key_normalizes_receiving_alias": [
      4,
      0
    ],
    "test_r3_5_is_receiving_snapshot_recognizes_receiving_alias": [
      4,
      0
    ],
    "test_r3_6_family_model_transition_canonical_receiving_and_none_structure": [
      3,
      0
    ],
    "test_r3_7_receiving_alias_accepted_across_navigation_and_projection": [
      3,
      0
    ],
    "test_r3_8_readback_marking_lines_rejects_extra_marking_lines": [
      0,
      1
    ],
    "test_r3_9_receiving_shared_settings_rejects_negative_and_bool_indices": [
      0,
      5
    ],
    "test_r3_10_receiving_destructive_tail_ids_rejects_bool_and_float": [
      0,
      4
    ],
    "test_r3_11_box_body_piece_features_side_panel_clips_to_piece_bounds": [
      2,
      0
    ],
    "test_r3_12_13_14_gui_rendering_and_dialog_fixes": [
      5,
      0
    ]
  },
  "tests/test_deep_audit_round4_bugfixes.py": {
    "test_bug51_assembly_visibility_reads_app_vars_without_panel_owner": [
      4,
      0
    ],
    "test_bug52_final_scene_ports_and_manufacturing_request_use_operator_dimensions": [
      8,
      0
    ],
    "test_bug53_hit_test_resolved_features_handles_open_and_layered_profiles": [
      5,
      0
    ],
    "test_bug54_resolved_features_to_primitives_open_two_point_and_endcap_check_actual_flanges": [
      3,
      0
    ],
    "test_bug55_normalize_rotation_rejects_bool_and_fractional_degrees": [
      0,
      4
    ],
    "test_bug56_standard_corner_geometry_validates_corner_name_and_mapping_rows_with_negative_lengths": [
      2,
      1
    ],
    "test_bug57_indicator_groups_reject_bool_and_non_positive": [
      0,
      3
    ],
    "test_bug58_receiving_candidates_and_shared_settings_validate_feature_types": [
      0,
      4
    ],
    "test_bug59_part_adapters_reject_bool_nan_and_negative_inputs": [
      0,
      6
    ],
    "test_bug60_build_box_body_result_from_fold_profile_supports_mapping_rows": [
      2,
      0
    ],
    "test_bug61_geometry_dataclasses_reject_bool_and_non_finite": [
      0,
      4
    ],
    "test_bug62_door_dividers_inner_panels_and_frames_reject_bool_and_nan": [
      0,
      5
    ],
    "test_bug63_manufacturing_projection_checks_fold_designer_app_snapshot": [
      0,
      1
    ],
    "test_bug64_reconcile_box_body_structure_default_driver_and_inactive_mode_tolerance": [
      6,
      0
    ],
    "test_bug65_custom_part_only_change_detects_custom_profile_edits_and_blocks_standard_edits": [
      2,
      0
    ],
    "test_bug66_receiving_bay_preview_request_preserves_custom_parts": [
      2,
      0
    ],
    "test_bug67_workspace_remove_part_prunes_stale_assembly_placements": [
      4,
      0
    ],
    "test_bug68_polygon_parts_recursively_flattens_nested_geometry_collections": [
      1,
      0
    ]
  },
  "tests/test_deep_audit_round5_bugfixes.py": {
    "test_bug71_clip_layered_profile_preserves_non_from_dxf_primary_points": [
      3,
      0
    ],
    "test_bug72_custom_fold_terminal_zero_angle_and_bool_rejection": [
      2,
      1
    ],
    "test_bug74_display_dimensions_rejects_bool_nan_and_handles_none_in_settings": [
      2,
      0
    ],
    "test_bug75_quantity_text_box_out_of_range_attachment": [
      2,
      0
    ],
    "test_bug76_dxf_acceptance_collinear_bends_and_circles_tolerance_order": [
      2,
      0
    ],
    "test_bug77_joint_marking_policy_malformed_plane_returns_fail_closed": [
      2,
      0
    ],
    "test_bug78_hole_catalog_rejects_bool_and_nonpositive_dimensions": [
      0,
      4
    ],
    "test_bug79_sheetmetal_feature_reference_rejects_bool_and_nan": [
      0,
      2
    ],
    "test_bug80_receiving_inner_door_pairing_rejects_negative_and_bool_indices": [
      0,
      3
    ],
    "test_bug81_receiving_assignment_core_rejects_bool_keys_and_malformed_sets": [
      0,
      3
    ],
    "test_bug82_83_84_receiving_base_and_fixing_plate_validation": [
      1,
      2
    ],
    "test_bug85_receiving_frame_baseline_rejects_bool_and_nan": [
      0,
      3
    ],
    "test_bug86_receiving_joint_locks_rejects_bool_indices": [
      0,
      2
    ],
    "test_bug87_receiving_joint_marking_malformed_divider_topology_fails_closed": [
      1,
      0
    ],
    "test_bug88_hole_editor_canvas_view_layered_profile_empty_primary_points": [
      2,
      0
    ],
    "test_bug89_hole_editor_session_rejects_bool_indices": [
      0,
      3
    ],
    "test_bug90_quantity_model_preserves_workspace_quantity_on_save_and_validates_both": [
      2,
      0
    ],
    "test_bug91_project_file_door_state_rejects_bool_and_nan": [
      0,
      4
    ],
    "test_bug92_cadcraft_bridges_reject_bool_timeout_pid_and_dimensions": [
      2,
      2
    ],
    "test_bug94_95_door_and_divider_panels_reject_bool_nan_and_handle_none_defaults": [
      6,
      2
    ]
  },
  "tests/test_deep_audit_round6_bugfixes.py": {
    "test_assembly_marking_geometry_normalization_and_backprojection_guards": [
      7,
      4
    ],
    "test_baseline_source_dxf_error_fallback_and_cutting_bounds": [
      3,
      0
    ],
    "test_contracts_and_material_segment_reject_bool_and_nonfinite": [
      0,
      5
    ],
    "test_receiving_nfb_depth_surface_policy_v5_brand_and_bool_guards": [
      1,
      3
    ],
    "test_receiving_nfb_model_identity_and_catalog_validation": [
      0,
      6
    ],
    "test_receiving_nfb_pad_generator_validation": [
      0,
      3
    ],
    "test_receiving_nfb_persistence_and_tier_ear_guards": [
      4,
      2
    ],
    "test_receiving_weld_ear_and_sheetmetal_corner_features_geometry_guards": [
      0,
      10
    ],
    "test_phase6_box_body_structure_string_bool_and_three_piece_guards": [
      6,
      1
    ],
    "test_phase6_manufacturing_geometry_and_endcap_guards": [
      9,
      1
    ]
  }
}
ORIGINAL_ROUND_IDS = ((1, 14), (15, 32), (33, 50),
                      (51, 70), (71, 95), (96, 116))


def _evidence_count(function: ast.FunctionDef) -> tuple[int, int]:
    nodes = tuple(ast.walk(function))
    direct_assertions = sum(isinstance(node, ast.Assert) for node in nodes)
    expected_exceptions = sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "raises"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pytest"
        for node in nodes
    )
    return direct_assertions, expected_exceptions


def test_original_six_rounds_represent_116_contiguous_audit_items():
    assert [item for first, last in ORIGINAL_ROUND_IDS
            for item in range(first, last + 1)] == list(range(1, 117))
    assert len(ORIGINAL_TEST_WITNESSES) == 6
    assert sum(map(len, ORIGINAL_TEST_WITNESSES.values())) == 87
    assert sum(sum(count) for cases in ORIGINAL_TEST_WITNESSES.values()
               for count in cases.values()) == 329


@pytest.mark.parametrize("relpath,baseline", list(ORIGINAL_TEST_WITNESSES.items()))
def test_original_116_source_witnesses_execute_in_current_product_ci(relpath, baseline):
    # CI selector must invoke the whole live suite, not an archived fixture
    # or a token test-name-only pass.
    assert relpath in PYTEST_PATHS
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)
                 and node.name.startswith("test_")}
    for name, minimum in baseline.items():
        assert name in functions, (relpath, name)
        fn = functions[name]
        got = _evidence_count(fn)
        assert got[0] >= minimum[0], (relpath, name, "assert", got, minimum)
        assert got[1] >= minimum[1], (relpath, name, "raises", got, minimum)
        # Direct test-level pytest skip/xfail would silently erase an audit
        # witness even when all names and assertions are still present.
        decorators = ast.unparse(fn.decorator_list) if fn.decorator_list else ""
        assert not any(flag in decorators for flag in (".skip(", ".skipif(", ".xfail(")), (
            relpath, name, decorators
        )


def test_original_116_automation_not_confused_with_physical_operator_evidence():
    mandatory_native_e2e = (
        "tests/test_phase6_2d_3d_round_trip.py",
        "tests/test_dm6_save_reload_semantic_determinism.py",
        "tests/test_receiving_door_dxf_roundtrip.py",
        "tests/test_original_fold_designer_gui_integration.py",
        "tests/test_gui_manufacturing_adapter.py",
        "tests/test_gui_fold_designer_transaction_contract.py",
    )
    assert all(path in PYTEST_PATHS for path in mandatory_native_e2e)
    assert len(mandatory_native_e2e) == 6
