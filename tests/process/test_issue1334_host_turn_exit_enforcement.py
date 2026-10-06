from dataclasses import replace
from pathlib import Path
import json

import pytest

from tools.execution_invocation_exit import (
    HOST_EXIT_PROOF_SCHEMA,
    InvocationExitError,
    build_host_exit_proof,
    validate_host_exit_proof,
)
from tools.execution_record import TransactionState, execution_record_from_payload
from tools.runtime_report_identity import (
    RuntimeReportIdentityError,
    build_runtime_report_identity,
    format_runtime_report_prefix,
)
from tools.flow_v2_runtime_observation import RuntimeObservationError, project_interactive_liveness
from tools.interactive_runtime_liveness import (
    InteractiveRuntimeLivenessError,
    parse_interactive_runtime_end_comment,
)


INV = "chatgpt.issue1334.impl.work1"
NOW = "2026-10-06T16:30:00Z"
LATER = "2026-10-06T16:31:01Z"
HEAD = "6" * 40
LANE = "chatgpt.flowv2.work1"
ROOT = Path(__file__).resolve().parents[2]


def _active_after_acquire():
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 2,
        "issue": 1334,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": LANE,
        "lane_id": LANE,
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": HEAD,
        "work_branch": "work/issue-1334",
        "head_sha": HEAD,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": HEAD,
        "state": "ACTIVE",
        "semantic_state": "CLAIMED",
        "next_action": {
            "kind": "START_BRANCH",
            "args": {},
            "display": "continue workspace implementation",
        },
        "lease": {
            "token": "lease:1334:test:1",
            "invocation_identity": INV,
            "expires_at": "2026-10-06T16:45:00Z",
        },
        "active_run": None,
        "transaction": {
            "id": "tx-acquire",
            "kind": "ACQUIRE",
            "status": "RECONCILED",
            "expected_fingerprint": "a" * 64,
            "invocation_identity": INV,
        },
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {"merged_sha": None, "issue_closed": False, "released_at": None},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-10-06T16:29:59Z",
    })


def _done():
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 9,
        "issue": 1334,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "NONE",
        "owner_id": "NONE",
        "lane_id": None,
        "slot_id": "worker.slot.1",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": HEAD,
        "work_branch": "work/issue-1334",
        "head_sha": HEAD,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": HEAD,
        "state": "DONE",
        "semantic_state": "TERMINAL_SUCCESS",
        "next_action": None,
        "lease": None,
        "active_run": None,
        "transaction": {
            "id": "tx-finalize",
            "kind": "FINALIZE",
            "status": "RECONCILED",
            "expected_fingerprint": "b" * 64,
            "invocation_identity": INV,
        },
        "qa": {"last_accepted_run": None, "accepted_head_sha": None},
        "blocker": None,
        "closure": {
            "merged_sha": HEAD,
            "issue_closed": True,
            "released_at": "2026-10-06T16:29:58Z",
        },
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-10-06T16:29:58Z",
    })


def _identity(record):
    return build_runtime_report_identity(
        handler="工作1",
        owner=record.owner_id,
        issue=record.issue,
        slot=record.slot_id or "NONE",
        invocation_identity=INV,
        runtime_kind="INTERACTIVE",
    )


def test_acquire_only_pending_start_branch_cannot_mint_host_exit_proof():
    record = _active_after_acquire()
    with pytest.raises(
        InvocationExitError,
        match="HOST_EXIT_BLOCKED.*SCHEDULER_EXECUTION_NO_PROGRESS",
    ):
        build_host_exit_proof(record, invocation_identity=INV, now=NOW)


def test_checkpoint_remains_visible_but_is_not_exit_authority():
    record = _active_after_acquire()
    prefix = format_runtime_report_prefix(
        _identity(record),
        event="CHECKPOINT",
    )
    assert "處理者：工作1" in prefix
    with pytest.raises(
        RuntimeReportIdentityError,
        match="EXIT .*host-exit proof",
    ):
        format_runtime_report_prefix(
            _identity(record),
            event="EXIT",
            execution_record=record,
            now=NOW,
        )


def test_done_record_mints_bound_proof_and_allows_exit_report():
    record = _done()
    proof = build_host_exit_proof(record, invocation_identity=INV, now=NOW)
    assert proof["schema"] == HOST_EXIT_PROOF_SCHEMA
    assert proof["decision"] == "TASK_TERMINAL"
    assert proof["may_return"] is True

    prefix = format_runtime_report_prefix(
        _identity(record),
        event="EXIT",
        execution_record=record,
        host_exit_proof=proof,
        now=NOW,
    )
    assert "owner=NONE" in prefix


