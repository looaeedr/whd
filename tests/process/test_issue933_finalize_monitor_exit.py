from __future__ import annotations

from datetime import datetime, timezone

from tools.execution_record import execution_record_from_payload
from tools.flow_v2_runtime_observation import project_terminal_record_exit
import tools.control_transaction_production_executor as executor


def _terminal_record():
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 10,
        "issue": 933,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "SCHEDULER",
        "owner_id": "chatgpt.flowv2.work0",
        "lane_id": "chatgpt.flowv2.work0",
        "slot_id": "worker.slot.0",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "work/issue933-finalize-monitor-exit-20260928",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "DONE",
        "semantic_state": "TERMINAL_SUCCESS",
        "next_action": None,
        "lease": None,
        "active_run": None,
        "transaction": None,
        "qa": {
            "last_accepted_run": 93301,
            "accepted_head_sha": "b" * 40,
        },
        "blocker": None,
        "closure": {
            "merged_sha": "c" * 40,
            "issue_closed": True,
            "released_at": "2026-09-28T13:38:00Z",
        },
        "chain": {
            "parent_issue": None,
            "next_issue": None,
            "next_action": None,
        },
        "recovery_history": [],
        "updated_at": "2026-09-28T13:38:00Z",
    })


def _live_previous():
    return {
        "schema": "WHD_RUNTIME_OBSERVATION_V2",
        "version": 2,
        "authority": "NON_AUTHORITY",
        "source": "work-0",
        "handler": "工作0",
        "entrypoint": "/工作0",
        "event": "PROGRESS",
        "runtime_state": "WORKING",
        "issue": 933,
        "slot_id": "worker.slot.0",
        "claim_worker": "chatgpt.flowv2.work0",
        "owner_id": "chatgpt.flowv2.work0",
        "invocation_identity": "interactive:work0:issue933:g1",
        "conversation_identity": None,
        "branch": "work/issue933-finalize-monitor-exit-20260928",
        "head_sha": "b" * 40,
        "action": "MERGE",
        "record_fingerprint": "d" * 64,
        "last_wake_at": "2026-09-28T13:30:00Z",
        "last_heartbeat_at": "2026-09-28T13:37:00Z",
        "heartbeat_expires_at": "2026-09-28T13:42:00Z",
        "last_progress_at": "2026-09-28T13:37:00Z",
        "exit_at": None,
        "exit_state": None,
        "liveness_state": "LIVE",
        "observed_at": "2026-09-28T13:37:00Z",
    }


def test_terminal_record_projects_exit_and_preserves_prior_heartbeat_fields():
    obs = project_terminal_record_exit(
        record=_terminal_record(),
        invocation_identity="interactive:work0:issue933:g1",
        runtime_owner="chatgpt.flowv2.work0",
        action="FINALIZE",
        previous=_live_previous(),
        observed_at=datetime(2026, 9, 28, 13, 38, tzinfo=timezone.utc),
    )

    assert obs["event"] == "EXIT"
    assert obs["runtime_state"] == "TERMINAL_SUCCESS"
    assert obs["exit_state"] == "TERMINAL_SUCCESS"
    assert obs["exit_at"] == "2026-09-28T13:38:00Z"
    assert obs["liveness_state"] == "ENDED"
    assert obs["last_heartbeat_at"] == "2026-09-28T13:37:00Z"
    assert obs["heartbeat_expires_at"] == "2026-09-28T13:42:00Z"
    assert obs["action"] == "FINALIZE"


def test_production_writer_uses_exit_projection_for_done_record(monkeypatch):
    previous = _live_previous()
    written = {}

    monkeypatch.setattr(
        executor,
        "_read_monitor_observation",
        lambda _repo, _token, _source: (previous, "existing-sha"),
    )

    def write(_repo, _token, observation):
        written.update(observation)
        return "e" * 40

    monkeypatch.setattr(executor, "_write_monitor_observation", write)

    commit_sha, observation = executor._publish_transaction_progress(
        "looaeedr/whd",
        "token",
        record=_terminal_record(),
        invocation_identity="interactive:work0:issue933:g1",
        runtime_owner="chatgpt.flowv2.work0",
        action="FINALIZE",
    )

    assert commit_sha == "e" * 40
    assert observation["event"] == "EXIT"
    assert observation["runtime_state"] == "TERMINAL_SUCCESS"
    assert observation["liveness_state"] == "ENDED"
    assert written["event"] == "EXIT"
    assert written["exit_state"] == "TERMINAL_SUCCESS"
