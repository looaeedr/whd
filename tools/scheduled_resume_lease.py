"""Shared GitHub-backed TTL lease for Scheduled Resume Bridge.

The lease authority is the GitHub issue body. Runner-local wake receipts remain
idempotency evidence only and are never treated as the cross-runtime lock.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from tools.continuity_controller import CheckpointError


LEASE_BEGIN = "<!-- WHD_SCHEDULED_RESUME_LEASE_BEGIN -->"
LEASE_END = "<!-- WHD_SCHEDULED_RESUME_LEASE_END -->"
LEASE_VERSION = 1


class IssueBodyStore(Protocol):
    def read_body(self) -> str: ...
    def write_body(self, body: str) -> None: ...


@dataclass(frozen=True)
class GitHubLeaseRecord:
    holder: str
    acquired_at: datetime
    ttl_seconds: int

    def __post_init__(self) -> None:
        holder = str(self.holder).strip()
        if not holder:
            raise CheckpointError("lease holder must be nonblank")
        acquired_at = self.acquired_at
        if acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
            raise CheckpointError("lease acquired_at must be timezone-aware")
        if isinstance(self.ttl_seconds, bool) or int(self.ttl_seconds) <= 0:
            raise CheckpointError("lease ttl_seconds must be a positive integer")
        object.__setattr__(self, "holder", holder)
        object.__setattr__(
            self,
            "acquired_at",
            acquired_at.astimezone(timezone.utc),
        )
        object.__setattr__(self, "ttl_seconds", int(self.ttl_seconds))

    @property
    def expires_at_epoch(self) -> float:
        return self.acquired_at.timestamp() + self.ttl_seconds

    def is_unexpired(self, now: datetime) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise CheckpointError("lease comparison time must be timezone-aware")
        return now.astimezone(timezone.utc).timestamp() < self.expires_at_epoch


@dataclass(frozen=True)
class SharedLeaseAcquireResult:
    acquired: bool
    owner: str | None
    already_owned: bool = False


def _lease_payload(lease: GitHubLeaseRecord) -> dict[str, object]:
    return {
        "version": LEASE_VERSION,
        "holder": lease.holder,
        "acquired_at": lease.acquired_at.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "ttl_seconds": lease.ttl_seconds,
    }


def _strip_lease_block(body: str) -> str:
    text = str(body or "")
    start = text.find(LEASE_BEGIN)
    if start < 0:
        return text.rstrip()
    end = text.find(LEASE_END, start + len(LEASE_BEGIN))
    if end < 0:
        raise CheckpointError("scheduled-resume lease block is malformed")
    end += len(LEASE_END)
    return (text[:start] + text[end:]).strip()


def render_issue_lease(body: str, lease: GitHubLeaseRecord) -> str:
    base = _strip_lease_block(body)
    block = (
        f"{LEASE_BEGIN}\n"
        + json.dumps(_lease_payload(lease), ensure_ascii=False, indent=2, sort_keys=True)
        + f"\n{LEASE_END}"
    )
    return f"{base}\n\n{block}\n" if base else f"{block}\n"


def clear_issue_lease(body: str) -> str:
    base = _strip_lease_block(body)
    return f"{base}\n" if base else ""


def parse_issue_lease(body: str) -> GitHubLeaseRecord | None:
    text = str(body or "")
    start = text.find(LEASE_BEGIN)
    if start < 0:
        return None
    end = text.find(LEASE_END, start + len(LEASE_BEGIN))
    if end < 0:
        raise CheckpointError("scheduled-resume lease block is malformed")
    raw = text[start + len(LEASE_BEGIN):end].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CheckpointError("scheduled-resume lease JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise CheckpointError("scheduled-resume lease must be a JSON object")
    expected = {"version", "holder", "acquired_at", "ttl_seconds"}
    if set(payload) != expected:
        raise CheckpointError(
            f"scheduled-resume lease fields invalid: expected={sorted(expected)} actual={sorted(payload)}"
        )
    if payload.get("version") != LEASE_VERSION:
        raise CheckpointError("scheduled-resume lease version unsupported")
    try:
        acquired_at = datetime.fromisoformat(
            str(payload["acquired_at"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CheckpointError("scheduled-resume lease acquired_at is invalid") from exc
    return GitHubLeaseRecord(
        holder=str(payload["holder"]),
        acquired_at=acquired_at,
        ttl_seconds=int(payload["ttl_seconds"]),
    )


def acquire_shared_lease(
    store: IssueBodyStore,
    *,
    holder: str,
    now: datetime,
    ttl_seconds: int,
) -> SharedLeaseAcquireResult:
    """Acquire or renew ownership using shared GitHub-backed issue state.

    This intentionally performs a fresh read after write. If a competing actor
    replaced the candidate lease, the caller does not own the lease and fails
    closed rather than mutating continuity state.
    """

    current_body = store.read_body()
    current = parse_issue_lease(current_body)
    holder = str(holder).strip()
    if not holder:
        raise CheckpointError("lease holder must be nonblank")

    if current is not None and current.is_unexpired(now):
        if current.holder == holder:
            return SharedLeaseAcquireResult(
                acquired=True,
                owner=holder,
                already_owned=True,
            )
        return SharedLeaseAcquireResult(acquired=False, owner=current.holder)

    candidate = GitHubLeaseRecord(
        holder=holder,
        acquired_at=now,
        ttl_seconds=ttl_seconds,
    )
    store.write_body(render_issue_lease(current_body, candidate))

    verified = parse_issue_lease(store.read_body())
    if verified is None:
        raise CheckpointError("shared lease disappeared during post-write verification")
    if verified != candidate:
        return SharedLeaseAcquireResult(acquired=False, owner=verified.holder)
    return SharedLeaseAcquireResult(acquired=True, owner=holder)


def release_shared_lease(store: IssueBodyStore, *, holder: str) -> bool:
    current_body = store.read_body()
    current = parse_issue_lease(current_body)
    if current is None:
        return True
    if current.holder != str(holder).strip():
        raise CheckpointError(
            f"lease owner mismatch: expected holder={holder!r} actual={current.holder!r}"
        )

    store.write_body(clear_issue_lease(current_body))
    verified = parse_issue_lease(store.read_body())
    if verified is None:
        return True
    if verified.holder != current.holder:
        raise CheckpointError(
            "lease changed owner during release verification; refusing to clear another actor"
        )
    raise CheckpointError("lease release did not persist")


Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitHubIssueBodyStore:
    """GitHub issue body backend implemented through the GitHub CLI.

    GitHub Actions provides GH_TOKEN/GITHUB_TOKEN; no chat/runtime memory is used.
    """

    def __init__(
        self,
        repo: str,
        issue_number: int,
        *,
        runner: Runner = subprocess.run,
    ) -> None:
        self.repo = str(repo).strip()
        self.issue_number = int(issue_number)
        self._runner = runner
        if not self.repo or "/" not in self.repo:
            raise CheckpointError("repo must be owner/name")
        if self.issue_number <= 0:
            raise CheckpointError("issue_number must be positive")

    @property
    def _endpoint(self) -> str:
        return f"repos/{self.repo}/issues/{self.issue_number}"

    def read_body(self) -> str:
        proc = self._runner(
            ["gh", "api", self._endpoint, "--jq", ".body // \"\""],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise CheckpointError(
                f"cannot read GitHub issue body: {proc.stderr.strip() or proc.stdout.strip()}"
            )
        return proc.stdout.rstrip("\n")

    def write_body(self, body: str) -> None:
        payload = json.dumps({"body": str(body)}, ensure_ascii=False)
        proc = self._runner(
            ["gh", "api", "--method", "PATCH", self._endpoint, "--input", "-"],
            input=payload,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise CheckpointError(
                f"cannot update GitHub issue body: {proc.stderr.strip() or proc.stdout.strip()}"
            )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shared Scheduled Resume GitHub TTL lease")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("acquire", "release", "show"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--issue", required=True, type=int)
        if name in {"acquire", "release"}:
            p.add_argument("--holder", required=True)
        if name == "acquire":
            p.add_argument("--ttl-seconds", type=int, default=600)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    store = GitHubIssueBodyStore(args.repo, args.issue)
    try:
        if args.command == "show":
            lease = parse_issue_lease(store.read_body())
            print(json.dumps(None if lease is None else _lease_payload(lease), ensure_ascii=False))
            return 0
        if args.command == "acquire":
            result = acquire_shared_lease(
                store,
                holder=args.holder,
                now=datetime.now(timezone.utc),
                ttl_seconds=args.ttl_seconds,
            )
            print(json.dumps({
                "acquired": result.acquired,
                "owner": result.owner,
                "already_owned": result.already_owned,
            }, ensure_ascii=False, sort_keys=True))
            return 0 if result.acquired else 3
        if args.command == "release":
            released = release_shared_lease(store, holder=args.holder)
            print(json.dumps({"released": released}, ensure_ascii=False))
            return 0
        raise CheckpointError(f"unsupported command: {args.command}")
    except CheckpointError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
