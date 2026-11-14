"""#2517 manual Corner parameters must retain raw physical source until Engine."""
from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode,
)
from gui_modules.parts.panels import assembly_corner as gui


class Field:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


def _gui_host(corner_type, amount="1.375", retain="0.625", depth="2.125"):
    class Host:
        _CORNER_MODE_BY_LABEL = {"留肉": CrossCornerMode.RETAIN}
        _CORNER_DIRECTION_BY_LABEL = {}
    host = Host()
    host.manual_corner_type_var = Field(corner_type.value)
    host.manual_corner_amount_var = Field(amount)
    host.manual_corner_secondary_retain_var = Field(retain)
    host.manual_corner_secondary_depth_var = Field(depth)
    host.manual_corner_cross_mode_var = Field("留肉")
    host.manual_corner_direction_var = Field("")
    return host


def _engine_host(corner_type):
    original = api.ensure_corner_part({}, {}, "head")
    state = api.commit_corner_type(
        original.corner_state, original.corner_pair_same,
        "head", "top", corner_type,
    )
    if corner_type is CornerTypeId.CROSS:
        state = api.commit_corner_mode(
            state.corner_state, state.corner_pair_same,
            "head", "top", CrossCornerMode.RETAIN,
        )
    return state


@pytest.mark.parametrize("corner_type,parameter", (
    (CornerTypeId.CROSS, "amount_t"),
    (CornerTypeId.OVERLAY, "amount_t"),
    (CornerTypeId.INSERT, "amount_t"),
    (CornerTypeId.INSERT_OVERLAY, "amount_t"),
    (CornerTypeId.INSERT_OVERLAY, "secondary_retain_t"),
    (CornerTypeId.INSERT_OVERLAY, "secondary_depth_t"),
))
@pytest.mark.parametrize("bad", (
    True, False, "nan", "inf", float("nan"), float("inf"), [], {},
))
def test_invalid_corner_source_fails_original_engine_transaction_without_mutation(
    corner_type, parameter, bad,
):
    state = _engine_host(corner_type)
    originals = deepcopy((state.corner_state, state.corner_pair_same))
    with pytest.raises((TypeError, ValueError)):
        api.commit_corner_parameters(
            state.corner_state, state.corner_pair_same,
            "head", "top", **{parameter: bad},
        )
    assert (state.corner_state, state.corner_pair_same) == originals


@pytest.mark.parametrize("corner_type,parameter", (
    (CornerTypeId.CROSS, "amount"),
    (CornerTypeId.OVERLAY, "amount"),
    (CornerTypeId.INSERT, "amount"),
    (CornerTypeId.INSERT_OVERLAY, "amount"),
    (CornerTypeId.INSERT_OVERLAY, "retain"),
    (CornerTypeId.INSERT_OVERLAY, "depth"),
))
@pytest.mark.parametrize("bad", (True, False, "nan", "inf", [], {}))
def test_gui_control_never_converts_invalid_manufacturing_parameter_to_a_corner(
    corner_type, parameter, bad,
):
    props = {"amount": "1.375", "retain": "0.625", "depth": "2.125"}
    props[parameter] = bad
    host = _gui_host(corner_type, **props)
    assert gui.selection_from_manual_corner_controls(host) is None


@pytest.mark.parametrize("corner_type", (
    CornerTypeId.CROSS, CornerTypeId.OVERLAY,
    CornerTypeId.INSERT, CornerTypeId.INSERT_OVERLAY,
))
def test_fractional_physical_corner_source_matches_engine_and_reload(corner_type):
    proposed = gui.selection_from_manual_corner_controls(_gui_host(corner_type))
    assert isinstance(proposed, CornerTypeSelection)
    assert proposed.amount_t == pytest.approx(1.375)
    state = _engine_host(corner_type)
    before = deepcopy((state.corner_state, state.corner_pair_same))
    params = {"amount_t": "1.375"}
    if corner_type is CornerTypeId.INSERT_OVERLAY:
        assert proposed.secondary_retain_t == pytest.approx(0.625)
        assert proposed.secondary_depth_t == pytest.approx(2.125)
        params.update(secondary_retain_t="0.625", secondary_depth_t="2.125")
    committed = api.commit_corner_parameters(
        state.corner_state, state.corner_pair_same,
        "head", "top", **params,
    )
    assert committed.value["amount_t"] == pytest.approx(proposed.amount_t)
    if corner_type is CornerTypeId.INSERT_OVERLAY:
        assert committed.value["secondary_retain_t"] == proposed.secondary_retain_t
        assert committed.value["secondary_depth_t"] == proposed.secondary_depth_t
    else:
        assert "secondary_retain_t" not in committed.value
    assert before == (state.corner_state, state.corner_pair_same)
    restored = json.loads(json.dumps(committed.corner_state, ensure_ascii=False))
    assert restored == committed.corner_state


def test_corner_source_conversion_has_no_gui_or_engine_bool_to_float_bypass():
    gui_code = inspect.getsource(gui.selection_from_manual_corner_controls)
    engine_code = inspect.getsource(api.commit_corner_parameters)
    for bad in (
        "float(self.manual_corner_amount_var.get())",
        "float(self.manual_corner_secondary_retain_var.get())",
        "float(self.manual_corner_secondary_depth_var.get())",
    ):
        assert bad not in gui_code
    for bad in ("float(amount_t)", "float(secondary_retain_t)", "float(secondary_depth_t)"):
        assert bad not in engine_code
    # Engine's original physical type still remains the only source authority.
    assert api.commit_corner_parameters is not None
