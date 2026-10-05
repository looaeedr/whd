from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
ADAPTER = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"
ROUTER = ROOT / "gui_modules" / "application" / "command_router.py"

P7_R_A_PROVEN_NO_CALLER = {
    "_phase6_active_mesh_profiles",
    "_phase6_query_assembly_render_data",
    "_phase6_final_scene_set_preview_enabled",
    "_phase6_commit_output_draw_stock",
    "_phase6_export_selected_dxf_from_3d",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_functions(path: Path) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in _tree(path).body
        if isinstance(node, ast.FunctionDef)
    }


def _source(path: Path, fn: ast.FunctionDef) -> str:
    return ast.get_source_segment(path.read_text(encoding="utf-8"), fn) or ""


def _call_lines(fn: ast.FunctionDef, *, name: str | None = None, attr: str | None = None) -> list[int]:
    result = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if name is not None and isinstance(node.func, ast.Name) and node.func.id == name:
            result.append(node.lineno)
        if attr is not None and isinstance(node.func, ast.Attribute) and node.func.attr == attr:
            result.append(node.lineno)
    return sorted(result)


def test_p7_r_a_removes_only_fresh_census_proven_no_caller_bridge_glue():
    funcs = _top_functions(BRIDGE)
    assert P7_R_A_PROVEN_NO_CALLER.isdisjoint(funcs), (
        "P7-R-A: fresh DT proved these helpers have no bridge caller/facade binding; "
        f"still present={sorted(P7_R_A_PROVEN_NO_CALLER.intersection(funcs))}"
    )


def test_p7_r_a_part_editor_activation_order_remains_compatibility_keep():
    fn = _top_functions(BRIDGE)["_fix11_activate_part"]
    plan = _call_lines(fn, attr="plan_activation")
    save = _call_lines(fn, attr="_save_current_part")
    begin = _call_lines(fn, attr="begin_activation")
    finish = _call_lines(fn, attr="finish_activation")
    assert len(plan) == len(save) == len(begin) == len(finish) == 1
    assert plan[0] < save[0] < begin[0] < finish[0]


def test_p7_r_a_update_scheduler_stays_command_router_owned():
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    router_source = ROUTER.read_text(encoding="utf-8")
    fn = _top_functions(BRIDGE)["_phase6_submit_update_intent"]
    body = _source(BRIDGE, fn)
    assert "submit_fold_designer_update_intent" in body
    assert "class _Phase6UpdateScheduler" in router_source
    assert "def submit_fold_designer_update_intent" in router_source
    assert "_Phase6UpdateScheduler" not in bridge_source


def test_p7_r_a_bootstrap_lifecycle_install_order_remains_bridge_keep():
    fn = _top_functions(BRIDGE)["_fix11_init"]
    body = _source(BRIDGE, fn)
    required = (
        "_phase6_bootstrap_authoritative_state",
        "_phase6_install_runtime_ports",
        "_phase6_prepare_predecessor_init",
        "_FIX10_INIT",
        "_phase6_finish_legacy_host_compatibility",
        "_phase6_bootstrap_workspace_profiles",
        "_phase6_install_part_editor_compatibility",
        "_phase6_install_initial_owner_views",
        "_phase6_select_initial_mode",
        "_phase6_mark_ready",
    )
    positions = [body.index(token) for token in required]
    assert positions == sorted(positions)
    assert "self._phase6_initializing = True" in body


