from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")

RETAINED = {
    "selected_part_key",
    "_phase6_part_profiles",
    "_phase6_part_features",
    "_phase6_part_face_features",
    "_phase6_workspace_dirty",
    "_phase6_switching_part",
    "_phase6_box_body_active_piece_key",
    "apply_external_assembly_type",
    "export_phase6_snapshot",
    "toggle_baseline_data",
}

NO_CALLER = {
    "show_global_settings",
    "save_settings_context_as_defaults",
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


def test_b6_3_zero_caller_entries_leave_facade():
    bindings = _facade_bindings()
    assert NO_CALLER.isdisjoint(bindings), (
        "B6-3 RED: zero-caller facade entries must be removed: "
        f"{sorted(NO_CALLER & set(bindings))}"
    )


def test_b6_3_evidence_backed_entries_remain():
    bindings = _facade_bindings()
    missing = RETAINED - set(bindings)
    assert not missing
    assert bindings["selected_part_key"].startswith("property(")
    assert bindings["_phase6_part_profiles"].startswith("property(")
    assert bindings["_phase6_part_features"].startswith("property(")
    assert bindings["_phase6_part_face_features"].startswith("property(")
    assert bindings["_phase6_workspace_dirty"].startswith("property(")
    assert bindings["_phase6_switching_part"].startswith("property(")
    assert bindings["_phase6_box_body_active_piece_key"].startswith("property(")
    assert bindings["apply_external_assembly_type"] == "_phase6_apply_external_assembly_type"
    assert bindings["export_phase6_snapshot"] == "_fix11_export"
    assert bindings["toggle_baseline_data"] == "_phase6_settings_panel_toggle_baseline"


def test_b6_3_facade_count_ratchets_by_two():
    assert len(_facade_bindings()) <= 62
