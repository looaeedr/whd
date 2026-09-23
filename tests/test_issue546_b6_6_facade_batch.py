from __future__ import annotations

import ast
from pathlib import Path

import fold_designer_bridge as bridge


BRIDGE = Path("fold_designer_bridge.py")

RETAINED = {
    "submit_update_intent",
    "set_3d_preview_enabled",
}

REMOVED = {
    "_phase6_render_endcap_edge_controls",
    "_phase6_commit_base_plate_edge_shrink",
    "apply_settings_delta",
    "switch_active_part",
    "publish_if_changed",
    "_phase6_flush_update_intents",
    "refresh_3d_preview",
}


def _facade_bindings() -> dict[str, str]:
    source = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BRIDGE))
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "install_fold_designer_bridge_facade"
    )
    mapping = next(arg for arg in call.args if isinstance(arg, ast.Dict))
    return {
        key.value: ast.unparse(value)
        for key, value in zip(mapping.keys, mapping.values)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def test_b6_6_removable_entries_leave_facade():
    bindings = _facade_bindings()
    assert REMOVED.isdisjoint(bindings), (
        "B6-6 RED: removable facade entries remain: "
        f"{sorted(REMOVED & set(bindings))}"
    )


def test_b6_6_public_runtime_entries_remain():
    bindings = _facade_bindings()
    assert RETAINED <= set(bindings)
    assert bindings["submit_update_intent"] == "_phase6_submit_update_intent"
    assert bindings["set_3d_preview_enabled"] == "_phase6_set_3d_preview_enabled"


def test_b6_6_direct_module_owner_peel_removes_stale_bridge_wrappers():
    for name in (
        "_phase6_render_endcap_edge_controls",
        "_phase6_commit_base_plate_edge_shrink",
    ):
        assert callable(getattr(bridge, name)), name

    for name in (
        "_phase6_apply_settings_delta",
        "_phase6_switch_active_part",
        "_phase6_publish_if_changed",
        "_phase6_flush_update_intents",
        "_phase6_refresh_3d_preview",
    ):
        assert not hasattr(bridge, name), name

def test_b6_6_legacy_class_orchestration_surface_is_reduced():
    cls = bridge.Phase6FoldDesignerApp
    assert hasattr(cls, "submit_update_intent")
    assert hasattr(cls, "set_3d_preview_enabled")
    for name in (
        "apply_settings_delta",
        "switch_active_part",
        "publish_if_changed",
        "_phase6_flush_update_intents",
        "refresh_3d_preview",
        "_phase6_render_endcap_edge_controls",
        "_phase6_commit_base_plate_edge_shrink",
    ):
        assert not hasattr(cls, name), f"B6-6 RED: stale class facade remains: {name}"


def test_b6_6_facade_count_ratchets_by_seven():
    assert len(_facade_bindings()) <= 45
