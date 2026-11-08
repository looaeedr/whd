# -*- coding: utf-8 -*-
"""#2517: raw Door grid mapper targets may not invent physical hole identity."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.door_layout_host_adapter import (
    _remap_door_layout_owned_data,
)


def _physical_source():
    return {
        "door_layout_features": {"0:0": [{"hole": "real"}]},
    }, {"workspace": {"door_c1_r1": [{"hole": "real"}], "other": ["keep"]}}


@pytest.mark.parametrize("target", ["1:0", (1, 0), [1, 0]])
def test_engine_accepts_existing_serialized_or_raw_integer_grid_target(target):
    cells, physical = _physical_source()
    before = deepcopy((cells, physical))
    result = api.remap_receiving_door_layout_after_delete(
        operation="map_cells",
        cell_transitions={"0:0": target},
        cell_sources=cells, physical_sources=physical,
    )
    assert (cells, physical) == before
    assert result["cell_sources"]["door_layout_features"] == {
        "1:0": [{"hole": "real"}],
    }
    assert result["physical_sources"]["workspace"] == {
        "door_c2_r1": [{"hole": "real"}], "other": ["keep"],
    }


@pytest.mark.parametrize("target", [
    "invalid", "-1:0", "0:-1", "0:1.5", "0:0:1", "", 1,
    True, (True, 0), (False, 0), (1.5, 0), (-1, 0),
    (0, -1), ("1", 0), (1,), [0, 0.0], {"column": 0},
])
def test_engine_rejects_bad_target_before_any_cell_or_physical_remap(target):
    cells, physical = _physical_source()
    before = deepcopy((cells, physical))
    with pytest.raises(ValueError, match="Door cell"):
        api.remap_receiving_door_layout_after_delete(
            operation="map_cells", cell_transitions={"0:0": target},
            cell_sources=cells, physical_sources=physical,
        )
    assert (cells, physical) == before


@pytest.mark.parametrize("bad_key", ["invalid", "-1:0", "0:-1", "0:1.5", "0:0:1"])
def test_engine_rejects_corrupt_original_cell_identity(bad_key):
    cells, physical = _physical_source()
    before = deepcopy((cells, physical))
    with pytest.raises(ValueError, match="Door cell"):
        api.remap_receiving_door_layout_after_delete(
            operation="map_cells", cell_transitions={bad_key: "1:0"},
            cell_sources=cells, physical_sources=physical,
        )
    assert (cells, physical) == before


def _gui_host():
    return SimpleNamespace(
        receiving_inner_doors=[],
        surface_features={"door_c1_r1": [{"hole": "real"}]},
        workspace_controller=None, fold_designer_app=None,
        door_layout_features={"0:0": [{"hole": "real"}]},
        door_layout_indicator_states={},
        door_layout_indicator_box_features={},
        door_layout_indicator_door_features={},
        door_layout_handle_edges={},
    )


@pytest.mark.parametrize("target", [(True, 0), (1.5, 0), (-1, 0)])
def test_actual_gui_legacy_mapper_preserves_original_holes_on_bad_target(target):
    host = _gui_host()
    original_features = deepcopy(host.door_layout_features)
    original_surface = deepcopy(host.surface_features)
    with pytest.raises(ValueError, match="Door cell"):
        _remap_door_layout_owned_data(host, mapper=lambda c, r: target)
    assert host.door_layout_features == original_features
    assert host.surface_features == original_surface


def test_actual_gui_legacy_mapper_delegates_raw_valid_coordinate_to_engine():
    host = _gui_host()
    _remap_door_layout_owned_data(host, mapper=lambda c, r: (c + 1, r))
    assert host.door_layout_features == {"1:0": [{"hole": "real"}]}
    assert host.surface_features == {"door_c2_r1": [{"hole": "real"}]}


def test_explicit_none_retains_legacy_cell_removal_semantics():
    cells, physical = _physical_source()
    result = api.remap_receiving_door_layout_after_delete(
        operation="map_cells", cell_transitions={"0:0": None},
        cell_sources=cells, physical_sources=physical,
    )
    assert result["cell_sources"]["door_layout_features"] == {}
    assert result["physical_sources"]["workspace"] == {"other": ["keep"]}
