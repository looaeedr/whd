"""#2517 Receiving live W/H/D request Settings follow Engine Family registry."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from phase6_manufacturing_adapter import build_manufacturing_request
from tests.test_issue356_manufacturing_adapter import _fake_app


CURRENT = {"w": 820.25, "h": 1600.5, "d": 360.75}


@pytest.mark.parametrize("family", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_every_receiving_family_alias_uses_same_committed_bay_dimensions(family):
    snapshot = {"model": family, "active_mode": "set_bay"}
    old_settings = {"w": 800, "h": 1600, "d": 350, "t": 2}
    current_box = {"w": "820.25", "h": 1600.5, "d": 360.75}
    before = deepcopy((snapshot, old_settings, current_box))
    projected = api.project_receiving_manufacturing_request_settings(
        snapshot, old_settings, current_box,
    )
    assert {key: projected[key] for key in CURRENT} == CURRENT
    assert projected["t"] == 2
    projected["w"] = 1
    assert (snapshot, old_settings, current_box) == before


@pytest.mark.parametrize("family", ["金庫型", "RO", "UNKNOWN", ""])
def test_other_family_settings_unchanged(family):
    settings = {"w": 500, "h": 600, "d": 250}
    projected = api.project_receiving_manufacturing_request_settings(
        {"model": family}, settings, CURRENT,
    )
    assert projected == settings and projected is not settings


@pytest.mark.parametrize("raw", [True, 0, -1, "nan", "inf", None, "invalid"])
def test_malformed_live_receiving_source_fails_before_request_construction(raw):
    settings = {"w": 800}
    current_box = {**CURRENT, "w": raw}
    old = deepcopy((settings, current_box))
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_receiving_manufacturing_request_settings(
            {"model": "receiving"}, settings, current_box,
        )
    assert (settings, current_box) == old


def test_full_request_uses_same_settings_for_every_registered_alias():
    for model in ("受電箱", "receiving", "ReCeIvInG"):
        app = _fake_app()
        app._phase6_input_snapshot["model"] = model
        app._settings_values.update({"w": 800, "h": 1600, "d": 350})
        app._phase6_box_whd = dict(CURRENT)
        request = build_manufacturing_request(app)
        assert {axis: request.settings[axis] for axis in CURRENT} == CURRENT
        assert {axis: request.box_dimensions[axis] for axis in CURRENT} == CURRENT
        assert app._settings_values["w"] == 800


def test_gui_delegates_family_and_physical_source_to_engine_public_api():
    source = inspect.getsource(build_manufacturing_request)
    assert "manufacturing_api.project_receiving_manufacturing_request_settings(" in source
    assert 'in {"受電箱", "RECEIVING"}' not in source
    from ae_engine import operator_settings_transactions as domain
    assert "from gui_modules" not in inspect.getsource(domain)
