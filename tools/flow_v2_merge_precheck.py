"""Pure merge precheck for WHD Flow v2.

The evaluator deliberately has no GitHub/network side effects.  Trusted
production execution gathers live PR/target/check evidence and passes it here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


READY_TO_MERGE = "READY_TO_MERGE"
TARGET_DRIFT = "TARGET_DRIFT"
PR_IDENTITY_MISMATCH = "PR_IDENTITY_MISMATCH"
REQUIRED_CHECKS_PENDING = "REQUIRED_CHECKS_PENDING"
PR_NOT_MERGEABLE = "PR_NOT_MERGEABLE"
ALREADY_MERGED = "ALREADY_MERGED"


@dataclass(frozen=True)
class MergePrecheckResult:
    classification: str
    reason: str
    observed_target_sha: str
    missing_required_checks: tuple[str, ...] = ()


def evaluate_merge_precheck(
    *,
    record_head_sha: str,
    record_target_branch: str,
    record_target_sha: str,
    pr_number: int,
    pr_state: str,
    pr_merged: bool,
    pr_head_sha: str,
    pr_base_branch: str,
    pr_base_sha: str,
    pr_mergeable: bool | None,
    observed_target_sha: str,
    required_checks: Iterable[str],
    check_conclusions: Mapping[str, str],
) -> MergePrecheckResult:
    """Classify whether an exact Flow v2 MERGE may execute now."""

    if pr_merged:
        return MergePrecheckResult(
            ALREADY_MERGED,
            f"PR #{pr_number} is already merged",
            observed_target_sha,
        )

    if pr_state != "open":
        return MergePrecheckResult(
            PR_IDENTITY_MISMATCH,
            f"PR #{pr_number} is not open",
            observed_target_sha,
        )

    if pr_head_sha != record_head_sha:
        return MergePrecheckResult(
            PR_IDENTITY_MISMATCH,
            "PR head does not match current ExecutionRecord head",
            observed_target_sha,
        )

    if pr_base_branch != record_target_branch:
        return MergePrecheckResult(
            PR_IDENTITY_MISMATCH,
            "PR base branch does not match ExecutionRecord target branch",
            observed_target_sha,
        )

    # Strict required checks are relative to the live target.  Any target/base
    # advance invalidates the merge attempt before mergeability/check polling.
    if observed_target_sha != record_target_sha or pr_base_sha != observed_target_sha:
        return MergePrecheckResult(
            TARGET_DRIFT,
            (
                "target advanced after accepted QA: "
                f"record={record_target_sha} pr_base={pr_base_sha} live={observed_target_sha}"
            ),
            observed_target_sha,
        )

    missing = tuple(
        sorted(
            context
            for context in set(required_checks)
            if str(check_conclusions.get(context) or "").lower() != "success"
        )
    )
    if missing:
        return MergePrecheckResult(
            REQUIRED_CHECKS_PENDING,
            "required status checks are not successful for the current PR head",
            observed_target_sha,
            missing_required_checks=missing,
        )

    if pr_mergeable is not True:
        return MergePrecheckResult(
            PR_NOT_MERGEABLE,
            "GitHub does not currently report the PR as mergeable",
            observed_target_sha,
        )

    return MergePrecheckResult(
        READY_TO_MERGE,
        "live PR identity, target SHA and required checks are current",
        observed_target_sha,
    )
