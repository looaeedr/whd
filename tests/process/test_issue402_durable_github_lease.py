from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tools.continuity_controller import CheckpointError
from tools.scheduled_resume_lease import (
    GitHubLeaseRecord,
    acquire_shared_lease,
    parse_issue_lease,
    release_shared_lease,
    render_issue_lease,
)


UTC = timezone.utc


class MemoryIssueBodyStore:
    def __init__(self, body: str = ""):
        self.body = body
        self.writes: list[str] = []

    def read_body(self) -> str:
        return self.body

    def write_body(self, body: str) -> None:
        self.body = body
        self.writes.append(body)


def dt(hour: int) -> datetime:
    return datetime(2026, 9, 20, hour, 0, 0, tzinfo=UTC)


def test_lease_roundtrip_in_shared_issue_body():
    lease = GitHubLeaseRecord(
        holder="scheduled-bridge-run-100",
        acquired_at=dt(6),
        ttl_seconds=600,
    )
    body = render_issue_lease("checkpoint text", lease)
    parsed = parse_issue_lease(body)
    assert parsed == lease
    assert "scheduled-bridge-run-100" in body
    assert "ttl_seconds" in body


def test_unexpired_shared_lease_blocks_other_actor():
    store = MemoryIssueBodyStore(
        render_issue_lease(
            "checkpoint",
            GitHubLeaseRecord("manual-runtime-1", dt(6), 600),
        )
    )
    result = acquire_shared_lease(
        store,
        holder="scheduled-bridge-run-200",
        now=dt(6) + timedelta(minutes=5),
        ttl_seconds=600,
    )
    assert result.acquired is False
    assert result.owner == "manual-runtime-1"
    assert store.writes == []


def test_expired_lease_can_be_replaced_and_post_write_verified():
    store = MemoryIssueBodyStore(
        render_issue_lease(
            "checkpoint",
            GitHubLeaseRecord("old-holder", dt(6), 600),
        )
    )
    result = acquire_shared_lease(
        store,
        holder="scheduled-bridge-run-201",
        now=dt(7),
        ttl_seconds=600,
    )
    assert result.acquired is True
    assert result.owner == "scheduled-bridge-run-201"
    assert parse_issue_lease(store.read_body()).holder == "scheduled-bridge-run-201"
    assert len(store.writes) == 1


def test_same_holder_acquire_is_idempotent_without_rewrite():
    store = MemoryIssueBodyStore(
        render_issue_lease(
            "checkpoint",
            GitHubLeaseRecord("scheduled-bridge-run-202", dt(6), 600),
        )
    )
    result = acquire_shared_lease(
        store,
        holder="scheduled-bridge-run-202",
        now=dt(6) + timedelta(minutes=2),
        ttl_seconds=600,
    )
    assert result.acquired is True
    assert result.already_owned is True
    assert store.writes == []


def test_post_write_verification_fails_closed_if_another_actor_wins():
    class RacingStore(MemoryIssueBodyStore):
        def write_body(self, body: str) -> None:
            super().write_body(body)
            self.body = render_issue_lease(
                "checkpoint",
                GitHubLeaseRecord("manual-runtime-winner", dt(7), 600),
            )

    store = RacingStore("checkpoint")
    result = acquire_shared_lease(
        store,
        holder="scheduled-bridge-run-loser",
        now=dt(7),
        ttl_seconds=600,
    )
    assert result.acquired is False
    assert result.owner == "manual-runtime-winner"


def test_release_requires_same_holder_and_clears_shared_lease():
    store = MemoryIssueBodyStore(
        render_issue_lease(
            "checkpoint",
            GitHubLeaseRecord("scheduled-bridge-run-203", dt(6), 600),
        )
    )
    released = release_shared_lease(store, holder="scheduled-bridge-run-203")
    assert released is True
    assert parse_issue_lease(store.read_body()) is None


def test_release_by_wrong_holder_fails_closed():
    store = MemoryIssueBodyStore(
        render_issue_lease(
            "checkpoint",
            GitHubLeaseRecord("manual-runtime-owner", dt(6), 600),
        )
    )
    with pytest.raises(CheckpointError, match="lease owner mismatch"):
        release_shared_lease(store, holder="scheduled-bridge-run-other")


def test_manual_and_scheduled_actors_share_one_lock_namespace():
    store = MemoryIssueBodyStore("checkpoint")
    scheduled = acquire_shared_lease(
        store,
        holder="scheduled-bridge-run-204",
        now=dt(6),
        ttl_seconds=600,
    )
    manual = acquire_shared_lease(
        store,
        holder="manual-runtime-9",
        now=dt(6) + timedelta(minutes=1),
        ttl_seconds=600,
    )
    assert scheduled.acquired is True
    assert manual.acquired is False
    assert manual.owner == "scheduled-bridge-run-204"


def test_github_issue_body_store_uses_issue_api_for_shared_state(monkeypatch):
    calls = []

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        if "--method" in args:
            return Result(stdout="{}")
        return Result(stdout="checkpoint body\n")

    from tools.scheduled_resume_lease import GitHubIssueBodyStore

    store = GitHubIssueBodyStore("looaeedr/whd", 402, runner=runner)
    assert store.read_body() == "checkpoint body"
    store.write_body("updated body")

    assert calls[0][0] == [
        "gh", "api", "repos/looaeedr/whd/issues/402", "--jq", ".body // \"\""
    ]
    assert calls[1][0] == [
        "gh", "api", "--method", "PATCH", "repos/looaeedr/whd/issues/402", "--input", "-"
    ]
    assert '"body": "updated body"' in calls[1][1]["input"]
