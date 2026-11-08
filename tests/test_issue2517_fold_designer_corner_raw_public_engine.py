"""#2517 Fold Designer Corner controls forward raw T multipliers to public Engine."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import CornerTypeId
from gui_modules.application import fold_designer_composition_registry_edges as gui


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


class EngineTransaction:
    """Minimal host adapter using the real public, immutable Engine transition."""
    def __init__(self):
        seeded = api.ensure_corner_part({}, {}, "head")
        self.state = api.commit_corner_type(
            seeded.corner_state, seeded.corner_pair_same,
            "head", "top", CornerTypeId.INSERT_OVERLAY,
        )
        self.requests = []

    def corner_selection(self, part, target):
        return api.corner_selection(
            self.state.corner_state[part],
            self.state.corner_pair_same[part],
            target,
        )

    def commit_corner_parameters(self, part, target, **kwargs):
        self.requests.append(deepcopy(kwargs))
        result = api.commit_corner_parameters(
            self.state.corner_state, self.state.corner_pair_same,
            part, target, **kwargs,
        )
        self.state = result
        return result.value


def _owner(field, raw):
    tx = EngineTransaction()
    events = []
    vars_by_name = {
        "amount": {"top": Var("1.375")},
        "retain": {"top": Var("0.625")},
        "depth": {"top": Var("2.125")},
    }
    vars_by_name[field]["top"] = Var(raw)
    app = SimpleNamespace(
        _phase6_corner_guard=False,
        _phase6_settings_rendering=False,
        corner_amount_vars=vars_by_name["amount"],
        corner_mode_vars={},
        corner_direction_vars={},
        corner_secondary_retain_vars=vars_by_name["retain"],
        corner_secondary_depth_vars=vars_by_name["depth"],
    )
    required = {
        "_phase6_corner_parameters_editable": lambda _app, _key: True,
        "_CORNER_MODE_BY_LABEL": {},
        "_CORNER_DIRECTION_BY_LABEL": {},
        "_phase6_notify_corner_change": lambda _app: events.append("notify"),
        "original": SimpleNamespace(tk=SimpleNamespace(TclError=type(
            "FakeTclError", (Exception,), {},
        ))),
    }
    owner = SimpleNamespace(
        app=app,
        settings_transactions=lambda: tx,
        _required=lambda _namespace, name: required[name],
    )
    return owner, tx, events


@pytest.mark.parametrize("field,parameter", (
    ("amount", "amount_t"),
    ("retain", "secondary_retain_t"),
    ("depth", "secondary_depth_t"),
))
@pytest.mark.parametrize("bad", (
    True, False, "nan", "inf", "bogus", [], {},
))
def test_invalid_fold_designer_corner_source_rejects_without_any_commit_or_notification(
    field, parameter, bad,
):
    owner, tx, events = _owner(field, bad)
    before = deepcopy((tx.state.corner_state, tx.state.corner_pair_same))
    assert gui.corner_target_var_changed(owner, None, "head", "top") is None
    assert tx.state.corner_state == before[0]
    assert tx.state.corner_pair_same == before[1]
    assert events == []
    assert len(tx.requests) == 1
    assert tx.requests[0][parameter] == bad


@pytest.mark.parametrize("field,parameter,expected", (
    ("amount", "amount_t", 1.375),
    ("retain", "secondary_retain_t", 0.625),
    ("depth", "secondary_depth_t", 2.125),
))
def test_fold_designer_valid_raw_fraction_is_committed_through_original_public_engine(
    field, parameter, expected,
):
    raw = str(expected)
    owner, tx, events = _owner(field, raw)
    before = deepcopy(tx.state.corner_state)
    assert gui.corner_target_var_changed(owner, None, "head", "top") is True
    assert tx.requests[0][parameter] == raw
    assert events == ["notify"]
    current = tx.state.corner_state["head"]
    assert current["top_left"][parameter] == pytest.approx(expected)
    assert current["top_right"][parameter] == pytest.approx(expected)
    assert tx.state.corner_state != before
    assert json.loads(json.dumps(tx.state.corner_state)) == tx.state.corner_state


def test_fold_designer_source_handling_preserves_original_engine_corner_ownership():
    code = inspect.getsource(gui.corner_target_var_changed)
    assert "float(amount_var.get())" not in code
    assert "float(retain_var.get())" not in code
    assert "float(depth_var.get())" not in code
    assert "transactions.commit_corner_parameters(" in code
