# -*- coding: utf-8 -*-
"""Issue #445 / T3 ownership contracts for the Settings presentation seam."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
PANEL = ROOT / "phase6_settings_panel.py"

SELECTED_BUILDERS = {
    "_phase6_build_endcap_fw_settings",
    "_phase6_build_box_structure_settings",
    "_phase6_build_endcap_joint_settings",
    "_phase6_build_receiving_bottom_wrap_settings",
    "_phase6_build_corner_settings",
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


def _facade_binding_count(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    facade_calls = []
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
            facade_calls.append(node)
    assert len(facade_calls) == 1, (
        "expected exactly one install_fold_designer_bridge_facade call, "
        f"got {len(facade_calls)}"
    )
    dict_args = [arg for arg in facade_calls[0].args if isinstance(arg, ast.Dict)]
    assert len(dict_args) == 1, (
        "expected exactly one facade binding dict argument, "
        f"got {len(dict_args)}"
    )
    return len(dict_args[0].keys)


def test_selected_settings_widget_builders_leave_bridge():
    bridge_defs = _top_level_defs(BRIDGE)
    assert not (SELECTED_BUILDERS & bridge_defs), (
        "T3 RED: selected Settings Tk builders are still implemented in the bridge: "
        f"{sorted(SELECTED_BUILDERS & bridge_defs)}"
    )


def test_existing_settings_panel_owns_context_extension_presentation():
    methods = _class_methods(PANEL, "Phase6SettingsPanel")
    assert "render_context_extensions" in methods
    assert "render_owned_context_extensions" in methods, (
        "T3 RED: Phase6SettingsPanel has not yet gained the concrete owned "
        "context-extension presentation entrypoint"
    )


def test_settings_panel_never_reverse_imports_bridge():
    tree = ast.parse(PANEL.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert "fold_designer_bridge" not in imports


def test_settings_panel_does_not_take_transaction_or_domain_mutation_ownership():
    source = PANEL.read_text(encoding="utf-8")
    forbidden = (
        "Phase6SettingsTransactionController",
        "Phase6SettingsTransactionService",
        "commit_box_fw(",
        "commit_endcap_fw(",
        "set_part_edge_relation(",
        "apply_box_assembly_type_to_raw_state(",
    )
    found = [token for token in forbidden if token in source]
    assert not found, f"presentation owner absorbed canonical mutation/domain ownership: {found}"


def test_bridge_facade_ratchet_does_not_grow_past_t0_baseline():
    entries = _facade_binding_count(BRIDGE)
    assert entries <= 69, f"bridge facade grew past T0 baseline: {entries} > 69"
