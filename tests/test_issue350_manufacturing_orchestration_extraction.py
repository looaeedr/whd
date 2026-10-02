import ast
from pathlib import Path


GEOMETRY_OWNER_FUNCTIONS = {
    "_phase6_resolve_family_divider_reliefs",
    "_phase6_resolve_explicit_joint_reliefs",
}
PHASE1_ONLY_CLASS_WIRING = {
    "_phase6_mesh_profiles_for_part",
    "_phase6_operator_finished_dimensions",
    "_phase6_scene_query_payload_for_part",
}


def _tree(path):
    return ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))


def _defined(tree):
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _class_wiring_targets(tree):
    out = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "Phase6FoldDesignerApp"
                ):
                    out.add(target.attr)
            continue
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not (
            isinstance(call.func, ast.Name)
            and call.func.id == "install_fold_designer_bridge_facade"
        ):
            continue
        bindings = call.args[1] if len(call.args) >= 2 else None
        if bindings is None:
            for keyword in call.keywords:
                if keyword.arg == "bindings":
                    bindings = keyword.value
                    break
        if not isinstance(bindings, ast.Dict):
            continue
        for key in bindings.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                out.add(key.value)
    return out


def test_issue350_manufacturing_orchestration_owner_survives_phase2_cutover():
    owner_tree = _tree("phase6_manufacturing_geometry.py")
    service_tree = _tree("phase6_manufacturing_service.py")
    bridge_tree = _tree("fold_designer_bridge.py")

    assert GEOMETRY_OWNER_FUNCTIONS <= _defined(owner_tree)
    assert "resolve" in _defined(service_tree)
    assert "_phase6_resolve_manufacturing_result" not in _defined(owner_tree)
    assert "_phase6_resolve_manufacturing_geometry" in _defined(bridge_tree)

    reverse = []
    for tree in (owner_tree, service_tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                reverse.extend(a.name for a in node.names if a.name == "fold_designer_bridge")
            elif isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge":
                reverse.append(node.module)
    assert reverse == []


def test_issue350_phase1_only_service_wiring_is_retired_after_t4():
    bridge_tree = _tree("fold_designer_bridge.py")
    wired = _class_wiring_targets(bridge_tree)
    assert not (PHASE1_ONLY_CLASS_WIRING & wired)
    assert "_phase6_publish_live_state" in wired


def test_issue350_pure_service_has_no_bridge_wrapper_or_self():
    tree = _tree("phase6_manufacturing_service.py")
    resolver = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    )
    loaded = {
        node.id
        for node in ast.walk(resolver)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert "_phase6_is_box_body_physical_piece_key" not in loaded
    assert "self" not in loaded
