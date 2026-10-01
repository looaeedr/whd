from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tools.control_transaction import (
    ControlTransactionConflict,
    execute_transaction,
    prepare_transaction,
)
from tools.execution_record import (
    ExecutionRecordError,
    MutationScopeState,
    execution_record_from_payload,
)

ROOT = Path(__file__).resolve().parents[2]
INV = "interactive:work1:issue1019:test"
LANE = "chatgpt.flowv2.work1"


def _payload(**overrides):
    payload = {
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 3,
        "issue": 1019,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": LANE,
        "lane_id": LANE,
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "governance/issue1019-terminal-tail-drain-hardening",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "ACTIVE",
        "semantic_state": "IMPLEMENTING",
        "next_action": {
            "kind": "APPLY_COMMIT",
            "args": {},
            "display": "continue",
        },
        "lease": {
            "token": "lease-1019",
            "invocation_identity": INV,
            "expires_at": "2026-09-29T14:00:00Z",
        },
        "active_run": None,
        "transaction": None,
        "mutation_scope": None,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-29T13:20:00Z",
    }
    payload.update(overrides)
    return payload


def _record(**overrides):
    return execution_record_from_payload(_payload(**overrides))


def _ready_record():
    return _record(
        owner_kind="UNCLAIMED",
        owner_id="NONE",
        lane_id=None,
        state="READY",
        semantic_state="READY",
        lease=None,
        next_action={"kind": "ACQUIRE", "args": {}, "display": "acquire"},
    )


def _integrating_finalize_record(*, lease_invocation: str = INV):
    return _record(
        state="INTEGRATING",
        semantic_state="MERGED",
        next_action={"kind": "FINALIZE", "args": {}, "display": "finalize"},
        lease={
            "token": "lease-finalize",
            "invocation_identity": lease_invocation,
            "expires_at": "2026-09-29T14:00:00Z",
        },
        qa={"last_accepted_run": 36570000001, "accepted_head_sha": "b" * 40},
        closure={"merged_sha": "c" * 40, "issue_closed": False, "released_at": None},
    )


def test_atomic_acquire_can_reserve_paths_in_same_admission_transaction():
    record = _ready_record()
    plan = prepare_transaction(
        record,
        kind="ACQUIRE",
        transaction_id="tx-admission",
        invocation_identity=INV,
    )
    updated = execute_transaction(
        record,
        plan,
        effect={
            "observed_at": "2026-09-29T13:21:00Z",
            "updated_at": "2026-09-29T13:21:00Z",
            "owner_kind": "SCHEDULER",
            "owner_id": LANE,
            "lane_id": LANE,
            "slot_id": "worker.slot.1",
            "lease": {
                "token": "lease-new",
                "invocation_identity": INV,
                "expires_at": "2026-09-29T13:36:00Z",
            },
            "admission_reservation": {
                "target_branch": "cleanup/2d-3d-sync",
                "base_sha": "c" * 40,
                "write_paths": ["tools/control_transaction.py"],
                "delete_paths": [],
            },
            "next_action": {
                "kind": "START_BRANCH",
                "args": {},
                "display": "create exact tested work branch after root freeze",
            },
        },
    )

    assert updated.state == "ACTIVE"
    assert updated.semantic_state == "PATHS_RESERVED"
    assert updated.lease.invocation_identity == INV
    assert updated.mutation_scope.reservation_state == "ACTIVE"
    assert updated.mutation_scope.write_paths == ("tools/control_transaction.py",)
    assert updated.next_action.kind == "START_BRANCH"


