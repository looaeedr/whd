from pathlib import Path


EXECUTION_SKILL = Path(".agents/skills/engineering/執行開發任務/SKILL.md")
MONITORING_SKILL = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_remote_qa_nonterminal_states_bridge_to_waiting_remote():
    execution = _read(EXECUTION_SKILL)
    assert "REMOTE_QA_STATE_BRIDGE" in execution
    assert "queued / in_progress → WAITING_REMOTE" in execution
    assert "same `run_id + head_sha`" in execution
    assert "WAITING_REMOTE → poll_locked_run" in execution


def test_remote_qa_terminal_success_resumes_next_acceptance_action():
    execution = _read(EXECUTION_SKILL)
    assert "terminal success → RUNNING(next_acceptance_action)" in execution
    assert "success 不是自動 COMPLETE" in execution


def test_remote_qa_terminal_failure_enters_recovering_not_blocked():
    execution = _read(EXECUTION_SKILL)
    assert "terminal failure → RECOVERING" in execution
    assert "failed-job log" in execution
    assert "不得停在 FAIL 回報" in execution


def test_monitoring_skill_remains_only_polling_authority_and_cadence_is_observation():
    execution = _read(EXECUTION_SKILL)
    monitoring = _read(MONITORING_SKILL)
    assert "polling mechanics remain owned by `monitoring-remote-qa`" in execution
    assert "30 秒 cadence 只影響聊天中的觀測回報" in monitoring
    assert "使用者不是 remote-QA scheduler" in monitoring
    assert "REMOTE_QA_ACTIVE_LOCK" in monitoring
