# -*- coding: utf-8 -*-
"""Issue #449 / T7 bootstrap-only lifecycle ownership contracts."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
BENDING = ROOT / "phase6_bending_ui.py"
SETTINGS = ROOT / "phase6_settings_panel.py"
REGISTRY_PANEL = ROOT / "phase6_registry_diagnostics_panel.py"
FINAL_VIEW = ROOT / "phase6_final_scene_view.py"
WORKSPACE_SHELL = ROOT / "phase6_workspace_shell.py"
PART_EDITOR_SESSION = ROOT / "phase6_part_editor_session.py"

TARGET_BOOTSTRAP_CALLS = (
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


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in _tree(path).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _source(path: Path, node: ast.AST) -> str:
    return ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""


def _call_names(fn: ast.FunctionDef) -> list[str]:
    result = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            result.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            result.append(node.func.attr)
    return result


def test_fix11_init_is_bootstrap_only_not_deep_owner_implementation():
    fn = _function(BRIDGE, "_fix11_init")
    body = _source(BRIDGE, fn)
    forbidden = (
        "Phase6DesignerWorkspace.from_snapshot",
        "Phase6BendingUI(",
        "Phase6AssemblyPanel(",
        "Phase6SettingsPanel(",
        "Phase6FinalSceneRenderer(",
        "Phase6FinalSceneView(",
        "Phase6RegistryDiagnosticsPanel(",
        "original.ttk.Frame(",
        "original.tk.StringVar(",
        "original.ttk.Treeview(",
        "original.ttk.Notebook(",
        "stable_fingerprint(",
        "clone_profile(",
    )
    found = [token for token in forbidden if token in body]
    assert not found, f"T7 RED: _fix11_init still contains deep/bootstrap implementation: {found}"


def test_fix11_init_owns_only_one_ordered_bootstrap_sequence():
    fn = _function(BRIDGE, "_fix11_init")
    calls = _call_names(fn)
    positions = []
    for name in TARGET_BOOTSTRAP_CALLS:
        matching = [i for i, call in enumerate(calls) if call == name]
        assert len(matching) == 1, f"T7 RED: expected one {name} call, got {matching}"
        positions.append(matching[0])
    assert positions == sorted(positions), (
        f"T7 RED: bootstrap order is not deterministic: {list(zip(TARGET_BOOTSTRAP_CALLS, positions))}"
    )


def test_fix10_predecessor_has_exactly_one_lifecycle_call_site():
    tree = _tree(BRIDGE)
    callers = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        count = sum(
            1
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "_FIX10_INIT"
        )
        if count:
            callers.append((node.name, count))
    assert callers == [("_fix11_init", 1)]



def test_t7_does_not_invent_second_shell_or_part_editor_root():
    assert WORKSPACE_SHELL.is_file()
    assert not PART_EDITOR_SESSION.exists()
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    shell_source = WORKSPACE_SHELL.read_text(encoding="utf-8")
    assert "from phase6_workspace_shell import" in bridge_source
    assert "mount_shared_content" in shell_source

def test_t7_accepted_owner_modules_remain_external_and_no_reverse_import():
    bridge_tree = _tree(BRIDGE)
    bridge_classes = {
        node.name
        for node in bridge_tree.body
        if isinstance(node, ast.ClassDef)
    }
    assert "Phase6BendingUI" not in bridge_classes

    for path in (BENDING, SETTINGS, REGISTRY_PANEL, FINAL_VIEW):
        source = path.read_text(encoding="utf-8")
        assert "from fold_designer_bridge import" not in source
        assert "import fold_designer_bridge" not in source


def test_t7_init_does_not_directly_construct_settings_or_final_scene_owners():
    fn = _function(BRIDGE, "_fix11_init")
    body = _source(BRIDGE, fn)
    forbidden = (
        "Phase6SettingsPanel",
        "Phase6FinalSceneRenderer",
        "Phase6FinalSceneViewAdapter",
        "Phase6FinalSceneView(",
    )
    assert not [token for token in forbidden if token in body]


def test_t7_bootstrap_helpers_are_not_alternate_predecessor_roots():
    tree = _tree(BRIDGE)
    funcs = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    for name in TARGET_BOOTSTRAP_CALLS:
        if name == "_FIX10_INIT":
            continue
        helper = funcs.get(name)
        assert helper is not None, f"T7 RED: missing bootstrap helper {name}"
        body = _source(BRIDGE, helper)
        assert "_FIX10_INIT(" not in body, f"{name} became a second lifecycle root"
