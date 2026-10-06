import pytest

import tools.control_transaction_production_executor as executor
import tools.control_transaction_request_ingress as ingress
from tools.execution_dispatch_ingress import (
    DispatchIngressRequest,
    plan_dispatch_ingress,
)


ISSUE = 1331
HEAD = "a" * 40
COORD = "c" * 40


def _interactive_request(**effect_overrides):
    effect = {
        "authority_kind": "USER_EXPLICIT",
        "authority_ref": "user-explicit:issue-1331",
    }
    effect.update(effect_overrides)
    return {
        "issue": ISSUE,
        "lane_id": "chatgpt.flowv2.work0",
        "effect": effect,
        "startup_transition": {
            "branch": "cleanup/2d-3d-sync",
            "head_sha": HEAD,
            "issued_at": "2026-10-06T15:00:00Z",
        },
    }


def _dispatch_request():
    return DispatchIngressRequest(
        issue=ISSUE,
        execution_intent="EXECUTE_TICKET",
        authority_kind="USER_EXPLICIT",
        authority_ref="user-explicit:issue-1331",
        source_branch="cleanup/2d-3d-sync",
        source_sha=HEAD,
        work_branch="work/issue-1331",
        target_branch="cleanup/2d-3d-sync",
        target_sha=HEAD,
        slot_id="worker.slot.0",
        created_at="2026-10-06T15:00:00Z",
    )


def test_dispatch_ready_is_a_trusted_request_kind():
    assert "DISPATCH_READY" in ingress.ALLOWED_KINDS


def test_interactive_dispatch_ready_binds_preflight_identity_and_lane_slot():
    request = ingress._build_dispatch_ready_ingress_request(
        _interactive_request(),
        execution_mode="INTERACTIVE",
    )
    plan = plan_dispatch_ingress(request)

    assert request.source_branch == "cleanup/2d-3d-sync"
    assert request.source_sha == HEAD
    assert request.target_branch == "cleanup/2d-3d-sync"
    assert request.target_sha == HEAD
    assert request.work_branch == "work/issue-1331"
    assert request.slot_id == "worker.slot.0"
    assert plan.record.generation == 1
    assert plan.record.state == "READY"
    assert plan.record.owner_kind == "UNCLAIMED"
    assert plan.record.owner_id == "NONE"
    assert plan.record.lease is None
    assert plan.record.next_action.kind == "ACQUIRE"


def test_interactive_dispatch_ready_rejects_slot_spoof():
    with pytest.raises(
        executor.ProductionExecutorError,
        match="slot_id conflicts with request lane",
    ):
        ingress._build_dispatch_ready_ingress_request(
            _interactive_request(slot_id="worker.slot.3"),
            execution_mode="INTERACTIVE",
        )


def test_dispatch_ready_writer_is_create_only_and_rebuilds_state(monkeypatch):
    ingress_request = _dispatch_request()
    planned = plan_dispatch_ingress(ingress_request).record
    reads = iter([
        (COORD, "tree-before", {}),
        ("d" * 40, "tree-after", {ISSUE: planned}),
    ])
    written = {}

    monkeypatch.setattr(executor, "_load_state", lambda *args, **kwargs: next(reads))

    def fake_write_state(repo, token, coord_branch, *, parent_sha, base_tree_sha, records, issue):
        written["parent_sha"] = parent_sha
        written["base_tree_sha"] = base_tree_sha
        written["records"] = records
        written["issue"] = issue
        return "d" * 40, "e" * 40

    monkeypatch.setattr(executor, "_write_state", fake_write_state)

    result = executor.dispatch_ready_missing_record(
        repo="looaeedr/whd",
        token="unused",
        coord_branch="coord/execution-v2",
        issue=ISSUE,
        expected_coord_head=COORD,
        ingress_request=ingress_request,
    )

    assert written["parent_sha"] == COORD
    assert written["issue"] == ISSUE
    assert written["records"][ISSUE].state == "READY"
    assert result["result"] == "APPLIED"
    assert result["kind"] == "DISPATCH_READY"
    assert result["post_generation"] == 1
    assert result["post_state"] == "READY"
    assert result["post_next_action"] == "ACQUIRE"
    assert result["lease_invocation_identity"] is None


def test_dispatch_ready_writer_rejects_existing_same_issue(monkeypatch):
    ingress_request = _dispatch_request()
    existing = plan_dispatch_ingress(ingress_request).record
    monkeypatch.setattr(
        executor,
        "_load_state",
        lambda *args, **kwargs: (COORD, "tree", {ISSUE: existing}),
    )

    with pytest.raises(
        executor.ControlTransactionConflict,
        match="requires missing ExecutionRecord",
    ):
        executor.dispatch_ready_missing_record(
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
            issue=ISSUE,
            expected_coord_head=COORD,
            ingress_request=ingress_request,
        )
