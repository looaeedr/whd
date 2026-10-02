"""Operational driver for one Scheduled Resume issue.

The driver is invoked by the default-branch scheduler after checkout of the
accepted runtime implementation. It acquires the shared GitHub issue lease,
fresh-reads live identity, applies the canonical runtime policy, persists any
checkpoint transition, and emits a machine-readable decision. It never invokes
the headless agent itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from tools.continuity_controller import (
    Checkpoint,
    CheckpointError,
    ContinuityState,
    transition_checkpoint,
)
from tools.scheduled_resume_executor import (
    build_headless_agent_prompt,
    should_invoke_headless_agent,
)
from tools.scheduled_resume_issue_state import (
    is_scheduled_resume_eligible,
    parse_issue_checkpoint,
    render_issue_checkpoint,
)
from tools.scheduled_resume_lease import (
    GitHubIssueBodyStore,
    IssueBodyStore,
    acquire_shared_lease,
    release_shared_lease,
)
from tools.scheduled_resume_runtime import (
    RemoteRunObservation,
    ScheduledWakeDisposition,
    ScheduledWakeEvaluation,
    evaluate_scheduled_wake,
)


@dataclass(frozen=True)
class ScheduledIssuePreparation:
    issue_number: int
    eligible: bool
    lease_acquired: bool
    lease_owner: str | None
    disposition: ScheduledWakeDisposition | None
    requires_agent: bool
    agent_prompt: str | None
    branch: str | None
    head_sha: str | None
    state: str | None
    run_id: int | None
    next_action: str | None
    notification: str | None
    reason: str

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["disposition"] = (
            None if self.disposition is None else self.disposition.value
        )
        return payload


def _persist_checkpoint(store: IssueBodyStore, checkpoint: Checkpoint) -> None:
    current_body = store.read_body()
    store.write_body(render_issue_checkpoint(current_body, checkpoint))
    verified = parse_issue_checkpoint(store.read_body())
    if verified != checkpoint:
        raise CheckpointError("GitHub issue checkpoint post-write verification failed")


def _head_drift_evaluation(
    checkpoint: Checkpoint,
    *,
    live_head_sha: str,
) -> ScheduledWakeEvaluation:
    if checkpoint.is_terminal:
        raise CheckpointError(
            "terminal checkpoint owner drift requires explicit closure revalidation"
        )
    old_head = checkpoint.head_sha
    next_action = (
        "classify execution branch HEAD drift: "
        f"checkpoint={old_head} live={live_head_sha}; "
        "revalidate only the affected scope, refresh durable ownership, and continue"
    )
    recovered = transition_checkpoint(
        checkpoint,
        state=ContinuityState.RECOVERING,
        next_action=next_action,
        head_sha=live_head_sha,
        evidence=(
            f"scheduled-resume owner drift checkpoint={old_head} live={live_head_sha}",
        ),
    )
    return ScheduledWakeEvaluation(
        checkpoint=recovered,
        disposition=ScheduledWakeDisposition.CONTINUE_RECOVERY,
        next_action=next_action,
        reason=f"owner head drift checkpoint={old_head} live={live_head_sha}",
    )


def prepare_scheduled_issue(
    store: IssueBodyStore,
    *,
    issue_number: int,
    holder: str,
    live_head_sha: str,
    now: datetime,
    remote: RemoteRunObservation | None = None,
    ttl_seconds: int = 600,
) -> ScheduledIssuePreparation:
    """Prepare exactly one eligible issue while retaining its lease for the caller."""

    issue_number = int(issue_number)
    body = store.read_body()
    if not is_scheduled_resume_eligible(body):
        return ScheduledIssuePreparation(
            issue_number=issue_number,
            eligible=False,
            lease_acquired=False,
            lease_owner=None,
            disposition=None,
            requires_agent=False,
            agent_prompt=None,
            branch=None,
            head_sha=None,
            state=None,
            run_id=None,
            next_action=None,
            notification=None,
            reason="issue is not scheduled-resume eligible",
        )

    checkpoint = parse_issue_checkpoint(body)
    if checkpoint is None:
        raise CheckpointError("eligible issue has no canonical continuity checkpoint")
    expected_issue = f"#{issue_number}"
    if checkpoint.issue != expected_issue:
        raise CheckpointError(
            f"checkpoint issue mismatch: expected={expected_issue!r} actual={checkpoint.issue!r}"
        )

    lease = acquire_shared_lease(
        store,
        holder=holder,
        now=now,
        ttl_seconds=ttl_seconds,
    )
    if not lease.acquired:
        return ScheduledIssuePreparation(
            issue_number=issue_number,
            eligible=True,
            lease_acquired=False,
            lease_owner=lease.owner,
            disposition=None,
            requires_agent=False,
            agent_prompt=None,
            branch=checkpoint.branch,
            head_sha=checkpoint.head_sha,
            state=checkpoint.state.value,
            run_id=checkpoint.run_id,
            next_action=checkpoint.next_action,
            notification=None,
            reason=f"shared lease owned by {lease.owner}",
        )

    # Re-read after lease mutation. This is the durable state the holder owns.
    checkpoint = parse_issue_checkpoint(store.read_body())
    if checkpoint is None:
        raise CheckpointError("checkpoint disappeared after lease acquisition")
    if checkpoint.issue != expected_issue:
        raise CheckpointError("checkpoint owner changed during lease acquisition")

    live_head_sha = str(live_head_sha).strip()
    if not live_head_sha:
        raise CheckpointError("fresh live branch HEAD is required")

    if checkpoint.head_sha != live_head_sha:
        evaluation = _head_drift_evaluation(
            checkpoint,
            live_head_sha=live_head_sha,
        )
    else:
        evaluation = evaluate_scheduled_wake(
            checkpoint,
            now=now,
            remote=remote,
        )

    if evaluation.checkpoint != checkpoint:
        _persist_checkpoint(store, evaluation.checkpoint)

    requires_agent = should_invoke_headless_agent(evaluation)
    prompt = build_headless_agent_prompt(evaluation) if requires_agent else None
    current = evaluation.checkpoint
    return ScheduledIssuePreparation(
        issue_number=issue_number,
        eligible=True,
        lease_acquired=True,
        lease_owner=holder,
        disposition=evaluation.disposition,
        requires_agent=requires_agent,
        agent_prompt=prompt,
        branch=current.branch,
        head_sha=current.head_sha,
        state=current.state.value,
        run_id=current.run_id,
        next_action=evaluation.next_action or current.next_action,
        notification=evaluation.notification,
        reason=evaluation.reason,
    )


def release_scheduled_issue(store: IssueBodyStore, *, holder: str) -> bool:
    return release_shared_lease(store, holder=holder)


Runner = callable


class GitHubScheduledResumeReader:
    """Fresh GitHub identity/run reader backed by gh api."""

    def __init__(self, repo: str, *, runner=subprocess.run) -> None:
        self.repo = str(repo).strip()
        self._runner = runner
        if not self.repo or "/" not in self.repo:
            raise CheckpointError("repo must be owner/name")

    def _api_json(self, endpoint: str, *, allow_404: bool = False) -> dict | None:
        proc = self._runner(
            ["gh", "api", endpoint],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "").strip()
            if allow_404 and ("404" in message or "Not Found" in message):
                return None
            raise CheckpointError(f"GitHub API read failed for {endpoint}: {message}")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise CheckpointError(f"GitHub API returned invalid JSON for {endpoint}") from exc
        if not isinstance(payload, dict):
            raise CheckpointError(f"GitHub API payload must be object for {endpoint}")
        return payload

    def branch_head(self, branch: str) -> str:
        encoded = quote(str(branch), safe="")
        payload = self._api_json(f"repos/{self.repo}/git/ref/heads/{encoded}")
        assert payload is not None
        try:
            sha = str(payload["object"]["sha"]).strip()
        except (KeyError, TypeError) as exc:
            raise CheckpointError("branch ref payload missing object.sha") from exc
        if not sha:
            raise CheckpointError("branch ref returned blank SHA")
        return sha

    def remote_run(self, run_id: int) -> RemoteRunObservation:
        payload = self._api_json(
            f"repos/{self.repo}/actions/runs/{int(run_id)}",
            allow_404=True,
        )
        if payload is None:
            return RemoteRunObservation(
                found=False,
                run_id=int(run_id),
                head_sha="missing",
                status=None,
                conclusion=None,
                updated_at=None,
            )
        updated_raw = payload.get("updated_at")
        updated_at = None
        if updated_raw:
            try:
                updated_at = datetime.fromisoformat(
                    str(updated_raw).replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise CheckpointError("remote run updated_at is invalid") from exc
        return RemoteRunObservation(
            found=True,
            run_id=int(payload.get("id", run_id)),
            head_sha=str(payload.get("head_sha") or "").strip(),
            status=payload.get("status"),
            conclusion=payload.get("conclusion"),
            updated_at=updated_at,
        )


def prepare_github_scheduled_issue(
    *,
    repo: str,
    issue_number: int,
    holder: str,
    now: datetime | None = None,
    ttl_seconds: int = 600,
    runner=subprocess.run,
) -> ScheduledIssuePreparation:
    store = GitHubIssueBodyStore(repo, issue_number, runner=runner)
    body = store.read_body()
    if not is_scheduled_resume_eligible(body):
        return prepare_scheduled_issue(
            store,
            issue_number=issue_number,
            holder=holder,
            live_head_sha="not-used",
            now=now or datetime.now(timezone.utc),
            ttl_seconds=ttl_seconds,
        )
    checkpoint = parse_issue_checkpoint(body)
    if checkpoint is None:
        raise CheckpointError("eligible issue has no canonical continuity checkpoint")

    reader = GitHubScheduledResumeReader(repo, runner=runner)
    live_head = reader.branch_head(checkpoint.branch)
    remote = (
        reader.remote_run(checkpoint.run_id)
        if checkpoint.state is ContinuityState.WAITING_REMOTE
        else None
    )
    return prepare_scheduled_issue(
        store,
        issue_number=issue_number,
        holder=holder,
        live_head_sha=live_head,
        now=now or datetime.now(timezone.utc),
        remote=remote,
        ttl_seconds=ttl_seconds,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WHD Scheduled Resume driver")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repo", required=True)
    prepare.add_argument("--issue", required=True, type=int)
    prepare.add_argument("--holder", required=True)
    prepare.add_argument("--ttl-seconds", type=int, default=600)

    release = sub.add_parser("release")
    release.add_argument("--repo", required=True)
    release.add_argument("--issue", required=True, type=int)
    release.add_argument("--holder", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_github_scheduled_issue(
                repo=args.repo,
                issue_number=args.issue,
                holder=args.holder,
                ttl_seconds=args.ttl_seconds,
            )
            print(json.dumps(result.to_payload(), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "release":
            store = GitHubIssueBodyStore(args.repo, args.issue)
            released = release_scheduled_issue(store, holder=args.holder)
            print(json.dumps({"released": released}, ensure_ascii=False))
            return 0
        raise CheckpointError(f"unsupported command: {args.command}")
    except CheckpointError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
