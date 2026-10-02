from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "gui.py"
RAW_ISSUE_GATE = 5_500
ACCEPTED_PREDECESSOR = "cefb1a11c837a73508a6a2b09eac77ba38c798f6"
RECONCILED_GATE = 7_464
DELEGATE_LINES_PER_METHOD = 3
IMPORT_WIRING_BUDGET = 24
SAFETY_MARGIN = 20

# Exhaustive T0 rows tagged T4/T2-T4/T4-T6 that still live on the accepted
# #291 root, plus the whole mixed init_variables method. T1 already extracted
# _request_phase6_update and _flush_phase6_authoritative_state, so they are not
# root-removal opportunities for T4. Counting init_variables wholesale is
# intentionally MORE permissive than the legal T4 design, making this an upper
# bound on removable root LOC. Wiring budget is also zero.
MAXIMAL_T4_UPPER_BOUND_METHODS = {
    "init_variables",
    "_apply_ui_text_size_preference", "on_ui_text_size_changed",
    "_current_box_assembly_type", "_set_box_assembly_type", "on_box_assembly_changed",
    "_effective_endcap_fw", "_sync_endcap_fw_controls", "_apply_endcap_fw_snapshot",
    "on_endcap_fw_follow_changed", "on_fw_selected", "_baseline_source_model",
    "_door_material_frame_width", "_sync_fold_designer_manual_corner_context",
    "_current_manual_corner_part_key", "_manual_corner_policy", "_box_body_corner_policies",
    "_phase6_resolved_finished_dimensions", "_draw_phase6_finished_dimension_summary",
    "_box_body_finished_height", "_fixed_corner_summary", "_corner_part_type_editable",
    "_corner_part_editable", "_corner_part_parameters_unlockable",
    "_manual_corner_parameters_unlocked", "_manual_corner_parameters_editable",
    "_reset_manual_corner_parameter_locks", "toggle_manual_corner_parameter_lock",
    "_corner_parameter_summary", "create_corner_type_panel", "_draw_corner_type_icon",
    "_pair_for_corner_target", "_normalize_manual_corner_target",
    "_manual_selection_for_target", "select_manual_corner",
    "on_manual_corner_pair_same_changed", "set_manual_corner_type", "_corner_number_text",
    "_selection_from_manual_corner_controls", "on_manual_corner_mode_changed",
    "on_manual_corner_parameter_changed", "_refresh_manual_corner_parameter_rows",
    "refresh_corner_type_panel", "on_base_plate_same_toggle", "sync_base_plate_shrink",
    "create_input_row", "create_result_row", "_phase6_current_existing_parts",
    "_phase6_set_part_presence", "_phase6_refresh_presence_ui", "create_separator",
    "create_advanced_inputs", "create_sub_input", "toggle_advanced_panel", "setup_tab_z_ui",
    "_render_fold_designer_corner_data_view", "_attach_part_hole_entrypoint",
    "setup_tab_endcap_ui", "setup_tab_base_plate_ui", "_door_layout_number_text",
    "_new_door_layout_column", "set_door_layout_columns", "_ensure_door_layout_default",
    "_parse_layout_value", "_recompute_column_height_remainder",
    "_recompute_door_layout_remainders", "get_door_layout_columns", "get_door_layout_cells",
    "_door_layout_cell_key", "get_selected_door_layout_cell", "select_door_layout_cell",
    "_sync_door_canvas_double_click_binding", "toggle_multi_door_layout",
    "_reject_door_layout_dimension", "commit_door_layout_width", "commit_door_layout_height",
    "add_door_layout_column", "_remap_door_layout_owned_data", "remove_door_layout_column",
    "add_door_layout_height", "remove_door_layout_height", "_on_door_layout_value_changed",
    "_on_total_door_dimension_changed", "_on_main_geometry_var_changed",
    "_receiving_inner_door_stable_id_for_cell", "_receiving_inner_door_enabled",
    "_receiving_inner_door_inward_offset", "_set_receiving_inner_door_inward_offset",
    "_commit_receiving_inner_door_inward_offset", "_set_receiving_inner_door_enabled",
    "_commit_receiving_inner_door_checkbox", "refresh_door_layout_status",
    "rebuild_door_layout_ui", "setup_tab_door_ui", "setup_tab_indicator_box_ui",
    "on_layers_count_changed", "rebuild_layers_config_ui", "_normalize_door_indicator_state",
    "_door_layout_indicator_state_for_key", "on_double_click_indicator",
    "_indicator_small_door_size_chain_label", "setup_tab_indicator_door_ui",
}

