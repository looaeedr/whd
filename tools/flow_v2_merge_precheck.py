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

# These three always-on PR workflows form the current WHD delivery acceptance
# floor. Path-filtered knowledge checks remain governed by required checks.
REQUIRED_PR_WORKFLOW_PATHS = (
    ".github/workflows/whd-control-plane-regression.yml",
    ".github/workflows/whd-product-regression.yml",
    ".github/workflows/whd-governance-single-authority-gate.yml",
)


def assert_required_pr_ci_evidence(
    *,
    pr_head_sha: str,
    pr_head_branch: str,
    required_workflows: Iterable[str],
    workflow_runs: Iterable[Mapping[str, object]],
    jobs_by_run: Mapping[int, Mapping[str, object]],
    repo_owner: str,
) -> tuple[str, ...]:
    """Fail closed unless every mandatory PR workflow ran real exact-head jobs.

    The caller must fetch live GitHub workflow run/job records. Check-run
    conclusions and historical GREEN are not sufficient acceptance evidence.
    """
    required = tuple(dict.fromkeys(str(v) for v in required_workflows))
    if not required or not pr_head_sha or not pr_head_branch or not repo_owner:
        raise ValueError("PR_CI_REQUIRED_IDENTITY_MISSING")
    runs = list(workflow_runs)
    accepted = []
    for path in required:
        if not path:
            raise ValueError("PR_CI_REQUIRED_WORKFLOW_MISSING")
        candidates = [
            run for run in runs
            if isinstance(run, Mapping)
            and run.get("path") == path
            and run.get("event") == "pull_request"
            and run.get("head_sha") == pr_head_sha
            and run.get("head_branch") == pr_head_branch
            and isinstance(run.get("id"), int)
            and not isinstance(run.get("id"), bool)
        ]
        if not candidates:
            raise ValueError(f"PR_CI_REQUIRED_RUN_MISSING: {path}")
        run = max(candidates, key=lambda x: (int(x["id"]), int(x.get("run_attempt") or 1)))
        actor = run.get("actor") or {}
        if (
            not isinstance(actor, Mapping)
            or str(actor.get("type") or "") != "User"
            or str(actor.get("login") or "").casefold() != repo_owner.casefold()
        ):
            raise ValueError(f"PR_CI_OWNER_ACTOR_REJECTED: {path}")
        if (
            str(run.get("status") or "").lower() != "completed"
            or str(run.get("conclusion") or "").lower() != "success"
        ):
            raise ValueError(f"PR_CI_RUN_NOT_GREEN: {path}")
        run_id = int(run["id"])
        payload = jobs_by_run.get(run_id)
        if not isinstance(payload, Mapping):
            raise ValueError(f"PR_CI_JOBS_MISSING: {path}")
        count = payload.get("total_count")
        jobs = payload.get("jobs")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
            or not isinstance(jobs, list)
            or len(jobs) != count
        ):
            raise ValueError(f"PR_CI_JOBS_INCOMPLETE: {path}")
        for job in jobs:
            if (
                not isinstance(job, Mapping)
                or job.get("run_id") != run_id
                or str(job.get("status") or "").lower() != "completed"
                or str(job.get("conclusion") or "").lower() != "success"
            ):
                raise ValueError(f"PR_CI_JOB_NOT_GREEN: {path}")
        accepted.append(path)
    return tuple(accepted)



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

    # Identity is checked even for an already-merged PR. Otherwise a caller
    # could point at an unrelated merged PR and incorrectly acquire its merge
    # evidence as this Issue's delivery anchor.
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
