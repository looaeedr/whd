from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from tools.control_transaction import ControlTransactionConflict
from tools.execution_record import (
    ActionSpec,
    ClosureState,
    ExecutionRecord,
    LeaseState,
    MutationScopeState,
    QAState,
)
from tools.flow_v2_merge_precheck import ALREADY_MERGED
from tools import control_transaction_production_executor as executor


INV = "chatgpt.flowv2.work1.issue1378"
HEAD = "a" * 40
TARGET = "b" * 40
LIVE_TARGET = "c" * 40
MERGED = "d" * 40


def _lease(*, expires_at: str = "2099-01-01T00:00:00Z") -> LeaseState:
    return LeaseState(
        token="lease-1378",
        invocation_identity=INV,
        expires_at=expires_at,
    )


def _merge_record() -> ExecutionRecord:
    return ExecutionRecord(
        issue=1378,
        execution_intent="EXECUTE_TICKET",
        owner_kind="SCHEDULER",
        owner_id="chatgpt.flowv2.work1",
        lane_id="chatgpt.flowv2.work1",
        slot_id="worker.slot.1",
        source_branch="cleanup/2d-3d-sync",
        source_sha=HEAD,
        work_branch="work/issue-1378",
        head_sha=HEAD,
        target_branch="cleanup/2d-3d-sync",
        target_sha=TARGET,
        state="INTEGRATING",
        semantic_state="QA_ACCEPTED",
        next_action=ActionSpec(
            kind="MERGE",
            args={"pr_number": 1408},
            display="merge",
        ),
        lease=_lease(),
        qa=QAState(last_accepted_run=1378001, accepted_head_sha=HEAD),
        generation=7,
        updated_at="2026-10-08T02:10:00Z",
    )


def _sync_record() -> ExecutionRecord:
    return replace(
        _merge_record(),
        semantic_state="TARGET_DRIFT_REQUIRES_SYNC",
        next_action=ActionSpec(
            kind="SYNC_TARGET",
            args={
                "target_sha": LIVE_TARGET,
                "pr_number": 1408,
                "target_branch": "cleanup/2d-3d-sync",
                "qa_workflow": ".github/workflows/whd-product-regression.yml",
            },
            display="sync",
        ),
    )


def _finalize_record() -> ExecutionRecord:
    return replace(
        _merge_record(),
        target_sha=LIVE_TARGET,
        semantic_state="MERGED",
        next_action=ActionSpec(kind="FINALIZE", args={}, display="finalize"),
        closure=ClosureState(
            merged_sha=MERGED,
            issue_closed=False,
            released_at=None,
        ),
    )


def _released_stale_record() -> ExecutionRecord:
    return ExecutionRecord(
        issue=1378,
        execution_intent="EXECUTE_TICKET",
        owner_kind="SCHEDULER",
        owner_id="chatgpt.flowv2.work1",
        lane_id="chatgpt.flowv2.work1",
        slot_id="worker.slot.1",
        source_branch="cleanup/2d-3d-sync",
        source_sha=HEAD,
        work_branch="work/issue-1378-stale",
        head_sha=HEAD,
        target_branch="cleanup/2d-3d-sync",
        target_sha=TARGET,
        state="ACTIVE",
        semantic_state="STALE_EXECUTION_RESERVATION_RELEASED_RESTART_REQUIRED",
        next_action=ActionSpec(kind="START_BRANCH", args={}, display="restart"),
        lease=_lease(expires_at="2026-10-08T01:00:00Z"),
        qa=QAState(last_accepted_run=None, accepted_head_sha=None),
        mutation_scope=MutationScopeState(
            target_branch="cleanup/2d-3d-sync",
            base_sha=TARGET,
            write_paths=("tests/process/test_issue1378_idempotent_readback_characterization.py",),
            delete_paths=(),
            reservation_state="RELEASED",
        ),
        generation=3,
        updated_at="2026-10-08T01:00:00Z",
    )


def _active_release_record() -> ExecutionRecord:
    return replace(
        _released_stale_record(),
        mutation_scope=MutationScopeState(
            target_branch="cleanup/2d-3d-sync",
            base_sha=TARGET,
            write_paths=("gui.py",),
            delete_paths=(),
            reservation_state="ACTIVE",
        ),
        semantic_state="IMPLEMENTING",
        lease=_lease(),
    )


