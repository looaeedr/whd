from datetime import datetime, timezone

import pytest

from tools.scheduler_entrypoint_observation import (
    SchedulerEntrypointObservationError,
    build_entrypoint_observation,
)
from tools.scheduler_host_watchdog import (
    ENTRYPOINTS,
    STATUS_HOST_ENTRY_FAILURE,
    classify_entrypoint,
)

NEW_A00 = "6abe13e395b88191898bbaa2993db13e"
NEW_B15 = "6abe1471dc4481919e423c0df1ed7e00"
LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"


def _spec(key: str):
    return next(spec for spec in ENTRYPOINTS if spec.key == key)


def _old_a00(task_id: str = "old-task") -> dict[str, object]:
    return {
        "schema": "WHD_SCHEDULER_ENTRYPOINT_OBSERVATION_V1",
        "entrypoint": "A00",
        "task_id": task_id,
        "lane_id": LANE_A,
        "invocation_identity": "old-invocation",
        "last_wake_at": "2026-10-05T04:00:00Z",
    }


def test_new_host_generation_can_rebind_on_wake() -> None:
    wake = build_entrypoint_observation(
        previous=_old_a00(),
        entrypoint="A00",
        task_id=NEW_A00,
        lane_id=LANE_A,
        invocation_identity="new-invocation",
        event="WAKE",
        observed_at="2026-10-05T05:00:00Z",
    )
    assert wake["task_id"] == NEW_A00
    assert wake["invocation_identity"] == "new-invocation"
    assert wake["last_wake_at"] == "2026-10-05T05:00:00Z"
    assert wake["last_heartbeat_at"] is None
    assert wake["exit_at"] is None


def test_task_generation_rebind_is_wake_only() -> None:
    with pytest.raises(SchedulerEntrypointObservationError, match="task_id"):
        build_entrypoint_observation(
            previous=_old_a00(),
            entrypoint="A00",
            task_id=NEW_A00,
            lane_id=LANE_A,
            invocation_identity="new-invocation",
            event="HEARTBEAT",
            observed_at="2026-10-05T05:01:00Z",
        )


def test_watchdog_uses_current_a00_and_b15_ids() -> None:
    assert _spec("a00").automation_id == NEW_A00
    assert _spec("b15").automation_id == NEW_B15


def test_host_run_without_matching_durable_wake_is_explicit_failure() -> None:
    spec = _spec("a00")
    now = datetime(2026, 10, 5, 5, 3, tzinfo=timezone.utc)
    host_snapshot = {
        "schema": "WHD_CHATGPT_AUTOMATION_HOST_SNAPSHOT_V1",
        "observed_at": "2026-10-05T05:02:30Z",
        "tasks": {
            NEW_A00: {
                "enabled": True,
                "last_run_time": "2026-10-05T05:00:05Z",
            }
        },
    }
    row = classify_entrypoint(
        spec,
        now=now,
        observation=None,
        host_snapshot=host_snapshot,
        grace_seconds=120,
    )
    assert row["status"] == STATUS_HOST_ENTRY_FAILURE
    assert row["reason"] == "HOST_RECORDED_RUN_BUT_DURABLE_WAKE_MISSING"
