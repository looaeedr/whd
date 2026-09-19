"""Executable scheduled wake dispatcher for WHD continuity checkpoints.

This module deliberately owns no workflow state transitions. It verifies exact
checkpoint ownership, delegates state routing to tools.continuity_controller,
and emits a machine-readable decision for the waking runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from tools.continuity_controller import (
    CheckpointError,
    ScheduledResumeAction,
    assert_checkpoint_owner,
    checkpoint_fingerprint,
    load_checkpoint,
    scheduled_resume_action,
)


@dataclass(frozen=True)
class ScheduledResumeDispatch:
    issue: str
    branch: str
    head_sha: str
    state: str
    action: ScheduledResumeAction
    next_action: str | None
    run_id: int | None
    job_id: int | None
    checkpoint_fingerprint: str
    wake_key: str

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["action"] = self.action.value
        return payload


@dataclass(frozen=True)
class ScheduledWakeClaim:
    claimed: bool
    wake_key: str
    receipt_path: Path


def _wake_key(
    *,
    issue: str,
    branch: str,
    head_sha: str,
    checkpoint_digest: str,
    action: ScheduledResumeAction,
) -> str:
    payload = json.dumps(
        {
            "issue": issue,
            "branch": branch,
            "head_sha": head_sha,
            "checkpoint_fingerprint": checkpoint_digest,
            "action": action.value,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def dispatch_scheduled_resume(
    path: Path,
    *,
    expected_issue: str,
    expected_branch: str,
    expected_head_sha: str,
) -> ScheduledResumeDispatch:
    checkpoint = load_checkpoint(Path(path))
    assert_checkpoint_owner(
        checkpoint,
        expected_issue=expected_issue,
        expected_branch=expected_branch,
        expected_head_sha=expected_head_sha,
    )
    action = scheduled_resume_action(checkpoint)
    digest = checkpoint_fingerprint(checkpoint)
    wake_key = _wake_key(
        issue=checkpoint.issue,
        branch=checkpoint.branch,
        head_sha=checkpoint.head_sha,
        checkpoint_digest=digest,
        action=action,
    )
    return ScheduledResumeDispatch(
        issue=checkpoint.issue,
        branch=checkpoint.branch,
        head_sha=checkpoint.head_sha,
        state=checkpoint.state.value,
        action=action,
        next_action=checkpoint.next_action,
        run_id=checkpoint.run_id,
        job_id=checkpoint.job_id,
        checkpoint_fingerprint=digest,
        wake_key=wake_key,
    )


def claim_scheduled_wake(
    lease_dir: Path,
    dispatch: ScheduledResumeDispatch,
) -> ScheduledWakeClaim:
    """Atomically claim one deterministic wake key.

    The receipt is idempotency evidence only. It does not mutate continuity state.
    A changed checkpoint produces a changed fingerprint/wake key and therefore a
    new independent claim.
    """

    lease_dir = Path(lease_dir)
    lease_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = lease_dir / f"{dispatch.wake_key}.json"
    payload = {
        "version": 1,
        "wake_key": dispatch.wake_key,
        "issue": dispatch.issue,
        "branch": dispatch.branch,
        "head_sha": dispatch.head_sha,
        "checkpoint_fingerprint": dispatch.checkpoint_fingerprint,
        "action": dispatch.action.value,
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")

    try:
        fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(
                f"invalid scheduled-wake receipt: {receipt_path}"
            ) from exc
        if existing != payload:
            raise CheckpointError(
                f"scheduled-wake receipt collision for wake_key={dispatch.wake_key}"
            )
        return ScheduledWakeClaim(
            claimed=False,
            wake_key=dispatch.wake_key,
            receipt_path=receipt_path,
        )

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            receipt_path.unlink()
        except FileNotFoundError:
            pass
        raise

    return ScheduledWakeClaim(
        claimed=True,
        wake_key=dispatch.wake_key,
        receipt_path=receipt_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dispatch one scheduled wake from an owned continuity checkpoint"
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--issue", required=True, dest="expected_issue")
    parser.add_argument("--branch", required=True, dest="expected_branch")
    parser.add_argument("--head-sha", required=True, dest="expected_head_sha")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        result = dispatch_scheduled_resume(
            args.path,
            expected_issue=args.expected_issue,
            expected_branch=args.expected_branch,
            expected_head_sha=args.expected_head_sha,
        )
    except CheckpointError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result.to_payload(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
