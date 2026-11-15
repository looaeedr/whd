from __future__ import annotations

import json
from pathlib import Path

from tools.phase6_skill_preflight import REGISTRY, required_skills_for, required_references_for
from tools.skill_catalog import inventory


ROOT = Path(__file__).resolve().parents[2]


def _active_canonical_rows():
    return [row for row in inventory() if row.active and row.classification == "canonical"]


def _skill_name(path: str) -> str:
    return Path(path).parent.name


def test_every_active_canonical_skill_is_registered() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registered = {
        str(skill)
        for route in registry["routes"]
        for skill in route.get("required_skills", [])
    }
    active = {_skill_name(row.path) for row in _active_canonical_rows()}
    assert active - registered == set()


def test_every_active_canonical_skill_is_explicitly_routable() -> None:
    failures: list[str] = []
    for row in _active_canonical_rows():
        name = _skill_name(row.path)
        by_name = set(required_skills_for(task=name))
        by_file = set(required_skills_for(changed_files=[row.path]))
        if name not in by_name:
            failures.append(f"{name}: task-name route missing")
        if name not in by_file:
            failures.append(f"{name}: skill-file route missing")
    assert failures == []

def test_handoff_skill_supports_chinese_slash_alias() -> None:
    assert "handoff" in set(required_skills_for(task="/交接"))
    assert "handoff" in set(required_skills_for(task="交接"))


def test_release_packaging_route_is_not_triggered_by_unrelated_governance_edits() -> None:
    generic = (
        "AGENTS.md",
        ".agents/skills/engineering/派工/SKILL.md",
        ".agents/skills/productivity/MCP工具操作/SKILL.md",
    )
    for path in generic:
        selected = set(required_skills_for(
            task="修改治理規範與權限", changed_files=[path],
        ))
        assert "phase6-release-packaging" not in selected, path

    skill_edit = set(required_skills_for(
        changed_files=[".agents/skills/engineering/派工/SKILL.md"],
    ))
    assert "寫技能" in skill_edit

    by_name = set(required_skills_for(task="正式出包"))
    by_file = set(required_skills_for(
        changed_files=[".agents/skills/engineering/phase6-release-packaging/SKILL.md"],
    ))
    assert "phase6-release-packaging" in by_name
    assert "phase6-release-packaging" in by_file



def test_code_review_route_accepts_pr_review_intent_without_generic_overtrigger() -> None:
    for task in (
        "請審查 PR #3286 的程式碼",
        "協助做 code review",
        "Review PR #3286",
        "幫忙檢查程式碼差異",
    ):
        assert "code-review" in set(required_skills_for(task=task)), task

    for task in (
        "review project timeline",
        "整理產品 PR 說明",
        "審查設計報告",
        "review README 文案",
    ):
        assert "code-review" not in set(required_skills_for(task=task)), task


def test_triage_route_accepts_explicit_issue_classification_but_not_general_issues() -> None:
    for task in (
        "/triage #42",
        "請做工單分類",
        "將這張工單分級",
        "Issue triage #42",
    ):
        assert "triage" in set(required_skills_for(task=task)), task
    for task in (
        "triageable style guide",
        "列出 GitHub issues",
        "整理工單施工進度",
        "審查 PR #42 的程式碼",
    ):
        assert "triage" not in set(required_skills_for(task=task)), task


def test_merge_conflict_route_requires_real_merge_conflict_intent() -> None:
    for task in (
        "請解決合併衝突",
        "處理合併衝突 #42",
        "merge conflict on pull request",
        "解決 rebase 衝突",
    ):
        assert "resolving-merge-conflicts" in set(required_skills_for(task=task)), task
    for task in (
        "合併已通過測試的 PR",
        "解決規格衝突",
        "研究不同分支的差異",
        "review code style",
    ):
        assert "resolving-merge-conflicts" not in set(required_skills_for(task=task)), task


def test_prompt_healthcheck_aliases_route_to_existing_owner() -> None:
    for task in (
        "/提示詞健檢",
        "/提視詞健檢",
        "使用 WHD 提示詞健檢，先不要修改",
        "prompt audit the CURRENT Skills",
        "prompt healthcheck on AGENTS.md",
    ):
        selected = set(required_skills_for(task=task))
        assert {"寫技能", "writing-for-agents"} <= selected, task
        assert not {"推推", "派工", "phase6-release-packaging"} & selected, task
        refs = set(required_references_for(task=task))
        assert "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md" in refs
        assert "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md" in refs


def test_prompt_healthcheck_negated_intent_does_not_fire() -> None:
    for task in (
        "不要 /提示詞健檢",
        "不用 /提視詞健檢",
        "這次不提示詞健檢",
        "不准直接執行 /提示詞健檢",
        "don't prompt audit",
        "do not run prompt healthcheck",
    ):
        selected = set(required_skills_for(task=task))
        assert not {"寫技能", "writing-for-agents", "推推", "派工"} & selected, task
    selected = set(required_skills_for(task="不要 /提示詞健檢，改用 /debug"))
    assert {"diagnosing-bugs", "tdd"} <= selected
    assert "writing-for-agents" not in selected


def test_prompt_healthcheck_is_read_only_without_second_current_owner() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = [route for route in registry["routes"] if route["id"] == "skill-prompt-healthcheck"]
    assert len(routes) == 1
    assert routes[0]["file_globs"] == []
    assert routes[0]["required_skills"] == ["寫技能", "writing-for-agents"]
    owner = (ROOT / ".agents/skills/engineering/寫技能/SKILL.md").read_text(encoding="utf-8")
    method = (ROOT / ".agents/skills/productivity/writing-for-agents/SKILL.md").read_text(encoding="utf-8")
    assert "**只要求健檢**" in owner
    assert "**明確要求修正**" in owner
    assert "不建立另一份 CURRENT Skill" in owner
    assert "not** a second WHD Skill authoring" in method
