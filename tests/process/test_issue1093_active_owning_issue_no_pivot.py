from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tools.control_transaction import (
    ControlTransactionConflict,
    execute_transaction,
    prepare_transaction,
)
from tools.execution_invocation_exit import (
    InvocationExitError,
    assert_active_owning_issue_sticky,
    classify_invocation_exit,
)
from tools.execution_record import ActionSpec, TransactionState, execution_record_from_payload

ROOT = Path(__file__).resolve().parents[2]
CURRENT = 1090
FOREIGN = 1062
LANE = "chatgpt.flowv2.work0"
INV = "interactive:work0:issue1090:test"
NOW = "2026-10-01T16:30:00Z"


def _record(issue: int, *, next_action: str = "APPLY_COMMIT"):
    args = {"candidate_commit_sha": "d" * 40} if next_action == "APPLY_COMMIT" else {"reason": "stale recovery"}
    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 7,
            "issue": issue,
            "execution_intent": "EXECUTE_TICKET",
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work0",
            "lane_id": LANE,
            "slot_id": "worker.slot.0",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": "a" * 40,
            "work_branch": f"work/issue-{issue}",
            "head_sha": "b" * 40,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": "c" * 40,
            "state": "ACTIVE",
            "semantic_state": "ROOT_TESTED_DIFF_APPLIED",
            "next_action": {"kind": next_action, "args": args, "display": "continue exact action"},
            "lease": {
                "token": f"lease-{issue}",
                "invocation_identity": INV,
                "expires_at": "2026-10-01T16:40:00Z",
            },
            "active_run": None,
            "transaction": None,
            "mutation_scope": None,
            "qa": {"last_accepted_run": None, "accepted_head_sha": None},
            "blocker": None,
            "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
            "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
            "recovery_history": [],
            "updated_at": "2026-10-01T16:29:00Z",
        }
    )


def test_apply_commit_next_action_forbids_host_boundary_yield():
    record = _record(CURRENT)
    prior = TransactionState(
        id="tx-prior",
        kind="APPLY_COMMIT",
        status="RECONCILED",
        expected_fingerprint="f" * 64,
        invocation_identity=INV,
    )
    decision = classify_invocation_exit(
        replace(record, transaction=prior),
        invocation_identity=INV,
        now=NOW,
        host_boundary=True,
    )
    assert decision.decision == "CONTINUE_EXECUTION"
    assert decision.may_return is False
    assert decision.requires_yield is False
    assert decision.next_action_kind == "APPLY_COMMIT"


def test_active_owning_issue_rejects_foreign_reconcile_but_allows_same_issue_and_read_only():
    record = _record(CURRENT)
    with pytest.raises(InvocationExitError, match="ACTIVE_OWNING_ISSUE_NO_PIVOT"):
        assert_active_owning_issue_sticky(
            record,
            requested_issue=FOREIGN,
            requested_action_kind="RECONCILE",
        )
    assert assert_active_owning_issue_sticky(
        record,
        requested_issue=CURRENT,
        requested_action_kind="RECONCILE",
    )
    assert assert_active_owning_issue_sticky(
        record,
        requested_issue=FOREIGN,
        requested_action_kind="READ_ONLY_STATUS",
    )


def test_durably_yielded_nonterminal_leaf_allows_foreign_issue_pivot():
    current = _record(CURRENT)
    yielded = replace(
        current,
        lease=None,
        transaction=TransactionState(
            id="tx-yield-current",
            kind="YIELD",
            status="RECONCILED",
            expected_fingerprint="f" * 64,
            invocation_identity=INV,
        ),
    )

    assert assert_active_owning_issue_sticky(
        yielded,
        requested_issue=FOREIGN,
        requested_action_kind="RECONCILE",
    )


def test_production_executor_blocks_foreign_reconcile_before_prepare_or_write(monkeypatch):
    from tools import control_transaction_production_executor as executor

    current = _record(CURRENT)
    foreign = _record(FOREIGN, next_action="RECONCILE")
    monkeypatch.setattr(
        executor,
        "_load_state",
        lambda *args, **kwargs: ("f" * 40, "e" * 40, {CURRENT: current, FOREIGN: foreign}),
    )
    monkeypatch.setattr(
        executor,
        "prepare_transaction",
        lambda *args, **kwargs: pytest.fail("foreign transaction must be blocked before prepare_transaction"),
    )
    monkeypatch.setattr(
        executor,
        "_write_state",
        lambda *args, **kwargs: pytest.fail("foreign transaction must not write coord"),
    )

    with pytest.raises(ControlTransactionConflict, match="ACTIVE_OWNING_ISSUE_NO_PIVOT"):
        executor._execute_one_attempt(
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
            issue=FOREIGN,
            kind="RECONCILE",
            lane_id=LANE,
            invocation_identity=INV,
            supplied_effect={
                "observed_work_branch": foreign.work_branch,
                "observed_head_sha": foreign.head_sha,
                "observed_target_sha": foreign.target_sha,
                "next_action": {
                    "kind": "RECONCILE",
                    "args": {"reason": "stale recovery"},
                    "display": "reconcile stale foreign issue",
                },
            },
        )


