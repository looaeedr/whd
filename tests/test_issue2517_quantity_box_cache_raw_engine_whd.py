# -*- coding: utf-8 -*-
"""#2517 Receiving Quantity W/H/D cache is validated by public Engine first."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_settings_transactions as owner
import fold_designer_bridge as bridge


ORIGINAL = {"w": "825.25", "h": 1600.5, "d": "375.75"}
STALE = {"w": 500, "h": 600, "d": 200}


def _app(box, *, mode="quantity", has_cache=True):
    snapshot = {"model": "受電箱", "active_mode": mode}
    if has_cache:
        snapshot["receiving_quantity_box"] = deepcopy(box)
    previous = dict(STALE)
    return SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _phase6_box_whd=previous,
    ), previous


@pytest.mark.parametrize("mode", ["quantity"])
def test_real_quantity_cache_uses_engine_confirmed_fractional_source_without_rebinding(mode):
    app, cache = _app(ORIGINAL, mode=mode)
    original = deepcopy(app._phase6_input_snapshot)
    actual = bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE)
    assert actual is cache is app._phase6_box_whd
    assert actual == {"w": 825.25, "h": 1600.5, "d": 375.75}
    assert actual == api.normalize_operator_live_box_dimensions(ORIGINAL)
    assert app._phase6_input_snapshot == original


@pytest.mark.parametrize("axis", ["w", "h", "d"])
@pytest.mark.parametrize("bad", [
    True, False, 0, -1, "0", "nan", "inf", float("inf"),
    float("nan"), None, "", "malformed",
])
def test_invalid_quantity_source_rejected_before_changing_any_cache(axis, bad):
    bad_box = {**ORIGINAL, axis: bad}
    app, cache = _app(bad_box)
    before = deepcopy((app._phase6_input_snapshot, cache))
    with pytest.raises(ValueError, match="包外尺寸"):
        bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE)
    assert (app._phase6_input_snapshot, cache) == before
    assert app._phase6_box_whd is cache


@pytest.mark.parametrize("bad_box", [{}, [], "bad-box", 2, True])
def test_explicit_malformed_common_box_does_not_fall_back_to_stale_header(bad_box):
    app, cache = _app(bad_box)
    prior = deepcopy((app._phase6_input_snapshot, cache))
    with pytest.raises((TypeError, ValueError)):
        bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE)
    assert (app._phase6_input_snapshot, cache) == prior
    assert app._phase6_box_whd is cache


def test_missing_required_axis_in_explicit_source_stays_invalid():
    app, cache = _app({"w": 800, "h": 1600})
    before = deepcopy(cache)
    with pytest.raises(ValueError, match="D 包外尺寸"):
        bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE)
    assert cache == before


def test_legacy_quantity_without_common_source_preserves_existing_initialization():
    app, cache = _app(None, has_cache=False)
    assert bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE) is cache
    assert cache == STALE
    app._phase6_input_snapshot["receiving_quantity_box"] = None
    assert bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE) is cache
    assert cache == STALE


def test_other_mode_and_other_mapping_do_not_use_irrelevant_quantity_box():
    app, cache = _app({"w": True}, mode="set_bay")
    assert bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE) is cache
    assert cache == STALE
    original_source = deepcopy(app._phase6_input_snapshot)
    pending = {"live": 1}
    app._phase6_pending_settings = pending
    assert bridge._phase6_replace_mapping(
        app, "_phase6_pending_settings", {"live": 2},
    ) is pending
    assert pending == {"live": 2}
    assert app._phase6_input_snapshot == original_source


def test_new_mapping_creation_does_not_precede_engine_source_validation():
    app, _ = _app({"w": True, "h": 1600, "d": 350})
    del app._phase6_box_whd
    with pytest.raises(ValueError):
        bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE)
    assert not hasattr(app, "_phase6_box_whd")


def test_json_saved_quantity_matches_direct_headless_engine_dimensions():
    saved = json.loads(json.dumps({"model": "受電箱",
        "active_mode": "quantity", "receiving_quantity_box": ORIGINAL}))
    app, cache = _app(saved["receiving_quantity_box"])
    expected = api.normalize_operator_live_box_dimensions(saved["receiving_quantity_box"])
    assert bridge._phase6_replace_mapping(app, "_phase6_box_whd", STALE) is cache
    assert cache == expected
    assert saved["receiving_quantity_box"] == ORIGINAL


def test_gui_cache_has_no_parallel_physical_number_parser():
    src = inspect.getsource(bridge._phase6_replace_mapping)
    assert api.normalize_operator_live_box_dimensions is owner.normalize_operator_live_box_dimensions
    assert "manufacturing_api.normalize_operator_live_box_dimensions(" in src
    assert 'float(source["receiving_quantity_box"][axis])' not in src
    assert 'source.get("receiving_quantity_box") is not None' in src
