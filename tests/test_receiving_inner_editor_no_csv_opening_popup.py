# -*- coding: utf-8 -*-
"""Regression: Receiving inner door uses the original Hole Editor directly.

The user removed the separate CSV world-X/opening verification workflow.
Selecting NFB metadata does not silently commit. The Receiving tab's own
Confirm stages user-selected CSV holes in the original editor, without
a duplicate verification popup. Only Confirm All can persist the result.
"""
import ast
from pathlib import Path

from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_numeric_catalog import model_spec

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "gui_modules/application/fold_designer_composition_receiving.py"


def _ui_source():
    return SOURCE.read_text(encoding="utf-8")


def _inner_editor_functions():
    tree = ast.parse(_ui_source())
    editor = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "inner_edit"
    )
    return {
        node.name: node for node in editor.body
        if isinstance(node, ast.FunctionDef)
    }


def test_csv_opening_world_x_button_and_popup_are_completely_removed():
    source = _ui_source()
    assert "CSV 開口位置" not in source
    assert "檢查 CSV 開口" not in source
    assert "NFB CSV 內門開口／底板孔位核對" not in source
    assert "尚未驗證 NFB CSV 內門主孔" not in source
    assert "open_nfb_world_x_dialog" not in source
    assert "_receiving_csv_door_proof" not in source
    assert "csv_openings_to_editor_features" not in source
    assert "verified_nfb_openings_to_editor_features" not in source
    assert "stage_csv_openings" not in source


def test_receiving_confirm_stages_csv_holes_only_in_original_editor_transaction():
    functions = _inner_editor_functions()
    confirm = functions["confirm"]
    calls = [
        n.func.id for n in ast.walk(confirm)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    ]
    assert "stage_in_editor" in calls
    assert "editor_nfb_features_from_csv" in calls
    assert "stage_in_editor(config, openings)" in _ui_source()
    assert "after_saved" in calls
    assert "close_editor" in calls
    assert "csv_openings_to_editor_features" not in calls
    assert "verified_nfb_openings_to_editor_features" not in calls
    # Basic independent source-model identity is still checked, not a hole
    # geometry proof or new mandatory world-X form.
    assert "model_spec" in calls
    assert "current_numeric_editor" in ast.unparse(confirm)
    source = _ui_source()
    assert 'ttk.Button(buttons, text="確認", command=confirm)' in source
    assert 'ttk.Button(buttons, text="取消"' in source


def test_original_inner_door_manual_hole_editor_remains_in_place():
    source = (ROOT / "gui_modules/application/receiving_inner_door_hole_editor.py").read_text(
        encoding="utf-8"
    )
    assert "def open_inner_door_hole_editor(" in source
    assert "host._open_unified_hole_editor(" in source
    assert "on_confirm_features" in source
    assert "feature_list_override=features" in source
    assert "inner-door" in source.lower().replace("_", "-")


def test_current_csv_catalog_still_supplies_model_and_opening_dimensions():
    # Removing a second POPUP must not delete the source CSV itself.
    ref = numeric_model_ref("士林", "2P400")
    assert ref == "nfbv5:士林:2P400"
    spec = model_spec("士林", "2P400")
    assert spec is not None
    assert spec.opening_mm == (57.0, 96.0)
    assert spec.screw_pitch_mm == (44.0, 194.0)
