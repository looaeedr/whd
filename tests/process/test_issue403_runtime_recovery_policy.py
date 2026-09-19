from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.continuity_controller import Checkpoint, ContinuityState, transition_checkpoint
from tools.scheduled_resume_runtime import (
    RemoteRunObservation,
    ScheduledWakeDisposition,
    evaluate_scheduled_wake,
)


UTC = timezone.utc
HEAD = "c" * 40


def now(hour=12):
    return datetime(2026, 9, 20, hour, 0, 0, tzinfo=UTC)


def cp(state, *, next_action="continue exact work", run_id=None, blocked_count=0, blocked_last_notified_at=None):
    if state is ContinuityState.WAITING_REMOTE and run_id is None:
        run_id = 12345
    if state in {ContinuityState.TERMINAL_SUCCESS, ContinuityState.TERMINAL_FAILURE}:
        next_action = None
    return Checkpoint(
        issue="#403",
        branch="continuity/issue403-runtime-recovery-policy-20260920",
        head_sha=HEAD,
        state=state,
        next_action=next_action,
        run_id=run_id,
        blocked_count=blocked_count,
        blocked_last_notified_at=blocked_last_notified_at,
    )


def test_running_and_recovering_route_to_exact_existing_next_action():
    running = evaluate_scheduled_wake(cp(ContinuityState.RUNNING), now=now())
    recovering = evaluate_scheduled_wake(cp(ContinuityState.RECOVERING), now=now())
    assert running.disposition is ScheduledWakeDisposition.EXECUTE_NEXT_ACTION
    assert running.next_action == "continue exact work"
    assert recovering.disposition is ScheduledWakeDisposition.CONTINUE_RECOVERY
    assert recovering.next_action == "continue exact work"


def test_waiting_remote_active_nonstale_is_noop_and_preserves_lock():
    checkpoint = cp(ContinuityState.WAITING_REMOTE, run_id=777)
    obs = RemoteRunObservation(
        found=True,
        run_id=777,
        head_sha=HEAD,
        status="in_progress",
        conclusion=None,
        updated_at=now() - timedelta(minutes=30),
    )
    out = evaluate_scheduled_wake(checkpoint, now=now(), remote=obs)
    assert out.disposition is ScheduledWakeDisposition.NO_OP
    assert out.checkpoint == checkpoint
    assert out.checkpoint.run_id == 777


def test_waiting_remote_uses_hour_scale_stale_threshold():
    checkpoint = cp(ContinuityState.WAITING_REMOTE, run_id=778)
    almost = RemoteRunObservation(
        found=True,
        run_id=778,
        head_sha=HEAD,
        status="in_progress",
        conclusion=None,
        updated_at=now() - timedelta(hours=1, minutes=59),
    )
    stale = RemoteRunObservation(
        found=True,
        run_id=778,
        head_sha=HEAD,
        status="in_progress",
        conclusion=None,
        updated_at=now() - timedelta(hours=2, seconds=1),
    )
    assert evaluate_scheduled_wake(checkpoint, now=now(), remote=almost).disposition is ScheduledWakeDisposition.NO_OP
    recovered = evaluate_scheduled_wake(checkpoint, now=now(), remote=stale)
    assert recovered.disposition is ScheduledWakeDisposition.CONTINUE_RECOVERY
    assert recovered.checkpoint.state is ContinuityState.RECOVERING
    assert "stale" in recovered.reason.lower()


def test_waiting_remote_terminal_missing_or_head_mismatch_enters_recovery_without_new_run():
    checkpoint = cp(ContinuityState.WAITING_REMOTE, run_id=779)
    terminal = RemoteRunObservation(
        found=True,
        run_id=779,
        head_sha=HEAD,
        status="completed",
        conclusion="failure",
        updated_at=now(),
    )
    missing = RemoteRunObservation(
        found=False,
        run_id=779,
        head_sha=HEAD,
        status=None,
        conclusion=None,
        updated_at=None,
    )
    wrong_head = RemoteRunObservation(
        found=True,
        run_id=779,
        head_sha="d" * 40,
        status="in_progress",
        conclusion=None,
        updated_at=now(),
    )
    for obs in (terminal, missing, wrong_head):
        out = evaluate_scheduled_wake(checkpoint, now=now(), remote=obs)
        assert out.disposition is ScheduledWakeDisposition.CONTINUE_RECOVERY
        assert out.checkpoint.state is ContinuityState.RECOVERING
        assert out.checkpoint.run_id == 779


def test_blocked_is_silent_before_threshold_then_notifies_genuine_blocker_only():
    checkpoint = cp(ContinuityState.BLOCKED, next_action="need repository secret ANTHROPIC_API_KEY")
    first = evaluate_scheduled_wake(checkpoint, now=now(6))
    second = evaluate_scheduled_wake(first.checkpoint, now=now(7))
    third = evaluate_scheduled_wake(second.checkpoint, now=now(8))

    assert first.disposition is ScheduledWakeDisposition.NO_OP
    assert second.disposition is ScheduledWakeDisposition.NO_OP
    assert third.disposition is ScheduledWakeDisposition.NOTIFY_BLOCKER
    assert third.checkpoint.blocked_count == 3
    assert third.notification == "need repository secret ANTHROPIC_API_KEY"
    assert "third" not in third.notification.lower()
    assert "schedule" not in third.notification.lower()


def test_blocked_notifications_back_off_for_six_hours_but_count_keeps_increasing():
    checkpoint = cp(
        ContinuityState.BLOCKED,
        next_action="need human credential setup",
        blocked_count=3,
        blocked_last_notified_at="2026-09-20T08:00:00Z",
    )
    quiet = evaluate_scheduled_wake(checkpoint, now=now(10))
    notify = evaluate_scheduled_wake(quiet.checkpoint, now=now(14))

    assert quiet.disposition is ScheduledWakeDisposition.NO_OP
    assert quiet.checkpoint.blocked_count == 4
    assert notify.disposition is ScheduledWakeDisposition.NOTIFY_BLOCKER
    assert notify.checkpoint.blocked_count == 5
    assert notify.notification == "need human credential setup"


def test_leaving_blocked_resets_blocked_metadata():
    blocked = cp(
        ContinuityState.BLOCKED,
        next_action="need secret",
        blocked_count=7,
        blocked_last_notified_at="2026-09-20T08:00:00Z",
    )
    resumed = transition_checkpoint(
        blocked,
        state=ContinuityState.RUNNING,
        next_action="continue after secret restored",
    )
    assert resumed.blocked_count == 0
    assert resumed.blocked_last_notified_at is None


def test_terminal_routes_to_closing_handoff_not_permanent_noop():
    success = evaluate_scheduled_wake(cp(ContinuityState.TERMINAL_SUCCESS), now=now())
    failure = evaluate_scheduled_wake(cp(ContinuityState.TERMINAL_FAILURE), now=now())
    assert success.disposition is ScheduledWakeDisposition.CLOSING_HANDOFF
    assert failure.disposition is ScheduledWakeDisposition.CLOSING_HANDOFF