def test_p7_r_a_does_not_create_second_composition_root_or_reverse_import():
    assert not (ROOT / "phase6_part_editor_session.py").exists()
    for rel in (
        "gui_modules/application/fold_designer_adapter.py",
        "phase6_workspace_navigation_controller.py",
        "phase6_designer_workspace.py",
        "phase6_final_scene_view.py",
        "phase6_settings_panel.py",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "from fold_designer_bridge import" not in source
        assert "import fold_designer_bridge" not in source


def test_p7_r_a_retains_composition_ports_proven_live_by_broader_readback():
    funcs = _top_functions(BRIDGE)
    for name in (
        "_phase6_refresh_sticky_structure_tree",
        "_phase6_install_keyboard_shortcuts",
        "_phase6_final_scene_view_request",
        "_phase6_save_settings_context_as_defaults",
        "_phase6_toggle_parameter_panel",
    ):
        assert name in funcs
    adapter = ADAPTER.read_text(encoding="utf-8")
    assert "_phase6_refresh_sticky_structure_tree" in adapter
    assert "_phase6_install_keyboard_shortcuts" in adapter
    assert "_phase6_final_scene_view_request" in adapter
    assert "_phase6_save_settings_context_as_defaults" in adapter
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    assert "return _phase6_composition(self).toggle_parameter_panel(globals())" in bridge_source
    assert "def toggle_parameter_panel" in adapter


def test_p7_r_a_parameter_panel_compat_port_toggles_workspace_visibility(monkeypatch):
    import fold_designer_bridge as bridge

    class FakeWidget:
        def __init__(self, manager=""):
            self.manager = manager
            self.text = ""

        def winfo_manager(self):
            return self.manager

        def pack_forget(self):
            self.manager = ""

        def pack(self, *args, **kwargs):
            self.manager = "pack"

        def configure(self, **kwargs):
            if "text" in kwargs:
                self.text = kwargs["text"]

    button = FakeWidget("pack")
    center = FakeWidget("pack")
    diagnostics = FakeWidget("")
    app = SimpleNamespace(
        _phase6_parameters_unlocked=False,
        parameter_lock_button=button,
        settings_center=center,
        active_part_key="box_body",
        _phase6_3d_display_mode="assembly",
        assembly_diagnostics_frame=diagnostics,
    )
    status_updates = []
    monkeypatch.setattr(
        bridge,
        "_phase6_pack_right_panel_above_canvas",
        lambda _app, widget: widget.pack(),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_update_assembly_diagnostic_status",
        lambda _app: status_updates.append("updated"),
    )

    assert bridge._phase6_toggle_parameter_panel(app) is True
    assert app._phase6_parameters_unlocked is True
    assert button.text == "參數解鎖"
    assert center.winfo_manager() == ""
    assert diagnostics.winfo_manager() == "pack"
    assert status_updates == ["updated"]

    assert bridge._phase6_toggle_parameter_panel(app) is False
    assert app._phase6_parameters_unlocked is False
    assert button.text == "參數鎖定"
    assert center.winfo_manager() == ""
    assert diagnostics.winfo_manager() == ""


def test_issue1213_settings_application_effects_live_only_in_composition_owner():
    moved = {
        "_phase6_settings_application_apply_profile_plan",
        "_phase6_settings_application_project_ui_values",
        "_phase6_settings_application_submit_update_intent",
        "_phase6_settings_application_publish_live_state",
    }
    assert moved.isdisjoint(_top_functions(BRIDGE))

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "settings_application_apply_profile_plan",
        "settings_application_project_ui_values",
        "settings_application_submit_update_intent",
        "settings_application_publish_live_state",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "_phase6_settings_application_apply_profile_plan" not in adapter_source
    assert "_phase6_settings_application_project_ui_values" not in adapter_source
    assert "_phase6_settings_application_submit_update_intent" not in adapter_source
    assert "_phase6_settings_application_publish_live_state" not in adapter_source
    assert "self.settings_application_apply_profile_plan(" in adapter_source
    assert "self.settings_application_project_ui_values(" in adapter_source
    assert "self.settings_application_submit_update_intent(" in adapter_source
    assert "self.settings_application_publish_live_state(" in adapter_source


def test_issue1215_project_effects_are_composition_owned_with_bridge_compat_ports():
    funcs = _top_functions(BRIDGE)
    for name in (
        "_phase6_build_project_snapshot",
        "_phase6_load_project_file",
        "_phase6_save_project_file",
    ):
        assert name in funcs

    build_body = _source(BRIDGE, funcs["_phase6_build_project_snapshot"])
    load_body = _source(BRIDGE, funcs["_phase6_load_project_file"])
    save_body = _source(BRIDGE, funcs["_phase6_save_project_file"])
    assert "build_project_snapshot(globals())" in build_body
    assert "load_project_file(globals())" in load_body
    assert "save_project_file(" in save_body
    assert "collect_final_geometry_diagnostics" not in build_body
    assert "filedialog" not in load_body
    assert "filedialog" not in save_body
    assert "write_designer_project" not in save_body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "build_project_snapshot",
        "load_project_file",
        "save_project_file",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "Phase6ProjectController.build_designer_payload" in adapter_source
    assert "Phase6ProjectController.validate_project_load" in adapter_source
    assert "Phase6ProjectController.write_designer_project" in adapter_source


def test_issue1217_settings_context_projection_is_composition_owned():
    moved = {
        "_phase6_settings_endcap_fw_projection",
        "_phase6_settings_box_structure_projection",
        "_phase6_settings_bottom_wrap_projection",
        "_phase6_settings_corner_projection",
        "_phase6_settings_context_extension_projection",
    }
    assert moved.isdisjoint(_top_functions(BRIDGE))

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "settings_context_extension_projection" in method_names

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "_phase6_settings_context_extension_projection" not in adapter_source
    assert "self.settings_context_extension_projection(" in adapter_source
    assert "context_extension_projection=lambda context:" in adapter_source


def test_issue1219_registry_application_sequencing_is_composition_owned():
    moved = {
        "_phase6_registry_preview_payload",
        "_phase6_registry_collect_rule_form",
        "_phase6_registry_sample_variables",
        "_phase6_registry_validate_formula_form",
        "_phase6_registry_save_candidate_form",
        "_phase6_registry_run_formula_matrix",
        "_phase6_registry_preview_assembly_3d",
        "_phase6_registry_promote_form",
    }
    funcs = _top_functions(BRIDGE)
    assert moved.isdisjoint(funcs)
    assert "_phase6_registry_validate_candidate_3d" in funcs

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "registry_collect_rule_form",
        "registry_sample_variables",
        "registry_validate_formula_form",
        "registry_preview_payload",
        "registry_save_candidate_form",
        "registry_run_formula_matrix",
        "registry_preview_assembly_3d",
        "registry_promote_form",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "self.registry_validate_formula_form()" in adapter_source
    assert "self.registry_preview_payload()" in adapter_source
    assert "self.registry_preview_assembly_3d(" in adapter_source
    assert "self.registry_save_candidate_form(namespace)" in adapter_source
    assert "self.registry_run_formula_matrix(" in adapter_source
    assert "self.registry_promote_form()" in adapter_source
    assert "_phase6_registry_validate_candidate_3d" in adapter_source


def test_issue1221_registry_presentation_translation_is_panel_owned():
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    funcs = _top_functions(BRIDGE)
    moved = {
        "_phase6_operator_label",
        "_phase6_operator_text",
        "_phase6_fail_closed_visible_text",
        "_phase6_registry_present_token",
        "_phase6_formula_display",
        "_phase6_formula_raw",
        "_phase6_registry_formula_display",
        "_phase6_preconditions_display",
        "_phase6_preconditions_raw",
        "_phase6_source_display",
        "_phase6_source_raw",
        "_phase6_registry_source_display",
    }
    assert moved.isdisjoint(funcs)
    assert "_PHASE6_OPERATOR_LABELS" not in bridge_source
    assert "_phase6_part_label" in funcs

    panel_source = (ROOT / "phase6_registry_diagnostics_panel.py").read_text(
        encoding="utf-8"
    )
    for token in (
        "REGISTRY_OPERATOR_LABELS",
        "def registry_present_token",
        "def registry_formula_display",
        "def registry_formula_raw",
        "def registry_preconditions_display",
        "def registry_preconditions_raw",
        "def registry_source_display",
        "def registry_source_raw",
    ):
        assert token in panel_source

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "_phase6_registry_present_token" not in adapter_source
    assert "_phase6_registry_formula_display" not in adapter_source
    assert "_phase6_registry_source_display" not in adapter_source
    assert "present_token=present_token" in adapter_source
    assert "formula_display=registry_formula_display" in adapter_source
    assert "source_display=source_display" in adapter_source


def test_issue1221_registry_presentation_behavior_stays_localized_and_fail_closed():
    from phase6_registry_diagnostics_panel import (
        registry_formula_display,
        registry_formula_raw,
        registry_preconditions_display,
        registry_preconditions_raw,
        registry_present_token,
        registry_source_display,
        registry_source_raw,
    )

    part_labels = {"box_body": "箱身"}
    part_label = lambda value, snapshot=None: part_labels.get(str(value), str(value))
    present = lambda value, **kwargs: registry_present_token(
        value, part_label=part_label, **kwargs
    )

    assert present("BOX_SIDE") == "箱身側邊"
    assert present("UNKNOWN_ASCII") == "未定義項目（代碼已記錄）"
    assert registry_formula_display("FW + T") == "框寬 + 板厚"
    assert registry_formula_raw("框寬 + 板厚") == "FW + T"
    assert registry_preconditions_display(
        "BOX_SIDE,TOP", present_token=present
    ) == "箱身側邊、上方"
    assert registry_preconditions_raw("箱身側邊、上方") == "BOX_SIDE,TOP"
    assert registry_source_display(
        "Registry 3D", part_labels=part_labels
    ) == "資料庫 立體"
    assert registry_source_raw(
        "資料庫 立體", part_labels=part_labels
    ) == "Registry 3D"


def test_issue1223_corner_data_application_orchestration_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    delegates = {
        "_phase6_corner_data_part_keys",
        "_phase6_corner_data_navigation_rows",
        "_phase6_select_corner_data_part",
        "_phase6_corner_data_info_request_for_key",
        "_phase6_corner_data_info_text_for_key",
        "_phase6_corner_data_unfold_projection_for_key",
        "_phase6_corner_data_unfold_projections",
        "_phase6_corner_data_unfold_projection",
        "_phase6_refresh_corner_data_unfold_view",
        "_phase6_corner_data_back_panel_mode_is_applicable",
        "_phase6_refresh_corner_data_back_panel_mode_control",
        "_phase6_refresh_corner_data_parts_panel",
        "_phase6_on_corner_data_mousewheel",
        "_phase6_prepare_corner_data_canvas",
    }
    assert delegates.issubset(funcs)

    for name in delegates:
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "Phase6CornerDataViewAdapter" not in body
        assert "designer_workspace" not in body
        assert "corner_data_canvas" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "corner_data_part_keys",
        "corner_data_navigation_rows",
        "select_corner_data_part",
        "corner_data_info_request_for_key",
        "corner_data_info_text_for_key",
        "corner_data_unfold_projection_for_key",
        "corner_data_unfold_projections",
        "corner_data_unfold_projection",
        "refresh_corner_data_unfold_view",
        "corner_data_back_panel_mode_is_applicable",
        "refresh_corner_data_back_panel_mode_control",
        "refresh_corner_data_parts_panel",
        "on_corner_data_mousewheel",
        "prepare_corner_data_canvas",
    }.issubset(method_names)

    bridge_source = BRIDGE.read_text(encoding="utf-8")
    assert '"_phase6_refresh_corner_data_unfold_view": _phase6_refresh_corner_data_unfold_view' in bridge_source