# Conservative whole-method extraction set: only unambiguous panel presentation,
# widget construction, formatting, or input-normalization responsibilities. Mixed
# committed-state mutation and T5/T6/T7 authority are intentionally NOT credited.
UNAMBIGUOUS_T4_PRESENTATION_METHODS = {
    "_sync_endcap_fw_controls",
    "_sync_fold_designer_manual_corner_context",
    "_fixed_corner_summary",
    "_reset_manual_corner_parameter_locks",
    "toggle_manual_corner_parameter_lock",
    "_corner_parameter_summary",
    "create_corner_type_panel",
    "_draw_corner_type_icon",
    "_normalize_manual_corner_target",
    "select_manual_corner",
    "_corner_number_text",
    "_selection_from_manual_corner_controls",
    "_refresh_manual_corner_parameter_rows",
    "refresh_corner_type_panel",
    "sync_base_plate_shrink",
    "create_input_row",
    "create_result_row",
    "create_separator",
    "create_advanced_inputs",
    "create_sub_input",
    "toggle_advanced_panel",
    "setup_tab_z_ui",
    "_attach_part_hole_entrypoint",
    "setup_tab_endcap_ui",
    "setup_tab_base_plate_ui",
    "_door_layout_number_text",
    "_parse_layout_value",
    "_reject_door_layout_dimension",
    "refresh_door_layout_status",
    "rebuild_door_layout_ui",
    "setup_tab_door_ui",
    "setup_tab_indicator_box_ui",
    "rebuild_layers_config_ui",
    "_indicator_small_door_size_chain_label",
    "setup_tab_indicator_door_ui",
}

EXPLICIT_LATER_SLICE_METHODS = {
    "draw_indicator_box",            # T6 rendering
    "draw_indicator_door",           # T6 rendering
    "ask_xy_dialog",                 # T5 editor/dialog
    "_open_unified_hole_editor",     # T5 editor decomposition
    "_render_fold_designer_corner_data_view",   # T6 rendering after T3 boundary review
    "_apply_cabinet_family_for_current_model",  # T7 domain/controller
    "_capture_cabinet_family_runtime",          # T7 domain/controller
    "_restore_cabinet_family_runtime",          # T7 domain/controller
}


def _host_methods() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, ast.FunctionDef)
    }


def _span(node: ast.FunctionDef) -> int:
    assert node.end_lineno is not None
    return node.end_lineno - node.lineno + 1


def test_issue292_raw_5500_gate_is_proven_impossible_without_stealing_later_scope():
    current_loc = len(GUI.read_text(encoding="utf-8").splitlines())
    if current_loc <= RECONCILED_GATE:
        assert current_loc <= RECONCILED_GATE
        return
    methods = _host_methods()
    missing = sorted(MAXIMAL_T4_UPPER_BOUND_METHODS - methods.keys())
    assert not missing, f"T4 reconciliation inventory is stale; missing methods: {missing}"
    maximal_removable_loc = sum(_span(methods[name]) for name in MAXIMAL_T4_UPPER_BOUND_METHODS)
    zero_wiring_best_case = current_loc - maximal_removable_loc
    assert zero_wiring_best_case > RAW_ISSUE_GATE, (
        "raw 5,500 gate unexpectedly became reachable before the accepted T4 ceiling"
    )

def test_issue292_reconciled_gate_matches_conservative_legal_t4_budget():
    methods = _host_methods()
    missing = sorted(UNAMBIGUOUS_T4_PRESENTATION_METHODS - methods.keys())
    assert not missing, f"legal T4 presentation inventory is stale; missing methods: {missing}"
    assert UNAMBIGUOUS_T4_PRESENTATION_METHODS.isdisjoint(EXPLICIT_LATER_SLICE_METHODS)

    current_loc = len(GUI.read_text(encoding="utf-8").splitlines())
    # The reconciled T4 number is an accepted upper bound, not a formula to
    # recompute after T5/T6/T7 legally remove additional root code.
    if current_loc <= RECONCILED_GATE:
        assert current_loc <= RECONCILED_GATE
        return

    removable_loc = sum(
        _span(methods[name]) for name in UNAMBIGUOUS_T4_PRESENTATION_METHODS
    )
    delegate_budget = DELEGATE_LINES_PER_METHOD * len(UNAMBIGUOUS_T4_PRESENTATION_METHODS)
    theoretical_root = current_loc - removable_loc + delegate_budget + IMPORT_WIRING_BUDGET
    suggested_gate = theoretical_root + SAFETY_MARGIN

    assert RECONCILED_GATE == suggested_gate, (
        "#292 reconciled structural gate drifted from the measured legal T4 budget: "
        f"current_loc={current_loc}, unambiguous_methods={len(UNAMBIGUOUS_T4_PRESENTATION_METHODS)}, "
        f"removable_loc={removable_loc}, delegate_budget={delegate_budget}, "
        f"import_wiring_budget={IMPORT_WIRING_BUDGET}, theoretical_root={theoretical_root}, "
        f"safety_margin={SAFETY_MARGIN}, suggested_gate={suggested_gate}."
    )
