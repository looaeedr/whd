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
