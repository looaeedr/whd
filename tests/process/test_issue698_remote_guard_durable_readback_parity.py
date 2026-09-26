from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TURN_EXIT_WORKFLOW = ROOT / ".github" / "workflows" / "whd-turn-exit-gate.yml"

GUARD_ACTIONS = (
    "branch-create",
    "claim-takeover",
    "write",
    "commit",
    "qa-dispatch",
    "workflow-dispatch",
    "pr-write",
)

READBACK_FIELDS = (
    "branch_exists",
    "branch_head_sha",
    "claim_cas_applied",
    "target_changed",
    "parent_sha",
    "post_head_sha",
    "committed_at",
    "run_created",
    "run_head_sha",
    "pr_readback",
)


def test_red_stop_19_trusted_turn_exit_produces_all_guard_readback_shapes():
    text = TURN_EXIT_WORKFLOW.read_text(encoding="utf-8")

    assert 'if receipt.get("action") != "commit":' not in text, (
        "RED-STOP-19: trusted durable-readback producer is still commit-only"
    )
    assert "GUARD_DURABLE_READBACK_ACTIONS" in text, (
        "RED-STOP-19: trusted producer lacks one explicit seven-action parity contract"
    )
    assert "_build_guard_durable_readback" in text, (
        "RED-STOP-19: trusted producer lacks a single action-bound readback adapter"
    )

    missing_actions = [action for action in GUARD_ACTIONS if f'"{action}"' not in text]
    assert not missing_actions, (
        "RED-STOP-19: trusted producer is missing Guard action parity: "
        f"{missing_actions}"
    )

    missing_fields = [field for field in READBACK_FIELDS if f'"{field}"' not in text]
    assert not missing_fields, (
        "RED-STOP-19: trusted producer is missing classifier readback evidence fields: "
        f"{missing_fields}"
    )

    assert "durable_readbacks=durable_readbacks" in text, (
        "RED-STOP-19: producer evidence is not bridged into the existing "
        "execution_claim_guard classifier"
    )
