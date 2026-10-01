from __future__ import annotations

import ast
from pathlib import Path

import fold_designer_bridge as bridge
import phase6_navigation_view_adapter as view

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
OWNER = ROOT / "phase6_navigation_view_adapter.py"


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
    assert "add_part(" not in source
    assert "remove_part(" not in source


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
