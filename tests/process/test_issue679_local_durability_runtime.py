from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

ISSUE = 679
WORKER = "chatgpt.sol260926.wi1.1"
SLOT = "worker.slot.1"
INVOCATION = "chatgpt.sol260926.wi1.1.invocation.001"
CONVERSATION = "chat.conversation.issue679.001"
BRANCH = "work/issue679-local-durability-runtime-boundary-20260926"
HEAD = "a" * 40
REMOTE_HEAD = "a" * 40
CLAIM_BLOB = "c" * 40


def _local_module():
    spec = importlib.util.find_spec("tools.local_durability_gate")
    assert spec is not None, (
        "R1_LOCAL_DURABILITY_OWNER_MISSING: tools/local_durability_gate.py"
    )
    return importlib.import_module("tools.local_durability_gate")


def _interactive_module():
    spec = importlib.util.find_spec("tools.interactive_runtime_liveness")
    assert spec is not None, (
        "R1_INTERACTIVE_RUNTIME_OWNER_MISSING: "
        "tools/interactive_runtime_liveness.py"
    )
    return importlib.import_module("tools.interactive_runtime_liveness")


def _snapshot(**overrides):
    payload = {
        "schema": "WHD_LOCAL_DURABILITY_SNAPSHOT_V1",
        "machine_reachable": True,
        "branch": BRANCH,
        "local_head_sha": HEAD,
        "remote_head_sha": REMOTE_HEAD,
        "worktree_clean": True,
        "has_conflicts": False,
        "unpushed_commits": 0,
        "mutation_in_progress": False,
    }
    payload.update(overrides)
    return payload


def _classify(**overrides):
    return _local_module().classify_local_durability(_snapshot(**overrides))


@pytest.mark.parametrize(
    ("overrides", "state", "result", "reason"),
    [
        ({}, "LOCAL_CLEAN_SYNCED", "SAFE", "LOCAL_CLEAN_SYNCED"),
        (
            {"worktree_clean": False},
            "LOCAL_DIRTY_RECOVERABLE",
            "NOT_SAFE",
            "LOCAL_DIRTY_NOT_DURABLE",
        ),
        (
            {"has_conflicts": True, "worktree_clean": False},
            "LOCAL_DIRTY_CONFLICT",
            "NOT_SAFE",
            "LOCAL_STATE_CONFLICT",
        ),
        (
            {"unpushed_commits": 2},
            "LOCAL_UNPUSHED",
            "NOT_SAFE",
            "LOCAL_UNPUSHED",
        ),
        (
            {"mutation_in_progress": True},
            "LOCAL_MUTATION_IN_PROGRESS",
            "NOT_SAFE",
            "LOCAL_MUTATION_IN_PROGRESS",
        ),
        (
            {
                "machine_reachable": False,
                "branch": None,
                "local_head_sha": None,
                "remote_head_sha": REMOTE_HEAD,
                "worktree_clean": None,
                "has_conflicts": None,
                "unpushed_commits": None,
                "mutation_in_progress": None,
            },
            "LOCAL_MACHINE_UNAVAILABLE",
            "ERROR",
            "LOCAL_MACHINE_UNREACHABLE",
        ),
    ],
)
def test_local_durability_six_states_are_machine_distinct(
    overrides, state, result, reason
):
    out = _classify(**overrides)
    assert out["schema"] == "WHD_LOCAL_DURABILITY_V1"
    assert out["state"] == state
    assert out["poweroff_result"] == result
    assert out["poweroff_reason"] == reason


def test_remote_clean_cannot_overwrite_dirty_local_truth():
    out = _classify(
        worktree_clean=False,
        remote_head_sha=HEAD,
    )
    assert out["state"] == "LOCAL_DIRTY_RECOVERABLE"
    assert out["poweroff_result"] == "NOT_SAFE"


def test_reachable_but_incomplete_local_truth_fails_closed_as_conflict():
    out = _classify(
        local_head_sha=None,
        worktree_clean=None,
        has_conflicts=None,
        unpushed_commits=None,
        mutation_in_progress=None,
    )
    assert out["state"] == "LOCAL_DIRTY_CONFLICT"
    assert out["poweroff_result"] == "NOT_SAFE"
    assert out["poweroff_reason"] == "LOCAL_STATE_CONFLICT"


def test_local_ahead_evidence_is_unpushed_even_if_worktree_is_clean():
    out = _classify(
        local_head_sha="b" * 40,
        remote_head_sha=REMOTE_HEAD,
        unpushed_commits=1,
        worktree_clean=True,
    )
    assert out["state"] == "LOCAL_UNPUSHED"


def _heartbeat(
    *,
    comment_id: int = 100,
    invocation: str = INVOCATION,
    conversation: str = CONVERSATION,
    claim_blob: str = CLAIM_BLOB,
    worker: str = WORKER,
):
    return {
        "id": comment_id,
        "created_at": "2026-09-26T05:00:00Z",
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_INTERACTIVE_RUNTIME_LIVENESS_V1\n"
            f"issue={ISSUE}\n"
            f"slot_id={SLOT}\n"
            f"worker={worker}\n"
            f"invocation_identity={invocation}\n"
            f"conversation_identity={conversation}\n"
            f"claim_blob_sha={claim_blob}\n"
            f"branch={BRANCH}\n"
            f"head_sha={HEAD}\n"
            "executor_source=chat\n"
            "emitted_at=2026-09-26T05:00:00Z\n"
            "expires_at=2026-09-26T05:05:00Z"
        ),
    }


