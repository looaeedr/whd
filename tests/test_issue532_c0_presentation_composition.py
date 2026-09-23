from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
COMPOSITION = Path("gui_modules/application/fold_designer_adapter.py")

BRIDGE_WIRING = {
    "_phase6_workspace_shell_owner": "WorkspaceShellOwner(",
    "_phase6_ensure_settings_panel": "Phase6SettingsPanel(",
    "_phase6_registry_panel": "Phase6RegistryDiagnosticsPanel(",
    "_phase6_corner_data_view": "Phase6CornerDataViewAdapter(",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_functions(path: Path) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in _tree(path).body
        if isinstance(node, ast.FunctionDef)
    }


def test_c0_presentation_owner_construction_lives_in_single_composition_root():
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    composition_source = COMPOSITION.read_text(encoding="utf-8")
    funcs = _top_functions(BRIDGE)

    missing = [
        name for name in BRIDGE_WIRING
        if name not in funcs
    ]
    assert not missing

    deep_bridge = {
        name: funcs[name].end_lineno - funcs[name].lineno + 1
        for name in BRIDGE_WIRING
        if funcs[name].end_lineno - funcs[name].lineno + 1 > 5
    }
    assert deep_bridge == {}, (
        "C0 RED: presentation-owner construction/port wiring remains deep in Bridge: "
        f"{deep_bridge}"
    )

    bridge_constructors = [
        token for token in BRIDGE_WIRING.values()
        if token in bridge_source
    ]
    assert bridge_constructors == [], (
        "C0 RED: Bridge still constructs presentation owners directly: "
        f"{bridge_constructors}"
    )

    composition_class = next(
        node
        for node in _tree(COMPOSITION).body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    body = ast.get_source_segment(composition_source, composition_class) or ""
    missing_constructors = [
        token for token in BRIDGE_WIRING.values()
        if token not in body
    ]
    assert missing_constructors == [], (
        "C0 RED: single composition root has not absorbed presentation-owner "
        f"construction: {missing_constructors}"
    )


def test_c0_composition_module_still_does_not_reverse_import_bridge():
    source = COMPOSITION.read_text(encoding="utf-8")
    assert "from fold_designer_bridge import" not in source
    assert "import fold_designer_bridge" not in source

SETTINGS_PORT_HELPERS = {
    "_phase6_settings_application_ports",
    "_phase6_settings_application_read_snapshot",
    "_phase6_settings_application_read_profile_snapshot",
    "_phase6_settings_application_save_current_part",
    "_phase6_settings_application_render_bending",
    "_phase6_settings_application_refresh_settings_panel",
    "_phase6_settings_application_refresh_persistent_controls",
    "_phase6_settings_application_project_status",
}

SETTINGS_KEEP_HELPERS = {
    "_phase6_settings_application_apply_profile_plan",
    "_phase6_settings_application_project_ui_values",
    "_phase6_settings_application_submit_update_intent",
    "_phase6_settings_application_publish_live_state",
}


def test_c0_settings_application_port_assembly_lives_in_composition_root():
    bridge_funcs = _top_functions(BRIDGE)
    composition_tree = _tree(COMPOSITION)
    composition_class = next(
        node
        for node in composition_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6FoldDesignerComposition"
    )
    composition_methods = {
        node.name
        for node in composition_class.body
        if isinstance(node, ast.FunctionDef)
    }

    stale = sorted(SETTINGS_PORT_HELPERS & set(bridge_funcs))
    assert stale == [], (
        "C0 RED: shallow Settings application port wiring still lives in Bridge: "
        f"{stale}"
    )
    assert "settings_application_ports" in composition_methods

    # C0 must not reopen Phase 5 KEEP boundaries just to satisfy LOC.
    missing_keep = sorted(SETTINGS_KEEP_HELPERS - set(bridge_funcs))
    assert missing_keep == [], (
        "C0 must preserve substantive Settings application behavior in Bridge: "
        f"{missing_keep}"
    )

    coordinator = ast.unparse(bridge_funcs["_phase6_settings_coordinator"])
    assert "settings_application_ports" in coordinator
    assert "Phase6SettingsApplicationPorts" not in coordinator

