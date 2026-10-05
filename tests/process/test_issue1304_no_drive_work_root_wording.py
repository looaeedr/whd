from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISPATCH = ROOT / ".agents/skills/engineering/派工/SKILL.md"
# Issue 1304: Drive is never a repository construction-root authority.


def test_dispatch_prohibits_drive_work_root_wording():
    text = DISPATCH.read_text(encoding="utf-8")
    assert "DRIVE_WORK_ROOT_WORDING_HARD_GATE_V1" in text
    assert "repository-content 施工根 = executor 自己的 repo workspace" in text
    assert "fresh baseline = GitHub production X" in text
    assert "Drive 不可見不得形成 startup/root blocker" in text
    assert "若沒有 native ExecutionRecord，判定為 execution-state / ingress 問題" in text


def test_dispatch_carries_safe_handoff_wording():
    text = DISPATCH.read_text(encoding="utf-8")
    assert "不得讀取 Drive 來解析施工 root" in text
    assert "不得把 /Google Drive/WHD 當 startup gate" in text
    assert "不得因 Drive 未掛載而停止" in text


def test_dispatch_explicitly_blacklists_legacy_drive_root_prompt():
    text = DISPATCH.read_text(encoding="utf-8")
    assert "讀取專案指定的 Google Drive 工作根目錄" in text
    assert "都不得再使用或生成以下語意" in text
