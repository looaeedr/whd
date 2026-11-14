"""#2517: original W/H/D/T manufacturing request source priority is Engine-owned."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import operator_settings_transactions as owner
from phase6_manufacturing_adapter import build_manufacturing_request
from tests.test_issue356_manufacturing_adapter import _fake_app


@pytest.mark.parametrize("snapshot,settings,box,expected", (
    (
        {"model": "金庫型", "w": 830.25, "t": "2.75"},
        {"w": 700, "h": 1600.25, "d": 300.75, "t": 1.5},
        {"w": 950.5, "h": 1800.75},
        {"w": 830.25, "h": 1800.75, "d": 300.75, "t": 2.75},
    ),
    (
        {"model": "受電箱"},
        {"w": 800.5, "h": 1600.25, "d": 355.125, "t": "1.75"},
        {},
        {"w": 800.5, "h": 1600.25, "d": 355.125, "t": 1.75},
    ),
    (
        {"model": "金庫型", "d": 350.125, "t": 2.35},
        {"w": 700.25, "h": 1600.5, "d": 500, "t": "invalid stale"},
        {"w": 860.75, "d": 450},
        {"w": 860.75, "h": 1600.5, "d": 350.125, "t": 2.35},
    ),
))
def test_public_engine_original_precedence_and_json_reload(snapshot, settings, box, expected):
    sources = deepcopy((snapshot, settings, box))
    reloaded = json.loads(json.dumps(sources, ensure_ascii=False))
    projected = api.project_operator_manufacturing_request_snapshot(
        snapshot, settings, box,
    )
    assert {key: projected[key] for key in ("w", "h", "d", "t")} == expected
    assert api.project_operator_manufacturing_request_snapshot(*reloaded) == projected
    assert (snapshot, settings, box) == sources
    projected["t"] = -10
    assert (snapshot, settings, box) == sources


def test_public_identity_and_no_gui_import():
    assert api.project_operator_manufacturing_request_snapshot is (
        owner.project_operator_manufacturing_request_snapshot
    )
    assert ae_engine.project_operator_manufacturing_request_snapshot is (
        owner.project_operator_manufacturing_request_snapshot
    )
    source = inspect.getsource(owner.project_operator_manufacturing_request_snapshot)
    assert "from gui_modules" not in source
    assert 'normalize_operator_source_dimension(raw_t, field="t")' in source


@pytest.mark.parametrize("bad", (None, True, False, "", "nan", "inf", -2, 0, {}, []))
def test_explicit_bad_snapshot_t_never_falls_back_and_does_not_mutate(bad):
    snapshot = {"model": "受電箱", "t": bad, "w": 850.75}
    settings = {"w": 800, "h": 1700, "d": 350, "t": 2.0}
    box = {"w": 900.5}
    original = deepcopy((snapshot, settings, box))
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_manufacturing_request_snapshot(snapshot, settings, box)
    assert (snapshot, settings, box) == original


def test_actual_gui_request_matches_engine_headless_dimensions_without_source_mutation():
    app = _fake_app()
    for axis in ("w", "h", "d", "t"):
        app._phase6_input_snapshot.pop(axis)
    app._settings_values.update({"h": 1710.125, "t": "1.75"})
    app._phase6_box_whd = {"w": 831.25, "d": 360.875}
    before = deepcopy((
        app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd,
    ))
    projected_settings = api.project_receiving_manufacturing_request_settings(
        *before,
    )
    direct = api.project_operator_manufacturing_request_snapshot(
        before[0], projected_settings, before[2],
    )
    request = build_manufacturing_request(app)
    # The immutable request freezes source lists (AssemblyJoint) to tuples;
    # compare their values without weakening that canonical frozen contract.
    request_snapshot = dict(request.input_snapshot)
    assert isinstance(request_snapshot["assembly_joints"], tuple)
    request_snapshot["assembly_joints"] = list(request_snapshot["assembly_joints"])
    assert request_snapshot == direct
    assert {key: request.input_snapshot[key] for key in ("w", "h", "d", "t")} == {
        "w": 831.25, "h": 1710.125, "d": 360.875, "t": 1.75,
    }
    assert (app._phase6_input_snapshot, app._settings_values, app._phase6_box_whd) == before
