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


@pytest.mark.parametrize("bad", ([0], [-1], ["corrupt"], [True], [2.5], [], ["2.5"]))
def test_invalid_enabled_indicator_groups_rejected_not_replaced(bad):
    data = snapshot()
    original = deepcopy(data)
    with pytest.raises(ValueError, match="指示燈"):
        api.project_fold_designer_snapshot_dimensions(data, bad)
    assert data == original


def test_gui_bad_enabled_box_is_rejected_without_partial_snapshot():
    data = snapshot()
    host = _controls(["corrupt"])
    before = deepcopy(data)
    with pytest.raises(ValueError, match="指示燈"):
        gui._snapshot_part_dimensions(host, data)
    assert data == before


def test_gui_disabled_box_controls_may_keep_display_only_one_layer():
    data = snapshot()
    host = _controls(["invalid"])
    host.is_indicator_box_var = SimpleNamespace(get=lambda: False)
    assert gui._snapshot_part_dimensions(host, data)["indicator_layer_groups"] == [1]
    assert data["door_indicator_box_enabled"] is False


def test_gui_bad_enabled_direct_indicator_fails_before_any_snapshot_commit():
    data = snapshot()
    host = _controls([2])
    host.is_door_indicator_var = SimpleNamespace(get=lambda: True)
    host.door_indicator_l_var = SimpleNamespace(get=lambda: 2)
    host.door_indicator_layer_g_vars = [SimpleNamespace(get=lambda: 3)]
    original = deepcopy(data)
    with pytest.raises(ValueError, match="門板指示燈"):
        gui._snapshot_part_dimensions(host, data)
    assert data == original


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_unphysical_door_or_baseplate_outside_sizes_do_not_become_one_mm(model):
    data = snapshot(model)
    for key, invalid in (("w", -800), ("h", float("nan")), ("t", True)):
        damaged = {**data, key: invalid}
        with pytest.raises(ValueError, match="物理尺寸"):
            api.project_fold_designer_snapshot_dimensions(damaged, [2])
    if model == "金庫型":
        data.update(base_plate_shrink_left=450., base_plate_shrink_right=450.)
        with pytest.raises(ValueError, match="底板成品寬"):
            api.project_fold_designer_snapshot_dimensions(data, [2])


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