def test_atomic_acquire_reservation_still_checks_cross_issue_conflicts(monkeypatch):
    import tools.control_transaction_production_executor as executor

    candidate = _ready_record()
    other = _record(
        issue=1017,
        slot_id="worker.slot.0",
        work_branch="governance/issue1017-root-local-first",
        mutation_scope={
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "c" * 40,
            "write_paths": ["tools/control_transaction.py"],
            "delete_paths": [],
            "reservation_state": "ACTIVE",
        },
    )
    monkeypatch.setattr(
        executor,
        "_load_state",
        lambda *args, **kwargs: ("f" * 40, "e" * 40, {1019: candidate, 1017: other}),
    )
    monkeypatch.setattr(
        executor,
        "_write_state",
        lambda *args, **kwargs: pytest.fail("conflicting admission must not write coord"),
    )

    # #1093 ACTIVE_OWNING_ISSUE_STICKINESS_HARD_GATE_V1 now wins earlier:
    # the same durable lane may not pivot to a READY foreign Issue merely to
    # discover its path conflict. Foreign mutation is rejected before prepare.
    with pytest.raises(ControlTransactionConflict, match="ACTIVE_OWNING_ISSUE_NO_PIVOT"):
        executor._execute_one_attempt(
            repo="looaeedr/whd",
            token="token",
            coord_branch="coord/execution-v2",
            issue=1019,
            kind="ACQUIRE",
            lane_id=LANE,
            invocation_identity=INV,
            supplied_effect={
                "admission_reservation": {
                    "target_branch": "cleanup/2d-3d-sync",
                    "base_sha": "c" * 40,
                    "write_paths": ["tools/control_transaction.py"],
                    "delete_paths": [],
                },
                "next_action": {
                    "kind": "START_BRANCH",
                    "args": {},
                    "display": "start",
                },
            },
        )


def test_integrating_record_without_structured_next_action_is_rejected():
    with pytest.raises(ExecutionRecordError, match="INTEGRATING record requires a next_action"):
        execution_record_from_payload(
            _payload(
                state="INTEGRATING",
                semantic_state="MERGED",
                next_action=None,
            )
        )


def test_finalize_releases_durable_owner_and_lane():
    record = _integrating_finalize_record()
    plan = prepare_transaction(
        record,
        kind="FINALIZE",
        transaction_id="tx-finalize",
        invocation_identity=INV,
    )
    done = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": "2026-09-29T13:22:00Z",
            "observed_target_sha": "c" * 40,
            "issue_closed": True,
            "issue_state": "closed",
            "issue_state_reason": "completed",
            "released_at": "2026-09-29T13:22:00Z",
        },
    )

    assert done.state == "DONE"
    assert done.owner_kind == "NONE"
    assert done.owner_id == "NONE"
    assert done.lane_id is None
    assert done.lease is None


def test_trusted_finalize_checks_current_invocation_lease_before_issue_close(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _integrating_finalize_record(lease_invocation="interactive:work0:other")
    monkeypatch.setattr(
        executor,
        "_load_state",
        lambda *args, **kwargs: ("f" * 40, "e" * 40, {1019: record}),
    )
    called = {"close": False}

    def forbidden_close(*args, **kwargs):
        called["close"] = True
        raise AssertionError("issue close must not run for a foreign lease")

    monkeypatch.setattr(executor, "_ensure_issue_closed_for_finalize", forbidden_close)

    with pytest.raises(ControlTransactionConflict, match="different invocation"):
        executor._execute_one_attempt(
            repo="looaeedr/whd",
            token="token",
            coord_branch="coord/execution-v2",
            issue=1019,
            kind="FINALIZE",
            lane_id=LANE,
            invocation_identity=INV,
            supplied_effect={},
        )
    assert called["close"] is False


def test_sync_target_reconciles_already_applied_merge_after_coord_cas_loss(monkeypatch):
    import tools.control_transaction_production_executor as executor

    record = _record(
        state="INTEGRATING",
        semantic_state="TARGET_DRIFT_REQUIRES_SYNC",
        next_action={
            "kind": "SYNC_TARGET",
            "args": {
                "target_sha": "c" * 40,
                "target_branch": "cleanup/2d-3d-sync",
                "pr_number": 1001,
                "qa_workflow": ".github/workflows/phase6-bridge-anti-regrowth.yml",
            },
            "display": "sync target",
        },
        qa={"last_accepted_run": 36570000001, "accepted_head_sha": "b" * 40},
    )

    def fake_head(repo, token, branch):
        if branch == "cleanup/2d-3d-sync":
            return "c" * 40
        if branch == record.work_branch:
            return "d" * 40
        raise AssertionError(branch)

    monkeypatch.setattr(executor, "_read_branch_head", fake_head)
    monkeypatch.setattr(executor, "_is_ancestor", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        executor,
        "_api",
        lambda *args, **kwargs: pytest.fail("already-applied reconciliation must not POST another merge"),
    )

    effect = executor._trusted_sync_target_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=INV,
    )
    assert effect["head_sha"] == "d" * 40
    assert effect["semantic_state"] == "QA_INVALIDATED_BY_TARGET_SYNC"
    assert effect["next_action"]["kind"] == "START_QA"


