from __future__ import annotations

import importlib
import importlib.util
import json
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
