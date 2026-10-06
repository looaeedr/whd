from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
OWNER = ROOT / "gui_modules" / "application" / "fold_designer_part_session.py"


def _top_functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_issue1321_moves_part_session_orchestration_out_of_bridge():
    bridge = _top_functions(BRIDGE)
    owner_tree = ast.parse(OWNER.read_text(encoding="utf-8"))
    owner_class = next(
        node for node in owner_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6PartSessionOwner"
    )
    owner = {
        node.name: node
        for node in owner_class.body
        if isinstance(node, ast.FunctionDef)
    }

    assert "save_current_part" in owner
    assert "activate_part" in owner

    save = bridge["_fix11_save_current_part"]
    activate = bridge["_fix11_activate_part"]
    assert save.end_lineno - save.lineno + 1 <= 4
    assert activate.end_lineno - activate.lineno + 1 <= 4

    save_body = ast.unparse(save)
    activate_body = ast.unparse(activate)
    assert "Phase6PartSessionOwner" in save_body or "_phase6_part_session_owner" in save_body
    assert "Phase6PartSessionOwner" in activate_body or "_phase6_part_session_owner" in activate_body
    assert "self.save_current_part()" in ast.unparse(owner["activate_part"])


def test_issue1321_owner_keeps_bridge_compatibility_via_lazy_bridge_resolution():
    source = OWNER.read_text(encoding="utf-8")
    assert "class Phase6PartSessionOwner" in source
    assert "__import__('fold_designer_bridge')" in source
    assert "formula ownership remains" in source
    assert "def __init__(self):" in source
    assert "def bind_application(self, host: Any):" in source
    assert "def __init__(self, app:" not in source


def test_issue1321_bridge_only_owns_delegate_ports():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "from gui_modules.application.fold_designer_part_session import Phase6PartSessionOwner" in source
    assert "def _phase6_part_session_owner(self):" in source
    assert 'return _phase6_part_session_owner(self).save_current_part(notify=notify)' in source
    assert 'return _phase6_part_session_owner(self).activate_part(key, initial=initial)' in source