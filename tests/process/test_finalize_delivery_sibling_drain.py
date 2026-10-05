from __future__ import annotations

from tools.execution_record import ActionSpec, ChainState, ClosureState, ExecutionRecord
import tools.control_transaction_production_executor as executor


DELIVERY = "1" * 40
TARGET = "2" * 40
HEAD = "3" * 40


def _record(*, issue: int = 1197, next_issue: int | None = None) -> ExecutionRecord:
    chain = ChainState(
        next_issue=next_issue,
        next_action=(
            ActionSpec(
                kind="RECOVER_POST_DELIVERY",
                args={"pr_number": 1205},
                display="recover sibling",
            )
            if next_issue is not None
            else None
        ),
    )
    return ExecutionRecord(
        issue=issue,
        execution_intent="EXECUTE_TICKET",
        owner_kind="NONE",
        owner_id="NONE",
        lane_id=None,
        slot_id="worker.slot.0",
        source_branch="refactor/delivery",
        source_sha=HEAD,
        work_branch="refactor/delivery",
        head_sha=HEAD,
        target_branch="cleanup/2d-3d-sync",
        target_sha=TARGET,
        state="DONE",
        semantic_state="TERMINAL_SUCCESS",
        next_action=None,
        closure=ClosureState(
            merged_sha=DELIVERY,
            issue_closed=True,
            released_at="2026-10-05T05:00:00Z",
        ),
        chain=chain,
        generation=8,
        updated_at="2026-10-05T05:00:00Z",
    )


def _finalizing_record(issue: int = 1197) -> ExecutionRecord:
    return ExecutionRecord(
        issue=issue,
        execution_intent="EXECUTE_TICKET",
        owner_kind="SCHEDULER",
        owner_id="chatgpt.flowv2.work0",
        lane_id="chatgpt.flowv2.work0",
        slot_id="worker.slot.0",
        source_branch="refactor/delivery",
        source_sha=HEAD,
        work_branch="refactor/delivery",
        head_sha=HEAD,
        target_branch="cleanup/2d-3d-sync",
        target_sha=TARGET,
        state="INTEGRATING",
        semantic_state="MERGED",
        next_action=ActionSpec(
            kind="FINALIZE",
            args={"pr_number": 1205},
            display="finalize exact delivery",
        ),
        closure=ClosureState(
            merged_sha=DELIVERY,
            issue_closed=False,
            released_at=None,
        ),
        generation=7,
        updated_at="2026-10-05T04:59:00Z",
    )


def test_closing_issue_parser_preserves_pr_body_order():
    assert executor._pr_body_closing_issues(
        "Closes #1197\nFixes #1202\nResolves #1203\nCloses #1202"
    ) == (1197, 1202, 1203)


def test_finalize_discovers_next_open_missing_record_sibling(monkeypatch):
    record = _finalizing_record()

    def fake_api(_repo, method, path, _token, payload=None):
        assert method == "GET"
        if path == "/pulls/1205":
            return {
                "merged": True,
                "merge_commit_sha": DELIVERY,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #1197\nCloses #1202\nCloses #1203",
            }
        if path == "/issues/1202":
            return {"number": 1202, "state": "open"}
        raise AssertionError(path)

    monkeypatch.setattr(executor, "_api", fake_api)
    found = executor._discover_open_delivery_sibling(
        "looaeedr/whd",
        "token",
        issue=1197,
        record=record,
        records={1197: record},
    )
    assert found == (1202, 1205)


def test_finalize_skips_sibling_that_already_has_execution_record(monkeypatch):
    record = _finalizing_record()
    existing = _finalizing_record(issue=1202)

    def fake_api(_repo, method, path, _token, payload=None):
        assert method == "GET"
        if path == "/pulls/1205":
            return {
                "merged": True,
                "merge_commit_sha": DELIVERY,
                "base": {"ref": "cleanup/2d-3d-sync"},
                "body": "Closes #1197\nCloses #1202\nCloses #1203",
            }
        if path == "/issues/1203":
            return {"number": 1203, "state": "open"}
        raise AssertionError(path)

    monkeypatch.setattr(executor, "_api", fake_api)
    found = executor._discover_open_delivery_sibling(
        "looaeedr/whd",
        "token",
        issue=1197,
        record=record,
        records={1197: record, 1202: existing},
    )
    assert found == (1203, 1205)


def test_done_record_with_sibling_continuation_projects_progress_not_exit(monkeypatch):
    record = _record(next_issue=1202)
    written = {}

    monkeypatch.setattr(
        executor,
        "_read_monitor_observation",
        lambda _repo, _token, _source: (None, None),
    )
    monkeypatch.setattr(
        executor,
        "_write_monitor_observation",
        lambda _repo, _token, observation: written.update(observation) or "a" * 40,
    )

    _, observation = executor._publish_transaction_progress(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity="interactive:delivery-tail",
        runtime_owner="chatgpt.flowv2.work0",
        action="FINALIZE",
    )

    assert observation["event"] == "PROGRESS"
    assert observation["liveness_state"] == "LIVE"
    assert observation["exit_at"] is None
    assert written["event"] == "PROGRESS"


def test_done_record_without_sibling_continuation_projects_exit(monkeypatch):
    record = _record()
    written = {}

    monkeypatch.setattr(
        executor,
        "_read_monitor_observation",
        lambda _repo, _token, _source: (None, None),
    )
    monkeypatch.setattr(
        executor,
        "_write_monitor_observation",
        lambda _repo, _token, observation: written.update(observation) or "b" * 40,
    )

    _, observation = executor._publish_transaction_progress(
        "looaeedr/whd",
        "token",
        record=record,
        invocation_identity="interactive:delivery-tail",
        runtime_owner="chatgpt.flowv2.work0",
        action="FINALIZE",
    )

    assert observation["event"] == "EXIT"
    assert observation["liveness_state"] == "ENDED"
    assert written["event"] == "EXIT"