def _end(
    *,
    comment_id: int = 101,
    invocation: str = INVOCATION,
    conversation: str = CONVERSATION,
    claim_blob: str = CLAIM_BLOB,
    worker: str = WORKER,
):
    return {
        "id": comment_id,
        "created_at": "2026-09-26T05:03:00Z",
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_INTERACTIVE_RUNTIME_END_V1\n"
            f"issue={ISSUE}\n"
            f"slot_id={SLOT}\n"
            f"worker={worker}\n"
            f"invocation_identity={invocation}\n"
            f"conversation_identity={conversation}\n"
            f"claim_blob_sha={claim_blob}\n"
            f"branch={BRANCH}\n"
            f"head_sha={HEAD}\n"
            "executor_source=chat\n"
            "ended_at=2026-09-26T05:02:30Z\n"
            "reason=PLANNED_HANDOFF"
        ),
    }


def test_interactive_runtime_end_binds_exact_provenance():
    mod = _interactive_module()
    selected = mod.select_interactive_runtime_liveness(
        [_heartbeat(), _end()],
        issue=ISSUE,
        worker=WORKER,
    )
    assert selected is not None
    assert selected["schema"] == "WHD_INTERACTIVE_RUNTIME_LIVENESS_V1"
    assert selected["runtime_status"] == "ENDED"
    assert selected["slot_id"] == SLOT
    assert selected["worker"] == WORKER
    assert selected["invocation_identity"] == INVOCATION
    assert selected["conversation_identity"] == CONVERSATION
    assert selected["claim_blob_sha"] == CLAIM_BLOB
    assert selected["branch"] == BRANCH
    assert selected["head_sha"] == HEAD
    assert selected["end_reason"] == "PLANNED_HANDOFF"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("invocation", "chatgpt.other.invocation"),
        ("conversation", "chat.other"),
        ("claim_blob", "d" * 40),
        ("worker", "chatgpt.other"),
    ],
)
def test_interactive_runtime_end_identity_drift_fails_closed(field, value):
    mod = _interactive_module()
    kwargs = {field: value}
    with pytest.raises(
        mod.InteractiveRuntimeLivenessError,
        match="does not match|mismatch|identity",
    ):
        mod.select_interactive_runtime_liveness(
            [_heartbeat(), _end(**kwargs)],
            issue=ISSUE,
            worker=WORKER,
        )


def test_scheduler_marker_is_not_interactive_liveness():
    mod = _interactive_module()
    scheduler_comment = {
        "id": 999,
        "created_at": "2026-09-26T05:00:00Z",
        "user": {"login": "looaeedr"},
        "body": (
            "WHD_SCHEDULER_RUNTIME_LIVENESS_V1\n"
            f"issue={ISSUE}\n"
            "scheduler_lane=scheduler.example\n"
            "invocation_identity=scheduler.example.invocation\n"
            f"claim_blob_sha={CLAIM_BLOB}\n"
            f"branch={BRANCH}\n"
            f"head_sha={HEAD}\n"
            "executor_source=scheduler\n"
            "emitted_at=2026-09-26T05:00:00Z\n"
            "expires_at=2026-09-26T05:05:00Z"
        ),
    }
    assert (
        mod.select_interactive_runtime_liveness(
            [scheduler_comment],
            issue=ISSUE,
            worker=WORKER,
        )
        is None
    )


def test_interactive_owner_does_not_import_scheduler_liveness_owner():
    mod = _interactive_module()
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "scheduler_runtime_liveness" not in source


def test_authority_map_routes_local_and_interactive_owners_uniquely():
    root = Path(__file__).resolve().parents[2]
    authority = (
        root
        / "個人AI檔案庫"
        / "第二層_專案與SOP"
        / "09_WHD_Canonical_Authority_Map.md"
    ).read_text(encoding="utf-8")
    assert authority.count(
        "contract=local-durability-machine role=CURRENT path=tools/local_durability_gate.py"
    ) == 1
    assert authority.count(
        "contract=interactive-runtime-liveness role=CURRENT path=tools/interactive_runtime_liveness.py"
    ) == 1
    assert (
        "Interactive heartbeat/liveness + exact provenance 已由 "
        "`tools/interactive_runtime_liveness.py` 擁有"
    ) in authority


def test_scheduled_resume_keeps_scheduler_and_interactive_namespaces_distinct():
    root = Path(__file__).resolve().parents[2]
    scheduled = (
        root
        / "個人AI檔案庫"
        / "第二層_專案與SOP"
        / "11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md"
    ).read_text(encoding="utf-8")
    assert "`tools/scheduler_runtime_liveness.py`" in scheduled
    assert "`tools/interactive_runtime_liveness.py`" in scheduled
    assert "兩個獨立 namespace" in scheduled
    assert "WHD_INTERACTIVE_RUNTIME_LIVENESS_V1" in scheduled
    assert "WHD_INTERACTIVE_RUNTIME_END_V1" in scheduled
