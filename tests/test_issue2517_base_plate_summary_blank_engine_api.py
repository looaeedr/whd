"""#2517: the BasePlate summary and both geometry builders share Engine W/H."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import base_plate_blank_dimensions, manufacturing_api
from ae_engine.sheetmetal_part_adapters import build_base_plate_result
from gui_modules.application.calculation_controller import update_calculations

ROOT = Path(__file__).resolve().parents[1]
GUI_SOURCE = ROOT / "gui_modules" / "application" / "calculation_controller.py"


@pytest.mark.parametrize("args, expected", [
    (dict(w=500, h=400, shrink_top=55, shrink_bottom=55,
          shrink_left=55, shrink_right=55, bend=15), (420.0, 320.0)),
    (dict(w=800, h=1600, shrink_top=0, shrink_bottom=8,
          shrink_left=4, shrink_right=6, bend=12), (814.0, 1616.0)),
])
def test_engine_public_baseplate_blank_matches_real_structural_geometry(args, expected):
    assert manufacturing_api.base_plate_blank_dimensions is base_plate_blank_dimensions
    assert base_plate_blank_dimensions(**args) == expected
    result = build_base_plate_result(t=2, **args)
    assert (result.width, result.height) == pytest.approx(expected)
    assert result.outline and result.bends


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), None])
def test_public_baseplate_projection_rejects_invalid_physical_input(bad):
    args = dict(w=500, h=400, shrink_top=55, shrink_bottom=55,
                shrink_left=55, shrink_right=55, bend=15)
    args["shrink_left"] = bad
    with pytest.raises(ValueError):
        base_plate_blank_dimensions(**args)


class _ResultVar:
    def __init__(self):
        self.text = None
    def set(self, value):
        self.text = value


class _Host:
    def __init__(self, with_base=True):
        self.val = dict(w=500.0, h=400.0, shrink_top=55,
                        base_plate_shrink_top=55, base_plate_shrink_bottom=55,
                        base_plate_shrink_left=55, base_plate_shrink_right=55,
                        base_plate_bend=15, t=2, fw=25)
        self.with_base = with_base
        self.workspace_controller = SimpleNamespace(part_profiles_snapshot=lambda: {})
        self.multi_door_enabled_var = SimpleNamespace(get=lambda: False)
        for key in ("z", "z_h", "y_w", "y_d", "door_w", "door_h",
                    "base_plate_w", "base_plate_h", "ib_w", "ib_h",
                    "ib_door_w", "ib_door_h"):
            setattr(self, "result_" + key + "_var", _ResultVar())
        self.draws = 0
    def get_float_values(self):
        return self.val
    def _box_body_part_spec(self, values):
        return "box"
    def _authoritative_render_data(self, spec, context):
        return SimpleNamespace(material=SimpleNamespace(bounds=(0, 0, 420, 320)))
    def _manufacturing_context(self, **kwargs):
        return None
    def _baseline_source_model(self):
        return ""
    def _phase6_current_existing_parts(self):
        return {"base_plate"} if self.with_base else set()
    def _phase6_logical_part_present(self, existing, name):
        return name in existing
    def _door_material_frame_width(self, fw, t):
        return fw
    def _clear_indicator_box_result_values(self):
        pass
    def _phase6_refresh_presence_ui(self, existing):
        pass
    def draw_preview(self):
        self.draws += 1


def test_main_gui_summary_forwards_to_public_engine_and_only_formats(monkeypatch):
    calls = []
    def fake(**kwargs):
        calls.append(kwargs)
        return 420.0, 320.0
    monkeypatch.setattr(manufacturing_api, "base_plate_blank_dimensions", fake)
    host = _Host()
    update_calculations(host)
    assert len(calls) == 1
    assert calls[0]["w"] == 500.0 and calls[0]["bend"] == 15
    assert host.result_base_plate_w_var.text == "420.00 mm"
    assert host.result_base_plate_h_var.text == "320.00 mm"
    assert host.draws == 1
    source = GUI_SOURCE.read_text(encoding="utf-8")
    assert "val['w'] - val['base_plate_shrink_left']" not in source
    assert "val['h'] - val['base_plate_shrink_top']" not in source


def test_main_gui_summary_does_not_query_absent_plate(monkeypatch):
    def unexpected(**_):
        raise AssertionError("absent BasePlate must not be evaluated")
    monkeypatch.setattr(manufacturing_api, "base_plate_blank_dimensions", unexpected)
    host = _Host(with_base=False)
    update_calculations(host)
    assert host.result_base_plate_w_var.text == "-"
    assert host.result_base_plate_h_var.text == "-"
