"""#2517: disabled single Door indicator controls use Engine display repair."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project.export_actions import _single_door_indicator_state_snapshot


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


def _host(
    *, box="false", direct="false", layers="2", groups=("3", "4"),
    offset_x="-1.25", offset_y="2.75", distance="false",
):
    return SimpleNamespace(
        is_indicator_box_var=Var(box),
        is_door_indicator_var=Var(direct),
        indicator_l_var=Var(layers),
        door_indicator_l_var=Var(layers),
        indicator_layer_g_vars=[Var(raw) for raw in groups],
        door_indicator_layer_g_vars=[Var(raw) for raw in groups],
        door_indicator_offset_x=offset_x,
        door_indicator_offset_y=offset_y,
        is_box_dist_var=Var(distance),
        _normalize_door_indicator_state=api.project_operator_door_indicator_display_state,
    )


def _raw(host):
    return {
        "mode": "none",
        "layers": host.door_indicator_l_var.get(),
        "groups": [var.get() for var in host.door_indicator_layer_g_vars[:6]],
        "offset_x": host.door_indicator_offset_x,
        "offset_y": host.door_indicator_offset_y,
        "is_box_dist": host.is_box_dist_var.get(),
    }


@pytest.mark.parametrize("raw_distance,expected", [
    ("false", False),
    ("0", False),
    (False, False),
    ("true", True),
    ("1", True),
])
def test_disabled_single_door_uses_public_engine_serialized_distance_flag(
    raw_distance, expected,
):
    host = _host(distance=raw_distance)
    original = deepcopy(_raw(host))
    snapshot = _single_door_indicator_state_snapshot(host)
    assert snapshot == api.project_operator_door_indicator_display_state(
        original, legacy_inactive_single_door=True,
    )
    assert snapshot["mode"] == "none"
    assert snapshot["is_box_dist"] is expected
    assert snapshot["offset_x"] == -1.25
    assert snapshot["offset_y"] == 2.75
    assert _raw(host) == original
    assert json.loads(json.dumps(snapshot)) == snapshot


@pytest.mark.parametrize("layers,groups,offset_x,offset_y", [
    ("not-integer", (True,), "bad", float("nan")),
    (True, (False, "not-count"), True, float("inf")),
    ("3", ("2",), "-1.125", "-2.875"),
    (7, ("5", "bad", "-1"), None, []),
])
def test_disabled_single_door_old_controls_are_repaired_only_by_engine(
    layers, groups, offset_x, offset_y,
):
    host = _host(
        layers=layers, groups=groups, offset_x=offset_x, offset_y=offset_y,
        distance="false",
    )
    before = _raw(host)
    expected = api.project_operator_door_indicator_display_state(
        before, legacy_inactive_single_door=True,
    )
    result = _single_door_indicator_state_snapshot(host)
    assert result == expected
    assert result["mode"] == "none"
    assert result["is_box_dist"] is False
    # No repaired UI defaults may be written into the operator controls.
    assert _raw(host)["layers"] == before["layers"]
    assert _raw(host)["groups"] == before["groups"]


@pytest.mark.parametrize("box,direct,mode", [
    ("true", "false", "indicator_box"),
    ("false", "true", "indicator"),
])
def test_enabled_single_door_keeps_strict_live_manufacturing_gate(box, direct, mode):
    host = _host(box=box, direct=direct, layers="2", groups=("3", "4"))
    state = _single_door_indicator_state_snapshot(host)
    assert state["mode"] == mode
    assert state["layers"] == 2
    assert state["groups"][:2] == [3, 4]

    host.door_indicator_l_var.raw = "not-valid"
    host.indicator_l_var.raw = "not-valid"
    with pytest.raises(ValueError):
        _single_door_indicator_state_snapshot(host)


def test_disabled_display_adapter_does_not_coerce_original_physical_controls():
    source = inspect.getsource(_single_door_indicator_state_snapshot)
    # Legacy display repair and its boolean/mm/integer interpretation are
    # Engine-only, rather than a second GUI fallback or coercion policy.
    disabled_branch = source.split("# A disabled mode", 1)[1]
    assert "manufacturing_api.project_operator_door_indicator_display_state(" in disabled_branch
    assert "legacy_inactive_single_door=True" in disabled_branch
    assert "int(" not in disabled_branch
    assert "float(" not in disabled_branch
    assert "bool(" not in disabled_branch


def test_existing_single_door_disabled_layer_clamp_is_engine_owned():
    host = _host(layers="9", groups=("bad",) * 6)
    state = _single_door_indicator_state_snapshot(host)
    assert state["mode"] == "none"
    assert state["layers"] == 6
    assert state["groups"] == [2] * 6
    raw = _raw(host)
    assert api.project_operator_door_indicator_display_state(raw)["layers"] == 1
    assert api.project_operator_door_indicator_display_state(
        raw, legacy_inactive_single_door=True,
    )["layers"] == 6


@pytest.mark.parametrize("raw,expected", [
    (9, 6), ("9", 6), (99, 6), (-2, 1), (0, 1),
    ("bad", 1), (True, 1), (9.8, 6), ("9.8", 1),
])
def test_engine_single_door_inactive_layer_legacy_cap_is_display_only(raw, expected):
    source = {"mode": "none", "layers": raw}
    assert api.project_operator_door_indicator_display_state(
        source, legacy_inactive_single_door=True,
    )["layers"] == expected
    assert source["layers"] == raw
