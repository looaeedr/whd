from datetime import datetime, timezone
from pathlib import Path

import pytest

import tools.continuity_controller as continuity
from tools.continuity_controller import (
    Checkpoint,
    ContinuityState,
    ScheduledResumeAction,
    load_checkpoint,
    save_checkpoint,
    scheduled_resume_action,
)
from tools.scheduled_resume_runtime import (
    ScheduledWakeDisposition,
    evaluate_scheduled_wake,
)


def _operation_api():
    state_cls = getattr(continuity, "OperationState", None)
    tx_cls = getattr(continuity, "OperationTransaction", None)
    assert isinstance(state_cls, type), (
        "RED-STOP-17: continuity controller is missing canonical OperationState"
    )
    assert isinstance(tx_cls, type), (
        "RED-STOP-17: continuity controller is missing canonical OperationTransaction"
    )
    return state_cls, tx_cls


def _transaction(state):
    state_cls, tx_cls = _operation_api()
    return tx_cls(
        operation_id="op-697-example",
        operation_type="repository-write",
        state=state_cls(state),
        target=".dispatch/claims/issue-697.json",
        payload_hash="a" * 64,
        recovery_action=(
            "reconcile operation op-697-example from exact durable readback"
        ),
    )


def _running_with_operation(operation):
    return Checkpoint(
        issue="697",
        branch="work/issue697-operation-transaction-core-20260926",
        head_sha="b" * 40,
        state=ContinuityState.RUNNING,
        next_action="ordinary checkpoint next action",
        operation=operation,
    )


def test_red_stop_17_exposes_canonical_operation_state_vocabulary():
    state_cls, _ = _operation_api()
    assert [member.value for member in state_cls] == [
        "NOT_STARTED",
        "PREPARED",
        "AUTHORIZED",
        "EFFECT_OBSERVED",
        "RECONCILED",
        "AMBIGUOUS",
    ]


def test_red_stop_17_operation_transaction_round_trips_with_checkpoint(tmp_path: Path):
    state_cls, _ = _operation_api()
    original = _running_with_operation(_transaction(state_cls.PREPARED))
    path = tmp_path / "checkpoint.json"

    save_checkpoint(path, original)
    resumed = load_checkpoint(path)

    assert resumed == original
    assert resumed.operation.operation_id == "op-697-example"
    assert resumed.operation.state is state_cls.PREPARED
    assert resumed.operation.payload_hash == "a" * 64


@pytest.mark.parametrize(
    "operation_state",
    ["PREPARED", "AUTHORIZED", "EFFECT_OBSERVED", "AMBIGUOUS"],
)
def test_red_stop_18_unresolved_operation_routes_before_ordinary_next_action(
    operation_state,
):
    state_cls, _ = _operation_api()
    checkpoint = _running_with_operation(_transaction(state_cls(operation_state)))

    assert scheduled_resume_action(checkpoint) is ScheduledResumeAction.CONTINUE_RECOVERY
    evaluation = evaluate_scheduled_wake(
        checkpoint,
        now=datetime(2026, 9, 26, tzinfo=timezone.utc),
    )
    assert evaluation.disposition is ScheduledWakeDisposition.CONTINUE_RECOVERY
    assert evaluation.next_action == checkpoint.operation.recovery_action
    assert "operation" in evaluation.reason.lower()


def test_red_stop_18_reconciled_operation_allows_ordinary_next_action():
    state_cls, _ = _operation_api()
    checkpoint = _running_with_operation(_transaction(state_cls.RECONCILED))

    assert scheduled_resume_action(checkpoint) is ScheduledResumeAction.EXECUTE_NEXT_ACTION
    evaluation = evaluate_scheduled_wake(
        checkpoint,
        now=datetime(2026, 9, 26, tzinfo=timezone.utc),
    )
    assert evaluation.disposition is ScheduledWakeDisposition.EXECUTE_NEXT_ACTION
    assert evaluation.next_action == "ordinary checkpoint next action"
