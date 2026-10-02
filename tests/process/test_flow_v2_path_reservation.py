from dataclasses import replace

import pytest

from tools.control_transaction import ControlTransactionError, execute_transaction, prepare_transaction
from tools.execution_path_reservation import (
    PathReservationError,
    find_path_reservation_conflicts,
    require_no_path_reservation_conflict,
)
from tools.execution_record import (
    ActionSpec,
    MutationScopeState,
    execution_record_from_payload,
    execution_record_to_payload,
)

INV = "interactive:work0:issue1001"


def _record(issue: int, *, target="cleanup/2d-3d-sync", state="ACTIVE", scope=None, invocation=INV):
    done = state == "DONE"
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 3,
        "issue": issue,
        "execution_intent": "USER_EXPLICIT",
        "owner_kind": "NONE" if done else "INTERACTIVE",
        "owner_id": "NONE" if done else "chatgpt.flowv2.work0",
        "lane_id": None,
        "slot_id": "worker.slot.0" if not done else None,
        "source_branch": target,
        "source_sha": "a" * 40,
        "work_branch": f"work/issue-{issue}",
        "head_sha": "b" * 40,
        "target_branch": target,
        "target_sha": "c" * 40,
        "state": state,
        "semantic_state": "TERMINAL_SUCCESS" if done else "IMPLEMENTING",
        "next_action": None if done else {"kind": "RESERVE_PATHS", "args": {"target_branch": target, "base_sha": "c" * 40, "write_paths": ["gui.py"], "delete_paths": []}, "display": "reserve paths"},
        "lease": None if done else {"token": "lease-a", "invocation_identity": invocation, "expires_at": "2026-09-29T11:30:00Z"},
        "active_run": None,
        "transaction": None,
        "mutation_scope": scope,
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": "d" * 40 if done else None, "issue_closed": done, "released_at": "2026-09-29T11:00:00Z" if done else None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-29T10:30:00Z",
    })


def _scope(*, write=(), delete=(), target="cleanup/2d-3d-sync", state="ACTIVE"):
    return MutationScopeState(
        target_branch=target,
        base_sha="c" * 40,
        write_paths=tuple(sorted(write)),
        delete_paths=tuple(sorted(delete)),
        reservation_state=state,
    )


def test_mutation_scope_round_trips_inside_execution_record_without_second_lock_db():
    scope = _scope(write=("gui.py", "tests/test_gui.py"))
    record = _record(1001, scope=scope)
    payload = execution_record_to_payload(record)
    assert payload["mutation_scope"] == {
        "target_branch": "cleanup/2d-3d-sync",
        "base_sha": "c" * 40,
        "write_paths": ["gui.py", "tests/test_gui.py"],
        "delete_paths": [],
        "reservation_state": "ACTIVE",
    }
    assert execution_record_from_payload(payload) == record


def test_same_target_write_write_conflict_reports_owning_issue_and_path():
    owner = _record(1001, scope=_scope(write=("gui.py",)))
    candidate = _scope(write=("gui.py", "tests/test_gui.py"))
    conflicts = find_path_reservation_conflicts(
        [owner], candidate_issue=1002, candidate_scope=candidate
    )
    assert [(row.conflicting_issue, row.paths) for row in conflicts] == [(1001, ("gui.py",))]
    with pytest.raises(PathReservationError, match=r"PATH_RESERVATION_CONFLICT.*conflicting_issue=1001.*gui.py"):
        require_no_path_reservation_conflict(
            [owner], candidate_issue=1002, candidate_scope=candidate
        )


def test_write_delete_and_delete_write_are_conflicts_but_other_target_is_not():
    owner = _record(1001, scope=_scope(delete=("gui.py",)))
    candidate = _scope(write=("gui.py",))
    assert find_path_reservation_conflicts([owner], candidate_issue=1002, candidate_scope=candidate)

    other_target = _record(
        1003,
        target="main",
        scope=_scope(write=("gui.py",), target="main"),
    )
    assert not find_path_reservation_conflicts(
        [other_target], candidate_issue=1002, candidate_scope=candidate
    )


