from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "application" / "manufacturing_adapter.py"

METHODS = (
    "_manufacturing_context",
    "_box_body_part_spec_from_values",
    "_box_body_part_spec",
    "_end_cap_part_spec_from_values",
    "_phase6_relief_profile_signature",
    "_resolved_committed_assembly_relief_cuts",
    "_end_cap_part_spec",
    "_door_part_spec_from_values",
    "_single_door_part_spec",
    "_door_layout_part_spec",
    "_validate_indicator_state_fit",
    "_validate_single_door_indicator_fit",
    "_validate_door_layout_indicator_fit",
    "_base_plate_part_spec_from_values",
    "_base_plate_part_spec",
    "_indicator_box_part_spec_from_values",
    "_indicator_box_part_spec",
    "_indicator_door_part_spec_from_values",
    "_indicator_door_part_spec",
    "_indicator_component_editor_contexts",
)


def _host_methods():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _loc(node):
    return node.end_lineno - node.lineno + 1


def test_manufacturing_adapter_owner_exists_and_root_is_thin():
    assert OWNER.is_file()
    funcs = {
        node.name: node
        for node in ast.parse(OWNER.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in METHODS:
        assert name in funcs, f"manufacturing adapter owner missing: {name}"
        assert _loc(funcs[name]) <= 150, f"{name} exceeds 150 lines"

    methods = _host_methods()
    thick = {
        name: _loc(methods[name])
        for name in METHODS
        if name in methods and _loc(methods[name]) > 5
    }
    assert not thick, f"manufacturing implementation still owned by gui.py: {thick}"


def test_manufacturing_context_contract_is_preserved():
    import gui

    host = object.__new__(gui.Phase6ApplicationHost)
    context = host._manufacturing_context(draw_stock=True)
    assert context.draw_stock is True
    assert context.overwrite is True


def test_relief_profile_signature_is_stable_and_numeric():
    import gui

    rows = [
        {"phase6_key": "a", "len": "12.0000004", "angle": "90", "core": "x"},
        {"phase6_key": "b", "length": 3, "angle": None, "core": ""},
    ]
    sig = gui.Phase6ApplicationHost._phase6_relief_profile_signature(rows)
    assert sig == (
        ("a", 12.0, 90.0, "x"),
        ("b", 3.0, None, ""),
    )


def test_manufacturing_adapter_delegates_existing_authority_only():
    if not OWNER.is_file():
        pytest.skip("RED: manufacturing adapter owner not created yet")
    text = OWNER.read_text(encoding="utf-8")
    for token in (
        "BoxBodyPartSpec",
        "EndCapPartSpec",
        "DoorPartSpec",
        "BasePlatePartSpec",
        "IndicatorBoxPartSpec",
        "ManufacturingContext",
        "manufacturing_api",
    ):
        assert token in text

    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "SettingsService(" not in text
    assert "PROJECT_SCHEMA =" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
