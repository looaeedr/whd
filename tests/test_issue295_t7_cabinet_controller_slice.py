from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "application" / "cabinet_controller.py"

CABINET_METHODS = (
    "_inherit_known_corner_state_into_custom",
    "_capture_cabinet_family_runtime",
    "_restore_cabinet_family_runtime",
    "_apply_cabinet_family_for_current_model",
    "on_baseline_changed",
    "get_float_values",
    "_active_indicator_box_groups_for_results",
    "_has_any_indicator_box",
    "_clear_indicator_box_result_values",
    "_refresh_indicator_box_result_values",
)


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


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


def test_cabinet_controller_owner_exists_and_root_is_thin():
    assert OWNER.is_file()
    text = OWNER.read_text(encoding="utf-8")
    for name in CABINET_METHODS:
        assert f"def {name.lstrip('_')}(" in text or f"def {name}(" in text

    methods = _host_methods()
    thick = {name: _loc(methods[name]) for name in CABINET_METHODS if name in methods and _loc(methods[name]) > 5}
    assert not thick, f"cabinet controller implementation still owned by gui.py: {thick}"


def test_get_float_values_contract():
    import gui

    host = object.__new__(gui.Phase6ApplicationHost)
    values = {
        "w_var": "800",
        "h_var": "1600",
        "d_var": "350",
        "fw_z_var": "29",
        "t_var": "2",
        "zl1_var": "20",
        "zl2_var": "25",
        "zr1_var": "20",
        "zr2_var": "25",
        "z_comp_var": "78",
        "yl1_var": "18",
        "yr1_var": "29",
        "ytop1_var": "106",
        "ybottom1_var": "17",
        "door_gap_w_var": "3",
        "door_gap_h_var": "3",
        "door_fold_l_var": "19",
        "door_fold_r_var": "15",
        "door_fold_t_var": "15",
        "door_fold_b_var": "15",
        "base_plate_shrink_top_var": "10",
        "base_plate_shrink_bottom_var": "10",
        "base_plate_shrink_left_var": "10",
        "base_plate_shrink_right_var": "10",
        "base_plate_bend_var": "20",
    }
    for attr, value in values.items():
        setattr(host, attr, Var(value))

    result = host.get_float_values()
    assert result["w"] == 800.0
    assert result["h"] == 1600.0
    assert result["d"] == 350.0
    assert result["fw"] == 29.0
    assert result["base_plate_bend"] == 20.0

    host.w_var = Var("bad")
    with pytest.raises(ValueError, match="請輸入有效的數字格式"):
        host.get_float_values()


def test_single_door_indicator_groups_contract():
    import gui

    host = object.__new__(gui.Phase6ApplicationHost)
    host.multi_door_enabled_var = Var(False)
    host.is_indicator_box_var = Var(True)
    host.indicator_l_var = Var("3")
    host.indicator_layer_g_vars = [Var("2"), Var("3"), Var("4"), Var("5"), Var("6"), Var("7")]

    assert host._active_indicator_box_groups_for_results() == (2, 3, 4)
    assert host._has_any_indicator_box() is True

    host.is_indicator_box_var.set(False)
    assert host._active_indicator_box_groups_for_results() is None
    assert host._has_any_indicator_box() is False


def test_cabinet_controller_has_no_authority_construction():
    if not OWNER.is_file():
        pytest.skip("RED: cabinet controller owner not created yet")
    text = OWNER.read_text(encoding="utf-8")
    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "SettingsService(" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
    assert "PROJECT_SCHEMA =" not in text