def test_released_or_done_scope_does_not_block_next_issue():
    released = _record(1001, scope=_scope(write=("gui.py",), state="RELEASED"))
    done = _record(1003, state="DONE", scope=_scope(write=("gui.py",), state="RELEASED"))
    candidate = _scope(write=("gui.py",))
    assert not find_path_reservation_conflicts(
        [released, done], candidate_issue=1002, candidate_scope=candidate
    )


def test_reserve_paths_is_atomic_record_transaction_and_only_allows_monotonic_expansion():
    record = _record(1001)
    plan = prepare_transaction(record, kind="RESERVE_PATHS", transaction_id="tx-reserve-missing-next", invocation_identity=INV)
    with pytest.raises(ControlTransactionError, match="next_action must be an object"):
        execute_transaction(
            record,
            plan,
            effect={
                "target_branch": "cleanup/2d-3d-sync",
                "base_sha": "c" * 40,
                "write_paths": ["gui.py"],
                "delete_paths": [],
                "updated_at": "2026-09-29T10:30:30Z",
            },
        )

    plan = prepare_transaction(record, kind="RESERVE_PATHS", transaction_id="tx-reserve-1", invocation_identity=INV)
    reserved = execute_transaction(
        record,
        plan,
        effect={
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "c" * 40,
            "write_paths": ["gui.py"],
            "delete_paths": [],
            "next_action": {
                "kind": "RESERVE_PATHS",
                "args": {
                    "target_branch": "cleanup/2d-3d-sync",
                    "base_sha": "c" * 40,
                    "write_paths": ["gui.py", "phase6_project_file.py"],
                    "delete_paths": [],
                },
                "display": "expand exact reserved scope",
            },
            "updated_at": "2026-09-29T10:31:00Z",
        },
    )
    assert reserved.mutation_scope.paths == ("gui.py",)
    assert reserved.semantic_state == "PATHS_RESERVED"
    assert reserved.next_action.kind == "RESERVE_PATHS"

    expanded_plan = prepare_transaction(reserved, kind="RESERVE_PATHS", transaction_id="tx-reserve-2", invocation_identity=INV)
    expanded = execute_transaction(
        reserved,
        expanded_plan,
        effect={
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "c" * 40,
            "write_paths": ["gui.py", "phase6_project_file.py"],
            "delete_paths": [],
            "next_action": {
                "kind": "RESERVE_PATHS",
                "args": {
                    "target_branch": "cleanup/2d-3d-sync",
                    "base_sha": "c" * 40,
                    "write_paths": ["gui.py", "phase6_project_file.py"],
                    "delete_paths": [],
                },
                "display": "finish reservation before implementation",
            },
            "updated_at": "2026-09-29T10:32:00Z",
        },
    )
    assert expanded.mutation_scope.paths == ("gui.py", "phase6_project_file.py")

    shrink_plan = prepare_transaction(expanded, kind="RESERVE_PATHS", transaction_id="tx-reserve-3", invocation_identity=INV)
    with pytest.raises(ControlTransactionError, match="cannot shrink active write_paths"):
        execute_transaction(
            expanded,
            shrink_plan,
            effect={
                "target_branch": "cleanup/2d-3d-sync",
                "base_sha": "c" * 40,
                "write_paths": ["gui.py"],
                "delete_paths": [],
                "next_action": {"kind": "APPLY_COMMIT", "args": {}, "display": "apply"},
                "updated_at": "2026-09-29T10:33:00Z",
            },
        )

    consume_plan = prepare_transaction(expanded, kind="RESERVE_PATHS", transaction_id="tx-reserve-4", invocation_identity=INV)
    consumed = execute_transaction(
        expanded,
        consume_plan,
        effect={
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "c" * 40,
            "write_paths": ["gui.py", "phase6_project_file.py"],
            "delete_paths": [],
            "next_action": {
                "kind": "APPLY_COMMIT",
                "args": {"diff_digest": "d" * 64},
                "display": "apply exact tested diff",
            },
            "updated_at": "2026-09-29T10:33:30Z",
        },
    )
    assert consumed.mutation_scope == expanded.mutation_scope
    assert consumed.next_action.kind == "APPLY_COMMIT"
    assert consumed.next_action.args["diff_digest"] == "d" * 64

