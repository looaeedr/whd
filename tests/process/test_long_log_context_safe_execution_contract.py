from pathlib import Path
import json

MARKER = "LONG_LOG_CONTEXT_SAFE_EXECUTION_V1"
SKILL = Path(".agents/skills/engineering/long-log-context-safe-execution/SKILL.md")
MONITOR = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
AGENTS = Path("AGENTS.md")
PITFALL = Path("個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md")
REGISTRY = Path(".agents/skills/skill_registry.json")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_canonical_long_log_skill_locks_context_safe_behavior():
    text = _read(SKILL)
    assert MARKER in text
    assert "禁止把完整超長 Log" in text
    assert "bounded tail" in text
    assert "offset/cursor" in text
    assert "FAIL 先定位" in text
    assert "執行視窗被切斷 ≠ 工作失敗" in text
    assert "terminal 後才做完整 evidence 收斂" in text


def test_remote_qa_bridges_to_long_log_authority_without_second_polling_machine():
    text = _read(MONITOR)
    assert MARKER in text
    assert "long-log-context-safe-execution/SKILL.md" in text
    assert "bounded failure slice" in text
    assert "whole log" in text
    assert "REMOTE_QA_ACTIVE_LOCK" in text


def test_agents_and_ai_pitfall_make_rule_durable():
    agents = _read(AGENTS)
    pitfall = _read(PITFALL)
    assert MARKER in agents
    assert "long-log-context-safe-execution/SKILL.md" in agents
    assert MARKER in pitfall
    assert "offset/cursor" in pitfall
    assert "禁止先重跑" in pitfall


def test_preflight_registry_routes_long_logs_and_remote_qa_to_context_safe_skill():
    data = json.loads(_read(REGISTRY))
    routes = {route["id"]: route for route in data["routes"]}
    long_log = routes["long-log-context-safe-execution"]
    assert "long-log-context-safe-execution" in long_log["required_skills"]
    assert "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md" in long_log["required_references"]
    remote = routes["remote-qa-monitoring"]
    assert "monitoring-remote-qa" in remote["required_skills"]
    assert "long-log-context-safe-execution" in remote["required_skills"]
    assert "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md" in remote["required_references"]
