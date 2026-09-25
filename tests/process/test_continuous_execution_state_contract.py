from pathlib import Path


EXECUTION_SKILL = Path(".agents/skills/engineering/執行開發任務/SKILL.md")


def _text() -> str:
    return EXECUTION_SKILL.read_text(encoding="utf-8")


def test_execution_state_machine_defines_all_authoritative_states():
    text = _text()
    assert "EXECUTION_STATE_MACHINE" in text
    for state in ("RUNNING", "WAITING_REMOTE", "RECOVERING", "BLOCKED", "COMPLETE"):
        assert f"`{state}`" in text


def test_every_nonterminal_state_has_a_required_next_action():
    text = _text()
    assert "RUNNING → execute_next_action" in text
    assert "WAITING_REMOTE → poll_locked_run" in text
    assert "RECOVERING → evidence_root_cause_fix_retry" in text
    assert "BLOCKED → wait_for_missing_authority" in text
    assert "COMPLETE → no_next_action" in text
    assert "non-terminal state 不得輸出 final" in text


def test_blocked_is_restricted_to_explicit_unrecoverable_conditions():
    text = _text()
    assert "BLOCKED_ALLOWED_REASONS" in text
    assert "產品語意決策" in text
    assert "必要權限" in text
    assert "不可推導資料" in text
    assert "系統硬性中止" in text
    assert "可恢復 FAIL 不得進 BLOCKED" in text


def test_complete_requires_acceptance_evidence_and_rejects_intermediate_events():
    text = _text()
    assert "COMPLETE_REQUIRES_ACCEPTANCE_EVIDENCE" in text
    for event in (
        "branch created",
        "commit created",
        "push complete",
        "run_id acquired",
        "queued",
        "in_progress",
        "focused PASS",
        "partial acceptance PASS",
    ):
        assert event in text
    assert "以上事件不得 transition 到 COMPLETE" in text
