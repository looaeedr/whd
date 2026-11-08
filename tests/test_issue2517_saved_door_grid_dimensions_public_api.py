"""#2517 physical Door-grid columns saved only through a public Engine projection."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.door_layout_feature_projection import (
    project_operator_saved_door_layout_columns as owner,
)
from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
from gui_modules.application import fold_designer_snapshot_projection as gui


def _columns():
    return [[800.25, [1100.125, 500.375]], [400.5, [1600.5]]]


def test_engine_owner_facade_and_root_expose_same_exact_callable():
    assert api.project_operator_saved_door_layout_columns is owner
    assert ae_engine.project_operator_saved_door_layout_columns is owner


def test_engine_grid_saved_projection_keeps_all_fractional_physical_cells_and_ids():
    src = _columns()
    original = deepcopy(src)
    result = api.project_operator_saved_door_layout_columns(src)
    assert result == src
    assert result is not src and result[0] is not src[0]
    assert result[0][1] is not src[0][1]
    assert len(derive_door_layout_cells(result)) == 3
    assert src == original
    result[0][1].append(30)
    assert src == original


def test_old_single_door_without_grid_stays_empty():
    assert api.project_operator_saved_door_layout_columns(None) == []
    assert api.project_operator_saved_door_layout_columns([]) == []


@pytest.mark.parametrize("columns", (
    "800:1600",
    {"width": 800, "heights": [1600]},
    [[True, [1600]]],
    [[800, [False]]],
    [[0, [1600]]],
    [[800, [-1]]],
    [[800, [0]]],
    [[float("nan"), [1600]]],
    [[800, [float("inf")]]],
    [[800, []]],
    [[800, "1600"]],
    [[800]],
    [None],
    [[800, [1600]], ["broken", [1600]]],
))
def test_invalid_physical_column_fails_closed_without_altering_source(columns):
    before = deepcopy(columns)
    with pytest.raises((ValueError, TypeError)):
        api.project_operator_saved_door_layout_columns(columns)
    assert columns == before


class _StopAtEngine(Exception):
    pass


class _Host:
    def __init__(self, columns):
        self.columns = columns
        self.workspace_controller = SimpleNamespace(active_part="door")
        self.project_controller = SimpleNamespace(project_path=None)
        self.baseline_var = SimpleNamespace(get=lambda: "金庫型")
        self.endcap_fw_state = {}
        self.door_layout_columns = [{"is_physical": True}]
        self.get_door_layout_columns = lambda: columns
        self._current_box_assembly_type = lambda: "OVERLAY"
        # Synthetic numeric controls default to 2; real boolean controls
        # must instead provide a valid operator boolean for Engine source
        # validation before this Door Grid test reaches its target API.
        self.is_box_dist_var = SimpleNamespace(get=lambda: False)
        self.multi_door_enabled_var = SimpleNamespace(get=lambda: False)

    def __getattr__(self, key):
        if key.endswith("_var"):
            return SimpleNamespace(get=lambda: 2)
        raise AttributeError(key)


def test_real_fold_designer_snapshot_hands_uncoerced_grid_to_public_engine(monkeypatch):
    columns = _columns()
    before = deepcopy(columns)
    observed = []

    def intercept(request):
        observed.append(deepcopy(request))
        expected = owner(request)
        assert expected == before
        raise _StopAtEngine

    monkeypatch.setattr(api, "project_operator_saved_door_layout_columns", intercept)
    with pytest.raises(_StopAtEngine):
        gui._snapshot_base_state(_Host(columns))
    assert observed == [columns]
    assert columns == before


def test_real_fold_designer_snapshot_bad_second_column_does_not_commit_any_candidate(monkeypatch):
    columns = [[800, [1600]], [True, [1600]]]
    host = _Host(columns)
    observed = []
    original = api.project_operator_saved_door_layout_columns

    def public(request):
        observed.append(deepcopy(request))
        return original(request)

    monkeypatch.setattr(api, "project_operator_saved_door_layout_columns", public)
    with pytest.raises(ValueError):
        gui._snapshot_base_state(host)
    assert observed == [columns]
    assert columns == [[800, [1600]], [True, [1600]]]


def test_actual_p6fold_save_reload_uses_same_engine_door_part_cell_topology(tmp_path):
    import phase6_project_file as project

    columns = _columns()
    source = {
        "model": "金庫型",
        "w": 1200.75, "h": 1600.5, "d": 350.0, "t": 2.0, "fw": 25.0,
        "multi_door_enabled": True,
        "door_layout_columns": api.project_operator_saved_door_layout_columns(columns),
        "part_features": {
            "door_c1_r1": [{"id": "upper"}],
            "door_c1_r2": [{"id": "lower"}],
            "door_c2_r1": [{"id": "second-column"}],
        },
    }
    before = deepcopy(source)
    target = project.write_project(
        tmp_path / "saved-door-grid.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    restored = project.read_project(target)["snapshot"]
    assert restored["door_layout_columns"] == columns
    old_cells = derive_door_layout_cells(columns)
    new_cells = derive_door_layout_cells(restored["door_layout_columns"])
    assert new_cells == old_cells
    # Existing project authority fills absent Head/Tail with empty Feature
    # rows. Door-grid physical Feature identity must remain unchanged.
    assert {
        key: restored["part_features"][key]
        for key in source["part_features"]
    } == source["part_features"]
    assert restored["part_features"]["head"] == []
    assert restored["part_features"]["tail"] == []
    assert source == before


def test_gui_has_no_second_float_cast_for_saved_door_grid_physical_dimensions():
    source = inspect.getsource(gui._snapshot_base_state)
    assert "manufacturing_api.project_operator_saved_door_layout_columns(door_columns)" in source
    assert "for width, heights in self.get_door_layout_columns()" not in source
