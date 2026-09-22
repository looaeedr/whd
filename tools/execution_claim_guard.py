"""Fail-closed execution-claim ownership guard for WHD development actions.

This module does not acquire, mutate, or release claims. It validates an already
acquired shared coordination claim immediately before a branch/write/QA/takeover action so a
second worker cannot treat comments, branch names, stale chat state, or a stale claim
snapshot as ownership.
"""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_ACTIONS = frozenset(
    {
        "branch-create",
        "claim-takeover",
        "write",
        "commit",
        "qa-dispatch",
        "workflow-dispatch",
        "pr-write",
    }
)
ACTIVE_PHASES = frozenset(
    {
        "CLAIMED",
        "RED",
        "IMPLEMENTING",
        "GREEN",
        "REMOTE_QA",
        "CLEANUP",
        "DRIFT_AUDIT",
        "CLOSING",
    }
)
INACTIVE_PHASES = frozenset(
    {
        "RELEASED",
        "CLOSED",
        "TERMINAL_SUCCESS",
        "TERMINAL_FAILURE",
    }
)
FILE_MUTATION_ACTIONS = frozenset({"write", "commit"})


class ExecutionClaimError(RuntimeError):
    """Raised when execution ownership cannot be proven exactly."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ExecutionClaimError(f"ambiguous execution claim: duplicate JSON key {key!r}")
        payload[key] = value
    return payload


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutionClaimError(f"missing required claim field: {key}")
    return value.strip()


def _validate_sha(value: str, label: str) -> str:
    value = str(value).strip()
    if not _SHA_RE.fullmatch(value):
        raise ExecutionClaimError(f"malformed {label}: expected 40-char lowercase SHA")
    return value


def _require_sha(payload: dict[str, object], key: str) -> str:
    return _validate_sha(_require_text(payload, key), f"claim field {key}")


def _normalize_changed_files(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for index, raw in enumerate(values):
        value = str(raw).strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if not value or value.startswith("/"):
            raise ExecutionClaimError(
                f"malformed changed-file[{index}]: expected repository-relative path"
            )
        if ".." in PurePosixPath(value).parts:
            raise ExecutionClaimError(
                f"malformed changed-file[{index}]: path traversal is not allowed"
            )
        if value not in result:
            result.append(value)
    return tuple(result)


def _is_skill_contract_path(path: str) -> bool:
    return path.startswith(".agents/skills/") and path.endswith("/SKILL.md")


def _assert_skill_authoring_preflight(
    changed_files: tuple[str, ...],
    evidence_paths: Iterable[str],
) -> None:
    skill_targets = tuple(path for path in changed_files if _is_skill_contract_path(path))
    if not skill_targets:
        return

    evidence = tuple(str(path).strip() for path in evidence_paths if str(path).strip())
    if not evidence:
        raise ExecutionClaimError(
            "Skill write preflight missing: .agents/skills/**/SKILL.md mutation requires "
            "canonical Phase6 Preflight evidence including 寫技能"
        )

    try:
        from tools.phase6_skill_preflight import (
            completed_references_from_evidence,
            completed_skills_from_evidence,
            required_references_for,
            required_skills_for,
        )
    except ModuleNotFoundError:
        from phase6_skill_preflight import (  # type: ignore[no-redef]
            completed_references_from_evidence,
            completed_skills_from_evidence,
            required_references_for,
            required_skills_for,
        )

    required_skills = required_skills_for(task="", changed_files=changed_files)
    required_references = required_references_for(task="", changed_files=changed_files)
    if "寫技能" not in required_skills:
        raise ExecutionClaimError(
            "Skill write preflight registry defect: 寫技能 is not required for Skill mutation"
        )

    completed_skills = completed_skills_from_evidence(evidence)
    completed_references = completed_references_from_evidence(
        evidence, required_references
    )
    missing_skills = [item for item in required_skills if item not in completed_skills]
    missing_references = [
        item for item in required_references if item not in completed_references
    ]
    if missing_skills or missing_references:
        raise ExecutionClaimError(
            "Skill write preflight incomplete: "
            f"missing_skills={missing_skills!r} "
            f"missing_references={missing_references!r}; "
            "寫技能 and all canonical required references must be completed before mutation"
        )


def _normalize_delegated(payload: dict[str, object]) -> tuple[str, ...]:
    raw = payload.get("delegated_branches", [])
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ExecutionClaimError("malformed delegated_branches: expected list")
    result: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            raise ExecutionClaimError(
                f"malformed delegated_branches[{index}]: expected nonblank branch"
            )
        result.append(item.strip())
    if len(set(result)) != len(result):
        raise ExecutionClaimError("malformed delegated_branches: duplicate branch")
    return tuple(result)


@dataclass(frozen=True)
class ExecutionClaim:
    issue: int
    issue_url: str
    worker: str
    work_branch: str
    claimed_at: str
    base_sha: str
    head_sha: str
    phase: str
    delegated_branches: tuple[str, ...] = ()


def load_execution_claim(path: Path) -> ExecutionClaim:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise ExecutionClaimError(f"execution claim not found: {path}") from exc
    except ExecutionClaimError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionClaimError(f"malformed execution claim {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ExecutionClaimError("malformed execution claim: root must be an object")

    issue = payload.get("issue")
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionClaimError("missing required claim field: issue")

    issue_url = _require_text(payload, "issue_url")
    worker = _require_text(payload, "worker")
    work_branch = _require_text(payload, "work_branch")
    claimed_at = _require_text(payload, "claimed_at")
    base_sha = _require_sha(payload, "base_sha")
    head_sha = _require_sha(payload, "head_sha")
    phase = _require_text(payload, "phase").upper()
    delegated = _normalize_delegated(payload)

    expected_url = f"https://github.com/looaeedr/whd/issues/{issue}"
    if issue_url != expected_url:
        raise ExecutionClaimError(
            f"claim issue_url mismatch: expected {expected_url!r}, got {issue_url!r}"
        )
    if phase in INACTIVE_PHASES:
        raise ExecutionClaimError(f"execution claim is inactive: phase={phase}")
    if phase not in ACTIVE_PHASES:
        raise ExecutionClaimError(f"ambiguous execution claim state: unknown phase={phase}")

    return ExecutionClaim(
        issue=issue,
        issue_url=issue_url,
        worker=worker,
        work_branch=work_branch,
        claimed_at=claimed_at,
        base_sha=base_sha,
        head_sha=head_sha,
        phase=phase,
        delegated_branches=delegated,
    )


def assert_execution_claim(
    path: Path,
    *,
    issue: int,
    worker: str,
    branch: str,
    action: str,
    expected_base_sha: str,
    expected_head_sha: str,
    changed_files: Iterable[str] = (),
    preflight_evidence: Iterable[str] = (),
) -> ExecutionClaim:
    """Return the validated current claim or raise before one repository action."""
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionClaimError("issue must be a positive integer")
    worker = str(worker).strip()
    branch = str(branch).strip()
    action = str(action).strip()
    expected_base_sha = _validate_sha(expected_base_sha, "expected base SHA")
    expected_head_sha = _validate_sha(expected_head_sha, "expected head SHA")
    if not worker:
        raise ExecutionClaimError("worker must be nonblank")
    if not branch:
        raise ExecutionClaimError("branch must be nonblank")
    if action not in ALLOWED_ACTIONS:
        raise ExecutionClaimError(
            f"unsupported guarded action {action!r}; allowed={sorted(ALLOWED_ACTIONS)!r}"
        )

    normalized_changed_files = _normalize_changed_files(changed_files)
    if action in FILE_MUTATION_ACTIONS and not normalized_changed_files:
        raise ExecutionClaimError(
            f"changed-file identity is required for guarded action {action!r}"
        )

    claim = load_execution_claim(path)
    if claim.issue != issue:
        raise ExecutionClaimError(
            f"issue mismatch: requested #{issue}, claim owns #{claim.issue}"
        )
    expected_url = f"https://github.com/looaeedr/whd/issues/{issue}"
    if claim.issue_url != expected_url:
        raise ExecutionClaimError(
            f"issue URL mismatch: expected {expected_url!r}, got {claim.issue_url!r}"
        )
    if claim.worker != worker:
        raise ExecutionClaimError(
            f"worker is not claim owner: requested={worker!r}, owner={claim.worker!r}"
        )
    if claim.base_sha != expected_base_sha:
        raise ExecutionClaimError(
            f"base SHA mismatch: expected={expected_base_sha}, claim={claim.base_sha}"
        )
    if claim.head_sha != expected_head_sha:
        raise ExecutionClaimError(
            f"stale claim head SHA: expected={expected_head_sha}, claim={claim.head_sha}"
        )

    allowed_branches = {claim.work_branch, *claim.delegated_branches}
    if branch not in allowed_branches:
        raise ExecutionClaimError(
            f"branch is not authorized by execution claim: {branch!r}; "
            f"owner_branch={claim.work_branch!r}; delegated={claim.delegated_branches!r}"
        )

    if action in FILE_MUTATION_ACTIONS:
        _assert_skill_authoring_preflight(
            normalized_changed_files,
            preflight_evidence,
        )
    return claim


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail closed unless the caller owns the current shared WHD execution claim"
    )
    parser.add_argument("--claim", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    parser.add_argument("--base-sha", required=True, dest="expected_base_sha")
    parser.add_argument("--head-sha", required=True, dest="expected_head_sha")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="repository-relative file mutated by write/commit; repeat for multiple files",
    )
    parser.add_argument(
        "--preflight-evidence",
        action="append",
        default=[],
        help="Phase6 Preflight evidence file; required when a changed file is a Skill SKILL.md",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        claim = assert_execution_claim(
            args.claim,
            issue=args.issue,
            worker=args.worker,
            branch=args.branch,
            action=args.action,
            expected_base_sha=args.expected_base_sha,
            expected_head_sha=args.expected_head_sha,
            changed_files=args.changed_file,
            preflight_evidence=args.preflight_evidence,
        )
    except ExecutionClaimError as exc:
        print(f"EXECUTION_CLAIM_GUARD_ERROR: {exc}")
        return 2
    print(
        "EXECUTION_CLAIM_GUARD_GREEN "
        f"issue={claim.issue} worker={claim.worker} branch={args.branch} action={args.action} "
        f"base_sha={claim.base_sha} head_sha={claim.head_sha} phase={claim.phase}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
