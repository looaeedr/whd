from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


class BranchCleanupGuardError(RuntimeError):
    """Raised when branch deletion cannot be proven safe."""


def _normalize_ref(value: object) -> str:
    if not isinstance(value, str):
        raise BranchCleanupGuardError("malformed OPEN PR ref evidence: ref must be a string")
    ref = value.strip()
    if ref.startswith("refs/heads/"):
        ref = ref.removeprefix("refs/heads/")
    if not ref:
        raise BranchCleanupGuardError("malformed OPEN PR ref evidence: ref must be nonblank")
    return ref


def _pull_side_ref(pull: Mapping[str, Any], side: str) -> str:
    side_data = pull.get(side)
    if not isinstance(side_data, Mapping):
        raise BranchCleanupGuardError(
            f"malformed OPEN PR ref evidence: missing or invalid {side}.ref"
        )
    try:
        return _normalize_ref(side_data["ref"])
    except KeyError as exc:
        raise BranchCleanupGuardError(
            f"malformed OPEN PR ref evidence: missing or invalid {side}.ref"
        ) from exc


def protected_open_pr_refs(pulls: Iterable[Mapping[str, Any]]) -> set[str]:
    """Return every head and base branch referenced by supplied OPEN PR records.

    Callers must live-fetch OPEN PRs immediately before branch cleanup.  This function
    deliberately fails closed if either side of any supplied PR is missing or malformed:
    deleting a branch is never safer than preserving an uncertain PR ref.
    """

    protected: set[str] = set()
    for pull in pulls:
        if not isinstance(pull, Mapping):
            raise BranchCleanupGuardError("malformed OPEN PR ref evidence: PR must be an object")
        protected.add(_pull_side_ref(pull, "head"))
        protected.add(_pull_side_ref(pull, "base"))
    return protected


def assert_delete_candidates_safe(
    candidates: Iterable[str], pulls: Iterable[Mapping[str, Any]]
) -> None:
    """Reject any branch-deletion candidate used by either side of an OPEN PR."""

    protected = protected_open_pr_refs(pulls)
    normalized_candidates = {_normalize_ref(candidate) for candidate in candidates}
    collisions = sorted(normalized_candidates & protected)
    if collisions:
        joined = ", ".join(collisions)
        raise BranchCleanupGuardError(f"OPEN PR protected ref cannot be deleted: {joined}")


def _load_pulls(path: Path) -> list[Mapping[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BranchCleanupGuardError(f"cannot read OPEN PR evidence: {path}") from exc
    if not isinstance(payload, list):
        raise BranchCleanupGuardError("OPEN PR evidence must be a JSON array")
    if not all(isinstance(item, Mapping) for item in payload):
        raise BranchCleanupGuardError("malformed OPEN PR ref evidence: PR must be an object")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed guard for remote branch cleanup against OPEN PR refs"
    )
    parser.add_argument("--pulls-json", type=Path, required=True)
    parser.add_argument("candidate", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        pulls = _load_pulls(args.pulls_json)
        assert_delete_candidates_safe(args.candidate, pulls)
    except BranchCleanupGuardError as exc:
        print(f"BRANCH_CLEANUP_GUARD_ERROR: {exc}")
        return 2
    print("BRANCH_CLEANUP_SAFE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
