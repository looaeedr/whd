"""Auto-drain missing-record Issue closure after a merge reaches production X.

This module is only a trigger/adapter.  It never closes an Issue directly.
When a merged PR targeting ``cleanup/2d-3d-sync`` carries an exact GitHub
closing keyword for an Issue that has no native Flow v2 ExecutionRecord, the
adapter delegates to the existing trusted ``RECOVER_POST_DELIVERY`` builder and
then to the existing ``FINALIZE`` transaction.  Existing native records remain
owned by their current Flow v2 terminal tail.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.control_transaction import is_post_delivery_recovery_finalize_record
from tools.control_transaction_production_executor import (
    _api,
    _load_state,
    _pr_body_closing_issues,
    execute_one,
    recover_post_delivery_missing_record,
)

PRODUCTION_BRANCH = "cleanup/2d-3d-sync"
COORD_BRANCH = "coord/execution-v2"
RECOVERY_LANE = "github.flowv2.postmerge"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class PostMergeFinalizeError(RuntimeError):
    pass


def _positive_pr_number(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _fresh_exact_merged_pr(
    repo: str,
    token: str,
    *,
    pr_number: int,
    head_sha: str,
) -> dict[str, object] | None:
    pr = _api(repo, "GET", f"/pulls/{pr_number}", token) or {}
    if not isinstance(pr, dict):
        raise PostMergeFinalizeError(f"PR #{pr_number} readback must be an object")
    if pr.get("merged") is not True:
        return None
    if str(pr.get("state") or "").strip().lower() != "closed":
        return None
    if str((pr.get("base") or {}).get("ref") or "").strip() != PRODUCTION_BRANCH:
        return None
    merged_sha = str(pr.get("merge_commit_sha") or "").strip().lower()
    if merged_sha != head_sha:
        return None
    if _positive_pr_number(pr.get("number")) != pr_number:
        raise PostMergeFinalizeError(f"PR #{pr_number} readback identity mismatch")
    return pr


def discover_exact_production_merge_prs(
    repo: str,
    token: str,
    head_sha: str,
) -> list[dict[str, object]]:
    """Return exact merged PRs for this production-X push HEAD.

    GitHub's commit-associated pull-request endpoint can legitimately return an
    empty list for the merge commit created by a PR merge. Candidate discovery
    therefore has narrow fallbacks, but no fallback is authority: every
    candidate is fresh-read and must prove exact merged/base/merge-SHA identity.
    """
    normalized = str(head_sha or "").strip().lower()
    if not SHA_RE.fullmatch(normalized):
        raise PostMergeFinalizeError("head_sha must be a 40-character lowercase SHA")

    candidate_numbers: set[int] = set()
    rows = _api(repo, "GET", f"/commits/{normalized}/pulls", token) or []
    if not isinstance(rows, list):
        raise PostMergeFinalizeError("commit-associated PR readback must be a list")
    for row in rows:
        if not isinstance(row, dict):
            continue
        number = _positive_pr_number(row.get("number"))
        if number is not None:
            candidate_numbers.add(number)

    if not candidate_numbers:
        commit = _api(repo, "GET", f"/git/commits/{normalized}", token) or {}
        if not isinstance(commit, dict):
            raise PostMergeFinalizeError("merge commit readback must be an object")
        message = str(commit.get("message") or "")
        match = re.search(r"(?m)^Merge pull request #(\d+)\b", message)
        if match is not None:
            candidate_numbers.add(int(match.group(1)))

    if not candidate_numbers:
        encoded_base = quote(PRODUCTION_BRANCH, safe="")
        rows = _api(
            repo,
            "GET",
            f"/pulls?state=closed&base={encoded_base}&sort=updated&direction=desc&per_page=50",
            token,
        ) or []
        if not isinstance(rows, list):
            raise PostMergeFinalizeError("closed production PR fallback must be a list")
        for row in rows:
            if not isinstance(row, dict):
                continue
            merged_sha = str(row.get("merge_commit_sha") or "").strip().lower()
            if merged_sha != normalized:
                continue
            number = _positive_pr_number(row.get("number"))
            if number is not None:
                candidate_numbers.add(number)

    matches: list[dict[str, object]] = []
    for number in sorted(candidate_numbers):
        pr = _fresh_exact_merged_pr(
            repo,
            token,
            pr_number=number,
            head_sha=normalized,
        )
        if pr is not None:
            matches.append(pr)
    return matches


def _issue_readback(repo: str, token: str, issue: int) -> dict[str, object]:
    payload = _api(repo, "GET", f"/issues/{issue}", token) or {}
    if payload.get("pull_request") is not None:
        raise PostMergeFinalizeError(f"closing target #{issue} resolves to a pull request")
    if int(payload.get("number") or 0) != issue:
        raise PostMergeFinalizeError(f"Issue #{issue} readback identity mismatch")
    return payload


def finalize_pr_closing_issues(
    *,
    repo: str,
    token: str,
    pr: dict[str, object],
    run_identity: str,
) -> list[dict[str, object]]:
    """Drain only missing-record linked Issues through canonical recovery/finalize."""
    pr_number = pr.get("number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise PostMergeFinalizeError("merged PR number must be positive")

    results: list[dict[str, object]] = []
    for issue in _pr_body_closing_issues(pr.get("body")):
        observed = _issue_readback(repo, token, issue)
        if str(observed.get("state") or "").strip().lower() == "closed":
            results.append({"issue": issue, "status": "ALREADY_CLOSED"})
            continue

        coord_head, _tree_sha, records = _load_state(repo, token, COORD_BRANCH)
        existing = records.get(issue)
        if existing is not None:
            results.append(
                {
                    "issue": issue,
                    "status": "NATIVE_RECORD_PRESENT",
                    "state": existing.state,
                }
            )
            continue

        invocation_identity = f"{run_identity}:pr{pr_number}:issue{issue}"
        recovery = recover_post_delivery_missing_record(
            repo=repo,
            token=token,
            coord_branch=COORD_BRANCH,
            issue=issue,
            lane_id=RECOVERY_LANE,
            invocation_identity=invocation_identity,
            expected_coord_head=coord_head,
            supplied_effect={"pr_number": pr_number},
        )
        if recovery.get("post_state") != "INTEGRATING":
            raise PostMergeFinalizeError(
                f"Issue #{issue} recovery did not enter INTEGRATING"
            )

        terminal = execute_one(
            repo=repo,
            token=token,
            coord_branch=COORD_BRANCH,
            issue=issue,
            kind="FINALIZE",
            lane_id=RECOVERY_LANE,
            invocation_identity=invocation_identity,
            supplied_effect={},
            _allow_terminal_drain=False,
            _allow_delivery_sibling_drain=True,
        )
        post_state = terminal.get("post_state")
        if post_state != "DONE":
            raise PostMergeFinalizeError(
                f"Issue #{issue} FINALIZE did not reach DONE: {post_state!r}"
            )
        results.append(
            {"issue": issue, "status": "FINALIZED", "post_state": post_state}
        )

    return results


def drain_pending_post_delivery_finalizes(
    *, repo: str, token: str,
) -> list[dict[str, object]]:
    """Resume exact trusted recovery tails left by an interrupted older push.

    Only already-merged records carrying the validated post-delivery recovery
    proof can enter this sweep. Reuse each recorded invocation identity as a
    replay of its exact failed terminal step, not a new work claim.
    """
    _coord_head, _tree_sha, records = _load_state(repo, token, COORD_BRANCH)
    finalized: list[dict[str, object]] = []
    for issue, record in sorted(records.items()):
        if not (
            record.owner_kind == "RECOVERY"
            and record.owner_id == RECOVERY_LANE
            and record.lane_id == RECOVERY_LANE
            and is_post_delivery_recovery_finalize_record(record)
        ):
            continue
        if record.lease is None or not str(record.lease.invocation_identity).strip():
            raise PostMergeFinalizeError(
                f"Issue #{issue} trusted recovery FINALIZE missing exact prior lease"
            )
        terminal = execute_one(
            repo=repo,
            token=token,
            coord_branch=COORD_BRANCH,
            issue=issue,
            kind="FINALIZE",
            lane_id=RECOVERY_LANE,
            invocation_identity=record.lease.invocation_identity,
            supplied_effect={},
            _allow_terminal_drain=False,
            _allow_delivery_sibling_drain=True,
        )
        if terminal.get("post_state") != "DONE":
            raise PostMergeFinalizeError(
                f"Issue #{issue} recovery backlog FINALIZE did not reach DONE"
            )
        finalized.append(
            {"issue": issue, "status": "FINALIZED", "post_state": "DONE"}
        )
    return finalized


def run(*, repo: str, token: str, head_sha: str, run_identity: str) -> dict[str, object]:
    recovery_backlog = drain_pending_post_delivery_finalizes(
        repo=repo, token=token,
    )
    prs = discover_exact_production_merge_prs(repo, token, head_sha)
    deliveries: list[dict[str, object]] = []
    for pr in prs:
        deliveries.append(
            {
                "pr_number": int(pr["number"]),
                "issues": finalize_pr_closing_issues(
                    repo=repo,
                    token=token,
                    pr=pr,
                    run_identity=run_identity,
                ),
            }
        )
    return {
        "schema": "WHD_PRODUCTION_X_POST_MERGE_FINALIZE_V1",
        "production_branch": PRODUCTION_BRANCH,
        "head_sha": head_sha,
        "associated_merged_prs": [int(pr["number"]) for pr in prs],
        "deliveries": deliveries,
        "recovery_backlog": recovery_backlog,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if not repo or not token or not run_id:
        raise SystemExit("GITHUB_REPOSITORY, GITHUB_TOKEN and GITHUB_RUN_ID are required")
    result = run(
        repo=repo,
        token=token,
        head_sha=args.head_sha,
        run_identity=f"github:production-x-post-merge:{run_id}",
    )
    output = Path(args.output)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
