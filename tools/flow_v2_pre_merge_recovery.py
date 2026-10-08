from __future__ import annotations
import re
from datetime import datetime

from tools.execution_action_contract import validate_execution_action
from tools.execution_record import (
    ActionSpec, ClosureState, ExecutionRecord, QAState,
)

PROOF_SCHEMA = "WHD_FLOW_V2_PRE_MERGE_RECOVERY_PROOF_V1"
RECOVERY_KIND = "PRE_MERGE_DELIVERY_RECOVERY"
TARGET_BRANCH = "cleanup/2d-3d-sync"


def build_pre_merge_recovery_ready_record(
    *, repository: str, issue: int, pr_number: int, lane_id: str,
    slot_id: str | None, issue_readback: dict, pr_readback: dict,
    observed_target_sha: str, required_checks: list[str],
    check_conclusions: dict[str, str],
    expected_pr_head_sha: str, expected_target_sha: str,
    pr_closes_issue: bool, observed_at: str,
) -> ExecutionRecord:
    """One *new* unclaimed READY record from fresh trusted GitHub evidence.

    Never fabricate ACQUIRE, prior accepted QA or a lease. The bound continuation
    revalidates the existing PR HEAD under the real native QA transaction.
    """
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ValueError("RECOVER_PRE_MERGE requires exact Issue number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ValueError("RECOVER_PRE_MERGE requires exact PR number")
    if not isinstance(lane_id, str) or not lane_id.strip():
        raise ValueError("RECOVER_PRE_MERGE requires lane identity")
    if issue_readback.get("pull_request") is not None or issue_readback.get("number") != issue:
        raise ValueError("RECOVER_PRE_MERGE requires matching owning Issue, not PR")
    if str(issue_readback.get("state") or "").lower() != "open":
        raise ValueError("RECOVER_PRE_MERGE requires OPEN owning Issue")
    if pr_readback.get("number") != pr_number or pr_readback.get("merged") is not False:
        raise ValueError("RECOVER_PRE_MERGE PR identity/merged state mismatch")
    if str(pr_readback.get("state") or "").lower() != "open":
        raise ValueError("RECOVER_PRE_MERGE requires OPEN unmerged PR")
    if not pr_closes_issue:
        raise ValueError("RECOVER_PRE_MERGE requires exact closing link to owning Issue")
    head = pr_readback.get("head") or {}
    base = pr_readback.get("base") or {}
    head_repo = head.get("repo") or {}
    branch = str(head.get("ref") or "")
    head_sha = str(head.get("sha") or "").lower()
    base_ref = str(base.get("ref") or "")
    if head_repo.get("full_name") != repository:
        raise ValueError("RECOVER_PRE_MERGE requires same-repository delivery")
    if not branch or not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", branch):
        raise ValueError("RECOVER_PRE_MERGE invalid PR branch")
    if base_ref != TARGET_BRANCH:
        raise ValueError("RECOVER_PRE_MERGE wrong production base")
    for label, sha in (
        ("PR head", head_sha), ("expected head", expected_pr_head_sha),
        ("target", observed_target_sha), ("expected target", expected_target_sha),
    ):
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError(f"RECOVER_PRE_MERGE invalid {label} SHA")
    if head_sha != expected_pr_head_sha.lower() or observed_target_sha != expected_target_sha.lower():
        raise ValueError("RECOVER_PRE_MERGE expected PR/target SHA drift")
    if pr_readback.get("mergeable") is not True:
        raise ValueError("RECOVER_PRE_MERGE PR is not confirmed mergeable")
    if not required_checks or any(check_conclusions.get(n) != "success" for n in required_checks):
        raise ValueError("RECOVER_PRE_MERGE required checks are not all GREEN")
    if not observed_at or not isinstance(observed_at, str):
        raise ValueError("RECOVER_PRE_MERGE missing trusted observation time")
    clock = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("RECOVER_PRE_MERGE timestamp must be timezone aware")
    workflow = ".github/workflows/whd-product-regression.yml"
    qa_action = ActionSpec(
        kind="START_QA",
        args={
            "workflow": workflow,
            "post_accept_pr_number": pr_number,
            "post_accept_target_branch": TARGET_BRANCH,
            "post_accept_revalidation_workflow": workflow,
        },
        display=f"Fresh native QA on existing PR #{pr_number} head before MERGE",
    )
    acquire = ActionSpec(
        kind="ACQUIRE",
        args={"post_acquire": {
            "kind": qa_action.kind, "args": dict(qa_action.args),
            "display": qa_action.display,
        }},
        display=f"Acquire Issue #{issue}; preserve PR #{pr_number} delivery",
    )
    validate_execution_action(acquire)
    proof = {
        "schema": PROOF_SCHEMA, "kind": RECOVERY_KIND,
        "issue": issue, "pr_number": pr_number,
        "pr_head_ref": branch, "pr_head_sha": head_sha,
        "target_branch": TARGET_BRANCH,
        "observed_target_sha": observed_target_sha,
        "required_checks": list(required_checks),
        "required_check_conclusions": {n: check_conclusions[n] for n in required_checks},
        "qa_history_reconstructed": False,
        "historical_acquire_reconstructed": False,
        "trusted_source": "control_transaction_production_executor",
        "observed_at": observed_at,
    }
    return ExecutionRecord(
        issue=issue, execution_intent="EXECUTE_TICKET",
        owner_kind="UNCLAIMED", owner_id="NONE",
        lane_id=None, slot_id=slot_id,
        source_branch=branch, source_sha=head_sha,
        work_branch=branch, head_sha=head_sha,
        target_branch=TARGET_BRANCH, target_sha=observed_target_sha,
        state="READY", semantic_state="PRE_MERGE_RECOVERY_READY",
        next_action=acquire, lease=None, active_run=None,
        transaction=None, qa=QAState(), blocker=None,
        closure=ClosureState(), recovery_history=(proof,),
        generation=1, updated_at=observed_at,
    )
