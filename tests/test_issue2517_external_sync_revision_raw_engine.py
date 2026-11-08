# -*- coding: utf-8 -*-
"""#2517 Settings external revision cannot be truncated before Engine sync."""
from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from phase6_settings_service import Phase6SettingsTransactionService
from phase6_settings_transitions import plan_external_sync


def packet(revision):
    return {"origin": "main_gui", "revision": revision,
            "transaction_id": "main:source", "delta": {
                "settings": {"w": 800.125, "t": 2.375},
            }}


@pytest.mark.parametrize("value", [
    True, False, 1.0, 2.0, 2.5, 3.75,
    float("nan"), float("inf"), float("-inf"),
    "2.5", "2_0", "0x2", "nan", "inf", "false",
    [], {}, (), object(),
])
def test_illegal_external_revision_cannot_consume_a_transaction_or_change_state(value):
    source = packet(value)
    before = deepcopy(source)
    owner = api.plan_operator_external_sync(source, last_external_revision=1)
    adapter = plan_external_sync(source, last_external_revision=1)
    assert owner == adapter
    assert owner.accepted is False
    assert owner.reason == "INVALID_REVISION"
    assert owner.revision == 1
    assert owner.settings == {}
    assert source == before
    service = Phase6SettingsTransactionService(last_external_revision=1)
    service_plan = service.plan_external_sync(source)
    assert service_plan == owner
    assert service.last_external_revision == 1
    assert service.last_external_transaction_id == ""


@pytest.mark.parametrize("value,expected", [
    (2, 2), ("2", 2), (" 2 ", 2), ("002", 2),
    ("+2", 2), (3, 3), ("3", 3),
])
def test_valid_integer_sources_follow_original_public_engine_delta(value, expected):
    source = packet(value)
    before = deepcopy(source)
    plan = api.plan_operator_external_sync(source, last_external_revision=1)
    assert plan == plan_external_sync(source, last_external_revision=1)
    assert plan.accepted is True and plan.reason == "OK"
    assert plan.revision == expected
    assert plan.settings == {"w": 800.125, "t": 2.375}
    assert source == before


@pytest.mark.parametrize("value,revision", [(0, 0), ("0", 0), (1, 1), ("1", 1), ("-1", -1)])
def test_stale_revision_order_keeps_prior_response(value, revision):
    result = api.plan_operator_external_sync(packet(value), last_external_revision=1)
    assert (result.accepted, result.reason, result.revision) == (
        False, "STALE_REVISION", revision,
    )


@pytest.mark.parametrize("value", [None, ""])
def test_existing_empty_revision_remains_stale_zero(value):
    plan = api.plan_operator_external_sync(packet(value), last_external_revision=1)
    assert plan.reason == "STALE_REVISION"
    assert plan.revision == 0


def test_revision_pipeline_recovers_after_rejected_false_or_fractional_input():
    service = Phase6SettingsTransactionService(last_external_revision=1)
    for raw in (True, 2.9, "2_0"):
        rejected = service.plan_external_sync(packet(raw))
        assert rejected.reason == "INVALID_REVISION"
        assert service.last_external_revision == 1
    accepted = service.plan_external_sync(packet(2))
    assert accepted.reason == "OK" and accepted.revision == 2
    assert service.last_external_revision == 2
    assert service.last_external_transaction_id == "main:source"
    saved = json.loads(json.dumps(packet(3)))
    next_plan = service.plan_external_sync(saved)
    assert next_plan.accepted is True
    assert service.last_external_revision == 3
    retry = service.plan_external_sync(packet(2))
    assert retry.reason == "STALE_REVISION"
    assert service.last_external_revision == 3


def test_other_origin_is_rejected_before_revision_source_decision():
    source = packet(2.5)
    source["origin"] = "CADSplit"
    result = api.plan_operator_external_sync(source, last_external_revision=1)
    assert result.reason == "WRONG_ORIGIN"
    assert not result.accepted


def test_external_revision_format_gate_is_inside_original_engine_public_owner():
    import ae_engine.operator_settings_transactions as owner
    source = inspect.getsource(owner.plan_operator_external_sync)
    assert "_external_sync_revision_number(" in source
    assert 'revision = int(raw.get("revision"' not in source
    ui = inspect.getsource(plan_external_sync)
    assert "manufacturing_api.plan_operator_external_sync(" in ui