class ReadbackOnlyFence:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, repo, method, path, token, payload=None):
        self.calls.append((method, path))
        if method != "GET":
            raise AssertionError(f"readback-only fence blocked provider mutation: {method} {path}")
        raise AssertionError(f"unexpected provider read escaped characterization seam: {method} {path}")


def test_merge_already_merged_is_readback_only_and_never_calls_merge_put(monkeypatch):
    record = _merge_record()
    fence = ReadbackOnlyFence()
    monkeypatch.setattr(
        executor,
        "_merge_precheck_readback",
        lambda *args, **kwargs: (
            {
                "merged": True,
                "merge_commit_sha": MERGED,
                "head": {"sha": HEAD},
                "base": {"ref": record.target_branch},
            },
            SimpleNamespace(
                classification=ALREADY_MERGED,
                observed_target_sha=LIVE_TARGET,
                missing_required_checks=(),
                reason="already merged",
            ),
        ),
    )
    monkeypatch.setattr(executor, "_read_branch_head", lambda *args, **kwargs: LIVE_TARGET)
    monkeypatch.setattr(executor, "_is_ancestor", lambda *args, **kwargs: True)
    monkeypatch.setattr(executor, "_api", fence)

    effect = executor._trusted_merge_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=INV,
        supplied={},
    )

    assert effect["merge_precheck_status"] == ALREADY_MERGED
    assert effect["next_action"]["kind"] == "FINALIZE"
    assert [call for call in fence.calls if call[0] == "PUT"] == []


def test_sync_target_already_applied_ancestry_never_posts_merges(monkeypatch):
    record = _sync_record()
    fence = ReadbackOnlyFence()

    def read_head(repo, token, branch):
        if branch == record.target_branch:
            return LIVE_TARGET
        assert branch == record.work_branch
        return MERGED

    monkeypatch.setattr(executor, "_read_branch_head", read_head)
    monkeypatch.setattr(executor, "_is_ancestor", lambda *args, **kwargs: True)
    monkeypatch.setattr(executor, "_api", fence)

    effect = executor._trusted_sync_target_effect(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity=INV,
    )

    assert effect["head_sha"] == MERGED
    assert effect["next_action"]["kind"] == "START_QA"
    assert [call for call in fence.calls if call == ("POST", "/merges")] == []


def test_finalize_already_closed_completed_never_patches_issue(monkeypatch):
    record = _finalize_record()
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        executor,
        "_finalize_target_readback",
        lambda *args, **kwargs: {"observed_target_sha": LIVE_TARGET},
    )

    def fake_api(repo, method, path, token, payload=None):
        calls.append((method, path))
        assert path == f"/issues/{record.issue}"
        assert method == "GET"
        return {
            "number": record.issue,
            "state": "closed",
            "state_reason": "completed",
            "closed_at": "2026-10-08T02:12:00Z",
        }

    monkeypatch.setattr(executor, "_api", fake_api)
    effect = executor._ensure_issue_closed_for_finalize(
        "looaeedr/whd",
        "token",
        issue=record.issue,
        record=record,
        records={record.issue: record},
    )

    assert effect["issue_closed"] is True
    assert effect["issue_state_reason"] == "completed"
    assert [call for call in calls if call[0] == "PATCH"] == []


def test_active_release_paths_kind_alone_does_not_trigger_external_mutation(monkeypatch):
    record = _active_release_record()

    def forbidden_api(*args, **kwargs):
        raise AssertionError("ACTIVE RELEASE_PATHS must not touch provider cleanup path")

    monkeypatch.setattr(executor, "_api", forbidden_api)
    monkeypatch.setattr(executor, "_read_branch_head", forbidden_api)

    supplied = {"reason": "normal live release"}
    assert executor._trusted_stale_release_effect(
        "looaeedr/whd",
        "token",
        record=record,
        records={record.issue: record},
        supplied=supplied,
    ) == supplied


