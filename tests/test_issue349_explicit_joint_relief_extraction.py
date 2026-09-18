import ast
from pathlib import Path


def _defined(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def test_issue349_explicit_joint_relief_solver_has_one_canonical_owner():
    import phase6_manufacturing_geometry as owner
    import fold_designer_bridge as bridge

    name = "_phase6_resolve_explicit_joint_reliefs"
    assert name in _defined("phase6_manufacturing_geometry.py")
    assert name not in _defined("fold_designer_bridge.py")
    assert getattr(bridge, name) is getattr(owner, name)

    tree = ast.parse(Path("phase6_manufacturing_geometry.py").read_text(encoding="utf-8"))
    reverse = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            reverse.extend(a.name for a in node.names if a.name == "fold_designer_bridge")
        elif isinstance(node, ast.ImportFrom) and node.module == "fold_designer_bridge":
            reverse.append(node.module)
    assert reverse == []

