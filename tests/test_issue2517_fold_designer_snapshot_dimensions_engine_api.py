"""#2517: original Fold Designer part sizes are exclusively Engine projections."""
from copy import deepcopy
from types import SimpleNamespace
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api, project_fold_designer_snapshot_dimensions
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
from gui_modules.application import fold_designer_snapshot_projection as gui


def snapshot(model="金庫型"):
    return {
        "model": model, "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
        "base_plate_shrink_left": 55.0, "base_plate_shrink_right": 55.0,
        "base_plate_shrink_top": 55.0, "base_plate_shrink_bottom": 55.0,
        "indicator_box_fold": 49.0, "indicator_door_fold": 19.0,
    }


def _controls(groups):
    def var(value):
        return SimpleNamespace(get=lambda: value)
    return SimpleNamespace(
        indicator_l_var=var(len(groups)),
        indicator_layer_g_vars=[var(v) for v in groups],
        is_door_indicator_var=var(False),
        door_indicator_offset_x=0, door_indicator_offset_y=0,
        is_indicator_box_var=var(True),
    )


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_engine_preserves_real_physical_dimensions_and_gui_parity(model):
    request = snapshot(model)
    before = deepcopy(request)
    result = project_fold_designer_snapshot_dimensions(request, [2, 3])
    assert api.project_fold_designer_snapshot_dimensions(request, [2, 3]) == result
    assert result.indicator_layer_groups == (2, 3)
    from ae_engine import ae
    material_fw = api.door_material_frame_width(
        model, frame_width=29.0, thickness=2.0,
    )
    expected_door = ae.calculate_door_finished_size(
        800.0, 1600.0, material_fw, 3.5, 3.5, 2.0,
        frame_edges=DoorFrameEdges(),
    )
    assert tuple(result.part_dimensions["door"].values()) == pytest.approx(expected_door)
    assert tuple(result.part_dimensions["indicator_box"].values()) == pytest.approx(
        api.indicator_box_unfolded_size([2, 3], thickness=2, context=ManufacturingContext())
    )
    assert result.part_dimensions["head"] == {"width": 800, "height": 350}
    assert result.part_dimensions["tail"] == {"width": 800, "height": 350}
    if model == "金庫型":
        assert result.part_dimensions["base_plate"] == {"width": 690, "height": 1490}
    else:
        from ae_engine.receiving_base_plate_config import receiving_base_plate_blank_dimensions
        physical = receiving_base_plate_blank_dimensions(request)
        if physical is not None:
            assert tuple(result.part_dimensions["base_plate"].values()) == pytest.approx(physical)
    assert request == before
    gui_request = deepcopy(request)
    assert gui._snapshot_part_dimensions(_controls([2, 3]), gui_request) is gui_request
    assert gui_request["part_dimensions"] == result.part_dimensions
    assert gui_request["indicator_layer_groups"] == [2, 3]
    assert gui_request["door_indicator_groups"] == []
    assert gui_request["door_indicator_offset"] == (0.0, 0.0)
    assert json.loads(json.dumps(gui_request))["part_dimensions"] == result.part_dimensions


def test_indicator_invalid_group_preserves_legacy_preview_fallback_and_does_not_mutate():
    data = snapshot()
    before = deepcopy(data)
    bad = api.project_fold_designer_snapshot_dimensions(data, [0])
    expected = api.project_fold_designer_snapshot_dimensions(data, [1])
    assert bad == expected
    assert bad.indicator_layer_groups == (1,)
    host = _controls(["corrupt"])
    projected = gui._snapshot_part_dimensions(host, deepcopy(data))
    assert projected["indicator_layer_groups"] == [1]
    assert projected["part_dimensions"] == expected.part_dimensions
    assert data == before


def test_multi_door_root_overview_is_not_a_second_physical_cell_authority():
    data = snapshot("受電箱")
    data.update({"multi_door_enabled": True, "door_layout_columns": [[800.0, [900.0, 700.0]]]})
    root = api.project_fold_designer_snapshot_dimensions(data, [1]).part_dimensions
    assert "door" in root
    assert "door_c1_r1" not in root
    cells = api.project_part_dimensions(data)
    assert "door" not in cells
    assert "door_c1_r1" in cells and "door_c1_r2" in cells


def test_gui_delegates_no_independent_material_calculation_or_policy(monkeypatch):
    original = api.project_fold_designer_snapshot_dimensions
    calls = []
    def forwarded(data, groups):
        calls.append((data.copy(), tuple(groups)))
        return original(data, groups)
    monkeypatch.setattr(api, "project_fold_designer_snapshot_dimensions", forwarded)
    data = snapshot()
    gui._snapshot_part_dimensions(_controls([2]), data)
    assert calls == [(snapshot(), (2,))]
    source = inspect.getsource(gui._snapshot_part_dimensions)
    assert "manufacturing_api.project_fold_designer_snapshot_dimensions(" in source
    assert "calculate_door_finished_size(" not in source
    assert "receiving_base_plate_blank_dimensions(" not in source
    assert "indicator_box_unfolded_size(" not in source
    assert "resolve_policy(" not in source
