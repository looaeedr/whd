from datetime import datetime, timezone

from tools.scheduler_host_watchdog import ENTRYPOINTS, STATUS_HOST_ENTRY_FAILURE, classify_entrypoint

NEW_A40_TASK_ID = "6abe0efee140819190b5d215eb3bceba"
OLD_A40_TASK_ID = "6ab13fa557fc8191935c671214b865e2"
LANE_A = "scheduler.6ab13fa557fc8191935c671214b865e2"

def _a40():
    return next(spec for spec in ENTRYPOINTS if spec.key == "a40")

def test_a40_watchdog_tracks_fresh_host_not_legacy_autopausing_host():
    spec = _a40()
    assert spec.automation_id == NEW_A40_TASK_ID
    assert spec.lane_owner == LANE_A
    assert spec.automation_id != spec.lane_owner

def test_legacy_disabled_host_cannot_classify_fresh_a40_as_host_auto_pause():
    spec = _a40()
    now = datetime(2026, 10, 1, 8, 43, tzinfo=timezone.utc)
    host_snapshot = {
        "schema": "WHD_CHATGPT_AUTOMATION_HOST_SNAPSHOT_V1",
        "observed_at": "2026-10-01T08:42:30Z",
        "tasks": {
            OLD_A40_TASK_ID: {"enabled": False, "last_run_time": "2026-10-01T06:36:49Z"},
            NEW_A40_TASK_ID: {"enabled": True, "last_run_time": None},
        },
    }
    row = classify_entrypoint(spec, now=now, observation=None, host_snapshot=host_snapshot, grace_seconds=120)
    assert row["automation_id"] == NEW_A40_TASK_ID
    assert row["host_enabled"] is True
    assert row["status"] == STATUS_HOST_ENTRY_FAILURE
    assert row["reason"] == "EXPECTED_WAKE_MISSING_WHILE_HOST_TASK_ENABLED"
