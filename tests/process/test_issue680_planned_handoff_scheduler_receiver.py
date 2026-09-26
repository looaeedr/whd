from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DISPATCH = ROOT / ".agents" / "skills" / "engineering" / "派工" / "SKILL.md"
SCHED_SIM = ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
REMOTE_GUARD = ROOT / ".agents" / "skills" / "engineering" / "remote-execution-guard" / "SKILL.md"
GUARD_EXECUTABLE = ROOT / "tools" / "execution_claim_guard.py"
REMOTE_GUARD_WORKFLOW = ROOT / ".github" / "workflows" / "whd-remote-execution-guard.yml"

MARKER = "WHD_WORK_EXECUTOR_HANDOFF_V1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_planned_handoff_sender_contract_is_durable_and_distinct_from_stale_takeover() -> None:
    text = _read(DISPATCH) + "\n" + _read(REMOTE_GUARD)
    assert MARKER in text
    assert "claim-handoff" in text
    assert "checkpoint fingerprint" in text.lower() or "checkpoint_fingerprint" in text
    assert "handoff generation" in text.lower() or "handoff_generation" in text
    assert "to_worker" in text


def test_scheduler_receiver_validates_exact_planned_handoff_identity() -> None:
    text = _read(SCHED_SIM)
    assert MARKER in text
    for token in (
        "target_lane",
        "to_worker",
        "handoff_generation",
        "checkpoint_fingerprint",
        "claim_blob",
        "next_action",
    ):
        assert token in text


def test_scheduler_receiver_does_not_reclassify_completed_planned_handoff_as_stale_takeover() -> None:
    text = _read(SCHED_SIM)
    section = text.split(MARKER, 1)[1]
    assert "claim-takeover" in section
    assert "stale" in section.lower()
    assert "不得" in section
    assert "planned" in section.lower()


def test_both_scheduler_lanes_share_planned_handoff_receiver_semantics() -> None:
    text = _read(SCHED_SIM)
    section = text.split(MARKER, 1)[1]
    assert "排程A" in section
    assert "排程B" in section
    assert "resume" in section.lower() or "續" in section


def test_claim_handoff_is_a_distinct_guarded_action_with_durable_readback() -> None:
    text = _read(GUARD_EXECUTABLE)
    assert '"claim-handoff"' in text
    assert 'if action == "claim-handoff"' in text
    assert "claim_handoff_cas_applied" in text
    for token in (
        "target_lane",
        "to_worker",
        "handoff_generation",
        "checkpoint_fingerprint",
        "next_action",
    ):
        assert token in text


def test_trusted_remote_guard_binds_exact_planned_handoff_identity() -> None:
    text = _read(REMOTE_GUARD_WORKFLOW)
    assert '"claim-handoff"' in text
    assert 'claim-handoff missing keys' in text
    assert 'claim-handoff to_worker does not match target_lane' in text
    assert 'claim-handoff checkpoint_fingerprint mismatch' in text
    assert 'claim-handoff next_action mismatch' in text
    assert 'planned handoff keys are only valid for claim-handoff' in text
    for token in (
        '"target_lane": request.get("target_lane")',
        '"to_worker": request.get("to_worker")',
        '"handoff_generation": request.get("handoff_generation")',
        '"checkpoint_fingerprint": request.get("checkpoint_fingerprint")',
        '"next_action": request.get("next_action")',
    ):
        assert token in text