def test_issue1225_assembly_application_sequencing_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    delegates = {
        "_phase6_on_assembly_diagnostic_changed",
        "_phase6_create_relief_promotion_candidates",
        "_phase6_update_assembly_diagnostic_status",
        "_phase6_on_assembly_part_visibility_changed",
        "_phase6_install_assembly_panel_aliases",
        "_phase6_current_assembly_panel_part_keys",
        "_phase6_refresh_assembly_parts_panel_if_topology_changed",
        "_phase6_refresh_assembly_parts_panel",
    }
    assert delegates.issubset(funcs)
    for name in delegates:
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "build_relief_promotion_candidate" not in body
        assert "diagnostic_status" not in body
        assert "render_available_parts" not in body
        assert "refresh_if_topology_changed" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "on_assembly_diagnostic_changed",
        "create_relief_promotion_candidates",
        "update_assembly_diagnostic_status",
        "on_assembly_part_visibility_changed",
        "install_assembly_panel_aliases",
        "current_assembly_panel_part_keys",
        "refresh_assembly_parts_panel_if_topology_changed",
        "refresh_assembly_parts_panel",
    }.issubset(method_names)


def test_issue1227_settings_panel_and_external_ingress_are_composition_owned():
    funcs = _top_functions(BRIDGE)
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    assert "_SETTINGS_EXTENSION_MAP_ATTRS" not in bridge_source
    assert "_phase6_sync_settings_panel_extension" not in funcs

    delegates = {
        "_phase6_on_baseline_model_changed",
        "_phase6_sync_settings_panel_compat",
        "_phase6_settings_panel_toggle_baseline",
        "_phase6_invalidate_settings_page",
        "_phase6_render_settings_context",
        "_phase6_save_current_settings_as_defaults",
        "_phase6_apply_external_settings",
        "_phase6_apply_external_model",
        "_phase6_apply_external_sync",
        "_phase6_update_left_workspace_width",
        "_phase6_apply_ui_text_size",
        "_phase6_on_ui_text_size_changed",
    }
    assert delegates.issubset(funcs)
    for name in delegates:
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "sync_settings_panel_extension",
        "sync_settings_panel_compat",
        "settings_panel_toggle_baseline",
        "invalidate_settings_page",
        "render_settings_context",
        "save_current_settings_as_defaults",
        "on_baseline_model_changed",
        "apply_external_settings",
        "apply_external_model",
        "apply_external_sync",
        "update_left_workspace_width",
        "apply_ui_text_size",
        "on_ui_text_size_changed",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "_phase6_sync_settings_panel_extension" not in adapter_source
    assert "_phase6_on_baseline_model_changed" not in adapter_source
    assert "_phase6_apply_ui_text_size" not in adapter_source