def test_other_lane_can_continue_in_parallel(monkeypatch):
    from tools import control_transaction_production_executor as executor

    current = _record(CURRENT)
    foreign = replace(
        _record(FOREIGN, next_action="RECONCILE"),
        owner_id="chatgpt.flowv2.work1",
        lane_id="chatgpt.flowv2.work1",
        slot_id="worker.slot.1",
    )
    records = {CURRENT: current, FOREIGN: foreign}
    monkeypatch.setattr(executor, "_load_state", lambda *args, **kwargs: ("f" * 40, "e" * 40, records))

    called = {"prepared": False}

    def _prepare(*args, **kwargs):
        called["prepared"] = True
        raise RuntimeError("stop after stickiness gate")

    monkeypatch.setattr(executor, "prepare_transaction", _prepare)
    with pytest.raises(RuntimeError, match="stop after stickiness gate"):
        executor._execute_one_attempt(
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
            issue=FOREIGN,
            kind="RECONCILE",
            lane_id="chatgpt.flowv2.work1",
            invocation_identity=INV,
            supplied_effect={},
        )
    assert called["prepared"] is True

def test_reserve_paths_can_atomically_advance_continuation_to_apply_commit():
    record = _record(CURRENT, next_action="RESERVE_PATHS")
    plan = prepare_transaction(
        record,
        kind="RESERVE_PATHS",
        transaction_id="tx-issue1093-reserve-to-apply",
        invocation_identity=INV,
    )
    updated = execute_transaction(
        record,
        plan,
        effect={
            "updated_at": NOW,
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": record.target_sha,
            "write_paths": ["tools/control_transaction.py"],
            "delete_paths": [],
            "semantic_state": "ROOT_TESTS_GREEN",
            "next_action": {
                "kind": "APPLY_COMMIT",
                "args": {"diff_digest": "a" * 64},
                "display": "apply exact tested diff",
            },
        },
    )

    assert updated.mutation_scope is not None
    assert updated.mutation_scope.reservation_state == "ACTIVE"
    assert updated.mutation_scope.write_paths == ("tools/control_transaction.py",)
    assert updated.next_action is not None
    assert updated.next_action.kind == "APPLY_COMMIT"
    assert updated.next_action.args["diff_digest"] == "a" * 64



def _released_stale_residue(issue: int = 1062):
    from tools.execution_record import MutationScopeState

    record = _record(issue, next_action="RESERVE_PATHS")
    return replace(
        record,
        semantic_state="STALE_EXECUTION_RESERVATION_RELEASED_RESTART_REQUIRED",
        lease=type(record.lease)(
            token=record.lease.token,
            invocation_identity=record.lease.invocation_identity,
            expires_at="2026-10-01T16:10:00Z",
        ),
        mutation_scope=MutationScopeState(
            target_branch=record.target_branch,
            base_sha=record.target_sha,
            write_paths=("fold_designer_bridge.py",),
            delete_paths=(),
            reservation_state="RELEASED",
        ),
    )


def _active_reserved_owner(issue: int = 1112):
    from tools.execution_record import MutationScopeState

    record = _record(issue, next_action="START_BRANCH")
    return replace(
        record,
        mutation_scope=MutationScopeState(
            target_branch=record.target_branch,
            base_sha=record.target_sha,
            write_paths=("ae_engine/receiving_layout.py",),
            delete_paths=(),
            reservation_state="ACTIVE",
        ),
    )


@pytest.mark.parametrize("reverse_order", [False, True])
def test_released_stale_residue_does_not_block_real_active_owner_continuation(monkeypatch, reverse_order):
    from datetime import datetime, timezone
    from tools import control_transaction_production_executor as executor

    stale = _released_stale_residue()
    active = _active_reserved_owner()
    rows = [(stale.issue, stale), (active.issue, active)]
    if reverse_order:
        rows.reverse()
    records = dict(rows)
    monkeypatch.setattr(executor, "_now", lambda: datetime(2026, 10, 1, 16, 30, tzinfo=timezone.utc))
    monkeypatch.setattr(executor, "_load_state", lambda *args, **kwargs: ("f" * 40, "e" * 40, records))

    called = {"prepared": False}
    def stop_after_gate(*args, **kwargs):
        called["prepared"] = True
        raise RuntimeError("passed stickiness gate")
    monkeypatch.setattr(executor, "prepare_transaction", stop_after_gate)

    with pytest.raises(RuntimeError, match="passed stickiness gate"):
        executor._execute_one_attempt(
            repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2",
            issue=active.issue, kind="START_BRANCH", lane_id=LANE, invocation_identity=INV, supplied_effect={},
        )
    assert called["prepared"] is True


