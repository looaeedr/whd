"""#2517: saved Door-cell holes may not be fabricated by GUI repair."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_snapshot_projection as gui
from gui_modules.parts.panels.door import normalize_door_indicator_state
from tests.test_issue2517_receiving_base_plate_snapshot_alias_save_reload import SnapshotHost
import phase6_project_file as project


def _state(mode="indicator_box", **change):
    raw = {"mode": mode, "layers": 2, "groups": [3, 2, 2, 2, 2, 2],
           "offset_x": 1.25, "offset_y": -2.5, "is_box_dist": False}
    raw.update(change)
    return raw


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("mode", ("indicator_box", "indicator"))
def test_real_gui_snapshot_save_reload_retains_exact_active_lamps(tmp_path, model, mode):
    raw = _state(mode)
    current = {"0:0": raw, "1:0": {"mode": "none", "groups": [False]}}
    before = deepcopy(current)
    host = SnapshotHost(model, {"model": model})
    host.door_layout_indicator_states = current
    snap = gui._snapshot_base_state(host)
    saved = snap["door_layout_indicator_states"]
    assert saved["0:0"]["mode"] == mode
    assert saved["0:0"]["groups"][:2] == [3, 2]
    assert saved["0:0"]["offset_x"] == 1.25
    assert saved["0:0"]["offset_y"] == -2.5
    assert saved["0:0"]["enabled"] is (mode == "indicator")
    assert saved["0:0"]["box_enabled"] is (mode == "indicator_box")
    assert saved["1:0"]["mode"] == "none"
    assert current == before
    saved["0:0"]["groups"][0] = 5
    assert current == before
    snap["door_layout_indicator_states"] = api.project_operator_door_layout_indicator_snapshot_states(current)
    file = project.write_project(tmp_path / "door-source.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": snap,
    })
    loaded = project.read_project(file)["snapshot"]
    assert loaded["door_layout_indicator_states"] == snap["door_layout_indicator_states"]
    assert current == before


@pytest.mark.parametrize("broken", (
    {"layers": True}, {"layers": 0}, {"layers": 1.5}, {"layers": 7},
    {"layers": "n/a"}, {"layers": 3, "groups": [1, 2]},
    {"groups": [False, 2]}, {"groups": [3.5, 2]},
    {"groups": [0, 2]}, {"groups": [9, 2]},
    {"offset_x": float("nan")}, {"offset_y": float("inf")},
    {"offset_x": "not-a-number"}, {"is_box_dist": "invalid"},
    {"mode": "unsupported"},
))
def test_gui_snapshot_refuses_active_corrupt_hole_source_before_save(broken):
    raw = _state(**broken)
    before = deepcopy(raw)
    host = SnapshotHost("金庫型", {"model": "金庫型"})
    host.door_layout_indicator_states = {"0:0": raw}
    with pytest.raises(ValueError, match="門格 0:0 指示燈來源無效"):
        gui._snapshot_base_state(host)
    assert raw == before


def test_gui_display_normalizer_cannot_be_manufacturing_or_save_authority():
    invalid = _state(groups=[False, 2])
    # The old presentation helper would turn False into two manufactured lamps.
    assert normalize_door_indicator_state(invalid)["groups"][0] == 2
    with pytest.raises(ValueError):
        api.project_operator_door_layout_indicator_snapshot_states({"0:0": invalid})
    source = inspect.getsource(gui._snapshot_base_state)
    assert "manufacturing_api.project_operator_door_layout_indicator_snapshot_states(" in source
    assert "normalize_door_indicator_state(" not in source


def test_legacy_flags_choose_mode_only_not_fabricated_geometry():
    old = {k: v for k, v in _state().items() if k != "mode"}
    old["box_enabled"] = True
    saved = api.project_operator_door_layout_indicator_snapshot_states({"0:0": old})
    assert saved["0:0"]["mode"] == "indicator_box"
    old["groups"] = []
    with pytest.raises(ValueError):
        api.project_operator_door_layout_indicator_snapshot_states({"0:0": old})
    with pytest.raises(ValueError):
        api.project_operator_door_layout_indicator_snapshot_states({"0:0": False})
    assert api.project_operator_door_layout_indicator_snapshot_states({}) == {}
