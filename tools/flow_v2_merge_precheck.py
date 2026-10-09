"""Pure merge precheck for WHD Flow v2.

The evaluator deliberately has no GitHub/network side effects.  Trusted
production execution gathers live PR/target/check evidence and passes it here.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
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



@lru_cache(maxsize=256)
def _github_glob_regex(pattern: str) -> re.Pattern[str]:
    """GitHub-style path globs: * never spans a slash, **/ allows zero dirs."""
    if not pattern or any(c in pattern for c in "[]{}"):
        raise ValueError("PR_CI_UNSUPPORTED_WORKFLOW_GLOB")
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            parts.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def _workflow_pr_paths(workflow_path: str, *, repo_root: Path) -> tuple[str, ...] | None:
    """Read the existing trusted workflow's pull_request.paths, not a new list.

    GitHub Actions YAML is deliberately treated as a narrow contract: unknown
    complex YAML is rejected rather than silently declaring a check optional.
    """
    root = repo_root.resolve()
    candidate = (root / workflow_path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ValueError("PR_CI_WORKFLOW_SOURCE_MISSING")
    lines = candidate.read_text(encoding="utf-8").splitlines()
    section = None
    pr = False
    inside_paths = False
    patterns: list[str] = []
    for line in lines:
        raw = line.split("#", 1)[0].rstrip()
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        item = raw.strip()
        if indent == 0:
            section = item[:-1] if item.endswith(":") else None
            inside_paths = False
        elif section == "on" and indent == 2:
            if item == "pull_request:":
                pr = True
                inside_paths = False
            elif item.endswith(":"):
                inside_paths = False
        elif section == "on" and pr and indent == 4:
            inside_paths = item == "paths:"
            if item.startswith(("paths-ignore:", "if:")):
                raise ValueError("PR_CI_WORKFLOW_TRIGGER_UNSUPPORTED")
        elif section == "on" and pr and inside_paths and indent == 6:
            if not item.startswith("- "):
                raise ValueError("PR_CI_WORKFLOW_PATH_INVALID")
            value = item[2:].strip().strip("'\\\"")
            if not value:
                raise ValueError("PR_CI_WORKFLOW_PATH_INVALID")
            patterns.append(value)
    if not pr:
        raise ValueError("PR_CI_WORKFLOW_PR_TRIGGER_MISSING")
    return tuple(patterns) if patterns else None


def select_pr_workflows_for_changed_paths(
    changed_paths: Iterable[str], *, repo_root: Path | None = None
) -> tuple[str, ...]:
    """Select actual PR-triggered workflows, keeping the always-on gate."""
    files = tuple(dict.fromkeys(str(path) for path in changed_paths))
    if not files or any(not f or f.startswith("/") or ".." in Path(f).parts for f in files):
        raise ValueError("PR_CI_CHANGED_FILES_INCOMPLETE")
    root = repo_root or Path(__file__).resolve().parents[1]
    required: list[str] = []
    for workflow in REQUIRED_PR_WORKFLOW_PATHS:
        rules = _workflow_pr_paths(workflow, repo_root=root)
        if rules is None:
            required.append(workflow)
            continue
        if any(
            _github_glob_regex(rule.lstrip("!")).fullmatch(f)
            for rule in rules if not rule.startswith("!")
            for f in files
        ):
            # A following exclusion can switch off a matched workflow path.
            matched = False
            for f in files:
                match_for_file = False
                for rule in rules:
                    if _github_glob_regex(rule.lstrip("!")).fullmatch(f):
                        match_for_file = not rule.startswith("!")
                matched = matched or match_for_file
            if matched:
                required.append(workflow)
    if not required:
        raise ValueError("PR_CI_NO_REQUIRED_WORKFLOWS")
    return tuple(required)

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
            or not str(actor.get("login") or "").strip()
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
