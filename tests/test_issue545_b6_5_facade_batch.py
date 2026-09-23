from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")

RETAINED = {
    "reset_initial_values",
    "save_project_file",
    "save_project_file_as",
    "load_project_file",
}

REMOVED = {
    "toggle_corner_parameter_lock",
    "_render_settings_context",
    "on_baseline_model_changed",
    "confirm_corner_transaction",
    "cancel_corner_transaction",
    "export_workspace_state_if_dirty",
    "save_diagnostic_file",
    "_phase6_on_endcap_edge_relation_selected",
}

TEST_ONLY_INSTANCE_PATTERNS = {
    "toggle_corner_parameter_lock": ".toggle_corner_parameter_lock(",
    "_render_settings_context": "._render_settings_context(",
    "on_baseline_model_changed": ".on_baseline_model_changed(",
    "confirm_corner_transaction": ".confirm_corner_transaction(",
    "cancel_corner_transaction": ".cancel_corner_transaction(",
    "export_workspace_state_if_dirty": ".export_workspace_state_if_dirty(",
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


def _all_test_source() -> str:
    chunks = []
    for path in sorted(Path("tests").rglob("test_*.py")):
        if path.name == "test_issue545_b6_5_facade_batch.py":
            continue
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def test_b6_5_removable_entries_leave_facade():
    bindings = _facade_bindings()
    assert REMOVED.isdisjoint(bindings), (
        "B6-5 RED: removable facade entries remain: "
        f"{sorted(REMOVED & set(bindings))}"
    )


def test_b6_5_test_only_callers_use_direct_module_owner():
    source = _all_test_source()
    stale = [
        key
        for key, pattern in TEST_ONLY_INSTANCE_PATTERNS.items()
        if pattern in source
    ]
    assert not stale, f"B6-5 RED: test-only instance callers remain: {stale}"

    for pattern in (
        "designer._phase6_on_endcap_edge_relation_selected(",
        "app._phase6_on_endcap_edge_relation_selected(",
        "loaded._phase6_on_endcap_edge_relation_selected(",
    ):
        assert pattern not in source, (
            "B6-5 RED: endcap relation test-only facade caller not migrated: "
            + pattern
        )

    required_module_calls = (
        "bridge._phase6_toggle_corner_parameter_lock(",
        "bridge._phase6_render_settings_context(",
        "bridge._phase6_on_baseline_model_changed(",
        "bridge._phase6_confirm_corner_transaction(",
        "bridge._phase6_cancel_corner_transaction(",
        "bridge._phase6_export_workspace_state_if_dirty(",
        "bridge._phase6_on_endcap_edge_relation_selected(",
    )
    for call in required_module_calls:
        assert call in source, f"B6-5 RED: direct module owner call missing: {call}"


def test_b6_5_live_public_entries_remain():
    bindings = _facade_bindings()
    missing = RETAINED - set(bindings)
    assert not missing
    assert bindings["reset_initial_values"] == "_phase6_reset_initial_values"
    assert bindings["save_project_file"] == "_phase6_save_project_file"
    assert bindings["save_project_file_as"] == "_phase6_save_project_file_as"
    assert bindings["load_project_file"] == "_phase6_load_project_file"


def test_b6_5_facade_count_ratchets_by_eight():
    assert len(_facade_bindings()) <= 52
