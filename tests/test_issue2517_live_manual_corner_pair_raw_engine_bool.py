# -*- coding: utf-8 -*-
"""#2517 live GUI Corner Pair uses the same strict Engine bool as saved transactions."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import corner_type_ui as owner
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection
from gui import Phase6ApplicationHost


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _state():
    left = CornerTypeSelection(CornerTypeId.C02)
    right = CornerTypeSelection(CornerTypeId.C03)
    return (
        {"top_left": left, "top_right": right,
         "bottom_left": CornerTypeSelection(CornerTypeId.C02),
         "bottom_right": CornerTypeSelection(CornerTypeId.C03)},
        {"top": True, "bottom": False},
    )


@pytest.mark.parametrize("raw", ("false", "FALSE", "off", "0", "", 0, False))
def test_live_engine_false_never_overwrites_distinct_physical_right_corner(raw):
    state, pairs = _state()
    right = state["top_right"]
    left = state["top_left"]
    assert right != left
    assert api.operator_set_manual_corner_pair_same is owner.set_manual_corner_pair_same
    assert api.operator_set_manual_corner_pair_same(
        state, pairs, "top", raw,
    ) is None
    assert pairs["top"] is False
    assert state["top_right"] is right and state["top_left"] is left
    assert state["top_right"] != state["top_left"]


@pytest.mark.parametrize("raw", ("true", "TRUE", "on", "1", 1, True))
def test_live_engine_true_rejoins_using_existing_left_corner(raw):
    state, pairs = _state()
    left = state["top_left"]
    owner.set_manual_corner_pair_same(state, pairs, "top", raw)
    assert pairs["top"] is True
    assert state["top_right"] is left


@pytest.mark.parametrize("bad", ("maybe", "2", 2, None, [], {},
                                  float("nan"), float("inf"), 0.5))
def test_invalid_live_pair_cannot_mutate_any_corner_or_pair(bad):
    state, pairs = _state()
    before = deepcopy((state, pairs))
    with pytest.raises(ValueError, match="布林"):
        api.operator_set_manual_corner_pair_same(state, pairs, "top", bad)
    assert (state, pairs) == before


def test_missing_source_corner_on_join_still_rejects_atomically():
    state, pairs = _state()
    del state["top_left"]
    before = deepcopy((state, pairs))
    with pytest.raises(KeyError):
        api.operator_set_manual_corner_pair_same(state, pairs, "top", True)
    assert (state, pairs) == before


def _host(raw):
    state, pairs = _state()
    calls = []
    host = SimpleNamespace(
        manual_corner_state={"head": state},
        manual_corner_pair_same={"head": pairs},
        manual_top_same_var=Var(raw),
        manual_bottom_same_var=Var(True),
        manual_active_corner_var=Var("top"),
        _current_manual_corner_part_key=lambda: "head",
        _manual_corner_parameters_editable=lambda _: True,
        _pair_for_corner_target=lambda target: "top" if target in (
            "top", "top_left", "top_right",
        ) else "bottom",
        refresh_corner_type_panel=lambda: calls.append("refresh"),
        _notify_fold_designer_corner_state=lambda: calls.append("notify"),
        _request_phase6_update=lambda reason: calls.append(("update", reason)),
    )
    return host, calls


@pytest.mark.parametrize("raw,accepted,target", (
    ("false", False, "top_left"),
    ("off", False, "top_left"),
    (0, False, "top_left"),
    ("true", True, "top"),
    ("1", True, "top"),
    (True, True, "top"),
))
def test_main_gui_uses_engine_result_to_route_physical_corner(raw, accepted, target):
    host, calls = _host(raw)
    before = deepcopy(host.manual_corner_state["head"])
    Phase6ApplicationHost.on_manual_corner_pair_same_changed(host, "top")
    assert host.manual_corner_pair_same["head"]["top"] is accepted
    assert host.manual_active_corner_var.get() == target
    if not accepted:
        assert host.manual_corner_state["head"] == before
    else:
        assert (host.manual_corner_state["head"]["top_right"] ==
                host.manual_corner_state["head"]["top_left"])
    assert calls == ["refresh", "notify", ("update", "geometry")]


@pytest.mark.parametrize("bad", ("not-a-bool", "2", None, 2, float("nan")))
def test_invalid_gui_toggle_fails_before_any_physical_or_ui_mutation(bad):
    host, calls = _host(bad)
    before = deepcopy((host.manual_corner_state,
                       host.manual_corner_pair_same))
    active = host.manual_active_corner_var.get()
    with pytest.raises(ValueError, match="布林"):
        Phase6ApplicationHost.on_manual_corner_pair_same_changed(host, "top")
    assert (host.manual_corner_state,
            host.manual_corner_pair_same) == before
    assert host.manual_active_corner_var.get() == active
    assert calls == []


def test_gui_and_headless_same_saved_json_pair_semantics():
    from ae_engine.endcap_factory_fold import selection_to_raw
    host, _ = _host("false")
    Phase6ApplicationHost.on_manual_corner_pair_same_changed(host, "top")
    gui_state = host.manual_corner_state["head"]
    gui_pair = host.manual_corner_pair_same["head"]
    direct, pairs = _state()
    api.operator_set_manual_corner_pair_same(direct, pairs, "top", "false")
    assert gui_state == direct and gui_pair == pairs
    saved = json.loads(json.dumps({
        "corners": {key: selection_to_raw(value)
                    for key, value in gui_state.items()},
        "pair_same": gui_pair,
    }))
    assert saved["pair_same"]["top"] is False
    assert saved["corners"]["top_left"] != saved["corners"]["top_right"]


def test_gui_source_decodes_without_rebuilding_bool_or_geometry():
    engine = inspect.getsource(owner.set_manual_corner_pair_same)
    gui = inspect.getsource(Phase6ApplicationHost.on_manual_corner_pair_same_changed)
    assert "normalize_operator_settings_boolean(enabled)" in engine
    assert "enabled = bool(enabled)" not in engine
    assert "self.manual_corner_pair_same[part_key][pair_key]" in gui
    assert "if raw_enabled:" not in gui
