from tools.scheduler_entrypoint_observation import build_entrypoint_observation


def test_wake_from_seed_creates_real_invocation_observation():
    seed = {
        "schema": "WHD_SCHEDULER_ENTRYPOINT_OBSERVATION_V1",
        "version": 1,
        "authority": "NON_AUTHORITY",
        "entrypoint": "A00",
        "task_id": "task-a00",
        "lane_id": "lane-a",
        "invocation_identity": None,
        "event": "SEED",
        "last_wake_at": None,
        "last_heartbeat_at": None,
        "heartbeat_expires_at": None,
        "last_progress_at": None,
        "exit_at": None,
        "exit_state": None,
        "observed_at": "2026-09-28T15:44:12Z",
    }
    wake = build_entrypoint_observation(
        previous=seed,
        entrypoint="A00",
        task_id="task-a00",
        lane_id="lane-a",
        invocation_identity="scheduled:a00:20261001T0500Z",
        event="WAKE",
        observed_at="2026-10-01T05:00:00Z",
    )
    assert wake["event"] == "WAKE"
    assert wake["invocation_identity"] == "scheduled:a00:20261001T0500Z"
    assert wake["last_wake_at"] == "2026-10-01T05:00:00Z"
    assert wake["exit_at"] is None


def test_heartbeat_and_exit_preserve_same_invocation_and_make_end_visible():
    wake = build_entrypoint_observation(
        previous=None,
        entrypoint="B15",
        task_id="task-b15",
        lane_id="lane-b",
        invocation_identity="scheduled:b15:20261001T0515Z",
        event="WAKE",
        observed_at="2026-10-01T05:15:00Z",
    )
    heartbeat = build_entrypoint_observation(
        previous=wake,
        entrypoint="B15",
        task_id="task-b15",
        lane_id="lane-b",
        invocation_identity="scheduled:b15:20261001T0515Z",
        event="HEARTBEAT",
        observed_at="2026-10-01T05:16:00Z",
    )
    end = build_entrypoint_observation(
        previous=heartbeat,
        entrypoint="B15",
        task_id="task-b15",
        lane_id="lane-b",
        invocation_identity="scheduled:b15:20261001T0515Z",
        event="EXIT",
        observed_at="2026-10-01T05:17:00Z",
        exit_state="NO_EXECUTABLE_WORK",
    )
    assert heartbeat["last_heartbeat_at"] == "2026-10-01T05:16:00Z"
    assert heartbeat["heartbeat_expires_at"] == "2026-10-01T05:21:00Z"
    assert end["event"] == "EXIT"
    assert end["exit_at"] == "2026-10-01T05:17:00Z"
    assert end["exit_state"] == "NO_EXECUTABLE_WORK"
