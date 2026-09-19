from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CONTROLLER = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
REMOTE = ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"
EXECUTION = ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md"
AI_CURRENT = ROOT / "個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md"
PITFALL = ROOT / "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"

STATUS_SET = ("WORKING", "WAITING_REMOTE", "RECOVERING", "BLOCKED", "COMPLETE")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_controller_owns_scheduled_progress_heartbeat_contract():
    text = read(CONTROLLER)
    assert "SCHEDULED_RESUME_PROGRESS_HEARTBEAT" in text
    assert all(status in text for status in STATUS_SET)
    assert "active work" in text
    assert "不得靜默" in text
    assert "heartbeat" in text.lower()
    assert "第二套 state machine" in text


def test_remote_qa_bridges_waiting_remote_heartbeat_without_owning_second_state_machine():
    text = read(REMOTE)
    assert "SCHEDULED_RESUME_PROGRESS_HEARTBEAT_BRIDGE" in text
    assert "run_id + head_sha" in text
    assert "current step" in text or "目前 step" in text
    assert "executable-continuity-controller" in text


def test_execution_skill_bridges_active_work_visibility_and_does_not_stop_after_reporting():
    text = read(EXECUTION)
    assert "SCHEDULED_RESUME_PROGRESS_HEARTBEAT_BRIDGE" in text
    assert "WORKING" in text
    assert "progress update" in text
    assert "不得" in text and "停" in text


def test_ai_library_records_user_visibility_rule_as_current_scheduled_resume_guidance():
    text = read(AI_CURRENT)
    assert "Scheduled progress heartbeat" in text
    assert all(status in text for status in STATUS_SET)
    assert "沒有 active work" in text
    assert "shared lease" in text
    assert "正常工作" in text or "正常等待" in text


def test_pitfall_records_silent_active_work_failure_mode():
    text = read(PITFALL)
    assert "SILENT_ACTIVE_WORK_PITFALL" in text
    assert "卡" in text
    assert "靜默" in text
    assert "SCHEDULED_RESUME_PROGRESS_HEARTBEAT" in text
