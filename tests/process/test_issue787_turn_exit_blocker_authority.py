from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import tools.continuity_controller as continuity


ISSUE = "787"
BRANCH = "governance/issue787-turn-exit-hard-gate-20260927"
HEAD = "a" * 40


def _blocked(*, proof=None) -> continuity.Checkpoint:
    return continuity.Checkpoint(
        issue=ISSUE,
        branch=BRANCH,
        head_sha=HEAD,
        state=continuity.ContinuityState.BLOCKED,
        next_action="wait for the single external authority blocker to change",
        blocked_exit_proof=proof,
    )


def _fresh_proof(**overrides):
    values = {
        "exhaustive": True,
        "executable_leaf_count": 0,
        "evidence": ("fresh GitHub durable readback: required user authority is absent",),
        "stop_reason": continuity.StopReason.EXTERNAL_AUTHORITY_REQUIRED,
        "blocker_id": "external-authority:issue-787:user-decision",
        "blocker_count": 1,
        "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    values.update(overrides)
    return continuity.BlockedExitProof(**values)


def _active_claim():
    return {
        "issue": int(ISSUE),
        "work_branch": BRANCH,
        "head_sha": HEAD,
        "phase": "IMPLEMENTING",
    }


def test_blocked_exit_proof_is_durable_and_roundtrips() -> None:
    proof = _fresh_proof()
    checkpoint = _blocked(proof=proof)

    payload = continuity.checkpoint_to_payload(checkpoint)
    assert payload["blocked_exit_proof"]["blocker_id"] == proof.blocker_id
    assert payload["blocked_exit_proof"]["blocker_count"] == 1
    assert payload["blocked_exit_proof"]["observed_at"] == proof.observed_at

    restored = continuity.checkpoint_from_payload(payload)
    assert restored.blocked_exit_proof == proof
    continuity.assert_turn_exitable(restored)


def test_blocked_exit_rejects_stale_evidence_even_when_leaf_census_is_zero() -> None:
    stale = (
        datetime.now(timezone.utc)
        - timedelta(seconds=continuity.BLOCKED_EXIT_PROOF_MAX_AGE_SECONDS + 5)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    checkpoint = _blocked(proof=_fresh_proof(observed_at=stale))

    with pytest.raises(continuity.TurnExitBlocked, match="STALE_BLOCKER_EVIDENCE"):
        continuity.assert_turn_exitable(checkpoint)


def test_blocked_exit_rejects_multiple_or_unidentified_blockers() -> None:
    with pytest.raises(continuity.TurnExitBlocked, match="BLOCKER_NOT_UNIQUE"):
        continuity.assert_turn_exitable(
            _blocked(proof=_fresh_proof(blocker_count=2))
        )

    with pytest.raises(continuity.TurnExitBlocked, match="BLOCKER_NOT_UNIQUE"):
        continuity.assert_turn_exitable(
            _blocked(proof=_fresh_proof(blocker_id=""))
        )


def test_progress_words_are_not_blocker_authority() -> None:
    for blocker_id in ("progress-report", "checkpoint-report", "status-update"):
        with pytest.raises(continuity.TurnExitBlocked, match="BLOCKER_ID_NOT_EXTERNAL"):
            continuity.assert_turn_exitable(
                _blocked(proof=_fresh_proof(blocker_id=blocker_id))
            )


def test_live_gate_allows_only_proven_blocked_without_terminal_closure() -> None:
    checkpoint = _blocked(proof=_fresh_proof())
    assert continuity.evaluate_remote_turn_exit_from_durable_state(
        checkpoint,
        issue_state="open",
        issue_state_reason=None,
        claim_state=_active_claim(),
        transaction_state=None,
        live_branch_head_sha=HEAD,
        active_remote_run=False,
        delegated_work_state="NONE",
        expected_issue=ISSUE,
        expected_branch=BRANCH,
        expected_head_sha=HEAD,
    ) == "TURN_EXIT_PERMITTED"


def test_live_blocked_exit_still_rejects_active_work_or_process_drift() -> None:
    checkpoint = _blocked(proof=_fresh_proof())

    with pytest.raises(continuity.TurnExitBlocked, match="ACTIVE_REMOTE_RUN"):
        continuity.evaluate_remote_turn_exit_from_durable_state(
            checkpoint,
            issue_state="open",
            issue_state_reason=None,
            claim_state=_active_claim(),
            transaction_state=None,
            live_branch_head_sha=HEAD,
            active_remote_run=True,
            delegated_work_state="NONE",
            expected_issue=ISSUE,
            expected_branch=BRANCH,
            expected_head_sha=HEAD,
        )

    with pytest.raises(continuity.TurnExitBlocked, match="BLOCKED_CLAIM_NOT_ACTIVE"):
        continuity.evaluate_remote_turn_exit_from_durable_state(
            checkpoint,
            issue_state="open",
            issue_state_reason=None,
            claim_state={**_active_claim(), "phase": "RELEASED"},
            transaction_state=None,
            live_branch_head_sha=HEAD,
            active_remote_run=False,
            delegated_work_state="NONE",
            expected_issue=ISSUE,
            expected_branch=BRANCH,
            expected_head_sha=HEAD,
        )


def test_supplied_only_proof_cannot_rescue_nondurable_blocked_checkpoint() -> None:
    checkpoint = continuity.Checkpoint(
        issue=ISSUE,
        branch=BRANCH,
        head_sha=HEAD,
        state=continuity.ContinuityState.BLOCKED,
        next_action="wait for external authority",
    )
    with pytest.raises(
        continuity.TurnExitBlocked,
        match="no durable blocked_exit_proof",
    ):
        continuity.assert_turn_exitable(
            checkpoint,
            blocked_exit_proof=_fresh_proof(),
        )


def test_nonblocked_payload_omits_optional_blocker_proof_for_fingerprint_compatibility() -> None:
    checkpoint = continuity.Checkpoint(
        issue=ISSUE,
        branch=BRANCH,
        head_sha=HEAD,
        state=continuity.ContinuityState.RUNNING,
        next_action="continue work",
    )
    payload = continuity.checkpoint_to_payload(checkpoint)
    assert "blocked_exit_proof" not in payload
