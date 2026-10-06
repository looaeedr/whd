from __future__ import annotations

import ast
from pathlib import Path

import fold_designer_bridge as bridge
import phase6_navigation_view_adapter as view

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
OWNER = ROOT / "phase6_navigation_view_adapter.py"
PART_SESSION = ROOT / "gui_modules" / "application" / "fold_designer_part_session.py"


def _function(name: str):
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def test_navigation_view_owner_exists_and_has_no_reverse_or_manufacturing_imports():
    source = OWNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "fold_designer_bridge" not in imports
    assert not [name for name in imports if name.startswith("ae_engine") or "manufacturing" in name]
    assert "sync_derived_parts" not in source
    assert "designer_workspace.add_part" not in source
    assert "designer_workspace.remove_part" not in source


def test_bridge_structure_tree_refresh_is_thin_view_wrapper():
    fn = _function("_phase6_refresh_structure_tree")
    assert len(fn.body) <= 2
    text = ast.unparse(fn)
    assert "_navigation_view_refresh_structure_tree" in text
    assert "tree.insert" not in text
    assert "selection_set" not in text


def test_bridge_piece_selector_refresh_is_thin_view_wrapper():
    fn = _function("_phase6_refresh_box_body_piece_selector")
    assert len(fn.body) <= 2
    text = ast.unparse(fn)
    assert "_navigation_view_refresh_box_body_piece_selector" in text
    assert "notebook.add" not in text
    assert "notebook.select" not in text


def test_owner_exports_both_projection_entrypoints():
    assert callable(view.refresh_structure_tree)
    assert callable(view.refresh_box_body_piece_selector)


def test_bridge_loc_ratchets_below_6240():
    assert BRIDGE.read_text(encoding="utf-8").count("\n") <= 6240


def test_navigation_event_glue_is_owned_by_view_adapter_and_bridge_wrappers_stay_thin():
    bridge_tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    adapter_source = OWNER.read_text(encoding="utf-8")
    for name in (
        "on_structure_tree_select",
        "set_structure_tree_visibility",
        "on_box_body_piece_tab_changed",
    ):
        assert f"def {name}(" in adapter_source

    funcs = {node.name: node for node in bridge_tree.body if isinstance(node, ast.FunctionDef)}
    for name in (
        "_phase6_on_structure_tree_select",
        "_phase6_set_structure_tree_visibility",
        "_phase6_on_box_body_piece_tab_changed",
    ):
        assert name in funcs
        assert (funcs[name].end_lineno - funcs[name].lineno + 1) <= 10


def test_bridge_loc_ratchets_below_6200_after_navigation_event_extraction():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 6200, f"Bridge regrew past #1100 extended ratchet: {loc}"


def test_navigation_compatibility_view_glue_is_owned_by_adapter():
    adapter_source = OWNER.read_text(encoding="utf-8")
    for name in (
        "refresh_sticky_structure_tree",
        "clear_navigation_residue",
        "refresh_content_switch",
        "build_content_switch",
        "on_structure_tree_click",
    ):
        assert f"def {name}(" in adapter_source

    bridge_tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    funcs = {node.name: node for node in bridge_tree.body if isinstance(node, ast.FunctionDef)}
    for name in (
        "_phase6_refresh_sticky_structure_tree",
        "_phase6_clear_navigation_residue",
        "_phase6_refresh_content_switch",
        "_phase6_build_content_switch",
        "_phase6_on_structure_tree_click",
    ):
        assert name in funcs
        assert (funcs[name].end_lineno - funcs[name].lineno + 1) <= 8


def test_bridge_loc_ratchets_below_6145_after_navigation_view_completion():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 6145, f"Bridge regrew past #1100 final navigation ratchet: {loc}"


def test_part_selector_and_add_menu_projection_are_owned_by_navigation_view_adapter():
    adapter_source = OWNER.read_text(encoding="utf-8")
    for name in ("refresh_part_selector", "refresh_part_button_states", "refresh_add_part_menu"):
        assert f"def {name}(" in adapter_source
    bridge_tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    funcs = {node.name: node for node in bridge_tree.body if isinstance(node, ast.FunctionDef)}
    for name in ("_fix11_refresh_part_buttons", "_fix11_refresh_part_button_states", "_fix11_refresh_add_part_menu"):
        assert name in funcs
        assert (funcs[name].end_lineno - funcs[name].lineno + 1) <= 20


def test_bridge_loc_ratchets_below_6100_after_part_selector_extraction():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 6100, f"Bridge regrew past #1100 part-selector ratchet: {loc}"

