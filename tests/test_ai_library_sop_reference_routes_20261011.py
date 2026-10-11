"""AI Library REFERENCE SOPs must not masquerade as live WHD execution endpoints."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOP = ROOT / "個人AI檔案庫/第二層_專案與SOP"


def test_historical_cad_and_prompt_templates_do_not_claim_current_project_root():
    cad = (SOP / "05_CAD批次拆圖與特徵萃取規範.md").read_text(encoding="utf-8")
    prompts = (SOP / "03_常用Prompt指令庫.md").read_text(encoding="utf-8")
    assert "whd_doc_role: REFERENCE" in cad[:180]
    assert "歷史拆圖方案，不是目前 WHD 執行入口" in cad
    assert "歷史專案路徑" in cad
    assert "非現行工作根目錄" in cad
    assert "歷史方案／不可直接當作現行 API" in cad
    assert "whd_doc_role: REFERENCE" in prompts[:180]
    assert "main.run_pipeline" in prompts
    assert "歷史範例" in prompts
    assert "需先查證入口" in prompts
    assert "可直接複製使用" not in prompts


def test_skill_discovery_reference_heading_cannot_claim_own_current_authority():
    doc = (SOP / "07_WHD技能發現與掃描深模組規則.md").read_text(encoding="utf-8")
    assert "whd_doc_role: REFERENCE" in doc[:180]
    assert "REFERENCE 導覽" in doc
    assert "## CURRENT" not in doc
    assert "不是現行修改與寫入前置門檻" in doc
    assert "skill_catalog.json" in doc
