from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "whd-remote-claim-activation.yml"

PARENT = "1" * 40
APPLIED = "2" * 40
CLAIM_PATH = ".dispatch/claims/issue-700.json"
CHECKPOINT_PATH = ".dispatch/checkpoints/issue-700.json"
CLAIM_BLOB = "3" * 40
CHECKPOINT_BLOB = "4" * 40


def _recovery():
    try:
        module = importlib.import_module("tools.claim_activation_recovery")
    except ModuleNotFoundError:
        pytest.fail(
            "RED-STOP-23: canonical Claim Activation durable-readback recovery "
            "classifier is missing"
        )
    state = getattr(module, "ClaimActivationReadbackState", None)
    classify = getattr(module, "classify_claim_activation_readback", None)
    assert isinstance(state, type), (
        "RED-STOP-23: ClaimActivationReadbackState is missing"
    )
    assert callable(classify), (
        "RED-STOP-23: classify_claim_activation_readback is missing"
    )
    return state, classify


def _classify(
    *,
    current_coord_sha: str = APPLIED,
    parent_shas: tuple[str, ...] = (PARENT,),
    changed_files: tuple[str, ...] = (CLAIM_PATH, CHECKPOINT_PATH),
    current_claim_blob_sha: str = CLAIM_BLOB,
    current_checkpoint_blob_sha: str = CHECKPOINT_BLOB,
):
    _, classify = _recovery()
    return classify(
        coord_parent_sha=PARENT,
        current_coord_sha=current_coord_sha,
        current_parent_shas=parent_shas,
        current_changed_files=changed_files,
        claim_path=CLAIM_PATH,
        checkpoint_path=CHECKPOINT_PATH,
        current_claim_blob_sha=current_claim_blob_sha,
        current_checkpoint_blob_sha=current_checkpoint_blob_sha,
        candidate_claim_blob_sha=CLAIM_BLOB,
        candidate_checkpoint_blob_sha=CHECKPOINT_BLOB,
    )


def test_red_stop_23_parent_still_current_allows_single_cas_attempt():
    state, _ = _recovery()
    decision = _classify(
        current_coord_sha=PARENT,
        parent_shas=(),
        changed_files=(),
        current_claim_blob_sha="",
        current_checkpoint_blob_sha="",
    )
    assert decision.state is state.NOT_APPLIED
    assert decision.commit_sha is None


def test_red_stop_23_exact_post_cas_readback_is_effect_observed_not_replayed():
    state, _ = _recovery()
    decision = _classify()
    assert decision.state is state.EFFECT_OBSERVED
    assert decision.commit_sha == APPLIED


@pytest.mark.parametrize(
    ("parent_shas", "changed_files", "claim_blob", "checkpoint_blob"),
    [
        (("9" * 40,), (CLAIM_PATH, CHECKPOINT_PATH), CLAIM_BLOB, CHECKPOINT_BLOB),
        ((PARENT, "8" * 40), (CLAIM_PATH, CHECKPOINT_PATH), CLAIM_BLOB, CHECKPOINT_BLOB),
        ((PARENT,), (CLAIM_PATH, CHECKPOINT_PATH, "docs/unrelated.md"), CLAIM_BLOB, CHECKPOINT_BLOB),
        ((PARENT,), (CLAIM_PATH, CHECKPOINT_PATH), "7" * 40, CHECKPOINT_BLOB),
        ((PARENT,), (CLAIM_PATH, CHECKPOINT_PATH), CLAIM_BLOB, "6" * 40),
    ],
)
def test_red_stop_23_unknown_or_drifted_coordination_state_fails_closed(
    parent_shas,
    changed_files,
    claim_blob,
    checkpoint_blob,
):
    state, _ = _recovery()
    decision = _classify(
        parent_shas=parent_shas,
        changed_files=changed_files,
        current_claim_blob_sha=claim_blob,
        current_checkpoint_blob_sha=checkpoint_blob,
    )
    assert decision.state is state.AMBIGUOUS
    assert decision.commit_sha is None


def test_red_stop_23_trusted_workflow_performs_readback_before_duplicate_cas():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "from tools.claim_activation_recovery import" in text, (
        "RED-STOP-23: trusted Claim Activation does not invoke the canonical "
        "post-CAS durable-readback recovery classifier"
    )
    assert "EFFECT_OBSERVED" in text, (
        "RED-STOP-23: trusted Claim Activation cannot project an already-applied "
        "exact candidate pair without replay"
    )
