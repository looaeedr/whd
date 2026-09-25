from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import tools.stale_claim_takeover as stale


UTC = timezone.utc
NOW = datetime(2026, 9, 25, 2, 30, 0, tzinfo=UTC)
PARENT_BLOB_A = "a" * 40
PARENT_BLOB_B = "b" * 40
HELPER_KEY = "finalization-proof"
LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
TOKEN_A = "reserve-a-20260925"
TOKEN_B = "reserve-b-20260925"


def _parent_claim():
    return {
        "issue": 640,
        "issue_url": "https://github.com/looaeedr/whd/issues/640",
        "worker": LANE_A,
        "executor_source": "scheduler",
        "work_branch": "workorder/issue640-guard-turn-exit-helper-hardening-20260925",
        "claimed_at": "2026-09-25T02:00:00Z",
        "base_sha": "1" * 40,
        "head_sha": "2" * 40,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-25T02:00:00Z",
        "next_action": "create exact helper if reservation wins",
        "blocker": None,
        "delegated_work": [],
    }


def _reserve(claim, *, current_blob, expected_blob, lane, token, now=NOW):
    reserve = getattr(stale, "reserve_helper_creation", None)
    assert callable(reserve), "D-R9: reserve_helper_creation parent-claim CAS API is missing"
    return reserve(
        deepcopy(claim),
        parent_claim_blob_sha=current_blob,
        expected_parent_claim_blob_sha=expected_blob,
        helper_key=HELPER_KEY,
        reserved_by=lane,
        reservation_token=token,
        now=now,
    )


def test_d_r9_cross_lane_same_key_has_only_one_cas_winner():
    first = _reserve(
        _parent_claim(),
        current_blob=PARENT_BLOB_A,
        expected_blob=PARENT_BLOB_A,
        lane=LANE_A,
        token=TOKEN_A,
    )
    assert first.outcome == "RESERVED"
    assert first.reservation["state"] == "RESERVING"
    assert first.reservation["reserved_by"] == LANE_A
    assert first.reservation["reservation_token"] == TOKEN_A

    with pytest.raises(stale.StaleTakeoverError, match="HELPER_RESERVATION_CAS_CONFLICT"):
        _reserve(
            first.parent_claim,
            current_blob=PARENT_BLOB_B,
            expected_blob=PARENT_BLOB_A,
            lane=LANE_B,
            token=TOKEN_B,
        )


def test_d_r10_cas_loser_fresh_read_resumes_existing_reservation():
    first = _reserve(
        _parent_claim(),
        current_blob=PARENT_BLOB_A,
        expected_blob=PARENT_BLOB_A,
        lane=LANE_A,
        token=TOKEN_A,
    )
    loser = _reserve(
        first.parent_claim,
        current_blob=PARENT_BLOB_B,
        expected_blob=PARENT_BLOB_B,
        lane=LANE_B,
        token=TOKEN_B,
    )
    assert loser.outcome == "ACTIVE_HELPER_ALREADY_RESERVED"
    assert loser.reservation["state"] == "RESERVING"
    assert loser.reservation["reserved_by"] == LANE_A
    assert loser.reservation["reservation_token"] == TOKEN_A
    assert loser.parent_claim == first.parent_claim


def test_d_r11_reserving_owner_crash_does_not_expire_into_duplicate_create():
    first = _reserve(
        _parent_claim(),
        current_blob=PARENT_BLOB_A,
        expected_blob=PARENT_BLOB_A,
        lane=LANE_A,
        token=TOKEN_A,
        now=NOW,
    )
    six_hours_later = NOW + timedelta(hours=6)
    recovered = _reserve(
        first.parent_claim,
        current_blob=PARENT_BLOB_B,
        expected_blob=PARENT_BLOB_B,
        lane=LANE_B,
        token=TOKEN_B,
        now=six_hours_later,
    )
    assert recovered.outcome == "ACTIVE_HELPER_ALREADY_RESERVED"
    assert recovered.reservation["reservation_token"] == TOKEN_A


def test_d_r12_reset_requires_proof_no_child_or_helper_durable_mutation():
    first = _reserve(
        _parent_claim(),
        current_blob=PARENT_BLOB_A,
        expected_blob=PARENT_BLOB_A,
        lane=LANE_A,
        token=TOKEN_A,
    )
    reset = getattr(stale, "reset_helper_reservation", None)
    assert callable(reset), "D-R12: canonical reservation reset/recovery API is missing"

    with pytest.raises(
        stale.StaleTakeoverError,
        match="HELPER_RESERVATION_RESET_REQUIRES_NO_DURABLE_CHILD_PROOF",
    ):
        reset(
            deepcopy(first.parent_claim),
            helper_key=HELPER_KEY,
            reserved_by=LANE_A,
            reservation_token=TOKEN_A,
            durable_child_proof=None,
        )

    cleared = reset(
        deepcopy(first.parent_claim),
        helper_key=HELPER_KEY,
        reserved_by=LANE_A,
        reservation_token=TOKEN_A,
        durable_child_proof={
            "child_issue_exists": False,
            "child_claim_exists": False,
            "helper_durable_mutation_exists": False,
        },
    )
    assert cleared.outcome == "RESET"
    assert not any(
        item.get("helper_key") == HELPER_KEY
        for item in cleared.parent_claim.get("delegated_work", [])
    )


def test_d_r13_helper_create_guard_requires_exact_reservation_owner_and_token():
    parent = _parent_claim()
    parent["delegated_work"] = [
        {
            "relationship": "helper",
            "helper_key": HELPER_KEY,
            "state": "ACTIVE",
            "reserved_by": LANE_A,
            "reservation_token": TOKEN_A,
            "reserved_at": "2026-09-25T02:30:00Z",
            "child_issue": 777,
            "child_claim_blob_sha": "c" * 40,
        }
    ]

    with pytest.raises(
        stale.StaleTakeoverError,
        match="HELPER_RESERVATION_AUTHORITY_MISMATCH",
    ):
        stale.assert_helper_creation_allowed(
            parent,
            helper_key=HELPER_KEY,
            delegated_work=[],
            now=NOW,
            reservation_owner=LANE_B,
            reservation_token=TOKEN_B,
        )
