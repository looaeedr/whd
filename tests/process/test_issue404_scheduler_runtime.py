from __future__ import annotations

from tools.continuity_controller import Checkpoint, ContinuityState
from tools.scheduled_resume_issue_state import (
    SCHEDULED_RESUME_ELIGIBLE_MARKER,
    is_scheduled_resume_eligible,
    parse_issue_checkpoint,
    render_issue_checkpoint,
    set_scheduled_resume_eligible,
)
from tools.scheduled_resume_executor import (
    build_headless_agent_prompt,
    should_invoke_headless_agent,
)
from tools.scheduled_resume_runtime import (
    ScheduledWakeDisposition,
    ScheduledWakeEvaluation,
)
from tools.scheduled_resume_lease import GitHubLeaseRecord, parse_issue_lease, render_issue_lease

from datetime import datetime, timezone


def cp(state=ContinuityState.RUNNING, *, next_action="run exact GREEN", run_id=None):
    if state is ContinuityState.WAITING_REMOTE and run_id is None:
        run_id = 456
    if state in {ContinuityState.TERMINAL_SUCCESS, ContinuityState.TERMINAL_FAILURE}:
        next_action = None
    return Checkpoint(
        issue="#404",
        branch="continuity/issue404-scheduled-resume-runtime-20260920",
        head_sha="e" * 40,
        state=state,
        next_action=next_action,
        run_id=run_id,
    )


def test_issue_body_roundtrips_canonical_checkpoint_and_preserves_narrative():
    body = "spec narrative\n"
    rendered = render_issue_checkpoint(body, cp())
    loaded = parse_issue_checkpoint(rendered)
    assert loaded == cp()
    assert rendered.startswith("spec narrative")
    assert '"state": "RUNNING"' in rendered


def test_checkpoint_update_preserves_shared_lease_block():
    lease = GitHubLeaseRecord(
        holder="scheduled-bridge-run-1",
        acquired_at=datetime(2026, 9, 20, 6, tzinfo=timezone.utc),
        ttl_seconds=600,
    )
    body = render_issue_lease("spec narrative", lease)
    body = render_issue_checkpoint(body, cp(ContinuityState.RECOVERING, next_action="fix exact failure"))
    assert parse_issue_lease(body) == lease
    assert parse_issue_checkpoint(body).state is ContinuityState.RECOVERING


def test_eligibility_marker_is_independent_from_checkpoint_and_lease():
    body = render_issue_checkpoint("spec narrative", cp())
    enabled = set_scheduled_resume_eligible(body, True)
    assert SCHEDULED_RESUME_ELIGIBLE_MARKER in enabled
    assert is_scheduled_resume_eligible(enabled) is True
    assert parse_issue_checkpoint(enabled) == cp()
    disabled = set_scheduled_resume_eligible(enabled, False)
    assert is_scheduled_resume_eligible(disabled) is False
    assert parse_issue_checkpoint(disabled) == cp()


def evaluation(disposition, checkpoint=None, *, next_action=None):
    checkpoint = checkpoint or cp()
    return ScheduledWakeEvaluation(
        checkpoint=checkpoint,
        disposition=disposition,
        next_action=next_action,
        reason="test",
    )


def test_agent_prompt_contains_exact_durable_owner_and_next_action():
    checkpoint = cp(ContinuityState.RUNNING, next_action="run exact GREEN")
    ev = evaluation(
        ScheduledWakeDisposition.EXECUTE_NEXT_ACTION,
        checkpoint,
        next_action=checkpoint.next_action,
    )
    assert should_invoke_headless_agent(ev) is True
    prompt = build_headless_agent_prompt(ev)
    assert "#404" in prompt
    assert checkpoint.branch in prompt
    assert checkpoint.head_sha in prompt
    assert "run_id=none" in prompt
    assert "run exact GREEN" in prompt
    assert "fresh-read" in prompt.lower()
    assert "force push" in prompt.lower()


def test_recovering_and_closing_handoff_are_agent_work_but_noop_blocked_are_not():
    recovering_cp = cp(ContinuityState.RECOVERING, next_action="inspect exact failure")
    recovering = evaluation(
        ScheduledWakeDisposition.CONTINUE_RECOVERY,
        recovering_cp,
        next_action=recovering_cp.next_action,
    )
    closing = evaluation(
        ScheduledWakeDisposition.CLOSING_HANDOFF,
        cp(ContinuityState.TERMINAL_SUCCESS),
    )
    noop = evaluation(ScheduledWakeDisposition.NO_OP)
    blocked = evaluation(ScheduledWakeDisposition.NOTIFY_BLOCKER)

    assert should_invoke_headless_agent(recovering) is True
    assert should_invoke_headless_agent(closing) is True
    assert should_invoke_headless_agent(noop) is False
    assert should_invoke_headless_agent(blocked) is False
    assert "inspect exact failure" in build_headless_agent_prompt(recovering)
    assert "issue-closure-gate" in build_headless_agent_prompt(closing)


def test_waiting_remote_identity_is_in_prompt_when_recovery_requires_agent():
    checkpoint = cp(
        ContinuityState.RECOVERING,
        next_action="recover locked remote evidence",
        run_id=98765,
    )
    ev = evaluation(
        ScheduledWakeDisposition.CONTINUE_RECOVERY,
        checkpoint,
        next_action=checkpoint.next_action,
    )
    prompt = build_headless_agent_prompt(ev)
    assert "run_id=98765" in prompt
