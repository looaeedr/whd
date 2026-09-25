from __future__ import annotations

import ast
from pathlib import Path

import fold_designer_bridge as bridge
import phase6_assembly_presentation as assembly_presentation
import phase6_manufacturing_adapter as manufacturing_adapter
import phase6_part_navigation as part_navigation


BRIDGE = Path("fold_designer_bridge.py")


def _facade_bindings() -> dict[str, str]:
    source = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BRIDGE))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "install_fold_designer_bridge_facade")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "install_fold_designer_bridge_facade")
        )
    ]
    assert len(calls) == 1
    mapping = next(arg for arg in calls[0].args if isinstance(arg, ast.Dict))
    result = {}
    for key, value in zip(mapping.keys, mapping.values):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        result[key.value] = ast.unparse(value)
    return result


def test_a3_direct_owner_delegates_are_identity_aliases():
    assert bridge._phase6_resolve_manufacturing_geometry is manufacturing_adapter.resolve_for_app
    assert (
        bridge._phase6_is_box_body_physical_piece_key
        is part_navigation.is_box_body_physical_piece_key
    )
    assert (
        bridge._phase6_operator_part_selector_keys
        is part_navigation.operator_part_selector_keys
    )
    assert bridge._phase6_box_body_piece_keys is part_navigation.box_body_piece_keys
    assert (
        bridge._phase6_assembly_presentation_groups
        is assembly_presentation.legacy_assembly_presentation_groups
    )


def test_a3_dynamic_getattr_protocol_is_retained_not_misclassified_no_caller():
    bindings = _facade_bindings()
    assert "__getattr__" in bindings
    assert bindings["__getattr__"] == "_phase6_legacy_getattr"
    assert bridge.Phase6FoldDesignerApp.__getattr__ is bridge._phase6_legacy_getattr


def test_a3_facade_does_not_grow():
    assert len(_facade_bindings()) <= 69
