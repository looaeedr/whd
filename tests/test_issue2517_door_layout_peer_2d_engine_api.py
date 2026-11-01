"""#2517 actual multi-Door 2D peer source readback is Engine-owned."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from math import nan
from copy import deepcopy
import inspect

import pytest
from shapely.geometry import box, Polygon

from ae_engine import manufacturing_api, project_operator_door_layout_peer_cells
from ae_engine.operator_door_layout_peer_2d import DoorLayoutPeerCell
from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
from gui_modules.application.render_snapshots import door_layout_overview_snapshot


def _cells():
    return derive_door_layout_cells([(600, (800, 1000)), (500, (1800,))])


def _render(material, scene):
    return SimpleNamespace(material=material, scene=scene)


def _get(value):
    return SimpleNamespace(get=lambda: value)


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_actual_canonical_multidoor_peers_keep_physical_owner_and_scene_identity(family):
    cells = _cells()
    one, two = object(), object()
    sources = {
        "door_c1_r1": _render(box(8, 12, 108, 72), one),
        "door_c2_r1": _render(box(-23, -13, 227, 87), two),
    }
    before = deepcopy(tuple(sources))
    result = manufacturing_api.project_operator_door_layout_peer_cells(cells, sources)
    assert result == (
        DoorLayoutPeerCell(0, 0, "door_c1_r1", one, 100., 60.),
        DoorLayoutPeerCell(0, 1, "door_c1_r2"),
        DoorLayoutPeerCell(1, 0, "door_c2_r1", two, 250., 100.),
    )
    assert result[0].scene is one and result[2].scene is two
    assert result[1].present is False
    assert tuple(sources) == tuple(before)
    assert result[0].width > 0
    assert manufacturing_api.project_operator_door_layout_peer_cells is (
        project_operator_door_layout_peer_cells
    )
    with pytest.raises(FrozenInstanceError):
        result[0].part_key = "fake"


@pytest.mark.parametrize("bad", [
    True, 0, (), None, "not-a-map",
])
def test_peer_source_requires_mapping_not_fabricated_door(bad):
    if isinstance(bad, dict):
        pytest.skip("guard")
    with pytest.raises(ValueError, match="DOOR_LAYOUT_PEER_SOURCE_MAPPING_INVALID"):
        project_operator_door_layout_peer_cells(_cells(), bad)


@pytest.mark.parametrize("bounds", [
    (0, 0, nan, 8), (0, 0, -5, 8),
    (0, 0, float("inf"), 8), (0, 0, 8),
])
def test_invalid_physical_bounds_fail_closed(bounds):
    fake = SimpleNamespace(bounds=bounds, is_empty=False)
    with pytest.raises(ValueError, match="DOOR_LAYOUT_PEER_SOURCE_BOUNDS_INVALID"):
        project_operator_door_layout_peer_cells(
            _cells(), {"door_c1_r1": _render(fake, object())},
        )


def test_empty_and_incomplete_peers_remain_hidden_without_neighbor_fallback():
    cells = _cells()
    sources = {
        "door_c1_r1": _render(box(0, 0, 20, 30), None),
        "door_c1_r2": _render(Polygon(), object()),
    }
    output = project_operator_door_layout_peer_cells(cells, sources)
    assert all(not row.present for row in output)
    assert output[0].width is None and output[1].scene is None


def test_duplicate_or_invalid_grid_identity_fails_closed():
    cells = _cells()
    for altered in (
        (cells[0], cells[0]),
        (SimpleNamespace(column_index=True, row_index=0),),
        (SimpleNamespace(column_index=-1, row_index=0),),
        (SimpleNamespace(column_index=0, row_index=1.0),),
    ):
        with pytest.raises(ValueError, match="DOOR_LAYOUT_PEER_CELL_ID_INVALID"):
            project_operator_door_layout_peer_cells(altered, {})


def test_real_gui_snapshot_delegates_entire_peer_source_scan(monkeypatch):
    cells = _cells()
    scenes = { "door_c1_r1": _render(box(0, 0, 100, 200), object()) }
    spy = []
    real = manufacturing_api.project_operator_door_layout_peer_cells

    def delegated(cells_arg, sources_arg):
        spy.append((cells_arg, sources_arg))
        return real(cells_arg, sources_arg)

    monkeypatch.setattr(manufacturing_api, "project_operator_door_layout_peer_cells", delegated)
    def not_local(*args):
        raise AssertionError("GUI generated an extra uncommitted Door source")
    host = SimpleNamespace(
        w_var=_get("1100"), h_var=_get("1800"),
        get_door_layout_columns=lambda: [(600, (800, 1000)), (500, (1800,))],
        get_door_layout_cells=lambda: cells,
        get_float_values=lambda: {"t": 2.0},
        door_layout_selected_var=_get("0:0"),
        _baseline_source_model=lambda: "金庫型",
        _door_layout_cell_result=not_local,
        _door_layout_baseline_scene=not_local,
        _door_layout_cell_resolved_features=not_local,
    )
    payload = door_layout_overview_snapshot(host, scenes)
    assert spy == [(cells, scenes)]
    assert payload["error"] is None
    assert payload["cell_payloads"][(0, 0)] == {
        "mode": "peer", "scene": scenes["door_c1_r1"].scene,
        "width": 100., "height": 200.,
    }
    assert payload["cell_payloads"][(0, 1)] == {"mode": "none"}
    assert payload["cell_payloads"][(1, 0)] == {"mode": "none"}
    source = inspect.getsource(door_layout_overview_snapshot)
    assert "manufacturing_api.project_operator_door_layout_peer_cells(" in source
    assert "door_c{column_index + 1}_r{row_index + 1}" not in source
    assert "material.bounds" not in source
