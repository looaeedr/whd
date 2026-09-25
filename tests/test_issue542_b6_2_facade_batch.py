from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")

RETAINED = {
    "_save_current_part",
    "_load_part_holes",
    "activate_part",
    "show_home",
    "on_3d_scroll",
    "add_part",
    "select_part",
    "remove_selected_part",
    "remove_part",
    "available_parts",
    "active_part_key",
}

NO_CALLER = {"activate_selected_part"}


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


def test_b6_2_zero_caller_activate_selected_part_leaves_facade():
    bindings = _facade_bindings()
    assert NO_CALLER.isdisjoint(bindings), (
        "B6-2 RED: zero-caller facade entry must be removed: "
        f"{sorted(NO_CALLER & set(bindings))}"
    )


def test_b6_2_evidence_backed_entries_remain():
    bindings = _facade_bindings()
    missing = RETAINED - set(bindings)
    assert not missing
    assert bindings["_save_current_part"] == "_fix11_save_current_part"
    assert bindings["_load_part_holes"] == "_fix11_load_part_holes"
    assert bindings["activate_part"] == "_fix11_activate_part"
    assert bindings["available_parts"].startswith("property(")
    assert bindings["active_part_key"].startswith("property(")


def test_b6_2_facade_count_ratchets_by_one():
    assert len(_facade_bindings()) <= 64
