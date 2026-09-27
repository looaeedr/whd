from __future__ import annotations

import copy
import importlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
REMOTE_GUARD = ROOT / ".github" / "workflows" / "whd-remote-execution-guard.yml"
REPAIR_WORKFLOW = ROOT / ".github" / "workflows" / "whd-remote-parent-branch-identity-repair.yml"

ORIGINAL_BRANCH = "work/issue702-crash-fault-combined-acceptance-20260927"
REPLACEMENT_BRANCH = "repair/issue702-sealed-finalization-20260927"
SEALED_HEAD = "f8a3397551c5975dafd842e8dcd28c1d4edcca32"
OBSERVED_DRIFT = "c59d73e245d2b4732c738a01bd062eb32763a05a"


def _current_claim() -> dict[str, object]:
    return {
        "issue": 702,
        "issue_url": "https://github.com/looaeedr/whd/issues/702",
        "worker": "scheduler.6ab13fa557fc8191935c671214b865e2",
        "executor_source": "scheduler",
        "work_branch": ORIGINAL_BRANCH,
        "base_sha": "cfbcaa1b4e50e117d8a3e1a738606814f48325d2",
        "head_sha": SEALED_HEAD,
        "phase": "CLEANUP",
        "evidence": ["sealed acceptance"],
        "next_action": "resume #702 finalization",
    }


def _current_checkpoint() -> dict[str, object]:
    return {
        "version": 1,
        "issue": "702",
        "branch": ORIGINAL_BRANCH,
        "head_sha": SEALED_HEAD,
        "state": "RUNNING",
        "next_action": "resume #702 finalization",
        "evidence": ["sealed acceptance"],
        "master_issue": None,
        "chain_state": "NONE",
        "next_issue": None,
        "chain_next_action": None,
        "chain_reason": None,
        "closure_state": "CLOSED",
        "closure_next_action": None,
    }


def _candidate_pair() -> tuple[dict[str, object], dict[str, object]]:
    claim = copy.deepcopy(_current_claim())
    checkpoint = copy.deepcopy(_current_checkpoint())
    claim["work_branch"] = REPLACEMENT_BRANCH
    checkpoint["branch"] = REPLACEMENT_BRANCH
    return claim, checkpoint


def _repair_module():
    try:
        return importlib.import_module("tools.parent_branch_identity_repair")
    except ModuleNotFoundError as exc:
        pytest.fail(f"RED: canonical parent-branch identity repair primitive is missing: {exc}")


def test_issue828_remote_guard_exposes_narrow_repair_authorization() -> None:
    text = REMOTE_GUARD.read_text(encoding="utf-8")
    required = (
        "parent-branch-identity-repair",
        "observed_live_head_sha",
        "replacement_branch",
        "PARENT_BRANCH_IDENTITY_REPAIR",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: Remote Guard repair authorization missing: {missing}"


def test_issue828_trusted_repair_transport_exists_and_is_non_force() -> None:
    assert REPAIR_WORKFLOW.is_file(), "RED: trusted parent-branch identity repair workflow is missing"
    text = REPAIR_WORKFLOW.read_text(encoding="utf-8")
    required = (
        "WHD_REMOTE_PARENT_BRANCH_IDENTITY_REPAIR_REQUEST_V1",
        "classify_claim_activation_readback",
        "candidate_claim_blob_sha",
        "candidate_checkpoint_blob_sha",
        "prior_claim_blob_sha",
        "prior_checkpoint_blob_sha",
        "observed_live_head_sha",
        "sealed_head_sha",
        "replacement_branch",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"RED: trusted repair transport incomplete: {missing}"
    assert '"force": true' not in text
    assert "force=true" not in text
    assert "force: true" not in text


def test_issue828_candidate_rebind_changes_only_branch_identity() -> None:
    repair = _repair_module()
    candidate_claim, candidate_checkpoint = _candidate_pair()
    repair.validate_parent_branch_identity_repair_candidate(
        current_claim=_current_claim(),
        current_checkpoint=_current_checkpoint(),
        candidate_claim=candidate_claim,
        candidate_checkpoint=candidate_checkpoint,
        original_branch=ORIGINAL_BRANCH,
        replacement_branch=REPLACEMENT_BRANCH,
        sealed_head_sha=SEALED_HEAD,
    )


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("claim", "head_sha", OBSERVED_DRIFT),
        ("claim", "phase", "CLOSING"),
        ("claim", "evidence", ["rewritten"]),
        ("claim", "next_action", "changed"),
        ("checkpoint", "head_sha", OBSERVED_DRIFT),
        ("checkpoint", "state", "TERMINAL_SUCCESS"),
        ("checkpoint", "evidence", ["rewritten"]),
        ("checkpoint", "next_action", "changed"),
    ],
)
def test_issue828_candidate_rebind_rejects_non_branch_mutation(
    target: str,
    field: str,
    value: object,
) -> None:
    repair = _repair_module()
    candidate_claim, candidate_checkpoint = _candidate_pair()
    if target == "claim":
        candidate_claim[field] = value
    else:
        candidate_checkpoint[field] = value
    with pytest.raises(repair.ParentBranchIdentityRepairError):
        repair.validate_parent_branch_identity_repair_candidate(
            current_claim=_current_claim(),
            current_checkpoint=_current_checkpoint(),
            candidate_claim=candidate_claim,
            candidate_checkpoint=candidate_checkpoint,
            original_branch=ORIGINAL_BRANCH,
            replacement_branch=REPLACEMENT_BRANCH,
            sealed_head_sha=SEALED_HEAD,
        )


def test_issue828_current_pair_must_already_be_sealed() -> None:
    repair = _repair_module()
    current_claim = _current_claim()
    current_claim["head_sha"] = OBSERVED_DRIFT
    candidate_claim, candidate_checkpoint = _candidate_pair()
    with pytest.raises(repair.ParentBranchIdentityRepairError):
        repair.validate_parent_branch_identity_repair_candidate(
            current_claim=current_claim,
            current_checkpoint=_current_checkpoint(),
            candidate_claim=candidate_claim,
            candidate_checkpoint=candidate_checkpoint,
            original_branch=ORIGINAL_BRANCH,
            replacement_branch=REPLACEMENT_BRANCH,
            sealed_head_sha=SEALED_HEAD,
        )