def test_issue1229_receiving_layer_connection_ui_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    delegates = {
        "_phase6_receiving_switch_adapter",
        "_phase6_mark_receiving_switch_layout_dirty",
        "_phase6_refresh_receiving_set_bay_control",
        "_phase6_on_receiving_switch_brand_selected",
        "_phase6_add_receiving_layer",
        "_phase6_resize_receiving_bays",
        "_phase6_confirm_receiving_opening",
        "_phase6_open_receiving_layer_preview",
    }
    assert delegates.issubset(funcs)
    for name in delegates:
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "ReceivingSwitchLayoutAdapter" not in body
        assert "refresh_receiving_layer_rows" not in body
        assert "open_receiving_layer_preview(" not in body or "_phase6_composition" in body

    # Canonical Set/Bay layout ownership is intentionally not moved by #1229.
    for name in (
        "_phase6_receiving_adapter",
        "_phase6_sync_receiving_current_bay",
        "_phase6_commit_receiving_current_bay_controls",
    ):
        assert name in funcs
        assert "_phase6_composition(self)" not in _source(BRIDGE, funcs[name])

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "receiving_switch_adapter",
        "mark_receiving_switch_layout_dirty",
        "refresh_receiving_set_bay_control",
        "on_receiving_switch_brand_selected",
        "add_receiving_layer",
        "resize_receiving_bays",
        "confirm_receiving_opening",
        "open_receiving_layer_preview",
    }.issubset(method_names)

    controls_source = (
        ROOT / "gui_modules" / "application" / "receiving_set_bay_controls.py"
    ).read_text(encoding="utf-8")
    assert "第{layer_index + 1}層" in controls_source
    assert "{connection_count}連" in controls_source
    assert "＋層" in controls_source


