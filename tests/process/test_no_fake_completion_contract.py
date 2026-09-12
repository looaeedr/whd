from pathlib import Path


EXECUTION_SKILL = Path(".agents/skills/engineering/執行開發任務/SKILL.md")


def _text() -> str:
    return EXECUTION_SKILL.read_text(encoding="utf-8")


def test_no_fake_completion_contract_covers_all_forbidden_stop_points():
    text = _text()
    assert "NO_FAKE_COMPLETION_CONTRACT" in text
    for marker in (
        "branch created",
        "code modified",
        "commit created",
        "push complete",
        "remote QA started",
        "run_id acquired",
        "queued / in_progress",
        "partial tests PASS",
        "focused tests PASS but final acceptance pending",
        "Combined PASS but invariant / drift / cleanup pending",
        "明確知道 next action",
    ):
        assert marker in text


def test_progress_update_is_observation_only_and_preserves_execution_state():
    text = _text()
    assert "PROGRESS_UPDATE_STATE_PRESERVATION" in text
    assert "progress update 只能觀測狀態" in text
    assert "不得改變 execution state" in text
    assert "回報後若仍有合法 next action，必須繼續執行" in text


def test_incomplete_work_uses_only_in_progress_or_blocked():
    text = _text()
    assert "未完成只能標示 `IN PROGRESS` 或 `BLOCKED`" in text
    assert "稍後繼續" in text
    assert "下一續跑點" in text
    assert "不得作為正常結束語義" in text


def test_only_genuine_blocked_or_complete_can_terminate_normally():
    text = _text()
    assert "NORMAL_TERMINATION_GATE" in text
    assert "genuine BLOCKED" in text
    assert "evidence-backed COMPLETE" in text
    assert "non-terminal state 不能產生 COMPLETE / final response" in text
    assert "system hard-cut" in text
    assert "CHECKPOINT_RESUME_CONTRACT" in text
