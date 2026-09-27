from copy import deepcopy
from datetime import datetime, timezone

import pytest

import tools.stale_claim_takeover as stale


NOW = datetime(2026, 9, 27, 9, 0, 0, tzinfo=timezone.utc)
BLOB = "a" * 40
WORKER = "chatgpt.issue836.20260927a"


def _claim():
    return {
        "issue": 836,
        "issue_url": "https://github.com/looaeedr/whd/issues/836",
        "worker": WORKER,
        "executor_source": "chat",
        "work_branch": "governance/issue836-stop-helper-churn-20260927",
        "claimed_at": "2026-09-27T08:53:00Z",
        "base_sha": "b" * 40,
        "head_sha": "b" * 40,
        "phase": "IMPLEMENTING",
        "last_update": "2026-09-27T09:00:00Z",
        "next_action": "repair current ticket in place",
        "blocker": None,
        "delegated_work": [],
    }


def _split(kind):
    return {
        "schema": "WHD_HELPER_SPLIT_EXCEPTION_V1",
        "kind": kind,
        "current_ticket_can_own": False,
        "evidence_ref": "issue:#836:authority-boundary-proof",
    }


@pytest.mark.parametrize(
    "purpose",
    [
        "CURRENT_TICKET_DEFECT",
        "QA_RETRY",
        "TRANSPORT_RETRY",
        "SAME_SCOPE_REPAIR",
    ],
)
def test_current_ticket_failures_must_repair_in_place_even_with_new_helper_key(purpose):
    with pytest.raises(stale.StaleTakeoverError, match="CURRENT_TICKET_REPAIR_REQUIRED"):
        stale.reserve_helper_creation(
            deepcopy(_claim()),
            parent_claim_blob_sha=BLOB,
            expected_parent_claim_blob_sha=BLOB,
            helper_key=f"fresh-key-{purpose.lower()}",
            reserved_by=WORKER,
            reservation_token=f"token-{purpose.lower()}",
            now=NOW,
            purpose_class=purpose,
            split_exception=None,
        )


def test_per_fix_governance_mirror_helper_is_rejected():
    with pytest.raises(stale.StaleTakeoverError, match="PARITY_SAME_OWNER_OR_BATCH_REQUIRED"):
        stale.reserve_helper_creation(
            deepcopy(_claim()),
            parent_claim_blob_sha=BLOB,
            expected_parent_claim_blob_sha=BLOB,
            helper_key="issue836-main-x-parity",
            reserved_by=WORKER,
            reservation_token="token-parity",
            now=NOW,
            purpose_class="PER_FIX_GOVERNANCE_MIRROR",
            split_exception=None,
        )


def test_helper_split_requires_machine_readable_distinct_boundary_proof():
    with pytest.raises(stale.StaleTakeoverError, match="HELPER_SPLIT_EXCEPTION_REQUIRED"):
        stale.reserve_helper_creation(
            deepcopy(_claim()),
            parent_claim_blob_sha=BLOB,
            expected_parent_claim_blob_sha=BLOB,
            helper_key="distinct-owner",
            reserved_by=WORKER,
            reservation_token="token-distinct-owner",
            now=NOW,
            purpose_class="DISTINCT_AUTHORITY_BOUNDARY",
            split_exception=None,
        )


def test_distinct_authority_boundary_can_reserve_and_persists_scope_proof():
    decision = stale.reserve_helper_creation(
        deepcopy(_claim()),
        parent_claim_blob_sha=BLOB,
        expected_parent_claim_blob_sha=BLOB,
        helper_key="distinct-owner",
        reserved_by=WORKER,
        reservation_token="token-distinct-owner",
        now=NOW,
        purpose_class="DISTINCT_AUTHORITY_BOUNDARY",
        split_exception=_split("DISTINCT_AUTHORITY_BOUNDARY"),
    )
    assert decision.outcome == "RESERVED"
    assert decision.reservation["purpose_class"] == "DISTINCT_AUTHORITY_BOUNDARY"
    assert decision.reservation["split_exception"]["schema"] == "WHD_HELPER_SPLIT_EXCEPTION_V1"
    assert decision.reservation["split_exception"]["current_ticket_can_own"] is False


def test_split_proof_kind_must_match_declared_purpose():
    with pytest.raises(stale.StaleTakeoverError, match="HELPER_SPLIT_EXCEPTION_MISMATCH"):
        stale.reserve_helper_creation(
            deepcopy(_claim()),
            parent_claim_blob_sha=BLOB,
            expected_parent_claim_blob_sha=BLOB,
            helper_key="distinct-blocker",
            reserved_by=WORKER,
            reservation_token="token-distinct-blocker",
            now=NOW,
            purpose_class="DISTINCT_EXTERNAL_BLOCKER",
            split_exception=_split("DISTINCT_AUTHORITY_BOUNDARY"),
        )
