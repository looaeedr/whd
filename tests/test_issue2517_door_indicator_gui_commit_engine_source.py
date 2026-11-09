"""#2517: Door Hole Editor commits cannot save display-repaired physical holes.

These tests exercise the *actual* main-GUI commit ports without needing Tk.
The Engine is the sole validator for indicator manufacturing source.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _source(*, mode="indicator", **overrides):
    return {
        **{
            "mode": mode, "layers": "2", "groups": ["3", "2", "2"],
            "offset_x": "-1.25", "offset_y": "2.75",
            "is_box_dist": "false",
        },
        **overrides,
    }


def _multi_host():
    target = api.project_operator_door_layout_indicator_snapshot_states({
        "0:0": _source(mode="indicator"),
    })["0:0"]
    existing = {"0:0": deepcopy(target)}
    snapshot = {"door_layout_indicator_states": deepcopy(existing)}
    notifications = []
    host = SimpleNamespace(
        door_layout_indicator_states=existing,
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=snapshot),
        _normalize_door_indicator_state=lambda _: pytest.fail(
            "display-only compatibility must not authorize a physical write"
        ),
        _request_phase6_update=lambda kind: notifications.append(kind),
    )
    return host, notifications


def _single_host():
    messages = []
    host = SimpleNamespace(
        is_door_indicator_var=Var("false"),
        is_indicator_box_var=Var("false"),
        door_indicator_l_var=Var("1"),
        indicator_l_var=Var("1"),
        door_indicator_layer_g_vars=[Var("2") for _ in range(6)],
        indicator_layer_g_vars=[Var("2") for _ in range(6)],
        door_indicator_offset_x=0.0,
        door_indicator_offset_y=0.0,
        is_box_dist_var=Var("false"),
        _normalize_door_indicator_state=lambda _: pytest.fail(
            "display-only compatibility must not authorize a physical write"
        ),
        _request_phase6_update=lambda kind: messages.append(kind),
    )
    return host, messages


def _single_state(host):
    return (
        host.is_door_indicator_var.value,
        host.is_indicator_box_var.value,
        host.door_indicator_l_var.value,
        host.indicator_l_var.value,
        tuple(v.value for v in host.door_indicator_layer_g_vars),
        tuple(v.value for v in host.indicator_layer_g_vars),
        host.door_indicator_offset_x,
        host.door_indicator_offset_y,
        host.is_box_dist_var.value,
    )


@pytest.mark.parametrize("bad", (
    {"groups": [True, 3]},
    {"groups": ["2"]},
    {"layers": "7"},
    {"layers": "1.5"},
    {"offset_x": float("nan")},
    {"offset_y": True},
    {"is_box_dist": "maybe"},
    {"mode": "unsupported"},
))
def test_invalid_multi_door_commit_is_atomic_not_display_repaired(bad):
    host, notifications = _multi_host()
    row = host.door_layout_indicator_states["0:0"]
    saved = deepcopy(row)
    snap = deepcopy(host.fold_designer_app._phase6_input_snapshot)
    with pytest.raises(ValueError):
        export_actions._apply_multi_door_indicator_state(
            host, "0:0", _source(**bad),
        )
    assert host.door_layout_indicator_states["0:0"] is row
    assert row == saved
    assert host.fold_designer_app._phase6_input_snapshot == snap
    assert notifications == []


@pytest.mark.parametrize("bad", (
    {"groups": [True, 3]},
    {"groups": ["2"]},
    {"layers": "7"},
    {"offset_y": "inf"},
    {"is_box_dist": "maybe"},
    {"mode": "unsupported"},
))
def test_invalid_single_door_commit_is_atomic_not_display_repaired(bad):
    host, notifications = _single_host()
    before = _single_state(host)
    with pytest.raises(ValueError):
        export_actions._apply_single_door_indicator_state(
            host, _source(**bad),
        )
    assert _single_state(host) == before
    assert notifications == []


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
@pytest.mark.parametrize("mode", ["indicator", "indicator_box"])
def test_multi_door_commit_matches_engine_saved_source_and_real_part_spec(
    family, mode, tmp_path,
):
    host, notifications = _multi_host()
    request = _source(mode=mode, groups=["3", "2", False])
    original = deepcopy(request)
    expected = api.project_operator_door_layout_indicator_snapshot_states({
        "0:0": request,
    })["0:0"]

    export_actions._apply_multi_door_indicator_state(host, "0:0", request)
    committed = host.door_layout_indicator_states["0:0"]
    assert committed == expected
    assert host.fold_designer_app._phase6_input_snapshot[
        "door_layout_indicator_states"
    ]["0:0"] == expected
    assert request == original
    assert notifications == ["geometry"]

    spec = api.build_door_operator_part_spec(
        {
            "model": family, "w": 600, "h": 800, "t": 2, "fw": 25,
            "door_gap_w": 2, "door_gap_h": 2,
            "door_fold_l": 10, "door_fold_r": 10,
            "door_fold_t": 10, "door_fold_b": 10,
        },
        model_name=family,
        features=(),
        indicator_source_state=committed,
    )
    assert (spec.door_indicator is not None) == (mode == "indicator")
    assert (spec.indicator_hole is not None) == (mode == "indicator_box")
    assert spec.door_indicator_offset == (-1.25, 2.75)

    filename = write_project(
        tmp_path / f"indicator-commit-{family}-{mode}",
        {"schema": PROJECT_SCHEMA, "snapshot": {
            "model": family, "door_layout_indicator_states": {
                "0:0": committed,
            },
        }},
    )
    restored = read_project(filename)["snapshot"]["door_layout_indicator_states"]
    assert api.project_operator_door_layout_indicator_snapshot_states(
        restored
    )["0:0"] == expected


@pytest.mark.parametrize("mode", ["none", "indicator", "indicator_box"])
def test_single_door_commit_uses_strict_engine_projection_before_widgets(mode):
    host, notifications = _single_host()
    input_data = _source(mode=mode)
    canonical = api.project_operator_door_cell_indicator_manufacturing_source(
        input_data
    )
    export_actions._apply_single_door_indicator_state(host, input_data)
    assert host.is_door_indicator_var.value is (mode == "indicator")
    assert host.is_indicator_box_var.value is (mode == "indicator_box")
    assert host.door_indicator_l_var.value == str(canonical["layers"])
    assert host.door_indicator_offset_x == canonical["offset_x"]
    assert host.door_indicator_offset_y == canonical["offset_y"]
    assert host.is_box_dist_var.value is canonical["is_box_dist"]
    assert notifications == ["geometry"]


def test_gui_commit_ports_use_engine_validation_not_display_repair():
    single = inspect.getsource(export_actions._apply_single_door_indicator_state)
    multi = inspect.getsource(export_actions._apply_multi_door_indicator_state)
    assert "project_operator_door_cell_indicator_manufacturing_source(" in single
    assert "project_operator_door_layout_indicator_snapshot_states(" in multi
    assert "_normalize_door_indicator_state(" not in single
    assert "_normalize_door_indicator_state(" not in multi
