
"""Exact-source and routing regressions for Skills / AI-library governance."""
from pathlib import Path

from tools.phase6_skill_preflight import required_skills_for, required_references_for

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_delete_tracked_baseline_is_github_localx_not_release_x():
    text = read(".agents/skills/engineering/刪除/SKILL.md")
    section = text.split("## 4. Repository tracked path 的刪除", 1)[1].split("## 5.", 1)[0]
    assert "GitHub `localX` 最新 exact HEAD" in section
    assert "完整 commit SHA" in section and "blob SHA" in section
    assert "TARGETED_NOT_RUN" in section
    assert "以 fresh `cleanup/2d-3d-sync` baseline" not in section


def test_bridge_current_routes_from_localx_not_formal_x_agents():
    text = read("個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md")
    section = text.split("## Integration / future change contract", 1)[1].split("## Accepted lineage provenance", 1)[0]
    assert "GitHub `localX` 最新 exact HEAD 的 `AGENTS.md`" in section
    assert "tools/change_lane_gate.py" in section
    assert "施工分流依正式 X `AGENTS.md`" not in section
    assert "當次 `/推推`" in section


def test_writing_skill_baseline_can_be_verified_without_local_checkout():
    text = read(".agents/skills/engineering/寫技能/SKILL.md")
    section = text.split("## 4. 修改既有 Skill", 1)[1].split("## 5. RED", 1)[0]
    assert "GitHub `localX` 最新完整 commit SHA" in section
    assert "對應 blob SHA" in section
    assert "不得要求先取得本機 checkout" in section
    assert "TARGETED_NOT_RUN" in section


def test_python_source_and_routing_helper_follow_current_localx():
    skill = read(".agents/skills/engineering/Python測試實務/SKILL.md")
    helper = read("tools/phase6_skill_preflight.py")
    assert "GitHub `localX` 最新 exact HEAD" in skill
    assert "tools/quick_test.py" in skill
    assert "tools/change_test_profile.py::build_fast_feedback" in skill
    assert "WHD Product Regression" in skill
    assert "以 X `AGENTS.md`" not in helper
    assert "GitHub `localX` 同一 HEAD" in helper
    assert "不會授權讀寫、執行或發布" in helper


def test_reference_is_not_a_second_execution_authority():
    ref = read(".agents/skills/engineering/寫技能/references/preflight-keyword-boundary.md")
    library = read("個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md")
    assert "REFERENCE／非執行權威" in ref
    assert "不虛構本地結果" in ref
    assert "不得當今日執行入口" in library
    assert "不能當成今天可執行的測試入口" not in library


def test_skill_routes_do_not_capture_unrelated_source_only_work():
    for task in ("檢查 Bridge ownership 來源", "查詢 localX HEAD 分支資訊", "整理 GitHub 版本差異"):
        skills = set(required_skills_for(task=task))
        assert "刪除" not in skills, task
        assert "寫技能" not in skills, task
        assert "Python測試實務" not in skills, task


def test_skill_routes_still_trigger_on_explicit_intent():
    cases = (
        ("刪除已追蹤的測試檔", "刪除"),
        ("修改技能 SKILL.md", "寫技能"),
        ("pytest fixture isolation", "Python測試實務"),
    )
    for task, owner in cases:
        assert owner in required_skills_for(task=task), task
    assert "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md" in required_references_for(task="pytest fixture isolation")
