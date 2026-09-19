from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / ".agents/skills/engineering/executable-continuity-controller/SKILL.md"
REMOTE = ROOT / ".agents/skills/engineering/monitoring-remote-qa/SKILL.md"
EXECUTION = ROOT / ".agents/skills/engineering/執行開發任務/SKILL.md"
AI_CURRENT = ROOT / "個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md"
PITFALL = ROOT / "個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def test_controller_owns_immediate_terminal_report_contract():
    text = read(CONTROLLER)
    assert "IMMEDIATE_TERMINAL_PROGRESS_REPORT" in text
    assert "evidence-backed" in text
    assert "立即回報" in text
    assert "回報後" in text and "繼續" in text
    assert "不能" in text or "不得" in text

def test_remote_qa_terminal_report_precedes_secondary_followup():
    text = read(REMOTE)
    assert "IMMEDIATE_TERMINAL_PROGRESS_REPORT_BRIDGE" in text
    assert "terminal" in text
    assert "立即回報" in text
    assert "cleanup" in text or "收尾" in text

def test_execution_skill_keeps_report_as_observation_not_stop():
    text = read(EXECUTION)
    assert "IMMEDIATE_TERMINAL_PROGRESS_REPORT_BRIDGE" in text
    assert "PASS" in text and "FAIL" in text and "COMPLETE" in text
    assert "回報後" in text and "繼續" in text

def test_ai_library_records_terminal_fast_report_rule():
    text = read(AI_CURRENT)
    assert "Immediate terminal progress report" in text
    assert "PASS / FAIL / COMPLETE" in text
    assert "立即" in text
    assert "secondary" in text or "額外" in text

def test_pitfall_records_terminal_evidence_hidden_by_extra_readback():
    text = read(PITFALL)
    assert "TERMINAL_EVIDENCE_DELAYED_REPORT_PITFALL" in text
    assert "卡" in text
    assert "立即回報" in text
