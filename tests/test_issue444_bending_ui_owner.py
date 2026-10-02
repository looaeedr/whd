from __future__ import annotations

import ast
from pathlib import Path

import pytest

import fold_designer_bridge as bridge
import fold_designer_original as original
import phase6_bending_ui as bending_ui


BRIDGE = Path(bridge.__file__)
OWNER = Path(bending_ui.__file__)
UI_STATE_TEST = Path("tests/test_phase6_ui_state_regressions.py")


def _top_level_defs(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def test_issue444_r2_owner_location_and_reverse_import_contract():
    bridge_defs = _top_level_defs(BRIDGE)
    owner_defs = _top_level_defs(OWNER)
    owner_tree = ast.parse(OWNER.read_text(encoding="utf-8"), filename=str(OWNER))
    imported_modules = {
        alias.name
        for node in owner_tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in owner_tree.body
        if isinstance(node, ast.ImportFrom)
    }

    assert "Phase6BendingUI" in owner_defs
    assert "Phase6BendingUI" not in bridge_defs
    assert "_phase6_resolve_profile_key" not in bridge_defs
    assert "_phase6_box_symmetry_allowed" not in bridge_defs
    assert "_phase6_apply_box_symmetry_policy" not in bridge_defs
    assert "fold_designer_bridge" not in imported_modules
    assert "fold_designer_bridge" not in imported_from


def test_issue444_r2_profile_compat_and_transaction_delegate_remain_in_bridge():
    source = BRIDGE.read_text(encoding="utf-8")
    assert "resolve_profile_key as _phase6_resolve_profile_key" in source
    assert "def _phase6_on_box_symmetry_changed(self):" in source
    delegate = source[source.index("def _phase6_on_box_symmetry_changed(self):"):]
    delegate = delegate[:delegate.index("\ndef ", 1)]
    assert "commit_symmetry" in delegate


def test_issue444_r2_constructor_seam_stays_three_args_and_owner_action_precedes_super():
    owner_class = _top_level_defs(OWNER)["Phase6BendingUI"]
    init = next(
        node for node in owner_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    assert [arg.arg for arg in init.args.args] == ["self", "parent", "state", "update_cb"]

    source = BRIDGE.read_text(encoding="utf-8")
    class_start = source.index("class Phase6FoldDesignerApp")
    init_start = source.index("    def __init__(self, root, snapshot", class_start)
    init_end = source.index("\n    def ", init_start + 5)
    init_source = source[init_start:init_end]
    assert init_source.index("self._phase6_on_box_symmetry_changed = lambda") < init_source.index("super().__init__(root)")
    assert "saved_bending_ui = original.BendingUI" in init_source
    assert "original.BendingUI = Phase6BendingUI" in init_source
    assert "finally:" in init_source
    assert "original.BendingUI = saved_bending_ui" in init_source


class _DummyRoot:
    def bind(self, *_args, **_kwargs):
        return None


def test_issue444_r2_monkey_patch_restores_on_normal_init(monkeypatch):
    before = original.BendingUI

    def fake_main_init(self, root):
        assert original.BendingUI is bending_ui.Phase6BendingUI
        assert callable(self._phase6_on_box_symmetry_changed)
        self.root = root

    monkeypatch.setattr(original.MainApp, "__init__", fake_main_init)
    monkeypatch.setattr(bridge.Phase6FoldDesignerApp, "load_phase6_snapshot", lambda *_a, **_k: None)

    app = object.__new__(bridge.Phase6FoldDesignerApp)
    bridge._FIX10_INIT(app, _DummyRoot(), {})
    assert original.BendingUI is before


def test_issue444_r2_monkey_patch_restores_on_injected_exception(monkeypatch):
    before = original.BendingUI

    def exploding_main_init(self, root):
        assert original.BendingUI is bending_ui.Phase6BendingUI
        assert callable(self._phase6_on_box_symmetry_changed)
        raise RuntimeError("injected predecessor init failure")

    monkeypatch.setattr(original.MainApp, "__init__", exploding_main_init)

    app = object.__new__(bridge.Phase6FoldDesignerApp)
    with pytest.raises(RuntimeError, match="injected predecessor init failure"):
        bridge._FIX10_INIT(app, _DummyRoot(), {})
    assert original.BendingUI is before


def test_issue444_r3_source_tests_follow_bending_owner_location():
    source = UI_STATE_TEST.read_text(encoding="utf-8")
    assert 'source.index("class Phase6BendingUI")' not in source
    assert 'assert \'text="對稱折彎"\' in source' not in source
    assert "Path(bending_ui.__file__)" in source
