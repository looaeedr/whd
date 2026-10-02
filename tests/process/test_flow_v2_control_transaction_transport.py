from dataclasses import replace

import pytest

from tools.control_transaction import execute_transaction, prepare_transaction
from tools.execution_record import ActionSpec, ExecutionRecord, LeaseState, execution_record_fingerprint
from tools.control_transaction_transport import (
    TransportError,
    build_transport_request,
    build_terminal_receipt,
    terminal_receipt_to_payload,
    transport_request_fingerprint,
    transport_request_from_payload,
    transport_request_to_payload,
    validate_terminal_receipt,
    validate_transport_request,
)


def _record():
    return ExecutionRecord(
        issue=844,
        execution_intent="SCHEDULER_LANE",
        owner_kind="SCHEDULER",
        owner_id="scheduler.a",
        lane_id="scheduler.a",
        slot_id=None,
        source_branch="cleanup/2d-3d-sync",
        source_sha="a" * 40,
        work_branch="work/844",
        head_sha="b" * 40,
        target_branch="cleanup/2d-3d-sync",
        target_sha="c" * 40,
        state="ACTIVE",
        semantic_state="IMPLEMENTING",
        next_action=ActionSpec(kind="APPLY_COMMIT", args={}, display="apply candidate"),
        lease=LeaseState(
            token="lease-1",
            invocation_identity="scheduled:00:one",
            expires_at="2026-09-28T02:00:00+00:00",
        ),
        generation=7,
        updated_at="2026-09-28T01:00:00+00:00",
    )


def _applied_record(record, plan):
    return execute_transaction(
        record,
        plan,
        effect={
            "head_sha": "d" * 40,
            "next_action": {"kind": "START_QA", "args": {}, "display": "run QA"},
            "updated_at": "2026-09-28T01:05:00+00:00",
        },
    )


def test_request_binds_exact_execution_record_and_effect_digest():
    record = _record()
    plan = prepare_transaction(
        record,
        kind="APPLY_COMMIT",
        transaction_id="tx-844-commit-1",
        invocation_identity="scheduled:00:one",
    )
    req = build_transport_request(plan, candidate_effect_digest="1" * 64)

    assert req.issue == 844
    assert req.expected_generation == 7
    assert req.expected_record_fingerprint == execution_record_fingerprint(record)
    assert req.expected_work_branch == "work/844"
    assert req.expected_head_sha == "b" * 40
    assert req.expected_target_sha == "c" * 40
    assert req.candidate_effect_digest == "1" * 64
    assert req.invocation_identity == "scheduled:00:one"
    assert validate_transport_request(req, record) is True
    assert transport_request_to_payload(req)["schema"] == "WHD_CONTROL_TRANSACTION_REQUEST_V2"
    assert len(transport_request_fingerprint(req)) == 64


def test_request_payload_round_trip_preserves_exact_identity():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-roundtrip")
    req = build_transport_request(plan, candidate_effect_digest="e" * 64)

    loaded = transport_request_from_payload(transport_request_to_payload(req))

    assert loaded == req
    assert transport_request_fingerprint(loaded) == transport_request_fingerprint(req)


def test_request_fails_closed_after_record_drift():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-1")
    req = build_transport_request(plan, candidate_effect_digest="2" * 64)

    with pytest.raises(TransportError, match="generation drift"):
        validate_transport_request(req, replace(record, generation=8))


def test_request_rejects_invalid_effect_digest():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-1")
    with pytest.raises(TransportError, match="candidate_effect_digest"):
        build_transport_request(plan, candidate_effect_digest="not-a-digest")


def test_applied_terminal_receipt_only_exists_after_reconciled_post_record():
    record = _record()
    plan = prepare_transaction(
        record,
        kind="APPLY_COMMIT",
        transaction_id="tx-844-commit-1",
        invocation_identity="scheduled:00:one",
    )
    req = build_transport_request(plan, candidate_effect_digest="3" * 64)
    post = _applied_record(record, plan)
    receipt = build_terminal_receipt(
        request=req,
        result="APPLIED",
        reason="EFFECT_READBACK_RECONCILED",
        observed_work_branch=post.work_branch,
        observed_head_sha=post.head_sha,
        observed_target_sha=post.target_sha,
        readback_digest="4" * 64,
        post_record=post,
    )

    assert receipt.result == "APPLIED"
    assert receipt.request_fingerprint == transport_request_fingerprint(req)
    assert receipt.post_generation == 8
    assert receipt.post_record_fingerprint == execution_record_fingerprint(post)
    assert validate_terminal_receipt(receipt, req, post_record=post) is True
    assert terminal_receipt_to_payload(receipt)["schema"] == "WHD_CONTROL_TRANSACTION_TERMINAL_RECEIPT_V2"


@pytest.mark.parametrize("result", ["GREEN", "PENDING", "AUTHORIZED", "PREPARED"])
def test_transport_has_no_pending_or_green_authority_state(result):
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-1")
    req = build_transport_request(plan, candidate_effect_digest="5" * 64)
    with pytest.raises(TransportError, match="terminal result"):
        build_terminal_receipt(
            request=req,
            result=result,
            reason="not terminal",
            observed_work_branch=record.work_branch,
            observed_head_sha=record.head_sha,
            observed_target_sha=record.target_sha,
            readback_digest="6" * 64,
        )


def test_applied_receipt_rejects_unreconciled_or_wrong_transaction_post_record():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-1")
    req = build_transport_request(plan, candidate_effect_digest="7" * 64)

    with pytest.raises(TransportError, match="post_record transaction"):
        build_terminal_receipt(
            request=req,
            result="APPLIED",
            reason="fake",
            observed_work_branch=record.work_branch,
            observed_head_sha="d" * 40,
            observed_target_sha=record.target_sha,
            readback_digest="8" * 64,
            post_record=replace(record, generation=8),
        )


def test_conflict_receipt_is_terminal_but_carries_no_post_record_authority():
    record = _record()
    plan = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-1")
    req = build_transport_request(plan, candidate_effect_digest="9" * 64)
    receipt = build_terminal_receipt(
        request=req,
        result="CONFLICT",
        reason="EXPECTED_FINGERPRINT_MISMATCH",
        observed_work_branch=record.work_branch,
        observed_head_sha=record.head_sha,
        observed_target_sha=record.target_sha,
        readback_digest="a" * 64,
    )
    assert receipt.post_generation is None
    assert receipt.post_record_fingerprint is None
    assert validate_terminal_receipt(receipt, req) is True


def test_receipt_cannot_be_rebound_to_another_request():
    record = _record()
    plan1 = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-1")
    plan2 = prepare_transaction(record, kind="APPLY_COMMIT", transaction_id="tx-2")
    req1 = build_transport_request(plan1, candidate_effect_digest="b" * 64)
    req2 = build_transport_request(plan2, candidate_effect_digest="b" * 64)
    receipt = build_terminal_receipt(
        request=req1,
        result="CONFLICT",
        reason="conflict",
        observed_work_branch=record.work_branch,
        observed_head_sha=record.head_sha,
        observed_target_sha=record.target_sha,
        readback_digest="c" * 64,
    )
    with pytest.raises(TransportError, match="request fingerprint"):
        validate_terminal_receipt(receipt, req2)
