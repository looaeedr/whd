# trigger repaired RED harness
from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
CONTROLLER = Path("phase6_project_controller.py")

T3_BRIDGE_FUNCTIONS = {
    "_phase6_build_diagnostic_snapshot",
    "_phase6_build_project_snapshot",
    "_phase6_save_diagnostic_file",
    "_phase6_load_project_file",
    "_phase6_save_project_file",
    "_phase6_save_project_file_as",
    "_phase6_export_workspace_state_if_dirty",
    "_phase6_status_projection",
    "_phase6_save_settings_context_as_defaults",
    "_phase6_commit_output_draw_stock",
    "_phase6_export_selected_dxf_from_3d",
}

REQUIRED_CONTROLLER_METHODS = {
    "build_designer_payload",
    "validate_project_load",
    "write_designer_project",
    "build_diagnostic_payload",
    "write_diagnostic",
    "build_workspace_export",
    "project_status_projection",
    "route_settings_defaults",
    "commit_output_stock",
    "route_selected_dxf_export",
}

DIRECT_IO_NAMES = {
    "read_project",
    "write_project",
    "_phase6_write_diagnostic_json",
}

PROJECT_SERIALIZATION_TOKENS = {
    '"schema"',
    '"saved_at"',
    '"snapshot"',
    '"final_geometry"',
    '"existing_parts"',
    '"part_profiles"',
    '"part_features"',
    '"part_face_features"',
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _controller_methods():
    tree = _tree(CONTROLLER)
    return {
        node.name
        for cls in tree.body
        if isinstance(cls, ast.ClassDef) and cls.name == "Phase6ProjectController"
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue367_requires_project_controller_command_surface():
    missing = sorted(REQUIRED_CONTROLLER_METHODS - _controller_methods())
    assert missing == [], f"RED: missing T3 project controller methods: {missing}"


def test_issue367_bridge_has_no_project_serialization_or_direct_io_ownership():
    funcs = _functions(_tree(BRIDGE))
    moved_to_controller = {
        "_phase6_build_diagnostic_snapshot",
        "_phase6_export_workspace_state_if_dirty",
        "_phase6_save_diagnostic_file",
    }
    missing = sorted(T3_BRIDGE_FUNCTIONS - set(funcs))
    assert set(missing) <= moved_to_controller

    violations = []
    for name in sorted(T3_BRIDGE_FUNCTIONS & set(funcs)):
        node = funcs[name]
        source = ast.unparse(node)

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id in DIRECT_IO_NAMES:
                    violations.append((name, "DIRECT_IO", child.func.id, child.lineno))
                if (
                    isinstance(child.func, ast.Attribute)
                    and child.func.attr in {"write_text", "write_bytes", "open"}
                ):
                    violations.append((name, "DIRECT_FILE_WRITE", child.func.attr, child.lineno))

        if name == "_phase6_build_project_snapshot":
            for token in PROJECT_SERIALIZATION_TOKENS:
                if token in source:
                    violations.append((name, "SERIALIZATION_POLICY", token))

    assert violations == [], (
        "RED: bridge still owns T3 project serialization/direct I/O: "
        f"{violations}"
    )


def test_issue367_bridge_commands_delegate_to_project_controller():
    funcs = _functions(_tree(BRIDGE))
    expected = {
        "_phase6_build_diagnostic_snapshot": "build_diagnostic_payload",
        "_phase6_build_project_snapshot": "build_designer_payload",
        "_phase6_save_diagnostic_file": "write_diagnostic",
        "_phase6_load_project_file": "validate_project_load",
        "_phase6_save_project_file": "write_designer_project",
        "_phase6_export_workspace_state_if_dirty": "build_workspace_export",
        "_phase6_status_projection": "project_status_projection",
        "_phase6_save_settings_context_as_defaults": "route_settings_defaults",
        "_phase6_commit_output_draw_stock": "commit_output_stock",
        "_phase6_export_selected_dxf_from_3d": "route_selected_dxf_export",
    }
    controller_methods = _controller_methods()
    violations = []
    for name, method in expected.items():
        if name not in funcs:
            if method not in controller_methods:
                violations.append((name, method))
            continue
        source = ast.unparse(funcs[name])
        if method not in source:
            violations.append((name, method))
    assert violations == [], f"RED: bridge T3 delegates missing: {violations}"
