# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from pathlib import Path


MOVED = {
    "_phase6_door_part_projections",
    "_phase6_is_box_body_physical_piece_key",
    "_phase6_is_side_back_editable_piece_key",
    "_phase6_operator_part_selector_keys",
    "_phase6_box_body_piece_keys",
    "_phase6_structure_tree_rows",
    "_phase6_reverse_fold_traversal",
    "_phase6_box_body_piece_part_profiles",
    "_phase6_is_door_part_key",
    "_phase6_is_base_plate_part_key",
}


def test_phase5_t1_owner_module_exists_and_is_pure():
    import phase6_derived_topology as topo

    source = Path(topo.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert "fold_designer_bridge" not in imported
    assert "tkinter" not in imported
    assert not any(name.startswith("gui") for name in imported)


def test_phase5_t1_bridge_no_longer_defines_moved_functions():
    source = Path("fold_designer_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not (MOVED & defined)


def test_phase5_t1_compatibility_aliases_resolve_to_new_owner():
    import fold_designer_bridge as bridge
    import phase6_derived_topology as topo

    for name in MOVED:
        assert getattr(bridge, name) is getattr(topo, name)


def test_phase5_t1_part_key_identity_characterization():
    import phase6_derived_topology as topo

    assert topo._phase6_is_side_back_editable_piece_key("box_body:left_side")
    assert topo._phase6_is_side_back_editable_piece_key("box_body:back")
    assert topo._phase6_is_side_back_editable_piece_key("box_body:right_side")
    assert not topo._phase6_is_side_back_editable_piece_key("box_body:top")

    assert topo._phase6_is_door_part_key("door")
    assert topo._phase6_is_door_part_key("door_c2_r3")
    assert not topo._phase6_is_door_part_key("door_c2")
    assert topo._phase6_is_base_plate_part_key("base_plate")
    assert topo._phase6_is_base_plate_part_key("base_plate_c1_r2")
    assert not topo._phase6_is_base_plate_part_key("base_plate_r2")


def test_phase5_t1_reverse_fold_traversal_characterization():
    import phase6_derived_topology as topo

    rows = [
        {"len": 10.0, "angle": 91.0, "phase6_key": "a"},
        {"len": 20.0, "angle": -92.0, "phase6_key": "b"},
        {"len": 30.0, "phase6_key": "c"},
    ]
    assert topo._phase6_reverse_fold_traversal(rows) == [
        {"len": 30.0, "phase6_key": "c", "angle": -92.0},
        {"len": 20.0, "phase6_key": "b", "angle": 91.0},
        {"len": 10.0, "phase6_key": "a"},
    ]
