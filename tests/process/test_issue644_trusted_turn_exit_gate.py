from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.continuity_controller as continuity


ROOT = Path(__file__).resolve().parents[2]
TURN_EXIT_WORKFLOW = ROOT / ".github" / "workflows" / "whd-turn-exit-gate.yml"
ISSUE = "644"
BRANCH = "workorder/issue640-guard-turn-exit-helper-hardening-20260925"
HEAD = "c7e1e6fa5664e8c877b411ab6dcac941c90c2341"


def _claim(phase: str) -> dict[str, object]:
    return {
        "issue": int(ISSUE),
        "work_branch": BRANCH,
        "head_sha": HEAD,
        "phase": phase,
    }


def _checkpoint(*, closure_state=continuity.ClosureState.CLOSED):
    return continuity.Checkpoint(
        issue=ISSUE,
        branch=BRANCH,
        head_sha=HEAD,
        state=continuity.ContinuityState.TERMINAL_SUCCESS,
        next_action=None,
        evidence=("accepted",),
        closure_state=closure_state,
        closure_next_action=(
            None
            if closure_state is continuity.ClosureState.CLOSED
            else "finish canonical closure"
        ),
    )


def _tx(state: str):
    return SimpleNamespace(state=state)


def _gate(
    *,
    checkpoint=None,
    claim_state=None,
    transaction_state=None,
    issue_state="closed",
    issue_state_reason="completed",
    active_remote_run=False,
    delegated_work_state="NONE",
):
    gate = getattr(continuity, "evaluate_remote_turn_exit_from_durable_state", None)
    assert callable(gate), (
        "RED-CLOSE-03: canonical remote durable turn-exit evaluator is missing"
    )
    return gate(
        checkpoint,
        issue_state=issue_state,
        issue_state_reason=issue_state_reason,
        claim_state=claim_state,
        transaction_state=transaction_state,
        live_branch_head_sha=HEAD,
        active_remote_run=active_remote_run,
        delegated_work_state=delegated_work_state,
        expected_issue=ISSUE,
        expected_branch=BRANCH,
        expected_head_sha=HEAD,
    )


def test_c_r1_active_claim_checkpoint_missing_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="ACTIVE_CLAIM_REQUIRES_CHECKPOINT"):
        _gate(checkpoint=None, claim_state=_claim("CLAIMED"), transaction_state=_tx("NONE"))


def test_c_r2_closing_claim_checkpoint_missing_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="ACTIVE_CLAIM_REQUIRES_CHECKPOINT"):
        _gate(checkpoint=None, claim_state=_claim("CLOSING"), transaction_state=_tx("NONE"))


def test_c_r3_unconsumed_green_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="UNCONSUMED_GREEN"):
        _gate(checkpoint=_checkpoint(), claim_state=_claim("RELEASED"), transaction_state=_tx("PENDING"))


def test_c_r4_durable_mutation_reconciliation_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="DURABLE_MUTATION_ALREADY_HAPPENED"):
        _gate(
            checkpoint=_checkpoint(),
            claim_state=_claim("RELEASED"),
            transaction_state=_tx("MUTATION_DONE_RECONCILE_ONLY"),
        )


def test_c_r5_durable_mutation_state_never_permits_replay_exit():
    with pytest.raises(continuity.TurnExitBlocked, match="DURABLE_MUTATION_ALREADY_HAPPENED"):
        _gate(
            checkpoint=_checkpoint(),
            claim_state=_claim("RELEASED"),
            transaction_state=_tx("MUTATION_DONE_RECONCILE_ONLY"),
        )


def test_c_r6_released_claim_checkpoint_missing_still_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="CHECKPOINT_MISSING"):
        _gate(checkpoint=None, claim_state=_claim("RELEASED"), transaction_state=_tx("NONE"))


def test_c_r7_terminal_checkpoint_issue_not_closed_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="ISSUE_NOT_CLOSED_COMPLETED"):
        _gate(
            checkpoint=_checkpoint(),
            claim_state=_claim("RELEASED"),
            transaction_state=_tx("NONE"),
            issue_state="open",
            issue_state_reason=None,
        )


def test_c_r8_issue_closed_claim_not_released_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="CLAIM_NOT_RELEASED"):
        _gate(checkpoint=_checkpoint(), claim_state=_claim("CLOSING"), transaction_state=_tx("NONE"))


def test_c_r9_checkpoint_closed_active_claim_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="CLAIM_NOT_RELEASED"):
        _gate(checkpoint=_checkpoint(), claim_state=_claim("GREEN"), transaction_state=_tx("NONE"))


def test_c_r10_released_claim_pending_closure_denied():
    with pytest.raises(continuity.TurnExitBlocked, match="closure transaction remains"):
        _gate(
            checkpoint=_checkpoint(closure_state=continuity.ClosureState.RELEASE_HANDOFF_PENDING),
            claim_state=_claim("RELEASED"),
            transaction_state=_tx("NONE"),
        )


def test_c_r11_only_fully_closed_idle_state_is_permitted():
    assert (
        _gate(
            checkpoint=_checkpoint(),
            claim_state=_claim("RELEASED"),
            transaction_state=_tx("NONE"),
        )
        == "TURN_EXIT_PERMITTED"
    )
    with pytest.raises(continuity.TurnExitBlocked, match="ACTIVE_REMOTE_RUN"):
        _gate(
            checkpoint=_checkpoint(),
            claim_state=_claim("RELEASED"),
            transaction_state=_tx("NONE"),
            active_remote_run=True,
        )
    with pytest.raises(continuity.TurnExitBlocked, match="ACTIVE_DELEGATED_WORK"):
        _gate(
            checkpoint=_checkpoint(),
            claim_state=_claim("RELEASED"),
            transaction_state=_tx("NONE"),
            delegated_work_state="ACTIVE_DELEGATED_WORK",
        )


def test_c_r12_trusted_workflow_binds_scheduler_end_to_machine_permission():
    assert TURN_EXIT_WORKFLOW.is_file(), (
        "RED-CLOSE-03: trusted .github/workflows/whd-turn-exit-gate.yml is missing"
    )
    text = TURN_EXIT_WORKFLOW.read_text(encoding="utf-8")
    required = (
        "WHD_REMOTE_TURN_EXIT_REQUEST_V1",
        "WHD_REMOTE_TURN_EXIT_RESULT_V1",
        "TURN_EXIT_PERMITTED",
        "TURN_EXIT_DENIED",
        "WHD_SCHEDULER_RUNTIME_END_V1",
        "scheduler_end_allowed",
        "tools/continuity_controller.py",
        "tools/execution_claim_guard.py",
        "tools/stale_claim_takeover.py",
    )
    missing = [token for token in required if token not in text]
    assert not missing, f"trusted turn-exit workflow contract missing: {missing}"