def test_issue1231_receiving_set_bay_application_orchestration_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    delegates = {
        "_phase6_receiving_layout_applicable",
        "_phase6_confirm_receiving_destructive",
        "_phase6_receiving_adapter",
        "_phase6_sync_receiving_current_bay",
        "_phase6_commit_receiving_current_bay_controls",
    }
    assert delegates.issubset(funcs)
    for name in delegates:
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "ReceivingSetBayAdapter" not in body
        assert "project_receiving_bay_legacy_aliases" not in body
        assert "ensure_receiving_layout" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "receiving_layout_applicable",
        "confirm_receiving_destructive",
        "receiving_adapter",
        "sync_receiving_current_bay",
        "commit_receiving_current_bay_controls",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert 'snapshot["receiving_layout"] = adapter.layout' in adapter_source
    assert 'persisted_ids=required("receiving_layout_stable_ids")' in adapter_source


def test_issue1234_settings_debounce_and_flush_are_composition_owned():
    funcs = _top_functions(BRIDGE)
    for name in (
        "_phase6_flush_pending_settings",
        "_phase6_stage_setting_update",
    ):
        assert name in funcs
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "after_cancel" not in body
        assert "root.after(" not in body
        assert "drain_pending" not in body
        assert "stage_setting_update(" not in body or "_phase6_composition" in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "flush_pending_settings",
        "stage_setting_update",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert 'service.drain_pending()' in adapter_source
    assert 'service.stage_setting_update(' in adapter_source
    assert 'lambda: self.flush_pending_settings(namespace)' in adapter_source
    assert '_phase6_stage_setting_update' not in adapter_source
    assert '_phase6_flush_pending_settings' not in adapter_source


def test_issue1239_settings_profile_projection_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    for name in (
        "_phase6_apply_settings_profile_projection",
        "_phase6_refresh_profiles_from_settings",
    ):
        assert name in funcs
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "SettingsProfileProjectionRequest" not in body
        assert "build_settings_profile_projection" not in body
        assert "materialize_settings_profile_value" not in body
        assert "navigation.stash_profiles" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "apply_settings_profile_projection",
        "refresh_profiles_from_settings",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert 'required("_phase6_refresh_profiles_from_settings")' not in adapter_source
    assert "return self.refresh_profiles_from_settings(" in adapter_source
    assert "self.sync_authoritative_derived_parts(namespace)" in adapter_source
    assert "self.refresh_assembly_parts_panel_if_topology_changed(namespace)" in adapter_source


