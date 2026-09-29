from __future__ import annotations

from dataclasses import replace

import pytest

from tools.control_transaction import (
    ControlTransactionConflict,
    execute_transaction,
    prepare_transaction,
)
from tools.execution_record import (
    ActionSpec,
    LeaseState,
    execution_record_from_payload,
)


INV = "interactive:work1:issue1019:test"
OTHER = "interactive:work2:foreign"
NOW = "2026-09-29T13:20:00Z"


def _integrating_record(*, lease_invocation: str | None = INV, next_action=True):
    lease = None
    if lease_invocation is not None:
        lease = {
            "token": "lease-1019",
            "invocation_identity": lease_invocation,
            "expires_at": "2099-09-29T13:40:00Z",
        }
    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 7,
            "issue": 1019,
            "execution_intent": "EXECUTE_TICKET",
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work1",
            "lane_id": "chatgpt.flowv2.work1",
            "slot_id": "worker.slot.1",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": "a" * 40,
            "work_branch": "governance/issue1019-terminal-tail-drain-hardening",
            "head_sha": "b" * 40,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": "d" * 40,
            "state": "INTEGRATING",
            "semantic_state": "MERGED",
            "next_action": (
                {"kind": "FINALIZE", "args": {}, "display": "finalize terminal tail"}
                if next_action
                else None
            ),
            "lease": lease,
            "active_run": None,
            "transaction": None,
            "mutation_scope": None,
            "qa": {"last_accepted_run": 36570000001, "accepted_head_sha": "b" * 40},
            "blocker": None,
            "closure": {"merged_sha": "d" * 40, "issue_closed": False, "released_at": None},
            "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
            "recovery_history": [],
            "updated_at": "2026-09-29T13:19:00Z",
        }
    )


def _finalize_effect():
    return {
        "observed_target_sha": "d" * 40,
        "issue_closed": True,
        "issue_state": "closed",
        "issue_state_reason": "completed",
        "released_at": "2026-09-29T13:20:00Z",
        "updated_at": "2026-09-29T13:20:00Z",
    }


def test_finalize_clears_durable_owner_and_lane_on_done():
    record = _integrating_record()
    plan = prepare_transaction(record, kind="FINALIZE", transaction_id="tx-finalize", invocation_identity=INV)
    done = execute_transaction(record, plan, effect=_finalize_effect())

    assert done.state == "DONE"
    assert done.owner_kind == "NONE"
    assert done.owner_id == "NONE"
    assert done.lane_id is None
    assert done.lease is None
    assert done.next_action is None


def test_integrating_record_without_executable_next_action_is_rejected():
    with pytest.raises(ValueError, match="INTEGRATING record requires a next_action"):
        _integrating_record(next_action=False)


def test_trusted_finalize_requires_current_invocation_live_lease(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _integrating_record(lease_invocation=OTHER)
    close_called = False

    def fake_load_state(repo, token, coord_branch):
        return "c" * 40, "e" * 40, {1019: record}

    def fake_close(*args, **kwargs):
        nonlocal close_called
        close_called = True
        return _finalize_effect()

    monkeypatch.setattr(executor, "_load_state", fake_load_state)
    monkeypatch.setattr(executor, "_ensure_issue_closed_for_finalize", fake_close)

    with pytest.raises(ControlTransactionConflict, match="different invocation"):
        executor.execute_one(
            repo="looaeedr/whd",
            token="token",
            coord_branch="coord/execution-v2",
            issue=1019,
            kind="FINALIZE",
            lane_id="chatgpt.flowv2.work1",
            invocation_identity=INV,
            supplied_effect={},
        )

    assert close_called is False


def test_coord_cas_retry_does_not_repeat_finalize_side_effect(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _integrating_record()
    state = {"write_calls": 0, "close_calls": 0, "post": None, "load_calls": 0}

    def fake_load_state(repo, token, coord_branch):
        state["load_calls"] += 1
        # first load = pre-transaction; second = retry fresh coord; third = exact post-write readback
        if state["load_calls"] <= 2:
            return ("c" if state["load_calls"] == 1 else "f") * 40, "e" * 40, {1019: record}
        assert state["post"] is not None
        return "9" * 40, "8" * 40, {1019: state["post"]}

    def fake_close(*args, **kwargs):
        state["close_calls"] += 1
        return _finalize_effect()

    def fake_write_state(repo, token, coord_branch, *, parent_sha, base_tree_sha, records, issue):
        state["write_calls"] += 1
        state["post"] = records[issue]
        if state["write_calls"] == 1:
            raise ControlTransactionConflict("coord/execution-v2 ref advanced during transaction")
        return "9" * 40, "7" * 40

    monkeypatch.setattr(executor, "_load_state", fake_load_state)
    monkeypatch.setattr(executor, "_ensure_issue_closed_for_finalize", fake_close)
    monkeypatch.setattr(executor, "_write_state", fake_write_state)
    monkeypatch.setattr(
        executor,
        "_publish_transaction_progress",
        lambda *args, **kwargs: ("6" * 40, {
            "event": "EXIT",
            "liveness_state": "ENDED",
            "last_heartbeat_at": NOW,
            "heartbeat_expires_at": NOW,
        }),
    )

    result = executor.execute_one(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=1019,
        kind="FINALIZE",
        lane_id="chatgpt.flowv2.work1",
        invocation_identity=INV,
        supplied_effect={},
    )

    assert result["result"] == "APPLIED"
    assert result["post_state"] == "DONE"
    assert state["write_calls"] == 2
    assert state["close_calls"] == 1


def test_non_authority_monitor_failure_does_not_turn_applied_transaction_into_failure(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _integrating_record()
    post_holder = {"post": None, "loads": 0}

    def fake_load_state(repo, token, coord_branch):
        post_holder["loads"] += 1
        if post_holder["loads"] == 1:
            return "c" * 40, "e" * 40, {1019: record}
        return "9" * 40, "8" * 40, {1019: post_holder["post"]}

    def fake_write_state(repo, token, coord_branch, *, parent_sha, base_tree_sha, records, issue):
        post_holder["post"] = records[issue]
        return "9" * 40, "7" * 40

    monkeypatch.setattr(executor, "_load_state", fake_load_state)
    monkeypatch.setattr(executor, "_ensure_issue_closed_for_finalize", lambda *a, **k: _finalize_effect())
    monkeypatch.setattr(executor, "_write_state", fake_write_state)
    monkeypatch.setattr(executor, "_publish_transaction_progress", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("monitor unavailable")))

    result = executor.execute_one(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=1019,
        kind="FINALIZE",
        lane_id="chatgpt.flowv2.work1",
        invocation_identity=INV,
        supplied_effect={},
    )

    assert result["result"] == "APPLIED"
    assert result["post_state"] == "DONE"
    assert result["monitor_projection_status"] == "DEGRADED"
    assert "monitor unavailable" in result["monitor_projection_error"]
