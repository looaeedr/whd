from pathlib import Path
import inspect

import tools.continuity_controller as continuity
import tools.execution_claim_guard as execution_guard


ROOT = Path(__file__).resolve().parents[2]
TURN_EXIT_WORKFLOW = ROOT / ".github" / "workflows" / "whd-turn-exit-gate.yml"


ISSUE638_POST_MERGE_GAP = {
    "issue": 638,
    "pr": 639,
    "production_head": "2bf5969aba8c8aa033b314f0d6f92165239f67c0",
    "work_head": "3ea1f75cada6ef8079528ca60122fcc81d226124",
    "claim": {
        "phase": "CLOSING",
        "merged": False,
        "next_action": "reconcile post-merge durable state before closure",
    },
    "checkpoint": None,
    "guard": {
        "result": "GREEN",
        "action": "write",
    },
}


def test_red_close_01_active_claim_requires_checkpoint_machine_gate():
    gate = getattr(execution_guard, "assert_active_claim_requires_checkpoint", None)
    assert callable(gate), (
        "RED-CLOSE-01: ACTIVE_CLAIM_REQUIRES_CHECKPOINT machine gate is missing"
    )


def test_red_close_02_turn_exit_api_has_machine_context_beyond_checkpoint_only():
    params = set(inspect.signature(continuity.assert_turn_exitable).parameters)
    has_claim_context = bool({"claim", "execution_claim", "claim_state"} & params)
    has_guard_context = bool(
        {"guard_transaction", "pending_guard_transaction", "transaction_state"} & params
    )
    assert has_claim_context and has_guard_context, (
        "RED-CLOSE-02: assert_turn_exitable is checkpoint-only and cannot machine-block "
        "UNCONSUMED_GREEN / EXPIRED_UNCONSUMED / durable-mutation reconciliation"
    )


def test_red_close_02_issue638_post_merge_gap_has_durable_state_evaluator():
    evaluator = getattr(continuity, "evaluate_turn_exit_from_durable_state", None)
    assert callable(evaluator), (
        "RED-CLOSE-02: #638/#639 merged-production-advanced + stale-claim + "
        "checkpoint-missing fixture has no durable turn-exit evaluator"
    )


def test_red_close_03_trusted_remote_turn_exit_executor_exists():
    assert TURN_EXIT_WORKFLOW.is_file(), (
        "RED-CLOSE-03: trusted .github/workflows/whd-turn-exit-gate.yml is missing"
    )
    text = TURN_EXIT_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "WHD_REMOTE_TURN_EXIT_RESULT_V1",
        "TURN_EXIT_PERMITTED",
        "continuity_controller.py",
    ):
        assert required in text, f"RED-CLOSE-03: trusted turn-exit workflow missing {required}"
