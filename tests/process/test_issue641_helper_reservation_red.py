from datetime import datetime, timezone

import tools.stale_claim_takeover as stale


UTC = timezone.utc


def _parent_claim():
    return {
        "issue": 640,
        "issue_url": "https://github.com/looaeedr/whd/issues/640",
        "worker": "scheduler.example.a",
        "executor_source": "scheduler",
        "work_branch": "workorder/issue640-guard-turn-exit-helper-hardening-20260925",
        "claimed_at": "2026-09-25T03:00:00+08:00",
        "base_sha": "a" * 40,
        "head_sha": "a" * 40,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-25T03:00:00+08:00",
        "remote_qa": None,
        "next_action": "create helper if none exists",
        "blocker": None,
        "delegated_work": [],
    }


def test_red_helper_01_parent_claim_atomic_reservation_api_exists():
    reserve = getattr(stale, "reserve_helper_creation", None)
    assert callable(reserve), (
        "RED-HELPER-01: parent-claim atomic helper reservation/CAS API is missing"
    )


def test_red_helper_02_same_snapshot_cannot_create_two_helpers_after_reservation():
    claim = _parent_claim()
    now = datetime(2026, 9, 25, 3, 10, 0, tzinfo=UTC)

    winner = stale.reserve_helper_creation(
        claim,
        parent_claim_blob_sha="a" * 40,
        expected_parent_claim_blob_sha="a" * 40,
        helper_key="finalization-proof",
        reserved_by="scheduler.example.a",
        reservation_token="winner-token",
        now=now,
    )
    assert winner.outcome == "RESERVED"

    loser = stale.reserve_helper_creation(
        winner.parent_claim,
        parent_claim_blob_sha="b" * 40,
        expected_parent_claim_blob_sha="b" * 40,
        helper_key="finalization-proof",
        reserved_by="scheduler.example.b",
        reservation_token="loser-token",
        now=now,
    )
    assert loser.outcome == "ACTIVE_HELPER_ALREADY_RESERVED"
    assert loser.reservation["reservation_token"] == "winner-token"
