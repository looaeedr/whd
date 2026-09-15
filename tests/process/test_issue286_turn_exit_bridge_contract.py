from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canonical_controller_skill_owns_assistant_turn_exit_gate():
    text = _read(".agents/skills/engineering/executable-continuity-controller/SKILL.md")
    assert "ASSISTANT_TURN_EXIT_GATE_V1" in text
    assert "assert_turn_exitable" in text
    assert "assert-turn-exitable" in text
    assert "WAITING_REMOTE → RUNNING(cleanup)" in text


def test_all_long_flow_entry_skills_bridge_to_global_turn_exit_gate():
    cases = {
        ".agents/skills/engineering/執行開發任務/SKILL.md": "GLOBAL_TURN_EXIT_GATE_BRIDGE",
        ".agents/skills/engineering/派工/SKILL.md": "GLOBAL_TURN_EXIT_GATE_BRIDGE",
        ".agents/skills/engineering/monitoring-remote-qa/SKILL.md": "GLOBAL_TURN_EXIT_AFTER_REMOTE_BRIDGE",
        ".agents/skills/engineering/issue-closure-gate/SKILL.md": "CLOSING_TURN_EXIT_BRIDGE",
    }
    for path, marker in cases.items():
        text = _read(path)
        assert marker in text, path
        assert "assert_turn_exitable" in text, path


def test_closing_lock_gap_is_durable_in_both_continuity_pitfalls():
    continuous = _read("個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md")
    controller = _read("個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md")
    assert "REMOTE_TERMINAL_CLOSING_LOCK_GAP" in continuous
    assert "assert_turn_exitable" in continuous
    assert "TURN_EXIT_ENFORCEMENT_V2" in controller
    assert "assert_turn_exitable" in controller
