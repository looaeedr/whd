"""#2517: IndicatorBox physical MARKING row is one Engine source for DXF/GUI."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api, ae
from ae_engine.sheetmetal_drawing import CirclePrimitive
from gui_modules.application import cabinet_controller


@pytest.mark.parametrize("groups", [
    (1,), (2,), (3,), (4,), (5,), (6,), (2, 4), (1, 3, 2),
])
def test_engine_public_marking_positions_match_actual_source_scene(groups):
    plan = manufacturing_api.project_indicator_box_marking_layout(groups)
    source = ae.get_indicator_box_data(groups, 2.0)
    circles = [
        primitive for primitive in source.scene.primitives
        if isinstance(primitive, CirclePrimitive)
        and primitive.layer == "MARKING" and primitive.radius == 2.0
    ]
    actual = sorted((round(c.center.x, 6), round(c.center.y, 6)) for c in circles)
    expected = sorted(
        (round(x, 6), round(plan.first_row_y + 280.0 * (len(groups) - 1 - layer), 6))
        for layer in range(len(groups))
        for x in plan.positions_x
    )
    assert actual == expected
    assert plan.count == len(plan.positions_x)
    assert plan.positions_x[0] == plan.start_x
    assert plan.group_max == max(groups)
    with pytest.raises(FrozenInstanceError):
        plan.count = 100


@pytest.mark.parametrize("invalid", [(), (0,), (True,), ("bad",), "2", (2.25,)])
def test_marking_projection_rejects_unknown_physical_groups(invalid):
    with pytest.raises(ValueError):
        manufacturing_api.project_indicator_box_marking_layout(invalid)


def test_main_gui_display_uses_engine_marking_projection(monkeypatch):
    class Var:
        def __init__(self):
            self.value = None

        def set(self, value):
            self.value = value

    names = (
        "result_ib_w_var", "result_ib_h_var", "result_ib_door_w_var",
        "result_ib_door_h_var", "indicator_g_var", "ib_hole_start_x_var",
        "ib_hole_pitch_var", "ib_hole_count_var", "ib_hole_y_var",
    )
    vars_by_name = {name: Var() for name in names}
    host = SimpleNamespace(
        _clear_indicator_box_result_values=lambda: None,
        _active_indicator_box_groups_for_results=lambda: (3, 2),
        **vars_by_name,
    )
    requested = []
    result = SimpleNamespace(
        group_max=3, count=2, start_x=123.0, pitch=80.0,
        first_row_y=456.0,
    )

    def project(groups):
        requested.append(tuple(groups))
        return result

    monkeypatch.setattr(manufacturing_api, "project_indicator_box_marking_layout", project)
    cabinet_controller._refresh_indicator_box_result_values(host, {"t": 2.0})
    assert requested == [(3, 2)]
    assert vars_by_name["indicator_g_var"].value == "3"
    assert vars_by_name["ib_hole_start_x_var"].value == "123"
    assert vars_by_name["ib_hole_pitch_var"].value == "80"
    assert vars_by_name["ib_hole_count_var"].value == "2"
    assert vars_by_name["ib_hole_y_var"].value == "456"
    assert vars_by_name["result_ib_w_var"].value.endswith(" mm")


def test_gui_has_no_independent_indicator_marking_formula():
    gui = inspect.getsource(cabinet_controller._refresh_indicator_box_result_values)
    engine = inspect.getsource(ae.get_indicator_box_data)
    assert "manufacturing_api.project_indicator_box_marking_layout(" in gui
    assert "project_indicator_box_marking_layout(groups)" in engine
    for forbidden in ("x_left_light", "x_right_light", "max_pitch", "hp = 150.0", "hc = 1"):
        assert forbidden not in gui