def test_navigation_view_owner_projects_corner_and_assembly_modes_without_reverse_authority():
    adapter_source = OWNER.read_text(encoding="utf-8")
    for name in ("hide_corner_data_canvas", "show_corner_data_mode", "project_assembly_mode"):
        assert f"def {name}(" in adapter_source
    bridge_tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    funcs = {node.name: node for node in bridge_tree.body if isinstance(node, ast.FunctionDef)}
    assert (funcs["_phase6_hide_corner_data_canvas"].end_lineno - funcs["_phase6_hide_corner_data_canvas"].lineno + 1) <= 8
    assert (funcs["_phase6_show_corner_data"].end_lineno - funcs["_phase6_show_corner_data"].lineno + 1) <= 16
    show_assembly = ast.unparse(funcs["_phase6_show_assembly"])
    assert "_phase6_manufacturing_state_signature" in show_assembly
    assert "_save_current_part" in show_assembly
    assert "_navigation_view_project_assembly_mode" in show_assembly


def test_bridge_loc_ratchets_below_6050_after_mode_projection_extraction():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 6050, f"Bridge regrew past #1100 mode-projection ratchet: {loc}"

def test_active_part_selector_and_canvas_settle_are_owned_by_navigation_view_adapter():
    adapter_source = OWNER.read_text(encoding="utf-8")
    assert "def project_active_part_selector(" in adapter_source
    assert "def finalize_single_part_layout(" in adapter_source

    bridge_activate = _function("_fix11_activate_part")
    bridge_source = ast.unparse(bridge_activate)
    assert len(bridge_activate.body) <= 2
    assert "_phase6_part_session" in bridge_source
    assert ".activate_part(" in bridge_source

    session_tree = ast.parse(PART_SESSION.read_text(encoding="utf-8"))
    controller = next(
        node
        for node in session_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "Phase6PartSessionController"
    )
    activate = ast.unparse(next(
        node
        for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name == "activate_part"
    ))
    assert "project_active_part_selector" in activate
    assert "finalize_single_part_layout" in activate
    assert "_phase6_manufacturing_state_signature" in activate
    assert "navigation.begin_activation" in activate
    assert "navigation.finish_activation" in activate


def test_bridge_loc_ratchets_below_6000_after_active_part_view_extraction():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 6000, f"Bridge regrew past #1100 active-part view ratchet: {loc}"

def test_persistent_structure_and_layout_helpers_are_owned_by_view_adapter():
    adapter_source = OWNER.read_text(encoding="utf-8")
    for name in (
        "refresh_persistent_structure_controls",
        "pack_right_panel_above_canvas",
        "hide_original_structure_mode_controls",
    ):
        assert f"def {name}(" in adapter_source
    bridge_tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    funcs = {node.name: node for node in bridge_tree.body if isinstance(node, ast.FunctionDef)}
    assert (funcs["_phase6_refresh_persistent_structure_controls"].end_lineno - funcs["_phase6_refresh_persistent_structure_controls"].lineno + 1) <= 10
    assert (funcs["_phase6_pack_right_panel_above_canvas"].end_lineno - funcs["_phase6_pack_right_panel_above_canvas"].lineno + 1) <= 8
    assert (funcs["_hide_original_structure_mode_controls"].end_lineno - funcs["_hide_original_structure_mode_controls"].lineno + 1) <= 8


def test_bridge_loc_ratchets_below_5970_after_layout_helper_extraction():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 5970, f"Bridge regrew past #1100 layout-helper ratchet: {loc}"

def test_part_navigation_widget_construction_is_owned_by_navigation_view_adapter():
    adapter_source = OWNER.read_text(encoding="utf-8")
    assert "def build_part_navigation_widgets(" in adapter_source
    adapter_tree = ast.parse(adapter_source)
    builder = next(
        node for node in adapter_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_part_navigation_widgets"
    )
    builder_text = ast.unparse(builder)
    assert "ttk.Treeview" in builder_text
    assert "ttk.Scrollbar" in builder_text
    assert "ttk.Notebook" in builder_text
    assert "takefocus=True" in builder_text

    installer = ast.unparse(_function("_phase6_install_part_editor_compatibility"))
    assert "_navigation_view_build_part_navigation_widgets" in installer
    for forbidden in ("ttk.Treeview", "ttk.Scrollbar", "ttk.Notebook", "structure_tree.bind"):
        assert forbidden not in installer


def test_bridge_loc_ratchets_below_5800_after_part_navigation_widget_construction_extraction():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 5800, f"Bridge regrew past #1197 navigation-widget ratchet: {loc}"

