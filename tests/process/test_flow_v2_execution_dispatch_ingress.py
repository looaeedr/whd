import pytest

from tools.execution_dispatch_ingress import (
    DispatchIngressError,
    DispatchIngressRequest,
    plan_dispatch_ingress,
)


def _request(**overrides):
    data = dict(
        issue=900,
        execution_intent="SCHEDULER_LANE",
        authority_kind="USER_EXPLICIT",
        authority_ref="user-request:flow-v2-test",
        source_branch="cleanup/2d-3d-sync",
        source_sha="a" * 40,
        work_branch="work/issue-900",
        target_branch="cleanup/2d-3d-sync",
        target_sha="c" * 40,
        parent_issue=None,
        slot_id=None,
        created_at="2026-09-28T03:00:00Z",
    )
    data.update(overrides)
    return DispatchIngressRequest(**data)


def test_explicit_authority_creates_unclaimed_ready_record_only():
    plan = plan_dispatch_ingress(_request())
    record = plan.record
    assert record.state == "READY"
    assert record.owner_kind == "UNCLAIMED"
    assert record.owner_id == "NONE"
    assert record.lane_id is None
    assert record.lease is None
    assert record.next_action.kind == "ACQUIRE"
    assert record.head_sha == record.source_sha
    assert plan.request_fingerprint
    assert plan.authority_fingerprint
    assert plan.record_fingerprint
    assert record.recovery_history[0]["authority_kind"] == "USER_EXPLICIT"


def test_open_issue_or_update_only_cannot_become_ready_work_by_inference():
    with pytest.raises(DispatchIngressError, match="authority_kind"):
        plan_dispatch_ingress(_request(authority_kind="OPEN_ISSUE"))
    with pytest.raises(DispatchIngressError, match="execution_intent"):
        plan_dispatch_ingress(_request(execution_intent="UPDATE_ONLY"))


def test_chain_successor_requires_exact_parent_issue():
    with pytest.raises(DispatchIngressError, match="parent_issue"):
        plan_dispatch_ingress(_request(authority_kind="CHAIN_SUCCESSOR"))
    plan = plan_dispatch_ingress(
        _request(authority_kind="CHAIN_SUCCESSOR", authority_ref="parent:842->900", parent_issue=842)
    )
    assert plan.record.chain.parent_issue == 842


def test_work_slot_assignment_requires_explicit_slot_and_preserves_it_as_tag():
    with pytest.raises(DispatchIngressError, match="slot_id"):
        plan_dispatch_ingress(_request(authority_kind="WORK_SLOT_ASSIGNMENT"))
    plan = plan_dispatch_ingress(
        _request(authority_kind="WORK_SLOT_ASSIGNMENT", authority_ref="user:/工作1 指派 #900", slot_id="worker.slot.1")
    )
    assert plan.record.slot_id == "worker.slot.1"
    assert plan.record.owner_kind == "UNCLAIMED"


def test_ingress_fingerprints_are_deterministic_and_authority_sensitive():
    first = plan_dispatch_ingress(_request())
    second = plan_dispatch_ingress(_request())
    changed = plan_dispatch_ingress(_request(authority_ref="user-request:different"))
    assert first.request_fingerprint == second.request_fingerprint
    assert first.record_fingerprint == second.record_fingerprint
    assert first.authority_fingerprint != changed.authority_fingerprint
