from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

WORK_SLOT = ROOT / ".agents" / "skills" / "engineering" / "工作槽" / "SKILL.md"
SCHED_SIM = ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
REMOTE_GUARD = ROOT / ".agents" / "skills" / "engineering" / "remote-execution-guard" / "SKILL.md"

MARKER = "WHD_WORK_EXECUTOR_HANDOFF_V1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_planned_handoff_sender_contract_is_durable_and_distinct_from_stale_takeover() -> None:
    text = _read(WORK_SLOT) + "\n" + _read(REMOTE_GUARD)
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
