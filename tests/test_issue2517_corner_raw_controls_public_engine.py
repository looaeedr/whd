"""#2517: original Corner Engine validates raw GUI parameters and paired flags."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace
import tkinter as tk

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import corner_state_transactions as owner
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection
from gui_modules.application import fold_designer_composition_registry_edges as gui
from gui_modules.parts.panels import assembly_corner as main_gui


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _state():
    return api.ensure_corner_part(
        {"head": {"top_left": {
            "type_id": "INSERT_OVERLAY",
            "amount_t": 1.0,
            "secondary_retain_t": 0.5,
            "secondary_depth_t": 2.0,
        }}}, None, "head",
    )


class Transactions:
    def __init__(self):
        self.result = _state()

    def corner_selection(self, part, target):
        return api.corner_selection(
            self.result.corner_state[part], self.result.corner_pair_same[part],
            target,
        )

    def commit_corner_parameters(self, part, target, **kwargs):
        self.result = api.commit_corner_parameters(
            self.result.corner_state, self.result.corner_pair_same,
            part, target, **kwargs,
        )

    def commit_corner_pair(self, part, target, value):
        self.result = api.commit_corner_pair(
            self.result.corner_state, self.result.corner_pair_same,
            part, target, value,
        )


@pytest.mark.parametrize("field", ["amount_t", "secondary_retain_t", "secondary_depth_t"])
@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), "invalid"])
def test_public_engine_corner_rejects_bad_raw_numerics_atomically(field, bad):
    state = _state()
    before = deepcopy((state.corner_state, state.corner_pair_same))
    for caller in (api.commit_corner_parameters, owner.commit_corner_parameters):
        with pytest.raises(ValueError):
            caller(
                state.corner_state, state.corner_pair_same,
                "head", "top", **{field: bad},
            )
        assert (state.corner_state, state.corner_pair_same) == before


def test_public_engine_corner_accepts_precise_saved_t_coefficients():
    state = _state()
    before = deepcopy(state.corner_state)
    committed = api.commit_corner_parameters(
        state.corner_state, state.corner_pair_same, "head", "top",
        amount_t="1.75", secondary_retain_t="0.25", secondary_depth_t="2.5",
    )
    for key in ("top_left", "top_right"):
        assert committed.corner_state["head"][key]["amount_t"] == pytest.approx(1.75)
        assert committed.corner_state["head"][key]["secondary_retain_t"] == pytest.approx(.25)
        assert committed.corner_state["head"][key]["secondary_depth_t"] == pytest.approx(2.5)
    assert state.corner_state == before
    reloaded = json.loads(json.dumps(committed.corner_state))
    assert reloaded["head"]["top_left"] == committed.corner_state["head"]["top_left"]


def _gui_owner(tx, *, amount="1.75", retain="0.5", depth="2.0"):
    events = []
    app = SimpleNamespace(
        _phase6_corner_guard=False,
        _phase6_settings_rendering=False,
        corner_amount_vars={"top": Var(amount)},
        corner_secondary_retain_vars={"top": Var(retain)},
        corner_secondary_depth_vars={"top": Var(depth)},
        corner_mode_vars={},
        corner_direction_vars={},
    )
    required = {
        "_phase6_corner_parameters_editable": lambda _app, _part: True,
        "_phase6_notify_corner_change": lambda _app: events.append("notify"),
        "original": SimpleNamespace(tk=tk),
    }
    gui_owner = SimpleNamespace(
        app=app,
        _required=lambda _namespace, name: required[name],
        settings_transactions=lambda: tx,
        invalidate_settings_page=lambda part: events.append(("invalidate", part)),
        render_settings_context=lambda namespace, part: events.append(("render", part)),
    )
    return gui_owner, app, events


@pytest.mark.parametrize(("field", "invalid"), [
    ("amount", True), ("retain", True), ("depth", True),
    ("amount", "NaN"), ("retain", "inf"), ("depth", "bad"),
])
def test_fold_designer_gui_does_not_convert_bad_corner_input_before_engine(field, invalid):
    tx = Transactions()
    values = {"amount": "1.75", "retain": "0.5", "depth": "2.0"}
    values[field] = invalid
    gui_owner, app, events = _gui_owner(tx, **values)
    original = deepcopy(tx.result.corner_state)
    assert gui.corner_target_var_changed(gui_owner, {}, "head", "top") is None
    assert tx.result.corner_state == original
    assert events == []
    assert app.corner_amount_vars["top"].get() == values["amount"]


def test_fold_designer_gui_corner_matches_headless_result_for_valid_raw_values():
    tx = Transactions()
    gui_owner, _app, events = _gui_owner(tx, amount="1.75", retain="0.25", depth="2.5")
    expected = api.commit_corner_parameters(
        _state().corner_state, _state().corner_pair_same,
        "head", "top",
        amount_t="1.75", secondary_retain_t="0.25", secondary_depth_t="2.5",
    )
    assert gui.corner_target_var_changed(gui_owner, {}, "head", "top") is True
    assert tx.result.corner_state == expected.corner_state
    assert events == ["notify"]


def test_gui_corner_pair_serialized_false_is_not_decoded_as_true():
    tx = Transactions()
    gui_owner, _app, events = _gui_owner(tx)
    assert gui.corner_pair_var_changed(
        gui_owner, {}, "head", "top", Var("false")
    ) is True
    assert tx.result.corner_pair_same["head"]["top"] is False
    assert events == ["notify", ("invalidate", "head"), ("render", "head")]
    before = deepcopy(tx.result.corner_pair_same)
    assert gui.corner_pair_var_changed(
        gui_owner, {}, "head", "top", Var("unknown")
    ) is None
    assert tx.result.corner_pair_same == before
    assert events == ["notify", ("invalidate", "head"), ("render", "head")]


def _main_controls(amount, retain, depth):
    return SimpleNamespace(
        manual_corner_type_var=Var(CornerTypeId.INSERT_OVERLAY.value),
        manual_corner_amount_var=Var(amount),
        manual_corner_secondary_retain_var=Var(retain),
        manual_corner_secondary_depth_var=Var(depth),
        manual_corner_cross_mode_var=Var(""),
        manual_corner_direction_var=Var(""),
        _CORNER_MODE_BY_LABEL={},
        _CORNER_DIRECTION_BY_LABEL={},
    )


@pytest.mark.parametrize(("amount", "retain", "depth"), [
    (True, "0.5", "2"), ("1", True, "2"), ("1", "0.5", True),
    ("NaN", "0.5", "2"),
])
def test_main_gui_manual_corner_rejects_boolean_and_nonfinite_raw_sources(amount, retain, depth):
    assert main_gui.selection_from_manual_corner_controls(
        _main_controls(amount, retain, depth)
    ) is None


def test_main_gui_manual_corner_uses_engine_corner_value_object():
    result = main_gui.selection_from_manual_corner_controls(
        _main_controls("1.75", "0.25", "2.5")
    )
    assert isinstance(result, CornerTypeSelection)
    assert result.amount_t == 1.75
    assert result.secondary_retain_t == 0.25
    assert result.secondary_depth_t == 2.5
    assert "float(self.manual_corner_amount_var.get())" not in inspect.getsource(
        main_gui.selection_from_manual_corner_controls
    )
    assert "float(amount_var.get())" not in inspect.getsource(
        gui.corner_target_var_changed
    )
