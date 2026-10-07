from dataclasses import replace

import pytest

from tools.execution_record import TransactionState, execution_record_from_payload
from tools.host_return_surface_gate import (
    HOST_RETURN_HARD_ENFORCED,
    HOST_RETURN_SEAM_UNENFORCED,
    HostReturnSurfaceGateError,
    assert_dispatch_completion,
    classify_dispatch_completion,
    classify_host_surface_enforcement,
    validate_host_return_seam_attestation,
)


INV = "chatgpt.issue1378.work1"
HEAD = "b" * 40


def _record():
    return execution_record_from_payload(
        {
            "schema": "WHD_EXECUTION_RECORD_V2",
            "version": 2,
            "generation": 3,
            "issue": 1378,
            "execution_intent": "EXECUTE_TICKET",
            "owner_kind": "SCHEDULER",
            "owner_id": "chatgpt.flowv2.work1",
            "lane_id": "chatgpt.flowv2.work1",
            "slot_id": "worker.slot.1",
            "source_branch": "cleanup/2d-3d-sync",
            "source_sha": HEAD,
            "work_branch": "work/issue-1378",
            "head_sha": HEAD,
            "target_branch": "cleanup/2d-3d-sync",
            "target_sha": HEAD,
            "state": "ACTIVE",
            "semantic_state": "CLAIMED",
            "next_action": {
                "kind": "START_BRANCH",
                "args": {},
                "display": "start #1378",
            },
            "lease": {
                "token": "lease:1378:test:1",
                "invocation_identity": INV,
                "expires_at": "2026-10-08T01:00:00Z",
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
            "closure": {
                "merged_sha": None,
                "issue_closed": False,
                "released_at": None,
            },
            "chain": {
                "parent_issue": 1374,
                "next_issue": None,
                "next_action": None,
            },
            "recovery_history": [],
            "updated_at": "2026-10-08T00:00:00Z",
        }
    )


def _attestation(**overrides):
    value = {
        "schema": "WHD_HOST_RETURN_SEAM_ENFORCEMENT_V1",
        "surface_id": "chatgpt-interactive",
        "return_hook_enforced": True,
        "plain_final_bypass_blocked": True,
        "exit_verifier": "tools.execution_invocation_exit.validate_host_exit_proof",
        "report_formatter": "tools.runtime_report_identity.format_runtime_report_prefix",
        "trusted_source": "host_runtime",
    }
    value.update(overrides)
    return value


def test_issue1378_acquire_only_is_not_dispatch_complete():
    decision = classify_dispatch_completion(
        _record(),
        invocation_identity=INV,
    )
    assert decision.status == "DISPATCH_INCOMPLETE"
    assert decision.may_claim_complete is False
    assert decision.transaction_kind == "ACQUIRE"
    assert decision.next_action_kind == "START_BRANCH"
    with pytest.raises(HostReturnSurfaceGateError, match="DISPATCH_INCOMPLETE"):
        assert_dispatch_completion(_record(), invocation_identity=INV)


def test_control_plane_reconcile_only_does_not_upgrade_dispatch_completion():
    record = replace(
        _record(),
        generation=4,
        transaction=TransactionState(
            id="tx-reconcile",
            kind="RECONCILE",
            status="RECONCILED",
            expected_fingerprint="c" * 64,
            invocation_identity=INV,
        ),
    )
    assert classify_dispatch_completion(
        record,
        invocation_identity=INV,
    ).status == "DISPATCH_INCOMPLETE"


def test_first_substantive_transaction_allows_dispatch_progress_claim():
    record = replace(
        _record(),
        generation=4,
        semantic_state="IMPLEMENTING",
        transaction=TransactionState(
            id="tx-start-branch",
            kind="START_BRANCH",
            status="RECONCILED",
            expected_fingerprint="d" * 64,
            invocation_identity=INV,
        ),
    )
    decision = assert_dispatch_completion(record, invocation_identity=INV)
    assert decision.status == "DISPATCH_SUBSTANTIVE_PROGRESS"
    assert decision.transaction_kind == "START_BRANCH"


def test_unattested_surface_cannot_claim_physical_hard_enforcement():
    assert classify_host_surface_enforcement(
        None,
        surface_id="chatgpt-interactive",
    ) == HOST_RETURN_SEAM_UNENFORCED
    with pytest.raises(
        HostReturnSurfaceGateError,
        match="HOST_RETURN_SEAM_UNENFORCED",
    ):
        validate_host_return_seam_attestation(
            None,
            surface_id="chatgpt-interactive",
        )


def test_attested_surface_requires_plain_final_bypass_to_be_machine_blocked():
    assert classify_host_surface_enforcement(
        _attestation(),
        surface_id="chatgpt-interactive",
    ) == HOST_RETURN_HARD_ENFORCED
    assert classify_host_surface_enforcement(
        _attestation(plain_final_bypass_blocked=False),
        surface_id="chatgpt-interactive",
    ) == HOST_RETURN_SEAM_UNENFORCED
