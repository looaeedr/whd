import json
import subprocess
import sys
from pathlib import Path

import pytest

import tools.continuity_controller as continuity


ROOT = Path(__file__).resolve().parents[2]
POWER_GATE = ROOT / "tools" / "workstation_poweroff_gate.py"


def _operation(state: continuity.OperationState):
    return continuity.OperationTransaction(
        operation_id="issue-close-699-op",
        operation_type="github-issue-close",
        state=state,
        target="https://github.com/looaeedr/whd/issues/699",
        payload_hash="a" * 64,
        recovery_action="read back Issue #699 and reconcile exact close operation",
    )


def _terminal_checkpoint(state: continuity.OperationState):
    return continuity.Checkpoint(
        issue="699",
        branch="work/issue699-turn-exit-poweroff-close-recovery-20260927",
        head_sha="b" * 40,
        state=continuity.ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        evidence=("acceptance complete",),
        closure_state=continuity.ClosureState.CLOSED,
        operation=_operation(state),
    )


@pytest.mark.parametrize(
    "state",
    [
        continuity.OperationState.PREPARED,
        continuity.OperationState.AUTHORIZED,
        continuity.OperationState.EFFECT_OBSERVED,
        continuity.OperationState.AMBIGUOUS,
    ],
)
def test_red_stop_20_unresolved_operation_blocks_terminal_turn_exit(state):
    with pytest.raises(continuity.TurnExitBlocked, match="UNRESOLVED_OPERATION"):
        continuity.assert_turn_exitable(_terminal_checkpoint(state))


def _safe_slot(operation_state: str) -> dict:
    return {
        "slot_id": "worker.slot.3",
        "local_dependent": True,
        "local_machine_state": "LOCAL_CLEAN_SYNCED",
        "local_mutation_in_progress": False,
        "local_worktree_clean": True,
        "local_head_matches_remote": True,
        "unpushed_commits": 0,
        "checkpoint_durable": True,
        "checkpoint_state": "RUNNING",
        "checkpoint_next_action": "continue exact durable next action",
        "checkpoint_head_matches_remote": True,
        "guard_transaction": "NONE",
        "operation_state": operation_state,
        "handoff_verified": True,
        "claim_owner_matches_scheduler": True,
        "scheduler_enablement": "ENABLED",
        "local_runtime_end_durable": True,
        "dependency_error": None,
    }


def _evaluate_poweroff(tmp_path: Path, operation_state: str) -> dict:
    snapshot = {
        "schema": "WHD_POWER_OFF_GATE_SNAPSHOT_V1",
        "poweroff_request_id": "REQ-699",
        "evidence_revision": "REV-699",
        "slots": [_safe_slot(operation_state)],
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(POWER_GATE), "evaluate", "--snapshot", str(path)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("state", ["PREPARED", "AUTHORIZED", "EFFECT_OBSERVED", "AMBIGUOUS"])
def test_red_stop_20_unresolved_operation_blocks_poweroff_safe(tmp_path, state):
    result = _evaluate_poweroff(tmp_path, state)
    assert result["result"] == "NOT_SAFE"
    assert result["reason"] == "UNRESOLVED_OPERATION"


def test_red_stop_20_reconciled_operation_does_not_block_poweroff(tmp_path):
    result = _evaluate_poweroff(tmp_path, "RECONCILED")
    assert result["result"] == "SAFE"


def _reconcile(operation, *, issue_state, issue_state_reason):
    fn = getattr(continuity, "reconcile_issue_close_operation", None)
    assert callable(fn), "RED-STOP-21: canonical Issue-close recovery seam is missing"
    return fn(
        operation,
        issue_state=issue_state,
        issue_state_reason=issue_state_reason,
    )



def test_red_stop_21_already_closed_completed_reconciles_without_replay():
    operation = _operation(continuity.OperationState.EFFECT_OBSERVED)
    reconciled = _reconcile(
        operation,
        issue_state="closed",
        issue_state_reason="completed",
    )
    assert reconciled.operation_id == operation.operation_id
    assert reconciled.state is continuity.OperationState.RECONCILED


def test_red_stop_21_open_issue_remains_distinguishable_as_not_applied():
    operation = _operation(continuity.OperationState.AUTHORIZED)
    observed = _reconcile(
        operation,
        issue_state="open",
        issue_state_reason=None,
    )
    assert observed == operation
    assert observed.state is continuity.OperationState.AUTHORIZED


@pytest.mark.parametrize(
    ("issue_state", "reason"),
    [("closed", "not_planned"), ("unknown", None), ("", None)],
)
def test_red_stop_21_ambiguous_issue_close_readback_fails_closed(issue_state, reason):
    operation = _operation(continuity.OperationState.EFFECT_OBSERVED)
    with pytest.raises(continuity.CheckpointError, match="ISSUE_CLOSE_READBACK_AMBIGUOUS"):
        _reconcile(
            operation,
            issue_state=issue_state,
            issue_state_reason=reason,
        )
