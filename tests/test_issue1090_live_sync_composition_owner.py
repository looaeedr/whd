from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
OWNER = ROOT / "gui_modules/application/fold_designer_adapter.py"
IMPLEMENTATION = ROOT / "gui_modules/application/fold_designer_composition_state.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_bridge_live_sync_publish_is_thin_composition_wrapper():
    fn = next(
        node for node in _tree(BRIDGE).body
        if isinstance(node, ast.FunctionDef) and node.name == "_phase6_publish_live_state"
    )
    block = ast.get_source_segment(BRIDGE.read_text(encoding="utf-8"), fn) or ""
    assert fn.end_lineno - fn.lineno + 1 <= 4
    assert "_phase6_composition(self).publish_live_state" in block
    assert "plan_live_sync_envelope" not in block
    assert "_live_sync_callback" not in block


def test_composition_owns_live_sync_effect_boundary():
    owner_tree = _tree(OWNER)
    owner = next(
        node for node in owner_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6FoldDesignerComposition"
    )
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "publish_live_state"
        for node in owner.body
    )
    tree = _tree(IMPLEMENTATION)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "publish_live_state"
    )
    block = ast.get_source_segment(IMPLEMENTATION.read_text(encoding="utf-8"), fn) or ""
    for token in (
        "plan_live_sync_envelope(",
        "materialize_sync_value(",
        "_phase6_sync_revision",
        "_phase6_last_live_fingerprint",
        "_phase6_live_sync_guard",
    ):
        assert token in block


def test_final_scene_live_sync_port_routes_directly_to_composition_owner():
    source = OWNER.read_text(encoding="utf-8")
    assert "publish_live_state=lambda **kwargs: self.publish_live_state(" in source


def test_bridge_loc_ratchets_below_5870_after_live_sync_owner_move():
    loc = BRIDGE.read_text(encoding="utf-8").count("\n")
    assert loc <= 5870, f"Bridge regrew past #1090 live-sync ratchet: {loc}"
