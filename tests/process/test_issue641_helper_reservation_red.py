from datetime import datetime, timezone

import pytest

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


def test_red_helper_02_check_then_create_snapshot_allows_two_lanes_today():
    claim = _parent_claim()
    now = datetime(2026, 9, 25, 3, 10, 0, tzinfo=UTC)

    stale.assert_helper_creation_allowed(
        claim,
        helper_key="finalization-proof",
        delegated_work=[],
        now=now,
    )
    stale.assert_helper_creation_allowed(
        claim,
        helper_key="finalization-proof",
        delegated_work=[],
        now=now,
    )

    pytest.fail(
        "RED-HELPER-02: two independent lanes can both pass helper check on the same "
        "parent snapshot; atomic RESERVING/CAS winner is missing"
    )
