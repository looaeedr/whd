"""#2517: a hot manufacturing cache must never override the live Family source."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from phase6_manufacturing_adapter import (
    _cache_service_for_app,
    build_manufacturing_cache_key,
    resolve_manufacturing_for_app,
)
from phase6_manufacturing_cache import ManufacturingCacheService
from tests.test_issue359_manufacturing_cache_service import _app, _result


class UnreadableFamilyControl:
    def get(self):
        raise RuntimeError("destroyed live Tk family selector")


def test_live_family_changes_cache_key_despite_unchanged_saved_and_stale_settings():
    app = _app()
    app._settings_values["model"] = "受電箱"
    saved = deepcopy(app._phase6_input_snapshot)
    vault = build_manufacturing_cache_key(app)
    app.baseline_model_var.value = "受電箱"
    receiving = build_manufacturing_cache_key(app)
    assert receiving != vault
    assert app._phase6_input_snapshot == saved
    app.baseline_model_var.value = "金庫型"
    assert build_manufacturing_cache_key(app) == vault


def test_unreadable_live_family_control_rejected_even_when_prior_cache_is_hot():
    app = _app()
    service = ManufacturingCacheService()
    key = build_manufacturing_cache_key(app)
    stale_geometry = object()
    service.store(key, _result(stale_geometry))
    app.baseline_model_var = UnreadableFamilyControl()
    with pytest.raises(
        ValueError, match="MANUFACTURING_OPERATOR_SOURCE_READ_FAILED:baseline_model_var",
    ):
        resolve_manufacturing_for_app(app, cache_service=service)
    # Cache contents remain intact; the invalid live source may never consume it.
    assert service.lookup(key).result.geometry is stale_geometry


def test_live_receiving_alias_controls_engine_history_policy_without_mutating_project():
    app = _app()
    app._phase6_input_snapshot["active_mode"] = "set_bay"
    saved = deepcopy(app._phase6_input_snapshot)
    assert _cache_service_for_app(app).max_entries == 1
    for live in ("受電箱", "RECEIVING", "receiving", " ReCeIvInG "):
        app.baseline_model_var.value = live
        assert _cache_service_for_app(app).max_entries == 2
    assert app._phase6_input_snapshot == saved


def test_public_engine_cache_key_uses_saved_family_not_stale_settings_mirror():
    kwargs = dict(
        input_snapshot={"model": "金庫型", "w": 800, "h": 1600, "d": 350},
        settings_values={"model": "受電箱", "t": 2},
        working_box={"w": 800, "h": 1600, "d": 350},
        corner_state={}, endcap_fw_state={}, endcap_bottom_wrap_state={},
        available_parts=("box_body",), part_profiles={"box_body": {}},
        assembly_intent="INSERT", ignore_fixed_corner=False, relief_clearance=0,
    )
    unchanged = deepcopy(kwargs)
    vault = manufacturing_api.manufacturing_state_fingerprint(**kwargs)
    kwargs["settings_values"] = {"model": "金庫型", "t": 2}
    assert manufacturing_api.manufacturing_state_fingerprint(**kwargs) == vault
    kwargs["input_snapshot"] = {"model": "受電箱", "w": 800, "h": 1600, "d": 350}
    assert manufacturing_api.manufacturing_state_fingerprint(**kwargs) != vault
    assert unchanged["input_snapshot"]["model"] == "金庫型"


def test_readable_blank_family_uses_persisted_family_in_cache_key():
    app = _app()
    app.baseline_model_var.value = ""
    saved = build_manufacturing_cache_key(app)
    app.baseline_model_var.value = "金庫型"
    assert build_manufacturing_cache_key(app) == saved
    app._phase6_input_snapshot["model"] = "受電箱"
    app.baseline_model_var.value = ""
    assert build_manufacturing_cache_key(app) != saved


def test_engine_cache_policy_recognizes_registered_receiving_aliases():
    for model in ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"):
        policy = manufacturing_api.plan_manufacturing_cache_source(
            {"model": model, "active_mode": "set_bay"},
        )
        assert policy.history_capacity == 2
        assert policy.witness_required is False
    assert manufacturing_api.plan_manufacturing_cache_source(
        {"model": "金庫型", "active_mode": "set_bay"},
    ).history_capacity == 1
