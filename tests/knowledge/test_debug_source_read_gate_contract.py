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
