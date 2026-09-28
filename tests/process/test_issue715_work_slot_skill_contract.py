from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "工作槽" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
README = ROOT / ".agents" / "skills" / "engineering" / "README.md"


def _skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_work_slot_skill_exists_with_canonical_chinese_identity():
    text = _skill()
    frontmatter = text.split("---", 2)[1]
    assert "name: 工作槽" in frontmatter
    assert "# 工作槽" in text
    assert "whd_contract: work-slot-routing" in frontmatter


def test_four_fixed_user_commands_map_to_four_fixed_slots():
    text = _skill()
    for command, slot in (
        ("/工作0", "worker.slot.0"),
        ("/工作1", "worker.slot.1"),
        ("/工作2", "worker.slot.2"),
        ("/工作3", "worker.slot.3"),
    ):
        assert command in text
        assert slot in text
    assert "WORK_SLOT_FIXED_IDENTITY_V2" in text
    assert "不得動態重新編號" in text


def test_bare_work_commands_are_query_only():
    text = _skill()
    for command in ("/工作0", "/工作1", "/工作2", "/工作3"):
        assert command in text
    assert "只查 projection，不取得 authority" in text
    assert "/工作槽" in text


def test_default_interactive_gate_uses_work0_without_new_authority():
    text = _skill()
    assert "DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1" in text
    assert "worker.slot.0" in text
    assert "真正 authority 仍必須來自 Flow v2" in text
    assert "SCHEDULER_LANE" in text


def test_runtime_observability_is_non_authoritative():
    text = _skill()
    canonical = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(encoding="utf-8")
    assert "WHD_RUNTIME_OBSERVABILITY_V1" in canonical
    assert "WAKE / PROGRESS / EXIT" in text
    assert "絕對不能反向授權施工" in text


def test_registry_routes_work0_through_work_slot_bridge():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = {route["id"]: route for route in registry["routes"]}
    route = routes["work-slot-routing"]
    assert "工作槽" in route["required_skills"]
    for keyword in ("/工作0", "/工作1", "/工作2", "/工作3", "/工作槽", "工作槽"):
        assert keyword in route["keywords"]
    assert ".agents/skills/engineering/工作槽/**" in route["file_globs"]


def test_engineering_readme_exposes_work0_as_default_entrypoint():
    text = README.read_text(encoding="utf-8")
    assert "[工作槽](./工作槽/SKILL.md)" in text
    assert "/工作0" in text
    assert "預設互動入口" in text
