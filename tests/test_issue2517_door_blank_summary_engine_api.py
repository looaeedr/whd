"""#2517 main Door summary is a real public headless Engine API client."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import ae, manufacturing_api, project_operator_door_blank_dimensions
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
from gui_modules.application.calculation_controller import update_calculations

GUI = Path(__file__).resolve().parents[1] / "gui_modules/application/calculation_controller.py"


def _values():
    return dict(w=800.0, h=1600.0, t=2.0, fw=25.0,
                door_gap_w=3.5, door_gap_h=4.0,
                door_fold_l=15.0, door_fold_r=17.0,
                door_fold_t=12.0, door_fold_b=14.0,
                base_plate_shrink_top=55.0, base_plate_shrink_bottom=55.0,
                base_plate_shrink_left=55.0, base_plate_shrink_right=55.0,
                base_plate_bend=15.0)


def test_public_door_summary_same_as_canonical_ae_blank_and_no_mutation():
    values = _values()
    original = deepcopy(values)
    expected = ae.calculate_door_blank_size(
        800.0, 1600.0, 2.0, 25.0, 3.5, 4.0, 15.0, 17.0, 12.0, 14.0)
    assert manufacturing_api.project_operator_door_blank_dimensions is project_operator_door_blank_dimensions
    assert project_operator_door_blank_dimensions(
        values, material_frame_width=25.0) == pytest.approx(expected)
    assert values == original


def test_multidoor_cell_uses_exact_selected_edges_not_whole_cabinet():
    values = _values()
    edges = DoorFrameEdges(left=True, right=False, top=False, bottom=True)
    expected = ae.calculate_door_blank_size(
        420.0, 600.0, 2.0, 25.0, 3.5, 4.0, 15.0, 17.0, 12.0, 14.0,
        frame_edges=edges)
    assert project_operator_door_blank_dimensions(
        values, material_frame_width=25.0,
        baseline_model="金庫型",
        selected_cell_size=(420.0, 600.0),
        frame_edges=edges,
    ) == pytest.approx(expected)


def test_baseline_success_then_legacy_display_fallback(monkeypatch):
    values = _values()
    called = []
    def stretched(model, *args):
        called.append((model, args))
        return SimpleNamespace(params={"total_width": 701.0, "total_depth": 1450.0})
    monkeypatch.setattr(ae, "get_stretched_door_data", stretched)
    assert project_operator_door_blank_dimensions(
        values, material_frame_width=25, baseline_model="金庫型",
    ) == (701.0, 1450.0)
    assert called and called[0][0] == "金庫型"
    def source_unavailable(*args):
        raise FileNotFoundError("source")
    monkeypatch.setattr(ae, "get_stretched_door_data", source_unavailable)
    assert project_operator_door_blank_dimensions(
        values, material_frame_width=25, baseline_model="金庫型",
    ) == ae.calculate_door_blank_size(
        800.0, 1600.0, 2.0, 25, 3.5, 4.0, 15.0, 17.0, 12.0, 14.0)


@pytest.mark.parametrize("bad", [(500,), "500,600", ()])
def test_invalid_cell_size_fails_closed(bad):
    with pytest.raises(ValueError, match="DOOR_CELL_OPERATOR_SIZE_INVALID"):
        project_operator_door_blank_dimensions(
            _values(), material_frame_width=25,
            selected_cell_size=bad)


class _Var:
    def __init__(self):
        self.value = None
    def set(self, value):
        self.value = value


class _Host:
    def __init__(self, *, door=True, multi=False):
        self.values = _values()
        self.parts = {"door"} if door else set()
        self.multi_door_enabled_var = SimpleNamespace(get=lambda: multi)
        self.workspace_controller = SimpleNamespace(part_profiles_snapshot=lambda: {})
        self.draws = 0
        for key in ("z", "z_h", "y_w", "y_d", "door_w", "door_h",
                    "base_plate_w", "base_plate_h", "ib_w", "ib_h",
                    "ib_door_w", "ib_door_h"):
            setattr(self, "result_" + key + "_var", _Var())
    def get_float_values(self):
        return self.values
    def _box_body_part_spec(self, val):
        return "box"
    def _authoritative_render_data(self, *args):
        return SimpleNamespace(material=SimpleNamespace(bounds=(0, 0, 300, 500)))
    def _manufacturing_context(self, **kwargs):
        return None
    def _baseline_source_model(self):
        return "金庫型"
    def _phase6_current_existing_parts(self):
        return self.parts
    def _phase6_logical_part_present(self, parts, part):
        return part in parts
    def _door_material_frame_width(self, fw, t):
        return fw
    def get_selected_door_layout_cell(self):
        return SimpleNamespace(start_width=420.0, start_height=600.0,
                               edges=DoorFrameEdges(left=False, right=True))
    def _clear_indicator_box_result_values(self):
        pass
    def _phase6_refresh_presence_ui(self, parts):
        pass
    def draw_preview(self):
        self.draws += 1


@pytest.mark.parametrize("multi", [False, True])
def test_gui_uses_only_public_door_projection_for_single_and_selected_cell(monkeypatch, multi):
    seen = []
    def fake(*args, **kwargs):
        seen.append((args, kwargs))
        return 703.0, 1402.0
    monkeypatch.setattr(manufacturing_api, "project_operator_door_blank_dimensions", fake)
    host = _Host(multi=multi)
    update_calculations(host)
    assert len(seen) == 1
    assert seen[0][0][0] is host.values
    assert seen[0][1]["baseline_model"] == "金庫型"
    assert seen[0][1]["selected_cell_size"] == ((420.0, 600.0) if multi else None)
    assert host.result_door_w_var.value == "703.00 mm"
    assert host.result_door_h_var.value == "1402.00 mm"
    assert host.draws == 1
    src = GUI.read_text(encoding="utf-8")
    assert "ae.calculate_door_blank_size(" not in src
    assert "ae.get_stretched_door_data(" not in src


def test_no_door_does_not_invoke_projection(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("door is absent")
    monkeypatch.setattr(manufacturing_api, "project_operator_door_blank_dimensions", fail)
    host = _Host(door=False)
    update_calculations(host)
    assert host.result_door_w_var.value == "-"
    assert host.result_door_h_var.value == "-"
