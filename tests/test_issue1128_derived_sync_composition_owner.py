import ast
from pathlib import Path


def _function_body(path: str, name: str) -> str:
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_issue1128_bridge_is_narrow_compatibility_delegate():
    body = _function_body("fold_designer_bridge.py", "_phase6_sync_authoritative_derived_parts")
    assert "_phase6_composition(self).sync_authoritative_derived_parts(globals())" in body
    assert len(body.splitlines()) <= 5
    forbidden = (
        "DerivedPartRequestAssemblyInput(",
        "derive_door_layout_cells",
        "derive_box_body_dividers",
        "derive_all_inner_door_frames",
        "apply_derived_sync_plan(plan)",
    )
    assert not [token for token in forbidden if token in body]


def test_issue1128_composition_is_single_orchestration_owner():
    path = Path("gui_modules/application/fold_designer_adapter.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    owners = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6FoldDesignerComposition"
    ]
    assert len(owners) == 1
    methods = [
        node for node in owners[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "sync_authoritative_derived_parts"
    ]
    assert len(methods) == 1
    body = ast.get_source_segment(source, methods[0]) or ""
    for token in (
        "DerivedPartRequestAssemblyInput(",
        "build_derived_part_projection_request(",
        "build_derived_part_sync_plan(request)",
        "navigation.apply_derived_sync_plan(plan)",
    ):
        assert token in body
    reverse_imports = [
        node for node in ast.walk(tree)
        if (isinstance(node, ast.Import) and any(alias.name == "fold_designer_bridge" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge")
    ]
    assert reverse_imports == []


def test_issue1128_bridge_loc_materially_decreases_and_return_contract_stays_delegated():
    body = _function_body("fold_designer_bridge.py", "_phase6_sync_authoritative_derived_parts")
    assert "return _phase6_composition(self).sync_authoritative_derived_parts(globals())" in body
    assert len(body.splitlines()) < 20