def test_release_paths_requires_same_live_invocation_and_keeps_audit_scope():
    record = _record(1001, scope=_scope(write=("gui.py",)))
    plan = prepare_transaction(record, kind="RELEASE_PATHS", transaction_id="tx-release", invocation_identity=INV)
    released = execute_transaction(
        record,
        plan,
        effect={
            "reason": "scope cancelled",
            "updated_at": "2026-09-29T10:34:00Z",
        },
    )
    assert released.mutation_scope.paths == ("gui.py",)
    assert released.mutation_scope.reservation_state == "RELEASED"

    wrong = prepare_transaction(replace(record), kind="RELEASE_PATHS", transaction_id="tx-wrong", invocation_identity="other-runtime")
    with pytest.raises(ControlTransactionError, match="lease invocation mismatch"):
        execute_transaction(
            record,
            wrong,
            effect={"reason": "bad handoff", "updated_at": "2026-09-29T10:35:00Z"},
        )


def _released_stale_record():
    record = _record(1001, scope=_scope(write=("gui.py",)))
    plan = prepare_transaction(
        record,
        kind="RELEASE_PATHS",
        transaction_id="tx-release-for-stale-cleanup",
        invocation_identity=INV,
    )
    released = execute_transaction(
        record,
        plan,
        effect={"reason": "scope cancelled", "updated_at": "2026-09-29T10:34:00Z"},
    )
    return replace(
        released,
        lease=type(released.lease)(
            token=released.lease.token,
            invocation_identity=released.lease.invocation_identity,
            expires_at="2026-09-29T10:35:00Z",
        ),
        semantic_state="PATH_RESERVATION_RELEASED",
        next_action=ActionSpec(kind="START_BRANCH", args={}, display="stale continuation"),
    )


def test_released_stale_record_resets_to_ready_only_with_all_five_conditions():
    record = _released_stale_record()
    plan = prepare_transaction(
        record,
        kind="RELEASE_PATHS",
        transaction_id="tx-stale-release-cleanup",
        invocation_identity="cleanup-runtime",
    )
    reset = execute_transaction(
        record,
        plan,
        effect={
            "reason": "clear abandoned continuation",
            "updated_at": "2026-09-29T10:40:00Z",
            "work_branch_exists": False,
            "fresh_target_sha": "d" * 40,
        },
    )
    assert reset.state == "READY"
    assert reset.semantic_state == "READY"
    assert reset.owner_kind == "NONE"
    assert reset.owner_id == "NONE"
    assert reset.lane_id is None
    assert reset.slot_id is None
    assert reset.lease is None
    assert reset.active_run is None
    assert reset.qa.last_accepted_run is None
    assert reset.qa.accepted_head_sha is None
    assert reset.mutation_scope.reservation_state == "RELEASED"
    assert reset.next_action.kind == "ACQUIRE"
    assert reset.source_sha == "d" * 40
    assert reset.head_sha == "d" * 40
    assert reset.target_sha == "d" * 40


