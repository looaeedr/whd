"""#2517: original Engine Door 2D physical part dimensions use saved source gate.

Settings/GUI, confirmed Receiving and Vault BasePlate must never disagree on
serialized multi-door enable or cast boolean cell widths to manufactured 1 mm.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
import fold_designer_bridge as gui
import phase6_project_file as project


def _snapshot(model):
    return {
        "model": model,
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
        "fw": 29.0 if model == "受電箱" else 25.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "part_dimensions": {},
    }


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("disabled", (False, "false", " FALSE ", "off", "0", 0))
def test_saved_disabled_mode_never_fabricates_physical_door_cell_dimensions(
    model, disabled,
):
    source = _snapshot(model)
    source["multi_door_enabled"] = disabled
    before = deepcopy(source)
    assert api.door_part_projections(source) == ()
    assert gui._phase6_door_part_projections(source) == ()
    projected = api.project_part_dimensions(source)
    assert "door" in projected
    assert not any(key.startswith("door_c") or key.startswith("base_plate_c")
                   for key in projected)
    assert source == before


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("enabled", (True, "true", " TRUE ", "on", "1", 1))
def test_saved_enabled_mode_uses_same_engine_door_and_base_plate_identity(
    model, enabled,
):
    source = _snapshot(model)
    source["multi_door_enabled"] = enabled
    before = deepcopy(source)
    actual = api.door_part_projections(source)
    expected = api.door_part_projections(_snapshot(model))
    assert actual == expected
    assert gui._phase6_door_part_projections(source) == actual
    assert [item.part_key for item in actual] == ["door_c1_r1", "door_c1_r2"]
    dimensions = api.project_part_dimensions(source)
    assert dimensions["door_c1_r1"]["width"] == pytest.approx(actual[0].formed_width)
    assert dimensions["door_c1_r2"]["height"] == pytest.approx(actual[1].formed_height)
    if model == "金庫型":
        assert "base_plate_c1_r1" in dimensions
        assert "base_plate_c1_r2" in dimensions
    assert source == before


@pytest.mark.parametrize("raw", (None, "perhaps", 2, -1, 0.3, {}, []))
def test_bad_saved_multidoor_mode_refuses_part_dimension_projection(raw):
    source = _snapshot("金庫型")
    source["multi_door_enabled"] = raw
    before = repr(source)
    with pytest.raises(ValueError, match="設定的布林值"):
        api.door_part_projections(source)
    with pytest.raises(ValueError, match="設定的布林值"):
        api.project_part_dimensions(source)
    assert repr(source) == before


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("invalid_grid", (
    [[True, [1100.0, 500.0]]],
    [[800.0, [False, 500.0]]],
    [[800.0, [0, 500.0]]],
    [[800.0, [float("nan"), 500.0]]],
    [[800.0, [1100.0, float("inf")]]],
    [[800.0, []]],
    "800:1100,500",
    False,
))
def test_enabled_mode_rejects_raw_invalid_cell_source_before_dimensions(
    model, invalid_grid,
):
    source = _snapshot(model)
    source["door_layout_columns"] = invalid_grid
    before = repr(source)
    with pytest.raises((ValueError, TypeError)):
        api.door_part_projections(source)
    with pytest.raises((ValueError, TypeError)):
        api.project_part_dimensions(source)
    assert repr(source) == before


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_reloaded_true_door_cells_match_gui_2d_and_real_engine_dxf(
    tmp_path, model,
):
    source = _snapshot(model)
    source["multi_door_enabled"] = "true"
    before = deepcopy(source)
    project_path = project.write_project(
        tmp_path / ("saved-door-" + model + ".p6fold"),
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    reopened = project.read_project(project_path)["snapshot"]
    assert reopened["multi_door_enabled"] == "true"
    cells = api.door_part_projections(reopened)
    assert len(cells) == 2
    assert cells == gui._phase6_door_part_projections(reopened)
    root = Path(__file__).resolve().parents[1]
    context = ManufacturingContext(resource_root=root)
    first = cells[0]
    spec = api.build_door_operator_part_spec(
        {
            "w": first.start_width, "h": first.start_height,
            "t": reopened["t"], "fw": reopened["fw"],
            "door_gap_w": reopened["door_gap_w"],
            "door_gap_h": reopened["door_gap_h"],
            "door_fold_l": 10.0, "door_fold_r": 10.0,
            "door_fold_t": 10.0, "door_fold_b": 10.0,
        },
        model_name=model, frame_edges=first.frame_edges,
    )
    assert api.door_finished_face_size(spec, context) == pytest.approx(
        (first.formed_width, first.formed_height),
    )
    render = api.build_part_render_data(spec, context)
    assert render.material is not None and render.material.area > 0
    target = tmp_path / ("door-" + model + ".dxf")
    api.save_part_render_data_dxf(render, target, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(render, target).ok
    layers = {
        entity.dxf.layer for entity in ezdxf.readfile(target).modelspace()
    }
    assert {"CUTTING", "BEND"} <= layers
    assert source == before