def test_stale_residue_allows_only_release_paths_cleanup_before_prepare(monkeypatch):
    from datetime import datetime, timezone
    from tools import control_transaction_production_executor as executor

    stale = _released_stale_residue()
    active = _active_reserved_owner()
    records = {stale.issue: stale, active.issue: active}
    monkeypatch.setattr(executor, "_now", lambda: datetime(2026, 10, 1, 16, 30, tzinfo=timezone.utc))
    monkeypatch.setattr(executor, "_load_state", lambda *args, **kwargs: ("f" * 40, "e" * 40, records))
    monkeypatch.setattr(executor, "prepare_transaction", lambda *args, **kwargs: pytest.fail("non-cleanup stale mutation must fail before prepare"))

    with pytest.raises(ControlTransactionConflict, match="STALE_RELEASED_RESIDUE_REQUIRES_RELEASE_PATHS_CLEANUP"):
        executor._execute_one_attempt(
            repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2",
            issue=stale.issue, kind="HANDOFF", lane_id=LANE, invocation_identity=INV, supplied_effect={},
        )


def test_stale_release_cleanup_is_narrow_exception_but_unrelated_issue_still_blocked(monkeypatch):
    from datetime import datetime, timezone
    from tools import control_transaction_production_executor as executor

    stale = _released_stale_residue()
    active = _active_reserved_owner()
    unrelated = _record(1200, next_action="RECONCILE")
    records = {active.issue: active, stale.issue: stale, unrelated.issue: unrelated}
    monkeypatch.setattr(executor, "_now", lambda: datetime(2026, 10, 1, 16, 30, tzinfo=timezone.utc))
    monkeypatch.setattr(executor, "_load_state", lambda *args, **kwargs: ("f" * 40, "e" * 40, records))

    prepared = []
    def stop_after_gate(record, **kwargs):
        prepared.append(record.issue)
        raise RuntimeError("passed gate")
    monkeypatch.setattr(executor, "prepare_transaction", stop_after_gate)

    with pytest.raises(RuntimeError, match="passed gate"):
        executor._execute_one_attempt(
            repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2",
            issue=stale.issue, kind="RELEASE_PATHS", lane_id=LANE, invocation_identity=INV, supplied_effect={"reason": "cleanup"},
        )
    assert prepared == [stale.issue]

    prepared.clear()
    with pytest.raises(ControlTransactionConflict, match=f"ACTIVE_OWNING_ISSUE_NO_PIVOT current_issue={active.issue}"):
        executor._execute_one_attempt(
            repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2",
            issue=unrelated.issue, kind="RECONCILE", lane_id=LANE, invocation_identity=INV, supplied_effect={},
        )
    assert prepared == []


def test_same_lane_blocker_selection_is_deterministic_across_record_order(monkeypatch):
    from datetime import datetime, timezone
    from tools import control_transaction_production_executor as executor

    blocker_a = _active_reserved_owner(1112)
    blocker_b = _active_reserved_owner(1115)
    unrelated = _record(1200, next_action="RECONCILE")
    monkeypatch.setattr(executor, "_now", lambda: datetime(2026, 10, 1, 16, 30, tzinfo=timezone.utc))

    errors = []
    for rows in [
        [(blocker_b.issue, blocker_b), (blocker_a.issue, blocker_a), (unrelated.issue, unrelated)],
        [(blocker_a.issue, blocker_a), (blocker_b.issue, blocker_b), (unrelated.issue, unrelated)],
    ]:
        monkeypatch.setattr(executor, "_load_state", lambda *args, rows=rows, **kwargs: ("f" * 40, "e" * 40, dict(rows)))
        with pytest.raises(ControlTransactionConflict) as exc:
            executor._execute_one_attempt(
                repo="looaeedr/whd", token="unused", coord_branch="coord/execution-v2",
                issue=unrelated.issue, kind="RECONCILE", lane_id=LANE, invocation_identity=INV, supplied_effect={},
            )
        errors.append(str(exc.value))
    assert errors[0] == errors[1]
    assert f"current_issue={blocker_a.issue}" in errors[0]
