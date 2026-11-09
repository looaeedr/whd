"""#2517: WRAP presence/Joint commits use original Engine boolean source."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
from ae_engine.endcap_bottom_wrap_state import (
    commit_endcap_bottom_wrap,
    commit_endcap_bottom_wrap_joint,
    normalize_endcap_bottom_wrap_state,
)
from phase6_endcap_semantics import (
    commit_endcap_bottom_wrap_joint as gui_joint_port,
)


def _source():
    return {"model": "受電箱"}


def _state():
    return normalize_endcap_bottom_wrap_state(_source())


def test_single_canonical_public_engine_owner_and_gui_delegate():
    assert api.commit_endcap_bottom_wrap is commit_endcap_bottom_wrap
    assert api.commit_endcap_bottom_wrap_joint is commit_endcap_bottom_wrap_joint
    assert "manufacturing_api.commit_endcap_bottom_wrap_joint(" in inspect.getsource(
        gui_joint_port
    )


@pytest.mark.parametrize("raw,enabled", [
    (False, False), ("false", False), (" off ", False), ("0", False),
    (0, False), (True, True), ("true", True), ("yes", True), ("1", True),
    (1, True),
])
@pytest.mark.parametrize("part", ["head", "tail"])
def test_raw_joint_flag_selects_actual_assembly_relation(raw, enabled, part):
    # Assembly Intent is an independent Engine topology gate: default
    # INSERT_OVERLAY accepts only INSERT; WRAP_OVERLAY accepts only WRAP.
    original = {
        **_source(),
        "assembly_type": "WRAP_OVERLAY" if enabled else "INSERT_OVERLAY",
    }
    prior = deepcopy(original)
    committed = api.commit_endcap_bottom_wrap_joint(original, part, raw)
    relation = edge_relation_for_part(committed, part, "BOTTOM")
    assert relation == (
        AssemblyJointRelation.WRAP if enabled else AssemblyJointRelation.INSERT
    )
    assert original == prior
    restored = json.loads(json.dumps(committed))
    assert edge_relation_for_part(restored, part, "BOTTOM") == relation


@pytest.mark.parametrize("raw,enabled", [
    (False, False), ("false", False), ("0", False),
    (True, True), ("true", True), ("1", True),
])
def test_raw_linked_head_tail_presence_is_engine_owned_and_serializable(raw, enabled):
    state = _state()
    original = deepcopy(state)
    committed = api.commit_endcap_bottom_wrap(
        state, "head", enabled=raw,
    )
    assert committed is state
    assert state["head"]["enabled"] is enabled
    assert state["tail"]["enabled"] is enabled
    assert original["head"]["enabled"] is True
    restored = json.loads(json.dumps(state))
    assert restored["head"]["enabled"] is enabled
    assert restored["tail"]["enabled"] is enabled


@pytest.mark.parametrize("invalid", [
    "maybe", "1.5", "NaN", "inf", 2, -1,
    float("nan"), float("inf"), None, [], {},
])
def test_illegal_joint_enabled_never_creates_wrap_or_mutates_source(invalid):
    source = _source()
    before = deepcopy(source)
    with pytest.raises((ValueError, TypeError)):
        api.commit_endcap_bottom_wrap_joint(source, "head", invalid)
    assert source == before


@pytest.mark.parametrize("invalid", [
    "maybe", "1.5", "NaN", "inf", 2, -1,
    float("nan"), float("inf"), [], {},
])
def test_illegal_enabled_and_valid_reserve_have_no_partial_head_tail_mutation(
    invalid,
):
    state = _state()
    before = deepcopy(state)
    with pytest.raises((ValueError, TypeError)):
        api.commit_endcap_bottom_wrap(
            state, "head", enabled=invalid,
            reserve_u="2.25", reserve_v="1.75",
        )
    assert state == before


def test_existing_legacy_readback_contract_not_rewritten_by_new_commit_gate():
    source = _source()
    saved = normalize_endcap_bottom_wrap_state(source)
    before = deepcopy(saved)
    new = api.commit_endcap_bottom_wrap(
        deepcopy(saved), "head", enabled="false",
    )
    assert saved == before
    assert api.resolve_endcap_bottom_wrap(
        {"model": "受電箱", "endcap_bottom_wrap": new}, "head",
    )["enabled"] is False


@pytest.mark.parametrize("intent,enabled", [
    ("INSERT_OVERLAY", True),
    ("WRAP_OVERLAY", False),
])
def test_raw_flag_never_bypasses_canonical_assembly_intent_policy(intent, enabled):
    source = {**_source(), "assembly_type": intent}
    before = deepcopy(source)
    with pytest.raises(ValueError, match="not allowed"):
        api.commit_endcap_bottom_wrap_joint(source, "head", enabled)
    assert source == before
