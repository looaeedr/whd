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
    assert_no_executable_leaf_for_turn_exit,
    assert_turn_exit_permitted,
)

from tools.runtime_report_identity import (  # noqa: E402
    RuntimeReportIdentityError,
    build_runtime_report_identity,
    format_runtime_report_prefix,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail-closed assistant turn-exit boundary")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--census-exhaustive", action="store_true")
    parser.add_argument("--executable-leaf-count", required=True, type=int)
    parser.add_argument("--continuation-action", default="")
    parser.add_argument("--census-observed-at", required=True)
    parser.add_argument("--report-handler", required=True)
    parser.add_argument("--report-owner", required=True)
    parser.add_argument("--report-issue", required=True)
    parser.add_argument("--report-slot", required=True)
    parser.add_argument("--report-invocation-identity", required=True)
    parser.add_argument(
        "--report-runtime-kind",
        required=True,
        choices=("INTERACTIVE", "SCHEDULER"),
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        report_identity = build_runtime_report_identity(
            handler=args.report_handler,
            owner=args.report_owner,
            issue=args.report_issue,
            slot=args.report_slot,
            invocation_identity=args.report_invocation_identity,
            runtime_kind=args.report_runtime_kind,
        )
        assert_no_executable_leaf_for_turn_exit(
            exhaustive=args.census_exhaustive,
            executable_leaf_count=args.executable_leaf_count,
            continuation_action=args.continuation_action,
            observed_at=args.census_observed_at,
        )
        checkpoint = assert_turn_exit_permitted(
            args.checkpoint,
            args.receipt,
            expected_issue=args.issue,
            expected_branch=args.branch,
            expected_head_sha=args.head_sha,
        )
    except (TurnExitBlocked, CheckpointError, RuntimeReportIdentityError) as exc:
        print(f"TURN_EXIT_FAIL_CLOSED: {exc}")
        return 2

    print(format_runtime_report_prefix(report_identity))
    print(
        "TURN_EXIT_PERMITTED "
        f"issue={checkpoint.issue} branch={checkpoint.branch} "
        f"head_sha={checkpoint.head_sha} state={checkpoint.state.value}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
