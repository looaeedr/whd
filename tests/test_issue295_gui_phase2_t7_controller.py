from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"

EXPECTED_MODULES = (
    ROOT / "gui_modules" / "application" / "state_sync.py",
    ROOT / "gui_modules" / "application" / "cabinet_controller.py",
    ROOT / "gui_modules" / "application" / "fold_designer_adapter.py",
    ROOT / "gui_modules" / "application" / "manufacturing_adapter.py",
    ROOT / "gui_modules" / "application" / "calculation_controller.py",
    ROOT / "gui_modules" / "project" / "export_actions.py",
    ROOT / "gui_modules" / "visibility" / "controller.py",
)

ROOT_METHODS_THAT_MUST_BECOME_THIN = (
    "init_variables",
    "_fold_designer_secondary_scene_rows",
    "_query_fold_designer_baseline_data",
    "_apply_cabinet_family_endcap_policy",
    "_fold_designer_corner_policy_from_payload",
    "_authoritative_render_data",
    "_require_verified_baseline_sources_for_manufacturing",
    "_export_authoritative_part",
    "_fold_designer_part_spec_from_payload",
    "_query_fold_designer_render_data",
    "_make_original_fold_designer_snapshot",
    "_inherit_known_corner_state_into_custom",
    "_capture_cabinet_family_runtime",
    "_restore_cabinet_family_runtime",
    "_apply_cabinet_family_for_current_model",
    "on_baseline_changed",
    "get_float_values",
    "_active_indicator_box_groups_for_results",
    "_has_any_indicator_box",
    "_clear_indicator_box_result_values",
    "_refresh_indicator_box_result_values",
    "update_calculations",
    "_manufacturing_context",
    "_box_body_part_spec_from_values",
    "_box_body_part_spec",
    "_end_cap_part_spec_from_values",
    "_phase6_relief_profile_signature",
    "_resolved_committed_assembly_relief_cuts",
    "_end_cap_part_spec",
    "_door_part_spec_from_values",
    "_single_door_part_spec",
    "_door_layout_part_spec",
    "_validate_indicator_state_fit",
    "_validate_single_door_indicator_fit",
    "_validate_door_layout_indicator_fit",
    "_base_plate_part_spec_from_values",
    "_base_plate_part_spec",
    "_indicator_box_part_spec_from_values",
    "_indicator_box_part_spec",
    "_indicator_door_part_spec_from_values",
    "_indicator_door_part_spec",
    "_indicator_component_editor_contexts",
    "export_multi_door_layout_dxfs",
    "export_multi_door_indicator_box_parts",
    "export_selected_dxf",
    "_single_door_indicator_state_snapshot",
    "_apply_single_door_indicator_state",
    "_apply_multi_door_indicator_state",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _host() -> ast.ClassDef:
    return next(
        node
        for node in _tree(GUI).body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )


def _host_methods() -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
    out: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in _host().body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, []).append(node)
    return out


def _loc(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def test_t7_target_module_surface_exists():
    missing = [str(path.relative_to(ROOT)) for path in EXPECTED_MODULES if not path.is_file()]
    assert not missing, "T7 focused owner modules missing: " + ", ".join(missing)


def test_t7_root_implementations_are_thin_routes_or_aliases():
    methods = _host_methods()
    thick = {}
    for name in ROOT_METHODS_THAT_MUST_BECOME_THIN:
        for node in methods.get(name, ()):
            if _loc(node) > 5:
                thick.setdefault(name, []).append(_loc(node))
    assert not thick, f"T7 implementation still owned by gui.py: {thick}"


def test_t7_final_root_gate_is_hard_2500():
    loc = len(GUI.read_text(encoding="utf-8").splitlines())
    assert loc <= 2500, f"Phase 2 final structural gate: gui.py={loc} > 2500"


def test_t7_new_modules_have_one_way_import_direction():
    for path in EXPECTED_MODULES:
        if not path.is_file():
            continue
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
                assert "gui" not in names, f"{path}: imports gui"
                assert not any(name.startswith("compatibility") for name in names), (
                    f"{path}: imports compatibility layer"
                )
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                assert module != "gui", f"{path}: imports from gui"
                assert not module.startswith("compatibility"), (
                    f"{path}: imports compatibility layer"
                )


def test_t7_project_schema_authority_stays_outside_gui_modules():
    for path in EXPECTED_MODULES:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert "PROJECT_SCHEMA =" not in text
        assert "write_project(" not in text
        assert "read_project(" not in text


def test_t7_workspace_presence_authority_remains_workspace_controller():
    text = GUI.read_text(encoding="utf-8")
    assert "Phase6WorkspaceController" in text
    assert "Phase6ProjectController" in text
    assert "SettingsService" in text

    for path in EXPECTED_MODULES:
        if not path.is_file():
            continue
        module_text = path.read_text(encoding="utf-8")
        assert "self.existing_parts =" not in module_text
        assert "host.existing_parts =" not in module_text


def test_t7_module_class_method_size_gates():
    for path in EXPECTED_MODULES:
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if path.name != "fold_designer_adapter.py":
            assert len(source.splitlines()) <= 1500, f"{path} exceeds 1500 lines"
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert _loc(node) <= 800, f"{path}:{node.name} exceeds 800 lines"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if path.name == "fold_designer_adapter.py" and node.name == "final_scene_ports":
                    continue
                assert _loc(node) <= 150, f"{path}:{node.name} exceeds 150 lines"
