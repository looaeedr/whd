from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHED_SIM = ROOT / ".agents" / "skills" / "engineering" / "排程模擬" / "SKILL.md"
WRITE_SCHED = ROOT / ".agents" / "skills" / "engineering" / "寫排程" / "SKILL.md"

MARKER = "READY_WORK_CENSUS_V1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_scheduler_simulation_requires_exhaustive_no_work_census() -> None:
    text = _read(SCHED_SIM)
    assert MARKER in text
    assert "NO_MATCHING_HANDOFF != NO_WORK" in text
    assert "NO_EXECUTABLE_WORK" in text
    assert "candidate executable leaves" in text
    assert "fresh durable exclusion evidence" in text
    for token in (
        "FOREIGN_LIVE_OWNER",
        "DEPENDENCY_BLOCKED",
        "ACTIVE_EXACT_RUN",
        "AUTHORITY_MISMATCH",
        "SHARED_SCOPE_CONFLICT",
    ):
        assert token in text


def test_scheduler_must_claim_scheduler_authorized_unclaimed_leaf() -> None:
    text = _read(SCHED_SIM)
    section = text.split(MARKER, 1)[1]
    assert "unclaimed + dependency-unblocked + scheduler-authorized" in section
    assert "MUST_CLAIM" in section
    assert "canonical claim path" in section
    assert "沒有 matching handoff" in section
    assert "不得" in section


def test_scheduler_authoring_propagates_no_work_census_to_live_prompts() -> None:
    text = _read(WRITE_SCHED)
    assert MARKER in text
    assert "NO_MATCHING_HANDOFF != NO_WORK" in text
    assert "NO_EXECUTABLE_WORK" in text
    assert "fresh durable exclusion evidence" in text
    assert "post-update readback" in text
    assert "不得刪除" in text


def test_no_work_census_is_provenance_not_new_execution_authority() -> None:
    for path in (SCHED_SIM, WRITE_SCHED):
        section = _read(path).split(MARKER, 1)[1]
        assert "不建立 execution authority" in section
        assert "lane owner" in section
        assert "claim ownership" in section


def test_scheduler_simulation_covers_real_recurring_and_interactive_entrypoints() -> None:
    text = _read(SCHED_SIM)
    assert "REAL_RECURRING_SCHEDULER_ENTRYPOINT_V1" in text
    section = text.split("REAL_RECURRING_SCHEDULER_ENTRYPOINT_V1", 1)[1]
    assert "00 / 20 / 40" in section
    assert "B15 / B45" in section
    assert "actual_invocation_source=scheduler" in section
    assert "actual_invocation_source=chatgpt_interactive" in section
    assert "SCHEDULER_LANE" in section


def test_scheduler_authoring_requires_scheduler_simulation_every_wake() -> None:
    text = _read(WRITE_SCHED)
    assert "SCHEDULER_SIMULATION_EVERY_WAKE_GATE_V1" in text
    section = text.split("SCHEDULER_SIMULATION_EVERY_WAKE_GATE_V1", 1)[1]
    assert ".agents/skills/engineering/排程模擬/SKILL.md" in section
    assert "每次 wake" in section
    assert "不論" in section
    assert "handoff" in section

def test_same_lane_nonterminal_claim_is_never_collapsed_to_no_work() -> None:
    text = _read(SCHED_SIM)
    assert "SAME_LANE_NONTERMINAL_WORK_V1" in text
    section = text.split("SAME_LANE_NONTERMINAL_WORK_V1", 1)[1]
    assert "same-lane" in section
    assert "non-terminal" in section
    assert "next_action" in section
    assert "SAME_LANE_RESUME" in section
    assert "NO_EXECUTABLE_WORK" in section
    assert "不得" in section


def test_scheduler_routes_drift_to_reconciliation_not_no_work() -> None:
    text = _read(SCHED_SIM)
    section = text.split("SAME_LANE_NONTERMINAL_WORK_V1", 1)[1]
    assert "RECONCILIATION_REQUIRED" in section
    assert "AUTHORITY_MISMATCH" in section
    assert "SHARED_SCOPE_CONFLICT" in section
    assert "target/head/checkpoint" in section
    assert "NO_WORK" in section


def test_scheduler_authoring_propagates_same_lane_nonterminal_gate() -> None:
    text = _read(WRITE_SCHED)
    assert "SAME_LANE_NONTERMINAL_WORK_V1" in text
    section = text.split("SAME_LANE_NONTERMINAL_WORK_V1", 1)[1]
    assert "RECONCILIATION_REQUIRED" in section
    assert "SHARED_SCOPE_CONFLICT" in section
    assert "post-update readback" in section

