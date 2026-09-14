"""Fail-closed execution-claim ownership guard for WHD development actions.

This module does not acquire, transfer, or release claims.  It validates an already
acquired shared coordination claim immediately before a branch/write/QA action so a
second worker cannot treat comments, branch names, or stale chat state as ownership.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_ACTIONS = frozenset(
    {
        "branch-create",
        "write",
        "commit",
        "qa-dispatch",
        "workflow-dispatch",
        "pr-write",
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


class ExecutionClaimError(RuntimeError):
    """Raised when execution ownership cannot be proven exactly."""


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExecutionClaimError(f"missing required claim field: {key}")
    return value.strip()


def _require_sha(payload: dict[str, object], key: str) -> str:
    value = _require_text(payload, key)
    if not _SHA_RE.fullmatch(value):
        raise ExecutionClaimError(f"malformed claim field {key}: expected 40-char lowercase SHA")
    return value


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExecutionClaimError(f"execution claim not found: {path}") from exc
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
) -> ExecutionClaim:
    """Return the validated claim or raise before the requested repository action."""
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise ExecutionClaimError("issue must be a positive integer")
    worker = str(worker).strip()
    branch = str(branch).strip()
    action = str(action).strip()
    if not worker:
        raise ExecutionClaimError("worker must be nonblank")
    if not branch:
        raise ExecutionClaimError("branch must be nonblank")
    if action not in ALLOWED_ACTIONS:
        raise ExecutionClaimError(
            f"unsupported guarded action {action!r}; allowed={sorted(ALLOWED_ACTIONS)!r}"
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

    allowed_branches = {claim.work_branch, *claim.delegated_branches}
    if branch not in allowed_branches:
        raise ExecutionClaimError(
            f"branch is not authorized by execution claim: {branch!r}; "
            f"owner_branch={claim.work_branch!r}; delegated={claim.delegated_branches!r}"
        )
    return claim


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail closed unless the caller owns the shared WHD execution claim"
    )
    parser.add_argument("--claim", required=True, type=Path)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
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
        )
    except ExecutionClaimError as exc:
        print(f"EXECUTION_CLAIM_GUARD_ERROR: {exc}")
        return 2
    print(
        "EXECUTION_CLAIM_GUARD_GREEN "
        f"issue={claim.issue} worker={claim.worker} branch={args.branch} action={args.action}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
