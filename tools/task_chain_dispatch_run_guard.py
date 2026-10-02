"""Fail-closed dispatch/preflight and remote RUN identity guard for WHD task chains.

T4 binds every dispatch/preflight decision to one frozen task-chain identity and binds
remote QA evidence to one exact branch + HEAD.  Absence of a concrete RUN is not a
wait state: polling is forbidden until the prerequisite that creates a RUN is executed
or repaired.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_TARGET = "X"
_REQUIRED_FIELDS = (
    "TASK_ID",
    "BASE_SHA",
    "EXPECTED_PARENT_SHA",
    "CHAIN_HEAD",
    "TARGET",
)
_NO_RUN_MARKER = (
    "RUN NOT CREATED polling=FORBIDDEN "
    "next_action=EXECUTE_OR_FIX_PREREQUISITE"
)


class DispatchRunIdentityError(RuntimeError):
    """Raised when dispatch or remote RUN identity cannot be proven exactly."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise DispatchRunIdentityError(
                f"ambiguous identity evidence: duplicate JSON key {key!r}"
            )
        payload[key] = value
    return payload


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    path = Path(path)
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FileNotFoundError as exc:
        raise DispatchRunIdentityError(f"{label} not found: {path}") from exc
    except DispatchRunIdentityError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchRunIdentityError(f"malformed {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DispatchRunIdentityError(f"malformed {label}: root must be an object")
    return payload


def _require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DispatchRunIdentityError(f"missing required identity field: {key}")
    return value.strip()


def _validate_sha(value: str, label: str) -> str:
    value = str(value).strip()
    if not _SHA_RE.fullmatch(value):
        raise DispatchRunIdentityError(f"malformed {label}: expected 40-char lowercase SHA")
    return value


@dataclass(frozen=True)
class DispatchIdentity:
    task_id: str
    base_sha: str
    expected_parent_sha: str
    chain_head: str
    target: str


@dataclass(frozen=True)
class RemoteRunIdentity:
    run_id: int
    branch: str
    head_sha: str


def load_dispatch_identity(path: Path) -> DispatchIdentity:
    payload = _read_json(path, label="dispatch identity contract")
    for key in _REQUIRED_FIELDS:
        if key not in payload:
            raise DispatchRunIdentityError(f"missing required identity field: {key}")

    task_id = _require_text(payload, "TASK_ID")
    base_sha = _validate_sha(_require_text(payload, "BASE_SHA"), "BASE_SHA")
    expected_parent_sha = _validate_sha(
        _require_text(payload, "EXPECTED_PARENT_SHA"), "EXPECTED_PARENT_SHA"
    )
    chain_head = _validate_sha(_require_text(payload, "CHAIN_HEAD"), "CHAIN_HEAD")
    target = _require_text(payload, "TARGET")
    if target != _REQUIRED_TARGET:
        raise DispatchRunIdentityError(
            f"TARGET identity is immutable: expected {_REQUIRED_TARGET!r}, got {target!r}"
        )
    return DispatchIdentity(
        task_id=task_id,
        base_sha=base_sha,
        expected_parent_sha=expected_parent_sha,
        chain_head=chain_head,
        target=target,
    )


def assert_dispatch_identity(
    path: Path,
    *,
    expected_task_id: str,
    expected_base_sha: str,
    expected_parent_sha: str,
    expected_chain_head: str,
    expected_target: str = _REQUIRED_TARGET,
) -> DispatchIdentity:
    expected_task_id = str(expected_task_id).strip()
    if not expected_task_id:
        raise DispatchRunIdentityError("expected TASK_ID must be nonblank")
    expected_base_sha = _validate_sha(expected_base_sha, "expected BASE_SHA")
    expected_parent_sha = _validate_sha(
        expected_parent_sha, "expected EXPECTED_PARENT_SHA"
    )
    expected_chain_head = _validate_sha(expected_chain_head, "expected CHAIN_HEAD")
    expected_target = str(expected_target).strip()
    if expected_target != _REQUIRED_TARGET:
        raise DispatchRunIdentityError(
            f"caller TARGET must be {_REQUIRED_TARGET!r}, got {expected_target!r}"
        )

    identity = load_dispatch_identity(path)
    expected = {
        "TASK_ID": expected_task_id,
        "BASE_SHA": expected_base_sha,
        "EXPECTED_PARENT_SHA": expected_parent_sha,
        "CHAIN_HEAD": expected_chain_head,
        "TARGET": expected_target,
    }
    observed = {
        "TASK_ID": identity.task_id,
        "BASE_SHA": identity.base_sha,
        "EXPECTED_PARENT_SHA": identity.expected_parent_sha,
        "CHAIN_HEAD": identity.chain_head,
        "TARGET": identity.target,
    }
    mismatches = [
        f"{key}: expected={expected[key]!r} observed={observed[key]!r}"
        for key in _REQUIRED_FIELDS
        if observed[key] != expected[key]
    ]
    if mismatches:
        raise DispatchRunIdentityError(
            "dispatch/preflight identity mismatch: " + "; ".join(mismatches)
        )
    return identity


def load_remote_run_identity(path: Path) -> RemoteRunIdentity:
    payload = _read_json(path, label="remote RUN evidence")
    run_id = payload.get("run_id")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise DispatchRunIdentityError("remote RUN run_id must be a positive integer")
    branch = payload.get("branch")
    if not isinstance(branch, str) or not branch.strip():
        raise DispatchRunIdentityError("remote RUN branch must be nonblank")
    head_sha = payload.get("head_sha")
    if not isinstance(head_sha, str) or not head_sha.strip():
        raise DispatchRunIdentityError("remote RUN head_sha must be nonblank")
    return RemoteRunIdentity(
        run_id=run_id,
        branch=branch.strip(),
        head_sha=_validate_sha(head_sha.strip(), "remote RUN head SHA"),
    )


def assert_remote_run_identity(
    path: Path,
    *,
    expected_branch: str,
    expected_head_sha: str,
) -> RemoteRunIdentity:
    expected_branch = str(expected_branch).strip()
    if not expected_branch:
        raise DispatchRunIdentityError("expected run branch must be nonblank")
    expected_head_sha = _validate_sha(expected_head_sha, "expected run head SHA")
    run = load_remote_run_identity(path)
    if run.branch != expected_branch:
        raise DispatchRunIdentityError(
            f"remote RUN branch mismatch: expected={expected_branch!r}, observed={run.branch!r}"
        )
    if run.head_sha != expected_head_sha:
        raise DispatchRunIdentityError(
            f"remote RUN head mismatch: expected={expected_head_sha}, observed={run.head_sha}"
        )
    return run


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate frozen task-chain dispatch identity and exact remote RUN identity"
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--task-id", required=True, dest="expected_task_id")
    parser.add_argument("--base-sha", required=True, dest="expected_base_sha")
    parser.add_argument(
        "--expected-parent-sha", required=True, dest="expected_parent_sha"
    )
    parser.add_argument("--chain-head", required=True, dest="expected_chain_head")
    parser.add_argument("--target", required=True, dest="expected_target")
    parser.add_argument("--run-evidence", type=Path)
    parser.add_argument("--run-branch")
    parser.add_argument("--run-head-sha")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        identity = assert_dispatch_identity(
            args.contract,
            expected_task_id=args.expected_task_id,
            expected_base_sha=args.expected_base_sha,
            expected_parent_sha=args.expected_parent_sha,
            expected_chain_head=args.expected_chain_head,
            expected_target=args.expected_target,
        )
    except DispatchRunIdentityError as exc:
        print(f"TASK_CHAIN_DISPATCH_RUN_ERROR: {exc}")
        return 2

    if args.run_evidence is None:
        print(_NO_RUN_MARKER)
        return 3
    if not args.run_branch or not args.run_head_sha:
        print(
            "TASK_CHAIN_DISPATCH_RUN_ERROR: run evidence requires exact "
            "--run-branch + --run-head-sha"
        )
        return 2

    try:
        run = assert_remote_run_identity(
            args.run_evidence,
            expected_branch=args.run_branch,
            expected_head_sha=args.run_head_sha,
        )
    except DispatchRunIdentityError as exc:
        print(f"TASK_CHAIN_DISPATCH_RUN_ERROR: {exc}")
        return 2

    print(
        "TASK_CHAIN_DISPATCH_RUN_GREEN "
        f"task_id={identity.task_id} target={identity.target} "
        f"base_sha={identity.base_sha} expected_parent_sha={identity.expected_parent_sha} "
        f"chain_head={identity.chain_head} run_id={run.run_id} "
        f"branch={run.branch} head_sha={run.head_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
