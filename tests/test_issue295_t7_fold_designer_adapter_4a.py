from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "application" / "fold_designer_adapter.py"

SLICE_METHODS = (
    "_fold_designer_secondary_scene_rows",
    "_query_fold_designer_baseline_data",
    "_apply_cabinet_family_endcap_policy",
    "_fold_designer_corner_policy_from_payload",
    "_authoritative_render_data",
    "_require_verified_baseline_sources_for_manufacturing",
    "_export_authoritative_part",
    "_query_fold_designer_render_data",
)


def _host():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )


def _method_map():
    return {
        node.name: node
        for node in _host().body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _loc(node):
    return node.end_lineno - node.lineno + 1


def test_fold_designer_adapter_4a_owner_exists_and_root_is_thin():
    assert OWNER.is_file()
    text = OWNER.read_text(encoding="utf-8")
    for name in SLICE_METHODS:
        assert f"def {name.lstrip('_')}(" in text or f"def {name}(" in text

    methods = _method_map()
    thick = {
        name: _loc(methods[name])
        for name in SLICE_METHODS
        if name in methods and _loc(methods[name]) > 5
    }
    assert not thick, f"Fold Designer 4A implementation still owned by gui.py: {thick}"


def test_secondary_scene_rows_preserve_cutting_outline_skip_and_numeric_features():
    import gui
    from ae_engine.sheetmetal_drawing import DrawingScene

    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 80), (0, 80)], layer="CUTTING", closed=True)
    scene.add_polyline([(10, 20), (30, 20), (30, 40), (10, 40)], layer="CUTTING", closed=True)
    scene.add_circle((50, 60), 5, layer="BLIND_HOLE")
    scene.add_circle((70, 70), 3, layer="DATUM")

    rows = gui.Phase6ApplicationHost._fold_designer_secondary_scene_rows(scene)
    assert rows == [
        {"kind": "方孔", "layer": "CUTTING", "x": 20.0, "y": 30.0, "d1": 20.0, "d2": 20.0},
        {"kind": "圓孔", "layer": "BLIND_HOLE", "x": 50.0, "y": 60.0, "d1": 10.0, "d2": 0.0},
    ]


def test_corner_policy_payload_missing_required_corner_returns_none():
    import gui

    assert gui.Phase6ApplicationHost._fold_designer_corner_policy_from_payload(
        {"head": {"top_left": {"type_id": "CROSS"}}},
        "head",
        29.0,
    ) is None


def test_fold_designer_adapter_4a_has_no_new_authority():
    if not OWNER.is_file():
        pytest.skip("RED: Fold Designer adapter owner not created yet")
    text = OWNER.read_text(encoding="utf-8")
    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "SettingsService(" not in text
    assert "PROJECT_SCHEMA =" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
