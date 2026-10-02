from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tools.execution_record import execution_record_from_payload
from tools.flow_v2_runtime_observation import (
    HEARTBEAT_TTL_SECONDS,
    derive_liveness_state,
    project_interactive_liveness,
    project_transaction_progress,
)
from tools.interactive_runtime_liveness import parse_interactive_runtime_liveness_comment
from tools.execution_work_slot_view import project_work_slot_liveness


def _record(*, owner_id="chatgpt.flowv2.work0", state="ACTIVE"):
    return execution_record_from_payload({
        "schema":"WHD_EXECUTION_RECORD_V2",
        "version":2,
        "generation":7,
        "issue":927,
        "execution_intent":"EXECUTE_TICKET",
        "owner_kind":"INTERACTIVE",
        "owner_id":owner_id,
        "lane_id":None,
        "slot_id":"worker.slot.0",
        "source_branch":"cleanup/2d-3d-sync",
        "source_sha":"a"*40,
        "work_branch":"work/issue927",
        "head_sha":"b"*40,
        "target_branch":"cleanup/2d-3d-sync",
        "target_sha":"c"*40,
        "state":state,
        "semantic_state":"IMPLEMENTING",
        "next_action":{"kind":"APPLY_COMMIT","args":{},"display":"continue"},
        "lease":None,
        "active_run":None,
        "transaction":None,
        "qa":{"last_accepted_run":None,"accepted_head_sha":None},
        "blocker":None,
        "closure":{"merged_sha":None,"issue_closed":False,"released_at":None},
        "chain":{"parent_issue":None,"next_issue":None,"next_action":None},
        "recovery_history":[],
        "updated_at":"2026-09-28T13:10:00Z",
    })


def _interactive_comment():
    return {
        "id": 92701,
        "created_at": "2026-09-28T13:10:00Z",
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_INTERACTIVE_RUNTIME_LIVENESS_V1\n"
            "issue=927\n"
            "slot_id=worker.slot.0\n"
            "worker=chatgpt.flowv2.work0\n"
            "invocation_identity=interactive.work0.issue927.invocation1\n"
            "conversation_identity=chat.issue927.conversation1\n"
            f"claim_blob_sha={'d'*40}\n"
            "branch=work/issue927\n"
            f"head_sha={'b'*40}\n"
            "executor_source=chat\n"
            "emitted_at=2026-09-28T13:10:00Z\n"
            "expires_at=2026-09-28T13:15:00Z"
        ),
    }


def test_adapter_reuses_issue679_interactive_machine_owner():
    parsed = parse_interactive_runtime_liveness_comment(_interactive_comment())
    obs = project_interactive_liveness(parsed)
    assert obs["schema"] == "WHD_RUNTIME_OBSERVATION_V2"
    assert obs["event"] == "HEARTBEAT"
    assert obs["source"] == "work-0"
    assert obs["claim_worker"] == "chatgpt.flowv2.work0"
    assert obs["invocation_identity"] == "interactive.work0.issue927.invocation1"
    assert obs["conversation_identity"] == "chat.issue927.conversation1"
    assert obs["last_heartbeat_at"] == "2026-09-28T13:10:00Z"
    assert obs["heartbeat_expires_at"] == "2026-09-28T13:15:00Z"
    assert obs["liveness_state"] == "LIVE"


def test_progress_refreshes_heartbeat_but_remains_progress_event():
    now = datetime(2026, 9, 28, 13, 20, tzinfo=timezone.utc)
    obs = project_transaction_progress(
        record=_record(),
        invocation_identity="interactive.work0.issue927.invocation2",
        runtime_owner="chatgpt.flowv2.work0",
        action="APPLY_COMMIT",
        observed_at=now,
    )
    assert obs["event"] == "PROGRESS"
    assert obs["last_progress_at"] == "2026-09-28T13:20:00Z"
    assert obs["last_heartbeat_at"] == "2026-09-28T13:20:00Z"
    assert obs["heartbeat_expires_at"] == "2026-09-28T13:25:00Z"
    assert HEARTBEAT_TTL_SECONDS == 300
    assert obs["liveness_state"] == "LIVE"


def test_liveness_expiry_is_independent_of_last_progress_field():
    obs = {
        "event":"PROGRESS",
        "last_progress_at":"2026-09-28T13:59:59Z",
        "last_heartbeat_at":"2026-09-28T13:10:00Z",
        "heartbeat_expires_at":"2026-09-28T13:15:00Z",
        "exit_at":None,
        "exit_state":None,
    }
    state = derive_liveness_state(
        obs, now=datetime(2026, 9, 28, 13, 16, tzinfo=timezone.utc)
    )
    assert state == "EXPIRED"


def test_work_slot_projection_exposes_required_liveness_fields_only_on_exact_identity():
    record = _record()
    obs = project_transaction_progress(
        record=record,
        invocation_identity="interactive.work0.issue927.invocation2",
        runtime_owner="chatgpt.flowv2.work0",
        action="APPLY_COMMIT",
        observed_at=datetime(2026, 9, 28, 13, 20, tzinfo=timezone.utc),
    )
    slots = project_work_slot_liveness(
        [record],
        {"work-0.json": obs},
        now=datetime(2026, 9, 28, 13, 21, tzinfo=timezone.utc),
    )
    slot = slots[0]
    assert slot.slot_id == "worker.slot.0"
    assert slot.issue == 927
    assert slot.claim_worker == "chatgpt.flowv2.work0"
    assert slot.invocation_identity == "interactive.work0.issue927.invocation2"
    assert slot.conversation_identity == "UNAVAILABLE"
    assert slot.work_branch == "work/issue927"
    assert slot.head_sha == "b"*40
    assert slot.last_heartbeat_at == "2026-09-28T13:20:00Z"
    assert slot.heartbeat_expires_at == "2026-09-28T13:25:00Z"
    assert slot.last_progress_at == "2026-09-28T13:20:00Z"
    assert slot.exit_at is None
    assert slot.exit_state is None
    assert slot.liveness_state == "LIVE"


def test_adapter_is_projection_not_second_liveness_authority():
    source = (Path(__file__).resolve().parents[2] / "tools/flow_v2_runtime_observation.py").read_text(encoding="utf-8")
    assert "interactive_runtime_liveness as interactive_liveness" in source
    assert "scheduler_runtime_liveness as scheduler_liveness" in source
    assert "Parse owner-authored interactive" not in source
    assert 'EVENTS = {"WAKE", "HEARTBEAT", "PROGRESS", "EXIT"}' in source
