# -*- coding: utf-8 -*-
"""Issue #479 / Phase 4 T1 FinalScene composition ownership contracts."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
ADAPTER = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"
FINAL_VIEW = ROOT / "phase6_final_scene_view.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_function(path: Path, name: str) -> ast.FunctionDef:
    return next(
        node for node in _tree(path).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _class(path: Path, name: str) -> ast.ClassDef:
    return next(
        node for node in _tree(path).body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _source(path: Path, node: ast.AST) -> str:
    return ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""


def _facade_binding_count() -> int:
    tree = _tree(BRIDGE)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "install_fold_designer_bridge_facade")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "install_fold_designer_bridge_facade")
        )
    ]
    assert len(calls) == 1
    dict_args = [arg for arg in calls[0].args if isinstance(arg, ast.Dict)]
    assert len(dict_args) == 1
    return len(dict_args[0].keys)


def test_t1_bridge_final_scene_adapter_is_narrow_delegate_not_port_builder():
    fn = _top_function(BRIDGE, "_phase6_final_scene_adapter")
    body = _source(BRIDGE, fn)
    assert "FinalSceneCompositionPorts(" not in body, (
        "T1 RED: bridge still owns the deep 35-port FinalScene composition"
    )
    assert "_phase6_composition(self)" in body
    assert ".final_scene_adapter(" in body


def test_t1_existing_application_composition_owner_builds_final_scene_ports():
    cls = _class(ADAPTER, "Phase6FoldDesignerComposition")
    body = _source(ADAPTER, cls)
    assert "FinalSceneCompositionPorts(" in body, (
        "T1 RED: the existing application composition owner has not taken over port assembly"
    )
    assert "Phase6FinalSceneViewAdapter(" in body


def test_t1_final_scene_ports_contract_remains_exactly_35_fields():
    cls = _class(ADAPTER, "FinalSceneCompositionPorts")
    fields = [
        node.target.id
        for node in cls.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    ]
    assert len(fields) == 35, f"FinalScene port contract drifted: {len(fields)} != 35"
    assert len(set(fields)) == 35


def test_t1_owner_modules_never_reverse_import_bridge():
    for path in (ADAPTER, FINAL_VIEW):
        source = path.read_text(encoding="utf-8")
        assert "from fold_designer_bridge import" not in source
        assert "import fold_designer_bridge" not in source


def test_t1_facade_ratchet_does_not_grow_past_t0_baseline():
    assert _facade_binding_count() <= 69


def test_t1_final_scene_port_inventory_is_exact_and_bounded():
    tree = _tree(ADAPTER)
    assign = next(
        (
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "FINAL_SCENE_PORT_INVENTORY"
                for target in node.targets
            )
        ),
        None,
    )
    assert assign is not None, "T1 RED: missing FinalScene port inventory"
    assert isinstance(assign.value, (ast.Tuple, ast.List))
    rows = []
    for item in assign.value.elts:
        assert isinstance(item, ast.Call)
        values = [ast.literal_eval(arg) for arg in item.args]
        assert len(values) == 6
        rows.append(values)
    port_cls = _class(ADAPTER, "FinalSceneCompositionPorts")
    fields = [
        node.target.id
        for node in port_cls.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    ]
    assert len(rows) == 35
    assert [row[0] for row in rows] == fields
    assert all(row[1] for row in rows)
    assert all(row[2] in {"READ", "WRITE", "READ_WRITE", "TYPE"} for row in rows)
    assert all(
        row[3] in {"APP_TO_FINAL_SCENE", "FINAL_SCENE_TO_APP", "BOOTSTRAP"}
        for row in rows
    )
    assert all(isinstance(row[4], bool) for row in rows)
    assert all(
        row[5] in {"NONE", "DISPLAY_EFFECT", "CANONICAL_APPLICATION_STATE"}
        for row in rows
    )
