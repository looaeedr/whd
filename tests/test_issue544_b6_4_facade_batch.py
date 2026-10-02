from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")
CORNER_TEST = Path("tests/test_corner_parameter_lock.py")

RETAINED = {
    "save_current_settings_as_defaults",
    "flush_pending_settings",
    "_phase6_publish_live_state",
    "_phase6_resolve_manufacturing_geometry",
    "apply_external_settings",
    "apply_external_model",
    "apply_external_sync",
    "_phase6_refresh_corner_data_unfold_view",
    "on_ui_text_size_changed",
    "apply_external_corner_state",
}

REMOVED = {
    "toggle_advanced_settings",
    "_phase6_corner_parameters_unlocked",
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


def test_b6_4_no_caller_and_direct_owner_entries_leave_facade():
    bindings = _facade_bindings()
    assert REMOVED.isdisjoint(bindings), (
        "B6-4 RED: removable facade entries remain: "
        f"{sorted(REMOVED & set(bindings))}"
    )


def test_b6_4_corner_parameter_tests_use_direct_module_owner():
    source = CORNER_TEST.read_text(encoding="utf-8")
    assert "designer._phase6_corner_parameters_unlocked(" not in source, (
        "B6-4 RED: test-only facade caller not migrated to module owner"
    )
    assert "loaded._phase6_corner_parameters_unlocked(" not in source, (
        "B6-4 RED: loaded-designer test-only facade caller not migrated"
    )
    assert "bridge._phase6_corner_parameters_unlocked(" in source


def test_b6_4_evidence_backed_entries_remain():
    bindings = _facade_bindings()
    missing = RETAINED - set(bindings)
    assert not missing
    assert bindings["save_current_settings_as_defaults"] == "_phase6_save_current_settings_as_defaults"
    assert bindings["flush_pending_settings"] == "_phase6_flush_pending_settings"
    assert bindings["_phase6_publish_live_state"] == "_phase6_publish_live_state"
    assert bindings["_phase6_resolve_manufacturing_geometry"] == "_phase6_resolve_manufacturing_geometry"
    assert bindings["apply_external_settings"] == "_phase6_apply_external_settings"
    assert bindings["apply_external_model"] == "_phase6_apply_external_model"
    assert bindings["apply_external_sync"] == "_phase6_apply_external_sync"
    assert bindings["_phase6_refresh_corner_data_unfold_view"] == "_phase6_refresh_corner_data_unfold_view"
    assert bindings["on_ui_text_size_changed"] == "_phase6_on_ui_text_size_changed"
    assert bindings["apply_external_corner_state"] == "_phase6_apply_external_corner_state"


def test_b6_4_facade_count_ratchets_by_two():
    assert len(_facade_bindings()) <= 60
