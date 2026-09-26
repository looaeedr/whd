from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
ROUTER = ROOT / "gui_modules" / "application" / "command_router.py"

P7_R_A_PROVEN_NO_CALLER = {
    "_phase6_active_mesh_profiles",
    "_phase6_query_assembly_render_data",
    "_phase6_final_scene_view_request",
    "_phase6_final_scene_set_preview_enabled",
    "_phase6_commit_output_draw_stock",
    "_phase6_export_selected_dxf_from_3d",
    "_phase6_toggle_parameter_panel",
    "_phase6_save_settings_context_as_defaults",
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
    ):
        assert name in funcs
    adapter = (ROOT / "gui_modules" / "application" / "fold_designer_adapter.py").read_text(
        encoding="utf-8"
    )
    assert 'required("_phase6_refresh_sticky_structure_tree")' in adapter
    assert 'required("_phase6_install_keyboard_shortcuts")' in adapter
