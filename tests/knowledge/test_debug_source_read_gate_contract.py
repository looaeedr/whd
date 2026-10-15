"""WHD /debug routing and read-before-mutation contract regression checks.

These checks guard the documented and routed protocol, not proof that a
particular agent has actually read an individual file in a future task.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.phase6_skill_preflight import required_skills_for


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"
AGENTS = ROOT / "AGENTS.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_slash_debug_explicitly_routes_canonical_diagnosis() -> None:
    registry = json.loads(_text(SKILLS / "skill_registry.json"))
    route = next(row for row in registry["routes"] if row["id"] == "explicit-debug-command")
    assert route["keywords"] == ["/debug"]
    assert set(route["required_skills"]) == {"diagnosing-bugs", "tdd"}
    for task in ("/debug", "/debug NFB 中隔 Z 軸碰撞", "請 /debug 受電箱 GUI"):
        assert {"diagnosing-bugs", "tdd"} <= set(required_skills_for(task=task))
    assert not (SKILLS / "engineering" / "debug" / "SKILL.md").exists()


def test_global_source_read_gate_is_fail_closed_before_product_edits() -> None:
    agents = _text(AGENTS)
    block = agents.split("## 所有產品修改前先讀程式與文檔硬閘門", 1)[1].split("\n## ", 1)[0]
    for required in (
        "SOURCE_READ_BEFORE_MUTATION_V1",
        "SOURCE_READ_EVIDENCE",
        "SOURCE_READ_PRECONDITION_FAILED",
        "實際內容",
        "CURRENT",
        "Z 基準",
        "禁止猜測後直接寫產品程式",
    ):
        assert required in block
    assert block.index("SOURCE_READ_EVIDENCE") < block.index("SOURCE_READ_PRECONDITION_FAILED")


def test_diagnose_reads_real_sources_before_red_green() -> None:
    diagnosis = _text(SKILLS / "engineering" / "diagnosing-bugs" / "SKILL.md")
    assert diagnosis.index("## Phase 0: SOURCE_READ_BEFORE_MUTATION_V1") < diagnosis.index("## Phase 1:")
    phase0 = diagnosis.split("## Phase 0:", 1)[1].split("## Redact", 1)[0]
    for required in (
        "actual implicated source modules",
        "real entrypoint",
        "SOURCE_READ_EVIDENCE",
        "CURRENT",
        "SOURCE_READ_PRECONDITION_FAILED",
        "do not patch product code",
    ):
        assert required in phase0
    assert "Phase 0 source/spec reading is mandatory" in diagnosis


def test_direct_execution_and_dispatch_inherit_same_precondition() -> None:
    for name in ("執行開發任務", "派工"):
        body = _text(SKILLS / "engineering" / name / "SKILL.md")
        assert "SOURCE_READ_BEFORE_MUTATION_V1" in body
        assert "SOURCE_READ_EVIDENCE" in body
        assert "SOURCE_READ_PRECONDITION_FAILED" in body


def test_feature_command_routes_single_canonical_skill_without_shadowing_debug() -> None:
    registry = json.loads(_text(SKILLS / "skill_registry.json"))
    route = next(row for row in registry["routes"] if row["id"] == "explicit-feature-command")
    assert route["keywords"] == ["/功能"]
    assert route["required_skills"] == ["新增功能"]
    for task in ("/功能 設計 受電箱第三層", "/功能 新增 受電箱第三層", "/功能 繼續 #1783"):
        assert "新增功能" in required_skills_for(task=task)
    for task in ("/debug 受電箱卡住", "請 /派工 修復 GUI"):
        assert "新增功能" not in required_skills_for(task=task)


def test_feature_skill_inherits_existing_gate_and_covers_full_function_chain() -> None:
    feature = _text(SKILLS / "engineering" / "新增功能" / "SKILL.md")
    assert "name: 新增功能" in feature
    for token in (
        "SOURCE_READ_EVIDENCE", "SOURCE_READ_PRECONDITION_FAILED",
        "CONFIRMED PRODUCT RULE", "FEATURE_ACCEPTANCE", "AFFECTED_SUBSYSTEM",
        "GITHUB_LOCALX_FIRST", "WINDOWS_UAT_PENDING", "VISUAL_ACCEPTANCE_PENDING",
        "Save → Reload", "N/A", "/推推", "不得治理直送 X", "不得修改程式", "不得猜測",
    ):
        assert token in feature
    assert "./新增功能/SKILL.md" in _text(SKILLS / "engineering" / "README.md")
    agents = _text(AGENTS)
    assert "FEATURE_FLOW_V1" in agents and "新增功能/SKILL.md" in agents


def test_old_skill_entrypoints_respect_localx_first_and_no_governance_direct_x() -> None:
    writing = _text(SKILLS / "engineering" / "寫技能" / "SKILL.md")
    publishing = _text(SKILLS / "engineering" / "推推" / "SKILL.md")
    design = _text(SKILLS / "engineering" / "UI設計與去AI味" / "SKILL.md")
    diagnosing = _text(SKILLS / "engineering" / "diagnosing-bugs" / "SKILL.md")
    reference = _text(ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD技能建立與修改規則.md")
    assert "先從最新 X 取得 baseline" not in writing
    assert "PR 合併 X。" not in writing
    assert "以正式 X 的 `AGENTS.md`" not in writing
    assert "純治理直送例外" not in publishing
    assert "不經 localX、不使用 /推推" not in publishing
    assert "先整合至**本機**" not in publishing
    assert "正式 X 的 `AGENTS.md`" not in design
    assert "Fresh-read official `X`" not in diagnosing
    assert "從最新 X 建立" not in reference
    for source in (writing, publishing, design, diagnosing, reference):
        assert "localX" in source