def test_record_change_invalidates_existing_host_exit_proof():
    record = _done()
    proof = build_host_exit_proof(record, invocation_identity=INV, now=NOW)
    changed = replace(record, generation=record.generation + 1)
    with pytest.raises(InvocationExitError, match="generation mismatch"):
        validate_host_exit_proof(
            proof,
            changed,
            invocation_identity=INV,
            now=NOW,
        )


def test_host_exit_proof_is_short_lived_even_when_record_is_unchanged():
    record = _done()
    proof = build_host_exit_proof(record, invocation_identity=INV, now=NOW)
    with pytest.raises(InvocationExitError, match="expired"):
        validate_host_exit_proof(
            proof,
            record,
            invocation_identity=INV,
            now=LATER,
        )


def test_terminal_exit_contract_and_skill_require_machine_proof():
    contract = (ROOT / ".agents/contracts/WHD_DURABLE_TERMINAL_EXIT_HARD_GATE_V1.json").read_text(
        encoding="utf-8"
    )
    flow = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "WHD_FLOW_V2_HOST_EXIT_PROOF_V1" in contract
    assert "terminal_exit_require_proof" in contract
    assert "build_host_exit_proof" in flow
    assert "validate_host_exit_proof" in flow
    assert "may_return=false" in flow

def test_yielded_and_lane_busy_are_exit_authority_but_not_terminal_completion():
    active = _active_after_acquire()
    yielded = replace(
        active,
        lease=None,
        transaction=TransactionState(
            id="tx-yield",
            kind="YIELD",
            status="RECONCILED",
            expected_fingerprint="d" * 64,
            invocation_identity=INV,
        ),
    )
    yielded_proof = build_host_exit_proof(
        yielded,
        invocation_identity=INV,
        now=NOW,
    )
    assert yielded_proof["decision"] == "YIELDED"
    assert "處理者：工作1" in format_runtime_report_prefix(
        _identity(yielded),
        event="EXIT",
        execution_record=yielded,
        host_exit_proof=yielded_proof,
        now=NOW,
    )
    with pytest.raises(
        RuntimeReportIdentityError,
        match="TERMINAL report requires TASK_TERMINAL",
    ):
        format_runtime_report_prefix(
            _identity(yielded),
            event="TERMINAL",
            execution_record=yielded,
            host_exit_proof=yielded_proof,
            now=NOW,
        )

    busy = replace(
        active,
        lease=replace(active.lease, invocation_identity="chatgpt.issue1334.other"),
    )
    busy_proof = build_host_exit_proof(
        busy,
        invocation_identity=INV,
        now=NOW,
    )
    assert busy_proof["decision"] == "LANE_BUSY"
    assert "處理者：工作1" in format_runtime_report_prefix(
        _identity(busy),
        event="EXIT",
        execution_record=busy,
        host_exit_proof=busy_proof,
        now=NOW,
    )


def test_interactive_end_requires_proof_and_fresh_record_revalidation():
    record = _done()
    proof = build_host_exit_proof(record, invocation_identity=INV, now=NOW)
    body = (
        "WHD_INTERACTIVE_RUNTIME_END_V1\n"
        "issue=1334\n"
        "slot_id=worker.slot.1\n"
        "worker=chatgpt.flowv2.work1\n"
        f"invocation_identity={INV}\n"
        "conversation_identity=chat.issue1334\n"
        f"claim_blob_sha={'c' * 40}\n"
        "branch=work/issue-1334\n"
        f"head_sha={HEAD}\n"
        "executor_source=chat\n"
        f"ended_at={NOW}\n"
        "reason=DONE\n"
        "host_exit_proof="
        + json.dumps(proof, separators=(",", ":"))
    )
    comment = {
        "id": 1334001,
        "created_at": NOW,
        "user": {"login": "looaeedr"},
        "body": body,
    }
    parsed = parse_interactive_runtime_end_comment(comment)
    parsed["runtime_status"] = "ENDED"
    observation = project_interactive_liveness(parsed, record=record)
    assert observation["event"] == "EXIT"
    assert observation["liveness_state"] == "ENDED"

    stale = replace(record, generation=record.generation + 1)
    with pytest.raises(RuntimeObservationError, match="host-exit proof rejected"):
        project_interactive_liveness(parsed, record=stale)

    missing = dict(comment)
    missing["body"] = body.rsplit("\nhost_exit_proof=", 1)[0]
    with pytest.raises(
        InteractiveRuntimeLivenessError,
        match="missing required keys",
    ):
        parse_interactive_runtime_end_comment(missing)

