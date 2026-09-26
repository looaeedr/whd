from __future__ import annotations

from pathlib import Path

import pytest

import tools.continuity_controller as continuity


ROOT = Path(__file__).resolve().parents[2]
CLAIM_ACTIVATION = ROOT / ".github" / "workflows" / "whd-remote-claim-activation.yml"


def _malformed_payload() -> dict[str, object]:
    return {
        "version": 1,
        "issue": "733",
        "branch": "governance/issue733-branch-create-auto-consume-cleanup-parity-20260926",
        "head_sha": "6" * 40,
        "state": "TERMINAL_SUCCESS",
        "next_action": None,
        "run_id": 36253372146,
        "job_id": 108435463578,
        "log_cursor": None,
        "blocked_count": 0,
        "blocked_last_notified_at": None,
        "evidence": ["batch parity accepted"],
        "master_issue": None,
        "chain_state": "NONE",
        "next_issue": None,
        "chain_next_action": None,
        "chain_reason": None,
        "closure_state": "READY_FOR_FINALIZATION",
        "closure_next_action": "run trusted finalization",
    }


def test_issue744_canonical_repair_primitive_exists_and_is_narrow() -> None:
    repair = getattr(continuity, "repair_malformed_terminal_checkpoint", None)
    assert callable(repair), "RED: canonical malformed-terminal repair primitive is missing"
    repaired = repair(
        _malformed_payload(),
        expected_issue="733",
        expected_branch="governance/issue733-branch-create-auto-consume-cleanup-parity-20260926",
        expected_head_sha="6" * 40,
    )
    assert repaired.state is continuity.ContinuityState.TERMINAL_SUCCESS
    assert repaired.closure_state is continuity.ClosureState.FINALIZATION_PENDING
    assert repaired.issue == "733"
    assert repaired.head_sha == "6" * 40


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issue", "999"),
        ("branch", "other"),
        ("head_sha", "7" * 40),
        ("state", "RUNNING"),
        ("closure_state", "CLOSED"),
    ],
)
def test_issue744_repair_refuses_identity_or_terminal_state_drift(
    field: str, value: object
) -> None:
    repair = getattr(continuity, "repair_malformed_terminal_checkpoint", None)
    assert callable(repair), "RED: canonical malformed-terminal repair primitive is missing"
    payload = _malformed_payload()
    payload[field] = value
    with pytest.raises(continuity.CheckpointError):
        repair(
            payload,
            expected_issue="733",
            expected_branch="governance/issue733-branch-create-auto-consume-cleanup-parity-20260926",
            expected_head_sha="6" * 40,
        )


def test_issue744_trusted_claim_activation_exposes_fixed_terminal_repair_transition() -> None:
    text = CLAIM_ACTIVATION.read_text(encoding="utf-8")
    required = (
        "terminal-checkpoint-repair",
        "prior_claim_blob_sha",
        "prior_checkpoint_blob_sha",
        "repair_malformed_terminal_checkpoint",
        "candidate claim must remain unchanged",
        "candidate checkpoint must equal canonical malformed-terminal repair",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: trusted terminal-checkpoint repair transport missing: {missing}"


def test_issue744_transport_does_not_relax_existing_activation_transitions() -> None:
    text = CLAIM_ACTIVATION.read_text(encoding="utf-8")
    for transition in (
        "fresh-create",
        "successor-create",
        "takeover",
        "reactivate",
        "legacy-checkpoint-repair",
    ):
        assert transition in text
    assert "prior checkpoint must exist" in text.lower() or "prior_checkpoint_blob_sha" in text
