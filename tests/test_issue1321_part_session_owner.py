"""Issue #1321 part-session ownership and anti-regrowth contracts."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
OWNER = ROOT / "gui_modules/application/fold_designer_part_session.py"


def _functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _class_methods(path: Path, class_name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    return {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}


def test_bridge_save_and_activation_are_narrow_part_session_delegates():
    funcs = _functions(BRIDGE)
    for name, method in (("_fix11_save_current_part", "save_current_part"), ("_fix11_activate_part", "activate_part")):
        node = funcs[name]
        source = ast.unparse(node)
        assert "_phase6_part_session" in source
        assert f".{method}(" in source
        assert (node.end_lineno - node.lineno + 1) <= 2


def test_part_session_owner_keeps_activation_transaction_order():
    methods = _class_methods(OWNER, "Phase6PartSessionController")
    source = ast.unparse(methods["activate_part"])
    plan = source.index("plan_activation")
    save = source.index("app._save_current_part")
    begin = source.index("navigation.begin_activation")
    finish = source.index("navigation.finish_activation")
    assert plan < save < begin < finish
    assert "project_active_part_selector" in source
    assert "finalize_single_part_layout" in source
    assert "_phase6_manufacturing_state_signature" in source


def test_part_session_owner_has_no_reverse_bridge_import():
    source = OWNER.read_text(encoding="utf-8")
    assert "import fold_designer_bridge" not in source
    assert "from fold_designer_bridge" not in source


def test_bridge_loc_ratchets_after_part_session_extraction():
    loc = len(BRIDGE.read_text(encoding="utf-8").splitlines())
    assert loc <= 3350, f"Bridge regrew past #1321 part-session ratchet: {loc}"
