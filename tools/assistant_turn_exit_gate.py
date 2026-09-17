"""Outer executable assistant turn-exit gate.

This hook never treats checkpoint existence as permission to exit. It requires a
current guard-invocation proof previously minted by the canonical continuity
controller against the exact owning checkpoint.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.continuity_controller import (  # noqa: E402
    CheckpointError,
    TurnExitBlocked,
    assert_turn_exit_permitted,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail-closed assistant turn-exit boundary")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--head-sha", required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        checkpoint = assert_turn_exit_permitted(
            args.checkpoint,
            args.receipt,
            expected_issue=args.issue,
            expected_branch=args.branch,
            expected_head_sha=args.head_sha,
        )
    except (TurnExitBlocked, CheckpointError) as exc:
        print(f"TURN_EXIT_FAIL_CLOSED: {exc}")
        return 2

    print(
        "TURN_EXIT_PERMITTED "
        f"issue={checkpoint.issue} branch={checkpoint.branch} "
        f"head_sha={checkpoint.head_sha} state={checkpoint.state.value}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
