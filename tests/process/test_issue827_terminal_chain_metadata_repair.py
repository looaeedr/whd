from __future__ import annotations

from pathlib import Path

import pytest

import tools.continuity_controller as continuity


ROOT = Path(__file__).resolve().parents[2]
CLAIM_ACTIVATION = ROOT / ".github" / "workflows" / "whd-remote-claim-activation.yml"
BRANCH = "work/issue696-startup-auth-purpose-20260926"
HEAD = "7ba0a951391a5d62b9ab3e851fe1ae2ecccf2785"


def _malformed_chain_payload() -> dict[str, object]:
    return {
        "version": 1,
        "issue": "696",
        "branch": BRANCH,
        "head_sha": HEAD,
        "state": "TERMINAL_SUCCESS",
        "next_action": None,
        "run_id": None,
        "job_id": None,
        "log_cursor": None,
        "blocked_count": 0,
        "blocked_last_notified_at": None,
        "evidence": ["A1 accepted and terminalized under #702"],
        "master_issue": "702",
        "chain_state": "CHAIN_COMPLETE",
        "next_issue": None,
        "chain_next_action": "return to #702 finalization",
        "chain_reason": "final amendment child",
        "closure_state": "FINALIZATION_PENDING",
        "closure_next_action": "advance canonical closure",
    }


def test_issue827_repairs_only_malformed_terminal_chain_metadata() -> None:
    repair = getattr(
        continuity,
        "repair_malformed_terminal_chain_metadata_checkpoint",
        None,
    )
    assert callable(repair), "RED: canonical terminal chain-metadata repair primitive is missing"

    repaired = repair(
        _malformed_chain_payload(),
        expected_issue="696",
        expected_branch=BRANCH,
        expected_head_sha=HEAD,
    )
    payload = continuity.checkpoint_to_payload(repaired)

    assert repaired.state is continuity.ContinuityState.TERMINAL_SUCCESS
    assert repaired.chain_state is continuity.ChainContinuationState.CHAIN_COMPLETE
    assert repaired.master_issue == "702"
    assert repaired.next_issue is None
    assert repaired.chain_next_action is None
    assert repaired.chain_reason == "final amendment child"
    assert repaired.closure_state is continuity.ClosureState.FINALIZATION_PENDING
    assert repaired.closure_next_action == "advance canonical closure"
    assert payload["issue"] == "696"
    assert payload["branch"] == BRANCH
    assert payload["head_sha"] == HEAD


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issue", "999"),
        ("branch", "other"),
        ("head_sha", "8" * 40),
        ("state", "RUNNING"),
        ("chain_state", "NEXT_CHILD_EXECUTABLE"),
        ("closure_state", "READY_FOR_FINALIZATION"),
    ],
)
def test_issue827_chain_repair_refuses_identity_state_or_other_semantic_drift(
    field: str,
    value: object,
) -> None:
    repair = getattr(
        continuity,
        "repair_malformed_terminal_chain_metadata_checkpoint",
        None,
    )
    assert callable(repair), "RED: canonical terminal chain-metadata repair primitive is missing"
    payload = _malformed_chain_payload()
    payload[field] = value
    with pytest.raises(continuity.CheckpointError):
        repair(
            payload,
            expected_issue="696",
            expected_branch=BRANCH,
            expected_head_sha=HEAD,
        )


def test_issue827_chain_repair_refuses_already_valid_chain_metadata() -> None:
    repair = getattr(
        continuity,
        "repair_malformed_terminal_chain_metadata_checkpoint",
        None,
    )
    assert callable(repair), "RED: canonical terminal chain-metadata repair primitive is missing"
    payload = _malformed_chain_payload()
    payload["chain_next_action"] = None
    with pytest.raises(continuity.CheckpointError):
        repair(
            payload,
            expected_issue="696",
            expected_branch=BRANCH,
            expected_head_sha=HEAD,
        )


def test_issue827_existing_closure_repair_remains_narrow() -> None:
    with pytest.raises(continuity.CheckpointError):
        continuity.repair_malformed_terminal_checkpoint(
            _malformed_chain_payload(),
            expected_issue="696",
            expected_branch=BRANCH,
            expected_head_sha=HEAD,
        )


def test_issue827_trusted_claim_activation_exposes_exact_chain_repair_transport() -> None:
    text = CLAIM_ACTIVATION.read_text(encoding="utf-8")
    required = (
        "terminal-chain-metadata-repair",
        "prior_claim_blob_sha",
        "prior_checkpoint_blob_sha",
        "repair_malformed_terminal_chain_metadata_checkpoint",
        "candidate claim must remain unchanged",
        "candidate checkpoint must equal canonical malformed-terminal chain-metadata repair",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: trusted terminal chain-metadata repair transport missing: {missing}"


def test_issue827_transport_does_not_relax_existing_activation_transitions() -> None:
    text = CLAIM_ACTIVATION.read_text(encoding="utf-8")
    for transition in (
        "fresh-create",
        "successor-create",
        "takeover",
        "reactivate",
        "legacy-checkpoint-repair",
        "terminal-checkpoint-repair",
    ):
        assert transition in text
