# -*- coding: utf-8 -*-
"""Issue #446 / T4 ownership contracts for Registry diagnostics presentation."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
CONTROLLER = ROOT / "phase6_registry_diagnostics_controller.py"
PANEL = ROOT / "phase6_registry_diagnostics_panel.py"

SELECTED_PRESENTATION_FUNCTIONS = {
    "_phase6_form_choice",
    "_phase6_registry_preview_2d",
    "_phase6_registry_refresh_rule_tree",
    "_phase6_registry_rule_selected",
    "_phase6_joint_form_refresh",
    "_phase6_open_relief_registry_form",
    "_phase6_refresh_joint_diagnostic_menu",
    "_phase6_build_assembly_diagnostics",
}


def _top_level_defs(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    raise AssertionError(f"missing class {class_name}")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _facade_binding_count(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
        )
        if name == "install_fold_designer_bridge_facade":
            calls.append(node)
    assert len(calls) == 1
    dict_args = [arg for arg in calls[0].args if isinstance(arg, ast.Dict)]
    assert len(dict_args) == 1
    return len(dict_args[0].keys)


def test_selected_registry_diagnostics_presentation_leaves_bridge():
    bridge_defs = _top_level_defs(BRIDGE)
    remaining = SELECTED_PRESENTATION_FUNCTIONS & bridge_defs
    assert not remaining, (
        "T4 RED: selected Registry/diagnostics presentation is still implemented "
        f"in the bridge: {sorted(remaining)}"
    )


def test_registry_diagnostics_panel_exists_and_owns_selected_surface():
    assert PANEL.is_file(), "T4 RED: phase6_registry_diagnostics_panel.py does not exist"
    methods = _class_methods(PANEL, "Phase6RegistryDiagnosticsPanel")
    required = {
        "open_registry_editor",
        "build_assembly_diagnostics",
        "refresh_rule_rows",
        "populate_rule_form",
        "refresh_joint_rows",
        "refresh_joint_diagnostic_menu",
        "draw_registry_preview",
    }
    assert required <= methods, f"missing Registry panel presentation methods: {sorted(required - methods)}"


def test_registry_panel_and_controller_never_reverse_import_bridge():
    assert "fold_designer_bridge" not in _imports(CONTROLLER)
    if PANEL.is_file():
        assert "fold_designer_bridge" not in _imports(PANEL)


def test_registry_panel_does_not_take_certified_or_mutation_semantics():
    if not PANEL.is_file():
        return
    source = PANEL.read_text(encoding="utf-8")
    forbidden = (
        "ae_engine.certified_relief_registry",
        "save_relief_rule_candidate",
        "promote_relief_rule_candidate",
        "evaluate_editable_endcap_rule_record",
        "build_relief_promotion_candidate",
        "_phase6_add_user_joint",
        "_phase6_delete_user_joint",
        "resolve_manufacturing_geometry",
        "AssemblyJointGraph",
    )
    found = [token for token in forbidden if token in source]
    assert not found, f"presentation owner absorbed Registry/domain semantics: {found}"


def test_registry_controller_remains_non_tk_semantic_owner():
    imports = _imports(CONTROLLER)
    assert "tkinter" not in imports
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "class Phase6RegistryDiagnosticsController" in source
    assert "diagnostic_status" in source
    assert "promote_candidate" in source


def test_bridge_facade_ratchet_does_not_grow_past_t0_baseline():
    entries = _facade_binding_count(BRIDGE)
    assert entries <= 69, f"bridge facade grew past T0 baseline: {entries} > 69"
