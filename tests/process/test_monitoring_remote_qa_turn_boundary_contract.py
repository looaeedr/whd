from pathlib import Path


SKILL = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_nonterminal_progress_update_cannot_end_assistant_turn():
    text = _skill_text()
    assert "Progress updates are not turn boundaries" in text
    assert "下一個動作必須是同一個 locked `run_id + head_sha` 的 poll" in text
    assert "進度回報不是 assistant turn / response 的結束點" in text


def test_user_is_not_remote_qa_scheduler():
    text = _skill_text()
    assert "使用者不是 remote-QA scheduler" in text
    assert "不得要求或依賴使用者輸入「繼續」「輪」「continue」「poll」" in text


def test_final_response_is_blocked_while_remote_qa_lock_is_nonterminal():
    text = _skill_text()
    assert "## Final-response gate" in text
    assert "non-terminal" in text
    assert "final 禁止" in text
