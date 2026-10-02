import ast
from pathlib import Path


MOVED_FUNCTIONS = {
    "_phase6_door_part_assembly_placement",
    "_phase6_assembly_placement_for_part",
    "_phase6_relief_polygon_coords",
    "_phase6_assembly_relief_clearance",
    "_phase6_current_cabinet_family",
    "_phase6_solution_is_committable",
    "_phase6_apply_resolved_cut_to_part",
    "_phase6_apply_resolved_cut_to_owner",
    "_phase6_side_wrap_target_corners",
    "_phase6_box_body_piece_solver_key",
    "_phase6_expand_box_body_fw_world_mid",
    "_phase6_shift_multistage_terminal_fold_world_mid",
    "_phase6_joint_relief_state_item_matches",
    "_phase6_cut_geometry_from_state_item",
    "_phase6_signature_canonical_value",
    "_phase6_manufacturing_state_signature",
    "_phase6_joint_registry_diagnostic_info",
}
MOVED_CONSTANTS = {"_PHASE6_ASSEMBLY_PLACEMENTS"}


def _module_tree(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


def _top_level_defined_names(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names



def test_issue347_helpers_have_one_canonical_owner_and_zero_reverse_import():
    import phase6_manufacturing_geometry as owner
    import fold_designer_bridge as bridge

    owner_tree = _module_tree("phase6_manufacturing_geometry.py")
    bridge_tree = _module_tree("fold_designer_bridge.py")

    owner_names = _top_level_defined_names(owner_tree)
    bridge_names = _top_level_defined_names(bridge_tree)

    all_moved = MOVED_FUNCTIONS | MOVED_CONSTANTS
    assert all_moved <= owner_names
    assert not all_moved & bridge_names

    reverse_imports = []
    for node in ast.walk(owner_tree):
        if isinstance(node, ast.Import):
            reverse_imports.extend(
                alias.name for alias in node.names if alias.name == "fold_designer_bridge"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge":
            reverse_imports.append(node.module)
    assert reverse_imports == []

    retained_bridge_reexports = {
        "_PHASE6_ASSEMBLY_PLACEMENTS",
        "_phase6_door_part_assembly_placement",
        "_phase6_assembly_placement_for_part",
        "_phase6_relief_polygon_coords",
        "_phase6_assembly_relief_clearance",
        "_phase6_current_cabinet_family",
        "_phase6_solution_is_committable",
        "_phase6_apply_resolved_cut_to_part",
        "_phase6_box_body_piece_solver_key",
        "_phase6_manufacturing_state_signature",
        "_phase6_joint_registry_diagnostic_info",
    }
    retired_reexports = all_moved - retained_bridge_reexports
    for name in retained_bridge_reexports:
        assert getattr(bridge, name) is getattr(owner, name)
    for name in retired_reexports:
        assert not hasattr(bridge, name)

def test_issue347_pure_helper_behavior_is_preserved():
    from types import SimpleNamespace
    from shapely.geometry import Polygon
    import phase6_manufacturing_geometry as owner

    polygon = Polygon([(0, 0), (10, 0), (10, 4), (0, 4)])
    assert owner._phase6_relief_polygon_coords(polygon) == [
        [[0.0, 0.0], [10.0, 0.0], [10.0, 4.0], [0.0, 4.0]]
    ]
    assert owner._phase6_side_wrap_target_corners("head") == ("top_left", "top_right")
    assert owner._phase6_side_wrap_target_corners("tail") == ("bottom_left", "bottom_right")

    value = {"b": {3, 1}, "a": [1, 2.0]}
    assert owner._phase6_signature_canonical_value(value) == {
        "b": (1.0, 3.0),
        "a": (1.0, 2.0),
    }

    assert owner._phase6_solution_is_committable(SimpleNamespace(verified=True))
    assert owner._phase6_solution_is_committable(
        SimpleNamespace(verified=False, rule_id="R1", trust_level="CERTIFIED")
    )
    assert not owner._phase6_solution_is_committable(
        SimpleNamespace(verified=False, rule_id=None, trust_level="")
    )