def test_monitor_failure_does_not_turn_committed_transaction_into_failed(monkeypatch):
    import tools.control_transaction_production_executor as executor

    initial = _record()
    written = {}
    loads = {"count": 0}

    def fake_load(*args, **kwargs):
        loads["count"] += 1
        if loads["count"] == 1:
            return "f" * 40, "e" * 40, {1019: initial}
        return "1" * 40, "2" * 40, {1019: written["record"]}

    def fake_write(repo, token, coord_branch, *, parent_sha, base_tree_sha, records, issue):
        written["record"] = records[issue]
        return "1" * 40, "3" * 40

    monkeypatch.setattr(executor, "_load_state", fake_load)
    monkeypatch.setattr(executor, "_write_state", fake_write)
    monkeypatch.setattr(
        executor,
        "_publish_transaction_progress",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("monitor unavailable")),
    )

    result = executor._execute_one_attempt(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=1019,
        kind="RECONCILE",
        lane_id=LANE,
        invocation_identity=INV,
        supplied_effect={
            "observed_work_branch": initial.work_branch,
            "observed_head_sha": initial.head_sha,
            "observed_target_sha": initial.target_sha,
            "next_action": {
                "kind": "APPLY_COMMIT",
                "args": {},
                "display": "continue",
            },
        },
    )

    assert result["result"] == "APPLIED"
    assert result["runtime_observation_status"] == "DEGRADED"
    assert "monitor unavailable" in result["runtime_observation_error"]


def test_trusted_side_effect_coord_race_retries_inside_same_workflow(monkeypatch):
    import tools.control_transaction_production_executor as executor

    calls = {"count": 0}

    def fake_attempt(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ControlTransactionConflict(
                "coord/execution-v2 ref advanced during transaction"
            )
        return {
            "schema": executor.RESULT_SCHEMA,
            "result": "APPLIED",
            "post_generation": 9,
            "post_state": "DONE",
            "post_next_action": None,
            "lease_invocation_identity": None,
        }

    monkeypatch.setattr(executor, "_execute_one_attempt", fake_attempt)
    result = executor.execute_one(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=1019,
        kind="FINALIZE",
        lane_id=LANE,
        invocation_identity=INV,
        supplied_effect={},
    )
    assert result["attempt"] == 2
    assert calls["count"] == 2


def test_merge_terminal_tail_is_drained_without_second_push_request(monkeypatch):
    import tools.control_transaction_production_executor as executor

    calls = []

    def fake_attempt(**kwargs):
        calls.append(kwargs["kind"])
        if kwargs["kind"] == "MERGE":
            return {
                "schema": executor.RESULT_SCHEMA,
                "result": "APPLIED",
                "post_generation": 7,
                "post_state": "INTEGRATING",
                "post_next_action": "FINALIZE",
                "lease_invocation_identity": INV,
            }
        assert kwargs["kind"] == "FINALIZE"
        return {
            "schema": executor.RESULT_SCHEMA,
            "result": "APPLIED",
            "coord_commit_sha": "9" * 40,
            "post_generation": 8,
            "post_state": "DONE",
            "post_next_action": None,
            "lease_invocation_identity": None,
            "runtime_observation_status": "APPLIED",
        }

    monkeypatch.setattr(executor, "_execute_one_attempt", fake_attempt)
    result = executor.execute_one(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=1019,
        kind="MERGE",
        lane_id=LANE,
        invocation_identity=INV,
        supplied_effect={},
    )

    assert calls == ["MERGE", "FINALIZE"]
    assert result["terminal_tail_drained"] is True
    assert result["post_state"] == "DONE"
    assert result["post_next_action"] is None


def test_flow_skill_marks_admission_as_session_level_and_atomic():
    text = (
        ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md"
    ).read_text(encoding="utf-8")
    assert "INVOCATION_ADMISSION_SESSION_V1" in text
    assert "invocation/session-level gate" in text
    assert "atomic ACQUIRE + admission reservation" in text
    assert "admission_reservation" in text
