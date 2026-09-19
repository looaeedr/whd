from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
REMOTE = ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"
EXECUTION = ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md"
AI_CURRENT = ROOT / "個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md"
PITFALL = ROOT / "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def test_controller_requires_real_progress_producer_for_waiting():
    text = read(CONTROLLER)
    assert "POLLING_OBSERVATION_ONLY" in text
    assert "progress producer" in text
    assert "WAITING_REMOTE" in text
    assert "輪詢" in text and "不能產生進度" in text

def test_remote_qa_forbids_waiting_without_active_executor():
    text = read(REMOTE)
    assert "REAL_PROGRESS_PRODUCER_GATE" in text
    assert "no executor" in text.lower() or "沒有 executor" in text
    assert "RUN_NOT_CREATED" in text
    assert "polling" in text.lower()

def test_execution_skill_requires_action_when_no_external_producer_exists():
    text = read(EXECUTION)
    assert "POLLING_OBSERVATION_ONLY_BRIDGE" in text
    assert "RUNNING" in text or "RECOVERING" in text
    assert "使用者" in text and "scheduler" in text

def test_ai_library_records_observation_only_polling_rule():
    text = read(AI_CURRENT)
    assert "Polling is observation-only" in text
    assert "progress producer" in text
    assert "WAITING_REMOTE" in text

def test_pitfall_records_status_only_polling_loop():
    text = read(PITFALL)
    assert "POLLING_WITHOUT_PROGRESS_PRODUCER_PITFALL" in text
    assert "輪詢" in text
    assert "進度" in text
