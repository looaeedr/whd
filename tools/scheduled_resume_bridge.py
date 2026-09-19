"""Executable scheduled wake dispatcher for WHD continuity checkpoints.

This module deliberately owns no workflow state transitions. It verifies exact
checkpoint ownership, delegates state routing to tools.continuity_controller,
and emits a machine-readable decision for the waking runtime.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from tools.continuity_controller import (
    CheckpointError,
    ScheduledResumeAction,
    assert_checkpoint_owner,
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

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["action"] = self.action.value
        return payload


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
    return ScheduledResumeDispatch(
        issue=checkpoint.issue,
        branch=checkpoint.branch,
        head_sha=checkpoint.head_sha,
        state=checkpoint.state.value,
        action=action,
        next_action=checkpoint.next_action,
        run_id=checkpoint.run_id,
        job_id=checkpoint.job_id,
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