def test_issue1241_workspace_snapshot_application_assembly_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    assert "_phase6_collect_workspace_state" in funcs
    body = _source(BRIDGE, funcs["_phase6_collect_workspace_state"])
    assert "_phase6_composition(self)" in body
    assert "export_shared_snapshot" not in body
    assert "resolve_and_store_assembly_placements" not in body
    assert "migrate_legacy_snapshot_joints" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "collect_workspace_state" in method_names

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "workspace = self.collect_workspace_state(namespace)" in adapter_source
    assert 'required("_phase6_collect_workspace_state")' not in adapter_source
    assert "workspace.export_shared_snapshot(" in adapter_source
    assert "workspace.resolve_and_store_assembly_placements(" in adapter_source


def test_issue1244_relief_persistence_application_assembly_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    for name in (
        "_phase6_current_relief_source_signature",
        "_phase6_serialize_assembly_relief_state",
    ):
        assert name in funcs
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "build_current_source_signature" not in body
        assert "build_persisted_relief_state" not in body
        assert "resolved_joint_graph_fingerprint" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "current_relief_source_signature",
        "serialize_assembly_relief_state",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "self.current_relief_source_signature(" in adapter_source
    assert "self.serialize_assembly_relief_state(" in adapter_source
    assert 'required("_phase6_serialize_assembly_relief_state")' not in adapter_source


def test_issue1246_live_sync_payload_assembly_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    assert "_phase6_corner_transaction_payload" in funcs
    body = _source(BRIDGE, funcs["_phase6_corner_transaction_payload"])
    assert "_phase6_composition(self)" in body
    assert "migrate_legacy_snapshot_joints" not in body
    assert "assembly_joint_schema_version" not in body
    assert "door_layout_columns" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "corner_transaction_payload" in method_names

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "state = self.corner_transaction_payload(namespace)" in adapter_source
    assert 'self._required(namespace, "_phase6_corner_transaction_payload")' not in adapter_source
    assert "self.collect_workspace_state(namespace)" in adapter_source
    assert "self.serialize_assembly_relief_state(namespace)" in adapter_source


def test_issue1248_back_panel_ui_orchestration_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    for name in (
        "_phase6_back_panel_mode_control_is_applicable",
        "_phase6_refresh_back_panel_mode_control",
        "_phase6_select_back_panel_mode",
    ):
        assert name in funcs
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "ReceivingSetBayAdapter" not in body
        assert "set_side_back_back_panel_mode" not in body
        assert "frame.pack(" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "back_panel_mode_control_is_applicable",
        "refresh_back_panel_mode_control",
        "select_back_panel_mode",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "self.refresh_back_panel_mode_control(namespace)" in adapter_source
    assert "self.select_back_panel_mode(" in adapter_source

    bridge_source = BRIDGE.read_text(encoding="utf-8")
    for label in ("全板", "半截", "背開孔"):
        assert label in bridge_source


def test_issue1248_receiving_back_panel_mode_ui_is_composition_owned():
    funcs = _top_functions(BRIDGE)
    delegates = {
        "_phase6_back_panel_mode_control_is_applicable",
        "_phase6_refresh_back_panel_mode_control",
        "_phase6_select_back_panel_mode",
    }
    assert delegates.issubset(funcs)
    for name in delegates:
        body = _source(BRIDGE, funcs[name])
        assert "_phase6_composition(self)" in body
        assert "ReceivingSetBayAdapter" not in body
        assert "_BACK_PANEL_MODE_LABEL_TO_MODE" not in body

    adapter_tree = _tree(ADAPTER)
    composition = next(
        node
        for node in adapter_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    method_names = {
        node.name
        for node in composition.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "back_panel_mode_control_is_applicable",
        "refresh_back_panel_mode_control",
        "select_back_panel_mode",
    }.issubset(method_names)

    adapter_source = ADAPTER.read_text(encoding="utf-8")
    assert "self.refresh_back_panel_mode_control(namespace)" in adapter_source
    assert "self.select_back_panel_mode(" in adapter_source
    assert 'required("_phase6_refresh_back_panel_mode_control")' not in adapter_source
    assert 'required("_phase6_select_back_panel_mode")' not in adapter_source

    bridge_source = BRIDGE.read_text(encoding="utf-8")
    for label in ("全板", "半截", "背開孔"):
        assert label in bridge_source
