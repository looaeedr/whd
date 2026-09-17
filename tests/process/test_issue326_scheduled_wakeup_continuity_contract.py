from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTINUITY = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
MONITORING = ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"
PITFALLS = ROOT / "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_canonical_skill_owns_scheduled_wakeup_execution_contract():
    text = _text(CONTINUITY)
    required = (
        "SCHEDULED_WAKEUP_CONTINUITY_CONTRACT",
        "wake-up trigger != execution owner",
        "RUN_NOT_CREATED",
        "terminal => continue next autonomous step",
        "status update != exit",
        "checkpoint before forced turn end",
    )
    for marker in required:
        assert marker in text


def test_monitoring_skill_bridges_without_becoming_second_execution_authority():
    text = _text(MONITORING)
    assert "SCHEDULED_WAKEUP_CONTINUITY_BRIDGE" in text
    assert "RUN_NOT_CREATED" in text
    assert "executable-continuity-controller/SKILL.md" in text
    assert "does not own scheduled wake-up execution" in text


def test_ai_library_records_scheduled_wakeup_pitfall_as_reference():
    text = _text(PITFALLS)
    assert "SCHEDULED_WAKEUP_STATUS_ONLY_PITFALL" in text
    assert "wake-up trigger != execution owner" in text
    assert "RUN_NOT_CREATED" in text
    assert "status update != exit" in text
    assert "executable-continuity-controller/SKILL.md" in text


def test_issue326_additions_do_not_erase_existing_continuity_authority():
    continuity = _text(CONTINUITY)
    monitoring = _text(MONITORING)
    pitfalls = _text(PITFALLS)

    for marker in (
        "OWNING_FINALIZATION_GUARD_V2",
        "ASSISTANT_TURN_EXIT_GATE_V1",
        "ASSISTANT_TURN_EXIT_HARD_GATE_V2",
        "NO_CURRENT_GUARD_INVOCATION_PROOF",
    ):
        assert marker in continuity

    for marker in (
        "LONG_LOG_CONTEXT_SAFE_EXECUTION_V1 bridge",
        "USER_VISIBLE_CHECKPOINT_GATE_BRIDGE",
        "REMOTE_QA_ACTIVE_LOCK",
        "User-visible reporting cadence",
        "Progress updates are not turn boundaries",
    ):
        assert marker in monitoring

    for marker in (
        "ISSUE188_STALE_WAIT_PITFALL",
        "WORK_ORDER_LINEAGE_PITFALL",
        "REMOTE_TERMINAL_CLOSING_LOCK_GAP",
    ):
        assert marker in pitfalls
