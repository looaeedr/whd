from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.continuity_controller import Checkpoint, ContinuityState
from tools.scheduled_resume_driver import prepare_scheduled_issue, release_scheduled_issue
from tools.scheduled_resume_issue_state import (
    parse_issue_checkpoint,
    render_issue_checkpoint,
    set_scheduled_resume_eligible,
)
from tools.scheduled_resume_lease import parse_issue_lease
from tools.scheduled_resume_runtime import RemoteRunObservation, ScheduledWakeDisposition


UTC = timezone.utc
ISSUE = 404
BRANCH = "continuity/issue404-scheduled-resume-runtime-20260920"
HEAD = "f" * 40


class Store:
    def __init__(self, body):
        self.body = body
        self.writes = []

    def read_body(self):
        return self.body

    def write_body(self, body):
        self.body = body
        self.writes.append(body)


def checkpoint(state=ContinuityState.RUNNING, *, head=HEAD, run_id=None, next_action="run exact task"):
    if state is ContinuityState.WAITING_REMOTE and run_id is None:
        run_id = 8001
    if state in {ContinuityState.TERMINAL_SUCCESS, ContinuityState.TERMINAL_FAILURE}:
        next_action = None
    return Checkpoint(
        issue="#404",
        branch=BRANCH,
        head_sha=head,
        state=state,
        next_action=next_action,
        run_id=run_id,
    )


def eligible_store(cp):
    return Store(set_scheduled_resume_eligible(render_issue_checkpoint("ticket", cp), True))


def test_ineligible_issue_is_safe_noop_without_acquiring_lease():
    store = Store(render_issue_checkpoint("ticket", checkpoint()))
    result = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-1",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
    )
    assert result.eligible is False
    assert result.lease_acquired is False
    assert result.requires_agent is False
    assert parse_issue_lease(store.body) is None


def test_running_acquires_shared_lease_and_emits_exact_agent_prompt():
    store = eligible_store(checkpoint())
    result = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-2",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
    )
    assert result.lease_acquired is True
    assert result.disposition is ScheduledWakeDisposition.EXECUTE_NEXT_ACTION
    assert result.requires_agent is True
    assert "#404" in result.agent_prompt
    assert BRANCH in result.agent_prompt
    assert HEAD in result.agent_prompt
    assert "run exact task" in result.agent_prompt
    assert parse_issue_lease(store.body).holder == "scheduled-run-2"


def test_duplicate_actor_cannot_prepare_same_issue_while_lease_is_live():
    store = eligible_store(checkpoint())
    first = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-owner",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
    )
    second = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="manual-runtime-other",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, 1, tzinfo=UTC),
    )
    assert first.lease_acquired is True
    assert second.lease_acquired is False
    assert second.requires_agent is False
    assert second.lease_owner == "scheduled-run-owner"


def test_active_waiting_remote_noops_without_agent_and_preserves_checkpoint():
    cp = checkpoint(ContinuityState.WAITING_REMOTE, run_id=8002, next_action="poll exact run")
    store = eligible_store(cp)
    remote = RemoteRunObservation(
        found=True,
        run_id=8002,
        head_sha=HEAD,
        status="in_progress",
        conclusion=None,
        updated_at=datetime(2026, 9, 20, 11, 30, tzinfo=UTC),
    )
    result = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-3",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
        remote=remote,
    )
    assert result.disposition is ScheduledWakeDisposition.NO_OP
    assert result.requires_agent is False
    assert parse_issue_checkpoint(store.body).state is ContinuityState.WAITING_REMOTE
    assert parse_issue_checkpoint(store.body).run_id == 8002


def test_terminal_remote_transitions_checkpoint_to_recovering_and_emits_agent_prompt():
    cp = checkpoint(ContinuityState.WAITING_REMOTE, run_id=8003, next_action="poll exact run")
    store = eligible_store(cp)
    remote = RemoteRunObservation(
        found=True,
        run_id=8003,
        head_sha=HEAD,
        status="completed",
        conclusion="success",
        updated_at=datetime(2026, 9, 20, 12, tzinfo=UTC),
    )
    result = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-4",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
        remote=remote,
    )
    persisted = parse_issue_checkpoint(store.body)
    assert result.disposition is ScheduledWakeDisposition.CONTINUE_RECOVERY
    assert result.requires_agent is True
    assert persisted.state is ContinuityState.RECOVERING
    assert persisted.run_id == 8003
    assert "run 8003 terminal" in result.agent_prompt


def test_live_head_drift_enters_recovery_on_fresh_head_before_agent():
    old = "a" * 40
    live = "b" * 40
    store = eligible_store(checkpoint(head=old))
    result = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-5",
        live_head_sha=live,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
    )
    persisted = parse_issue_checkpoint(store.body)
    assert persisted.state is ContinuityState.RECOVERING
    assert persisted.head_sha == live
    assert result.requires_agent is True
    assert old in result.agent_prompt
    assert live in result.agent_prompt


def test_release_uses_same_shared_holder_and_clears_lease_only():
    store = eligible_store(checkpoint())
    prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-6",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
    )
    assert release_scheduled_issue(store, holder="scheduled-run-6") is True
    assert parse_issue_lease(store.body) is None
    assert parse_issue_checkpoint(store.body) is not None


def test_terminal_checkpoint_requests_closing_agent_handoff():
    store = eligible_store(checkpoint(ContinuityState.TERMINAL_SUCCESS))
    result = prepare_scheduled_issue(
        store,
        issue_number=ISSUE,
        holder="scheduled-run-7",
        live_head_sha=HEAD,
        now=datetime(2026, 9, 20, 12, tzinfo=UTC),
    )
    assert result.disposition is ScheduledWakeDisposition.CLOSING_HANDOFF
    assert result.requires_agent is True
    assert "issue-closure-gate" in result.agent_prompt


def test_github_reader_fresh_reads_encoded_branch_and_exact_actions_run():
    import json
    from tools.scheduled_resume_driver import GitHubScheduledResumeReader

    calls = []

    class Result:
        def __init__(self, payload, returncode=0, stderr=""):
            self.returncode = returncode
            self.stdout = json.dumps(payload)
            self.stderr = stderr

    def runner(args, **kwargs):
        calls.append(args)
        endpoint = args[-1]
        if "/git/ref/heads/" in endpoint:
            return Result({"object": {"sha": HEAD}})
        if "/actions/runs/9001" in endpoint:
            return Result({
                "id": 9001,
                "head_sha": HEAD,
                "status": "in_progress",
                "conclusion": None,
                "updated_at": "2026-09-20T11:30:00Z",
            })
        raise AssertionError(endpoint)

    reader = GitHubScheduledResumeReader("looaeedr/whd", runner=runner)
    assert reader.branch_head(BRANCH) == HEAD
    obs = reader.remote_run(9001)
    assert obs.run_id == 9001
    assert obs.head_sha == HEAD
    assert obs.status == "in_progress"
    assert obs.updated_at == datetime(2026, 9, 20, 11, 30, tzinfo=UTC)
    assert "%2F" in calls[0][-1]
    assert calls[1][-1] == "repos/looaeedr/whd/actions/runs/9001"
