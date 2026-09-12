from pathlib import Path


DISPATCH_SKILL = Path(".agents/skills/engineering/派工/SKILL.md")
EXECUTION_SKILL = Path(".agents/skills/engineering/執行開發任務/SKILL.md")
PITFALLS = Path("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
MONITORING_SKILL = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dispatch_issue_creation_is_not_a_terminal_state():
    text = _read(DISPATCH_SKILL)
    assert "DISPATCH_IS_NOT_TERMINAL" in text
    assert "第一張可執行子工單" in text
    assert "GitHub 工單建立完成" in text
    assert "不得輸出 final" in text


def test_nonterminal_next_action_blocks_final_response():
    text = _read(EXECUTION_SKILL)
    assert "NONTERMINAL_NEXT_ACTION_GATE" in text
    assert "存在可自主執行的下一步" in text
    assert "final 禁止" in text
    assert "Gate RED" in text
    assert "完成 Gate 所要求的 evidence" in text


def test_ai_library_records_dispatch_stop_as_a_repeatable_pitfall():
    text = _read(PITFALLS)
    assert "把派工完成當成停工點" in text
    assert "進度回報不是工作終點" in text
    assert "使用者不是續跑 scheduler" in text


def test_remote_qa_authority_remains_delegated_to_monitoring_skill():
    dispatch = _read(DISPATCH_SKILL)
    execution = _read(EXECUTION_SKILL)
    monitoring = _read(MONITORING_SKILL)

    assert "monitoring-remote-qa" in dispatch
    assert "monitoring-remote-qa" in execution
    assert "REMOTE_QA_ACTIVE_LOCK" in monitoring
    assert "使用者不是 remote-QA scheduler" in monitoring
