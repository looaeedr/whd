from __future__ import annotations

from pathlib import Path

import pytest

import tools.continuity_controller as continuity


BRANCH = "governance/issue851-recurring-lifecycle-turn-exit-20260927"
HEAD = "8" * 40
FINGERPRINT = "f" * 64
CENSUS_FINGERPRINT = "c" * 64


def _turn_exit_receipt(*, explicit_lifecycle: bool = True) -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema": "WHD_REMOTE_TURN_EXIT_RESULT_V1",
        "request_comment_id": 85101,
        "issue": 851,
        "worker": "scheduler.example",
        "invocation_identity": "invocation-851",
        "claim_blob_sha": "a" * 40,
        "checkpoint_blob_sha": "b" * 40,
        "checkpoint_fingerprint": FINGERPRINT,
        "branch": BRANCH,
        "head_sha": HEAD,
        "closure_state": "CLOSED",
        "pending_guard_state": "CONSUMED",
        "durable_mutation_state": "CONSUMED",
        "delegated_work_state": "NONE",
        "active_remote_run": False,
        "result": "TURN_EXIT_PERMITTED",
        "reason": "TURN_EXIT_PERMITTED",
        "scheduler_end_allowed": True,
        "required_end_marker": "WHD_SCHEDULER_RUNTIME_END_V1",
        "issued_at": "2026-09-27T10:00:00Z",
        "run_id": 85103,
        "ready_work_census_fingerprint": CENSUS_FINGERPRINT,
    }
    if explicit_lifecycle:
        receipt.update(
            {
                "invocation_end_allowed": True,
                "recurring_automation_action": "KEEP_ENABLED",
                "recurring_automation_terminal": False,
            }
        )
    return receipt


def _scheduler_end() -> dict[str, object]:
    return {
        "schema": "WHD_SCHEDULER_RUNTIME_END_V1",
        "issue": 851,
        "scheduler_lane": "scheduler.example",
        "invocation_identity": "invocation-851",
        "request_comment_id": 85101,
        "result_comment_id": 85102,
        "checkpoint_fingerprint": FINGERPRINT,
        "turn_exit_run_id": 85103,
        "ready_work_census_fingerprint": CENSUS_FINGERPRINT,
    }


def _verify(receipt: dict[str, object]) -> None:
    continuity.assert_scheduler_end_receipt(
        _scheduler_end(),
        turn_exit_receipt=receipt,
        result_comment_id=85102,
    )


def test_explicit_lifecycle_contract_accepts_invocation_end_while_keep_enabled() -> None:
    _verify(_turn_exit_receipt())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("invocation_end_allowed", False),
        ("recurring_automation_action", "DISABLE"),
        ("recurring_automation_terminal", True),
    ],
)
def test_explicit_lifecycle_contract_rejects_recurring_terminal_semantics(
    field: str,
    value: object,
) -> None:
    receipt = _turn_exit_receipt()
    receipt[field] = value
    with pytest.raises(continuity.TurnExitBlocked, match="recurring|lifecycle|invocation"):
        _verify(receipt)


def test_explicit_lifecycle_contract_rejects_partial_new_schema() -> None:
    receipt = _turn_exit_receipt()
    del receipt["recurring_automation_terminal"]
    with pytest.raises(continuity.TurnExitBlocked, match="lifecycle"):
        _verify(receipt)


def test_legacy_turn_exit_receipt_remains_accepted_for_inflight_handoffs() -> None:
    _verify(_turn_exit_receipt(explicit_lifecycle=False))


def test_trusted_turn_exit_workflow_emits_explicit_recurring_lifecycle_fields() -> None:
    text = Path(".github/workflows/whd-turn-exit-gate.yml").read_text(
        encoding="utf-8"
    )
    for token in (
        '"invocation_end_allowed"',
        '"recurring_automation_action"',
        '"KEEP_ENABLED"',
        '"recurring_automation_terminal"',
        '"scheduler_end_allowed"',
    ):
        assert token in text
