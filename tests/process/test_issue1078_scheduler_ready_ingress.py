from tools.execution_scheduler_view import build_scheduler_view
from tools.scheduler_ready_ingress import (
    SchedulerIssueCandidateError,
    build_scheduler_dispatch_candidate,
)

LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"
LANE_B = "scheduler.e58ea936e7d0b12bd0d475314709d6f1"
NOW = "2026-10-01T05:00:00Z"


def _issue(body: str, *, number: int = 1078, state: str = "open", author: str = "looaeedr"):
    return {
        "issue_number": number,
        "state": state,
        "user": {"login": author},
        "body": body,
        "title": "scheduler ingress test",
    }


def test_owner_authored_explicit_scheduler_marker_becomes_ingress_required_when_ready_index_empty():
    candidate = build_scheduler_dispatch_candidate(
        _issue("WHD_SCHEDULER_DISPATCH_REQUEST_V1\nlane=ANY"),
        repository_owner="looaeedr",
        source_branch="cleanup/2d-3d-sync",
        source_sha="a" * 40,
        target_branch="cleanup/2d-3d-sync",
        target_sha="a" * 40,
    )
    view = build_scheduler_view(
        [],
        lane_id=LANE_A,
        invocation_identity="scheduled:00:new",
        now=NOW,
        dispatch_candidates=[candidate],
    )
    assert view.decision == "INGRESS_REQUIRED"
    assert view.selected_issue == 1078
    assert view.requires_transaction == "DISPATCH_READY"


def test_arbitrary_open_issue_is_still_not_execution_authority():
    try:
        build_scheduler_dispatch_candidate(
            _issue("ordinary open issue"),
            repository_owner="looaeedr",
            source_branch="cleanup/2d-3d-sync",
            source_sha="a" * 40,
            target_branch="cleanup/2d-3d-sync",
            target_sha="a" * 40,
        )
    except SchedulerIssueCandidateError as exc:
        assert "marker" in str(exc)
    else:
        raise AssertionError("plain open issue must not become scheduler authority")


def test_lane_specific_marker_is_visible_only_to_matching_lane():
    candidate = build_scheduler_dispatch_candidate(
        _issue("WHD_SCHEDULER_DISPATCH_REQUEST_V1\nlane=B"),
        repository_owner="looaeedr",
        source_branch="cleanup/2d-3d-sync",
        source_sha="a" * 40,
        target_branch="cleanup/2d-3d-sync",
        target_sha="a" * 40,
    )
    a = build_scheduler_view([], lane_id=LANE_A, invocation_identity="scheduled:00:new", now=NOW, dispatch_candidates=[candidate])
    b = build_scheduler_view([], lane_id=LANE_B, invocation_identity="scheduled:B15:new", now=NOW, dispatch_candidates=[candidate])
    assert a.decision == "NO_EXECUTABLE_WORK"
    assert b.decision == "INGRESS_REQUIRED"
