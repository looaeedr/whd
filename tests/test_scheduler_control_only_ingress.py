from tools.scheduler_ready_ingress import (
    LANE_A,
    build_scheduler_dispatch_candidate,
)


SHA = "9a10dc9113284c5daf1554b6122b06d526008c1c"


def test_control_only_scheduler_marker_binds_finalize_without_content_branch() -> None:
    candidate = build_scheduler_dispatch_candidate(
        {
            "state": "open",
            "pull_request": None,
            "issue_number": 1080,
            "created_at": "2026-10-06T02:56:32Z",
            "user": {"login": "looaeedr"},
            "body": (
                "WHD_SCHEDULER_DISPATCH_REQUEST_V1\n"
                "lane=A\n"
                "completion=CONTROL_ONLY\n"
            ),
        },
        repository_owner="looaeedr",
        source_branch="cleanup/2d-3d-sync",
        source_sha=SHA,
        target_branch="cleanup/2d-3d-sync",
        target_sha=SHA,
    )

    request = candidate.ingress_request
    assert candidate.lane == "A"
    assert candidate.completion == "CONTROL_ONLY"
    assert request.work_branch == "cleanup/2d-3d-sync"
    assert request.post_acquire is not None
    assert request.post_acquire.kind == "FINALIZE"
    assert request.post_acquire.args == {"completion_mode": "CONTROL_ONLY"}
