import ast
from pathlib import Path


MOVED = {
    "_phase6_resolve_family_divider_reliefs",
    "_phase6_resolve_manufacturing_geometry",
}
REQUIRED_BOUND = {
    "_phase6_mesh_profiles_for_part",
    "_phase6_operator_finished_dimensions",
    "_phase6_scene_query_payload_for_part",
    "_phase6_publish_live_state",
}


def _tree(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


def _defined(tree):
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _class_wiring_targets(tree):
    out = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "Phase6FoldDesignerApp"
            ):
                out.add(target.attr)
    return out


def test_issue350_manufacturing_orchestration_has_one_owner_and_zero_reverse_import():
    import phase6_manufacturing_geometry as owner
    import fold_designer_bridge as bridge

    owner_tree = _tree("phase6_manufacturing_geometry.py")
    bridge_tree = _tree("fold_designer_bridge.py")
    assert MOVED <= _defined(owner_tree)
    assert not (MOVED & _defined(bridge_tree))

    for name in MOVED:
        assert getattr(bridge, name) is getattr(owner, name)

    reverse = []
    for node in ast.walk(owner_tree):
        if isinstance(node, ast.Import):
            reverse.extend(a.name for a in node.names if a.name == "fold_designer_bridge")
        elif isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge":
            reverse.append(node.module)
    assert reverse == []


def test_issue350_self_bound_dependencies_are_wired_before_runtime_use():
    bridge_tree = _tree("fold_designer_bridge.py")
    wired = _class_wiring_targets(bridge_tree)
    assert REQUIRED_BOUND <= wired


def test_issue350_owner_uses_canonical_part_navigation_name_not_bridge_wrapper():
    owner_tree = _tree("phase6_manufacturing_geometry.py")
    resolver = next(
        node for node in owner_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_phase6_resolve_manufacturing_geometry"
    )
    loaded = {
        node.id
        for node in ast.walk(resolver)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert "_phase6_is_box_body_physical_piece_key" not in loaded
    assert "is_box_body_physical_piece_key" in loaded