def test_stale_release_absent_branch_is_idempotent_and_delete_count_zero(monkeypatch):
    record = _released_stale_record()
    delete_calls: list[str] = []
    monkeypatch.setattr(
        executor,
        "_now",
        lambda: datetime(2026, 10, 8, 2, 12, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(executor, "_read_branch_head", lambda *args, **kwargs: LIVE_TARGET)

    def fake_api(repo, method, path, token, payload=None):
        if method == "DELETE":
            delete_calls.append(path)
        if method == "GET" and path.startswith("/git/ref/heads/"):
            raise HTTPError("https://example.invalid", 404, "Not Found", None, None)
        raise AssertionError(f"unexpected API call: {method} {path}")

    monkeypatch.setattr(executor, "_api", fake_api)
    effect = executor._trusted_stale_release_effect(
        "looaeedr/whd",
        "token",
        record=record,
        records={record.issue: record},
        supplied={"reason": "stale cleanup"},
    )

    assert delete_calls == []
    assert effect["stale_work_branch_deleted"] is False
    assert effect["stale_work_branch_readback"] == "ABSENT"


def _install_stale_delete_provider(monkeypatch, record):
    delete_calls: list[str] = []
    state = {"deleted": False}
    monkeypatch.setattr(
        executor,
        "_now",
        lambda: datetime(2026, 10, 8, 2, 12, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(executor, "_read_branch_head", lambda *args, **kwargs: LIVE_TARGET)
    monkeypatch.setattr(executor, "_is_ancestor", lambda *args, **kwargs: True)

    def fake_api(repo, method, path, token, payload=None):
        if method == "GET" and path.startswith("/git/ref/heads/"):
            if state["deleted"]:
                raise HTTPError("https://example.invalid", 404, "Not Found", None, None)
            return {"object": {"sha": record.head_sha}}
        if method == "GET" and path.startswith("/branches/"):
            return {"commit": {"sha": record.head_sha}, "protected": False}
        if method == "DELETE" and path.startswith("/git/refs/heads/"):
            delete_calls.append(path)
            state["deleted"] = True
            return {}
        raise AssertionError(f"unexpected API call: {method} {path}")

    monkeypatch.setattr(executor, "_api", fake_api)
    return delete_calls


def test_stale_delete_is_conditional_external_mutation_and_executes_once(monkeypatch):
    record = _released_stale_record()
    delete_calls = _install_stale_delete_provider(monkeypatch, record)

    effect = executor._trusted_stale_release_effect(
        "looaeedr/whd",
        "token",
        record=record,
        records={record.issue: record},
        supplied={
            "reason": "stale cleanup",
            "delete_stale_work_branch": True,
        },
    )

    assert len(delete_calls) == 1
    assert effect["stale_work_branch_deleted"] is True
    assert effect["stale_work_branch_readback"] == "ABSENT"


def test_unrelated_coord_cas_race_does_not_replay_stale_provider_delete(monkeypatch):
    record = _released_stale_record()
    unrelated = replace(record, issue=9999, work_branch="work/issue-9999")
    fresh_unrelated = replace(unrelated, generation=unrelated.generation + 1)
    delete_calls = _install_stale_delete_provider(monkeypatch, record)

    candidate_after_retry = {}
    load_count = {"value": 0}

    def fake_load_state(repo, token, coord_branch):
        load_count["value"] += 1
        if load_count["value"] <= 2:
            return "1" * 40, "2" * 40, {record.issue: record, unrelated.issue: unrelated}
        if load_count["value"] == 3:
            return "3" * 40, "4" * 40, {record.issue: record, unrelated.issue: fresh_unrelated}
        return "5" * 40, "6" * 40, candidate_after_retry["records"]

    write_count = {"value": 0}

    def fake_write_state(repo, token, coord_branch, *, parent_sha, base_tree_sha, records, issue):
        write_count["value"] += 1
        if write_count["value"] == 1:
            raise ControlTransactionConflict(
                "coord/execution-v2 ref advanced during transaction test race"
            )
        candidate_after_retry["records"] = records
        return "5" * 40, "7" * 40

    monkeypatch.setattr(executor, "_load_state", fake_load_state)
    monkeypatch.setattr(executor, "_write_state", fake_write_state)
    monkeypatch.setattr(
        executor,
        "_publish_transaction_progress",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("monitor irrelevant")),
    )

    result = executor.execute_one(
        repo="looaeedr/whd",
        token="token",
        coord_branch="coord/execution-v2",
        issue=record.issue,
        kind="RELEASE_PATHS",
        lane_id="chatgpt.flowv2.work1",
        invocation_identity="cleanup-runtime",
        supplied_effect={
            "reason": "stale cleanup",
            "delete_stale_work_branch": True,
        },
    )

    assert result["result"] == "APPLIED"
    assert write_count["value"] == 2
    assert len(delete_calls) == 1


def test_same_issue_coord_drift_fails_closed_without_replaying_delete(monkeypatch):
    record = _released_stale_record()
    delete_calls = _install_stale_delete_provider(monkeypatch, record)
    drifted = replace(record, updated_at="2026-10-08T02:12:59Z")
    load_count = {"value": 0}

    def fake_load_state(repo, token, coord_branch):
        load_count["value"] += 1
        if load_count["value"] <= 2:
            return "1" * 40, "2" * 40, {record.issue: record}
        return "3" * 40, "4" * 40, {record.issue: drifted}

    def fake_write_state(*args, **kwargs):
        raise ControlTransactionConflict(
            "coord/execution-v2 ref advanced during transaction test race"
        )

    monkeypatch.setattr(executor, "_load_state", fake_load_state)
    monkeypatch.setattr(executor, "_write_state", fake_write_state)

    with pytest.raises(ControlTransactionConflict, match="current Issue changed"):
        executor.execute_one(
            repo="looaeedr/whd",
            token="token",
            coord_branch="coord/execution-v2",
            issue=record.issue,
            kind="RELEASE_PATHS",
            lane_id="chatgpt.flowv2.work1",
            invocation_identity="cleanup-runtime",
            supplied_effect={
                "reason": "stale cleanup",
                "delete_stale_work_branch": True,
            },
        )

    assert len(delete_calls) == 1

@pytest.mark.parametrize("kind,method,path", [
    ("MERGE", "PUT", "/pulls/1408/merge"),
    ("SYNC_TARGET", "POST", "/merges"),
    ("FINALIZE", "PATCH", "/issues/1378"),
])
def test_readback_only_fence_blocks_actual_mutation_branches(monkeypatch, kind, method, path):
    """Exercise each production mutation branch against a GET-only provider seam."""
    fence = ReadbackOnlyFence()

    def provider(repo, verb, endpoint, token, payload=None):
        if verb == "GET" and endpoint == "/issues/1378":
            return {"number": 1378, "state": "open", "state_reason": None}
        return fence(repo, verb, endpoint, token, payload)

    monkeypatch.setattr(executor, "_api", provider)
    if kind == "MERGE":
        monkeypatch.setattr(executor, "_merge_precheck_readback",
            lambda *args, **kwargs: ({}, SimpleNamespace(classification="READY_TO_MERGE")))
        invoke = lambda: executor._trusted_merge_effect(
            "looaeedr/whd", "token", record=_merge_record(),
            invocation_identity=INV, supplied={})
    elif kind == "SYNC_TARGET":
        monkeypatch.setattr(executor, "_verified_sync_target_user_token", lambda repo: "verified-test-user-pat")
        record = _sync_record()
        monkeypatch.setattr(executor, "_read_branch_head",
            lambda repo, token, branch: LIVE_TARGET if branch == record.target_branch else HEAD)
        invoke = lambda: executor._trusted_sync_target_effect(
            "looaeedr/whd", "token", record=record, invocation_identity=INV)
    else:
        monkeypatch.setattr(executor, "_finalize_target_readback",
            lambda *args, **kwargs: {"observed_target_sha": LIVE_TARGET})
        invoke = lambda: executor._ensure_issue_closed_for_finalize(
            "looaeedr/whd", "token", issue=1378, record=_finalize_record())

    with pytest.raises(AssertionError, match="readback-only fence blocked provider mutation"):
        invoke()
    assert fence.calls == [(method, path)]

[executed on device: 5bca4a576178 (b0fad557-80aa-4ade-ab0b-d009a426005a)]