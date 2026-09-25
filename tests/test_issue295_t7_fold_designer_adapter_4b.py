from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"


def _host():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )


def _root_method(name):
    return next(
        (
            node for node in _host().body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ),
        None,
    )


def test_fold_designer_part_spec_owner_moves_to_adapter_and_stays_under_150():
    assert OWNER.is_file()
    tree = ast.parse(OWNER.read_text(encoding="utf-8"))
    fn = next(
        (
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_fold_designer_part_spec_from_payload"
        ),
        None,
    )
    assert fn is not None, "4B owner function missing from fold_designer_adapter.py"
    assert fn.end_lineno - fn.lineno + 1 <= 150

    root = _root_method("_fold_designer_part_spec_from_payload")
    if root is not None:
        assert root.end_lineno - root.lineno + 1 <= 5
    else:
        assert "_fold_designer_part_spec_from_payload = _phase6_fold_adapter._fold_designer_part_spec_from_payload" in GUI.read_text(encoding="utf-8")


def test_indicator_box_payload_part_spec_contract_is_preserved():
    import gui
    from ae_engine.contracts import IndicatorBoxPartSpec, ManufacturingContext

    host = object.__new__(gui.Phase6ApplicationHost)
    spec, context = host._fold_designer_part_spec_from_payload(
        "indicator_box",
        {
            "model": "自訂",
            "t": 2.0,
            "indicator_layer_groups": [2, 3],
            "features": [],
        },
    )
    assert isinstance(spec, IndicatorBoxPartSpec)
    assert spec.layer_groups == (2, 3)
    assert spec.thickness == 2.0
    assert spec.features == ()
    assert isinstance(context, ManufacturingContext)


def test_fold_designer_part_spec_adapter_has_no_gui_or_owner_construction():
    text = OWNER.read_text(encoding="utf-8")
    assert "import gui" not in text
    assert "from gui import" not in text
    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "SettingsService(" not in text
    assert "PROJECT_SCHEMA =" not in text
