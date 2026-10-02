from __future__ import annotations

import ast
from pathlib import Path


BRIDGE = Path("fold_designer_bridge.py")

RETAINED = {
    "__getattr__",
    "_phase6_last_cutting_mesh",
    "_phase6_last_cutting_material",
    "_phase6_zoom_scale",
    "__init__",
    "_refresh_part_buttons",
    "_refresh_part_button_states",
    "_refresh_add_part_menu",
}

NO_CALLER = {
    "_phase6_cutting_mesh_error",
    "_phase6_view_initialized",
    "_phase6_base_renderer_render",
    "_phase6_scroll_cid",
}


def _facade_bindings() -> dict[str, str]:
    source = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BRIDGE))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "install_fold_designer_bridge_facade"
    ]
    assert len(calls) == 1
    mapping = next(arg for arg in calls[0].args if isinstance(arg, ast.Dict))
    result = {}
    for key, value in zip(mapping.keys, mapping.values):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        result[key.value] = ast.unparse(value)
    return result


def test_b6_1_no_caller_private_view_properties_leave_facade():
    bindings = _facade_bindings()
    assert NO_CALLER.isdisjoint(bindings), (
        "B6-1 RED: zero-caller private view facade entries must be removed: "
        f"{sorted(NO_CALLER & set(bindings))}"
    )


def test_b6_1_evidence_backed_compatibility_entries_remain():
    bindings = _facade_bindings()
    missing = RETAINED - set(bindings)
    assert not missing
    assert bindings["__getattr__"] == "_phase6_legacy_getattr"
    assert bindings["__init__"] == "_fix11_init"
    assert bindings["_refresh_part_buttons"] == "_fix11_refresh_part_buttons"
    assert bindings["_refresh_part_button_states"] == "_fix11_refresh_part_button_states"
    assert bindings["_refresh_add_part_menu"] == "_fix11_refresh_add_part_menu"


def test_b6_1_facade_count_ratchets_by_four():
    assert len(_facade_bindings()) <= 65