def test_released_stale_record_reset_rejects_live_lease_active_run_qa_or_existing_branch():
    from tools.execution_record import RunState

    base = _released_stale_record()

    live = replace(
        base,
        lease=type(base.lease)(
            token=base.lease.token,
            invocation_identity=base.lease.invocation_identity,
            expires_at="2026-09-29T10:45:00Z",
        ),
    )
    plan = prepare_transaction(
        live, kind="RELEASE_PATHS", transaction_id="tx-live",
        invocation_identity="cleanup-runtime"
    )
    with pytest.raises(ControlTransactionError, match="requires an expired lease"):
        execute_transaction(
            live, plan,
            effect={
                "reason": "no", "updated_at": "2026-09-29T10:40:00Z",
                "work_branch_exists": False, "fresh_target_sha": "d" * 40,
            },
        )

    running = replace(
        base, active_run=RunState(id=123, head_sha=base.head_sha, purpose="qa")
    )
    plan = prepare_transaction(
        running, kind="RELEASE_PATHS", transaction_id="tx-run",
        invocation_identity="cleanup-runtime"
    )
    with pytest.raises(ControlTransactionError, match="active_run=null"):
        execute_transaction(
            running, plan,
            effect={
                "reason": "no", "updated_at": "2026-09-29T10:40:00Z",
                "work_branch_exists": False, "fresh_target_sha": "d" * 40,
            },
        )

    qa_locked = replace(
        base, qa=type(base.qa)(last_accepted_run=456, accepted_head_sha=base.head_sha)
    )
    plan = prepare_transaction(
        qa_locked, kind="RELEASE_PATHS", transaction_id="tx-qa",
        invocation_identity="cleanup-runtime"
    )
    with pytest.raises(ControlTransactionError, match="no QA lock"):
        execute_transaction(
            qa_locked, plan,
            effect={
                "reason": "no", "updated_at": "2026-09-29T10:40:00Z",
                "work_branch_exists": False, "fresh_target_sha": "d" * 40,
            },
        )

    plan = prepare_transaction(
        base, kind="RELEASE_PATHS", transaction_id="tx-branch",
        invocation_identity="cleanup-runtime"
    )
    with pytest.raises(ControlTransactionError, match="absent work branch"):
        execute_transaction(
            base, plan,
            effect={
                "reason": "no", "updated_at": "2026-09-29T10:40:00Z",
                "work_branch_exists": True, "fresh_target_sha": "d" * 40,
            },
        )


def test_trusted_executor_proves_absent_work_branch_before_stale_release_reset(monkeypatch):
    from datetime import datetime, timezone
    from urllib.error import HTTPError
    from tools import control_transaction_production_executor as executor

    record = _released_stale_record()
    monkeypatch.setattr(
        executor, "_now",
        lambda: datetime(2026, 9, 29, 10, 40, tzinfo=timezone.utc)
    )

    def fake_api(repo, method, path, token, payload=None):
        if path.startswith("/git/ref/heads/work%2Fissue-1001"):
            raise HTTPError("https://example.invalid", 404, "Not Found", None, None)
        raise AssertionError(f"unexpected API call: {method} {path}")

    monkeypatch.setattr(executor, "_api", fake_api)
    monkeypatch.setattr(
        executor, "_read_branch_head", lambda repo, token, branch: "d" * 40
    )
    effect = executor._trusted_stale_release_effect(
        "looaeedr/whd",
        "unused",
        record=record,
        supplied={"reason": "clear abandoned continuation"},
    )
    assert effect["work_branch_exists"] is False
    assert effect["fresh_target_sha"] == "d" * 40
    assert effect["updated_at"] == "2026-09-29T10:40:00Z"


def test_issue_scoped_drive_workspaces_are_physically_isolated():
    from tools.work_root_gate import build_interactive_work_path

    a = build_interactive_work_path(issue=1001, source_sha="a" * 40)
    b = build_interactive_work_path(issue=1002, source_sha="a" * 40)
    assert a != b
    assert "/issue-1001/" in a
    assert "/issue-1002/" in b


