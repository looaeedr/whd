# -*- coding: utf-8 -*-
"""#2517: Receiving WRAP reserve input must go raw through public Engine."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.endcap_bottom_wrap_state import (
    commit_endcap_bottom_wrap, normalize_endcap_bottom_wrap_state,
)
from phase6_settings_transaction_controller import Phase6SettingsTransactionController
import fold_designer_bridge as bridge


class Field:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _state():
    return normalize_endcap_bottom_wrap_state({"model": "受電箱"})


def test_existing_public_wrap_ports_are_one_engine_authority():
    assert api.commit_endcap_bottom_wrap is commit_endcap_bottom_wrap
    assert api.normalize_endcap_bottom_wrap_state is normalize_endcap_bottom_wrap_state
    source = inspect.getsource(bridge._phase6_commit_receiving_bottom_wrap_controls)
    assert "max(0.0" not in source
    assert "float(reserve_" not in source
    assert "reserve_u_var.get()" in source and "reserve_v_var.get()" in source


@pytest.mark.parametrize("bad", [
    True, False, -1, -0.25, "-0.1", "nan", "inf",
    float("nan"), float("inf"), float("-inf"), "", "invalid", [], {},
])
@pytest.mark.parametrize("axis", ["reserve_u", "reserve_v"])
def test_lowlevel_and_operator_engine_reject_bad_reserve_without_mutating_source(bad, axis):
    state = _state()
    original = deepcopy(state)
    with pytest.raises(ValueError):
        commit_endcap_bottom_wrap(state, "head", **{axis: bad})
    assert state == original

    raw_snapshot = {"model": "受電箱"}
    kwargs = {"reserve_u": "2.25", "reserve_v": "1.5"}
    kwargs[axis] = bad
    with pytest.raises(ValueError):
        api.operator_endcap_bottom_wrap(
            raw_snapshot, state, "head", **kwargs,
        )
    assert state == original and raw_snapshot == {"model": "受電箱"}


def test_operator_required_values_reject_none_before_state_commit():
    original = _state()
    with pytest.raises(ValueError):
        api.operator_endcap_bottom_wrap(
            {"model": "受電箱"}, original, "head", reserve_u=None, reserve_v=1,
        )
    assert original == _state()


def test_zero_and_fractional_raw_reserves_roundtrip_and_keep_joint_linkage():
    source = {"model": "受電箱"}
    prior = _state()
    result = api.operator_endcap_bottom_wrap(
        source, prior, "head", reserve_u="2.75", reserve_v="0",
    )
    assert source == {"model": "受電箱"} and prior == _state()
    assert result.state["head"] == result.state["tail"]
    assert result.resolved["reserve_u"] == 2.75
    assert result.resolved["reserve_v"] == 0
    encoded = json.loads(json.dumps({"endcap_bottom_wrap": result.state, "model": "受電箱"}))
    assert api.resolve_endcap_bottom_wrap(encoded, "tail")["reserve_u"] == 2.75


def test_real_settings_transaction_controller_does_not_dirty_project_on_invalid_late_axis():
    snapshot = {"model": "受電箱"}
    state = _state()
    ctrl = Phase6SettingsTransactionController(
        settings_values={}, input_snapshot=snapshot, box_whd={},
        endcap_bottom_wrap_state=state,
    )
    original = deepcopy(state)
    with pytest.raises(ValueError):
        ctrl.commit_bottom_wrap("head", reserve_u="3.25", reserve_v="nan")
    assert snapshot == {"model": "受電箱"} and state == original
    valid = ctrl.commit_bottom_wrap("head", reserve_u="3.25", reserve_v="1.5")
    assert valid["reserve_u"] == 3.25 and state["head"]["reserve_v"] == 1.5


@pytest.mark.parametrize("bad", ["-1", "nan", True, "inf"])
def test_actual_fold_designer_gui_never_sends_clamped_manufacturing_source(monkeypatch, bad):
    source = {"model": "受電箱"}
    saved = _state()
    host = SimpleNamespace(
        _phase6_input_snapshot=source,
        _phase6_endcap_bottom_wrap_state=saved,
        _phase6_last_resolved_manufacturing_geometry="existing",
        _phase6_last_resolved_manufacturing_signature="existing",
    )
    redraws = []
    host.do_update = lambda: redraws.append("redraw")
    monkeypatch.setattr(api, "operator_supports_bottom_wrap_controls", lambda snapshot: True)
    monkeypatch.setattr(bridge, "resolve_endcap_bottom_wrap",
                        lambda *args, **kwargs: {"enabled": True, "reserve_u": 2, "reserve_v": 1})
    monkeypatch.setattr(bridge, "_phase6_invalidate_settings_page",
                        lambda *args: redraws.append("invalidate"))

    class Controller:
        def commit_bottom_wrap(self, key, *, reserve_u, reserve_v):
            assert reserve_u == bad
            return api.operator_endcap_bottom_wrap(
                source, saved, key, reserve_u=reserve_u, reserve_v=reserve_v,
            ).resolved

    monkeypatch.setattr(bridge, "_phase6_settings_transactions", lambda app: Controller())
    assert bridge._phase6_commit_receiving_bottom_wrap_controls(
        host, "head", Field(bad), Field("1"),
    ) is None
    assert source == {"model": "受電箱"} and saved == _state()
    assert redraws == []
    assert host._phase6_last_resolved_manufacturing_geometry == "existing"
