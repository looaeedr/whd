# -*- coding: utf-8 -*-
"""#2517: unreadable live manufacturing controls must not become default inputs."""
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from phase6_manufacturing_adapter import (
    _cabinet_model,
    _relief_clearance,
    _manufacturing_operator_var_get,
    build_manufacturing_request,
)
from tests.test_issue356_manufacturing_adapter import _fake_app


class BrokenVar:
    def get(self):
        raise RuntimeError("Tk source no longer readable")


@pytest.mark.parametrize("attr,default", [
    ("assembly_ignore_fixed_corner_var", False),
    ("assembly_relief_clearance_var", "0"),
    ("baseline_model_var", ""),
])
def test_unreadable_existing_operator_variable_cannot_silently_default(attr, default):
    app = SimpleNamespace(**{attr: BrokenVar()})
    with pytest.raises(ValueError, match=f"MANUFACTURING_OPERATOR_SOURCE_READ_FAILED:{attr}") as exc:
        _manufacturing_operator_var_get(app, attr, default)
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.parametrize("attr,default", [
    ("assembly_ignore_fixed_corner_var", False),
    ("assembly_relief_clearance_var", "0"),
    ("baseline_model_var", ""),
])
def test_missing_optional_controls_retain_facade_defaults(attr, default):
    assert _manufacturing_operator_var_get(SimpleNamespace(), attr, default) == default


def test_direct_value_and_live_tk_value_are_read_as_operator_input():
    app = SimpleNamespace(baseline_model_var="受電箱")
    assert _cabinet_model(app, {"model": "金庫型"}) == "受電箱"
    app.baseline_model_var = SimpleNamespace(get=lambda: "金庫型")
    assert _cabinet_model(app, {"model": "受電箱"}) == "金庫型"
    assert _cabinet_model(SimpleNamespace(), {"model": "受電箱"}) == "受電箱"


@pytest.mark.parametrize("attr", [
    "assembly_ignore_fixed_corner_var",
    "assembly_relief_clearance_var",
    "baseline_model_var",
])
def test_full_request_refuses_unreadable_live_operator_control(attr):
    app = _fake_app()
    setattr(app, attr, BrokenVar())
    with pytest.raises(ValueError, match=f"MANUFACTURING_OPERATOR_SOURCE_READ_FAILED:{attr}"):
        build_manufacturing_request(app)


def test_gui_and_headless_relief_input_keep_engine_contract_when_read_succeeds():
    app = SimpleNamespace(assembly_relief_clearance_var=SimpleNamespace(get=lambda: "2.75"))
    assert _relief_clearance(app) == api.normalize_operator_relief_clearance("2.75")


def test_unreadable_live_model_cannot_replace_operator_choice_with_stale_snapshot():
    app = SimpleNamespace(baseline_model_var=BrokenVar())
    with pytest.raises(ValueError, match="MANUFACTURING_OPERATOR_SOURCE_READ_FAILED:baseline_model_var"):
        _cabinet_model(app, {"model": "金庫型"})