def test_trusted_executor_rejects_second_issue_before_coord_write(monkeypatch):
    from tools import control_transaction_production_executor as executor
    from tools.control_transaction import ControlTransactionConflict

    owner = _record(1001, scope=_scope(write=("gui.py",)), invocation="owner-runtime")
    candidate = _record(1002, invocation="candidate-runtime")
    records = {1001: owner, 1002: candidate}
    monkeypatch.setattr(executor, "_load_state", lambda repo, token, coord_branch: ("f" * 40, "e" * 40, records))

    def _must_not_write(*args, **kwargs):
        raise AssertionError("coord write must not occur after PATH_RESERVATION_CONFLICT")

    monkeypatch.setattr(executor, "_write_state", _must_not_write)

    with pytest.raises(ControlTransactionConflict, match=r"PATH_RESERVATION_CONFLICT.*conflicting_issue=1001.*gui.py"):
        executor.execute_one(
            repo="looaeedr/whd",
            token="unused",
            coord_branch="coord/execution-v2",
            issue=1002,
            kind="RESERVE_PATHS",
            lane_id="chatgpt.flowv2.work0",
            invocation_identity="candidate-runtime",
            supplied_effect={
                "target_branch": "cleanup/2d-3d-sync",
                "base_sha": "c" * 40,
                "write_paths": ["gui.py"],
                "delete_paths": [],
                "next_action": {
                    "kind": "APPLY_COMMIT",
                    "args": {"diff_digest": "f" * 64},
                    "display": "apply after reservation",
                },
            },
        )


def test_finalize_automatically_releases_active_path_reservation():
    record = _record(1001, scope=_scope(write=("gui.py",)))
    record = replace(
        record,
        state="INTEGRATING",
        semantic_state="MERGED",
        qa=type(record.qa)(last_accepted_run=123, accepted_head_sha=record.head_sha),
        closure=type(record.closure)(merged_sha="d" * 40, issue_closed=False, released_at=None),
    )
    # replace the ActionSpec separately to keep dataclass validation explicit.
    from tools.execution_record import ActionSpec
    record = replace(record, next_action=ActionSpec(kind="FINALIZE", args={}, display="finalize"))
    plan = prepare_transaction(record, kind="FINALIZE", transaction_id="tx-finalize", invocation_identity=INV)
    done = execute_transaction(
        record,
        plan,
        effect={
            "observed_target_sha": "d" * 40,
            "issue_closed": True,
            "issue_state": "closed",
            "issue_state_reason": "completed",
            "released_at": "2026-09-29T10:40:00Z",
            "updated_at": "2026-09-29T10:40:00Z",
        },
    )
    assert done.state == "DONE"
    assert done.mutation_scope.reservation_state == "RELEASED"


def test_action_contract_accepts_reserve_and_release_path_actions():
    from tools.execution_action_contract import validate_execution_action
    from tools.execution_record import ActionSpec

    assert validate_execution_action(ActionSpec(
        kind="RESERVE_PATHS",
        args={
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "c" * 40,
            "write_paths": ["gui.py"],
            "delete_paths": [],
        },
    ))
    assert validate_execution_action(ActionSpec(kind="RELEASE_PATHS", args={"reason": "cancel scope"}))


def test_static_contract_declares_execution_record_as_only_dynamic_state_owner():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    payload = json.loads((root / ".agents/contracts/WHD_PATH_RESERVATION_V1.json").read_text(encoding="utf-8"))
    assert payload["status"] == "CURRENT"
    assert payload["state_owner"] == "WHD_EXECUTION_RECORD_V2.mutation_scope"
    assert payload["evaluator"] == "tools/execution_path_reservation.py"
    assert payload["writer_policy"] == "SINGLE_AUTHORITATIVE_WRITER_PER_PATH"
    assert payload["second_database_forbidden"] is True
    assert payload["reservation_counts_as_substantive_progress"] is False


def test_path_reservation_evidence_binds_issue_base_and_isolated_workspace():
    from tools.execution_path_reservation import (
        build_path_reservation_evidence,
        validate_path_reservation_evidence,
    )

    record = _record(1001, scope=_scope(write=("gui.py",)))
    evidence = build_path_reservation_evidence(record)
    assert evidence["issue"] == 1001
    assert evidence["base_sha"] == "c" * 40
    assert evidence["workspace_path"].endswith("/issue-1001/cccccccccccc")
    assert validate_path_reservation_evidence(evidence) == evidence
