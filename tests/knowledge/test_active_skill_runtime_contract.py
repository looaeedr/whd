from __future__ import annotations

import json
from pathlib import Path

from tools.skill_catalog import inventory


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents/skills"
CATALOG = json.loads((SKILLS / "skill_catalog.json").read_text(encoding="utf-8"))

TARGETS = {
    "research": SKILLS / "engineering/research/SKILL.md",
    "code-review": SKILLS / "engineering/code-review/SKILL.md",
    "wayfinder": SKILLS / "engineering/wayfinder/SKILL.md",
    "triage": SKILLS / "engineering/triage/SKILL.md",
    "wizard": SKILLS / "engineering/wizard/SKILL.md",
    "tdd": SKILLS / "engineering/tdd/SKILL.md",
    "diagnosing-bugs": SKILLS / "engineering/diagnosing-bugs/SKILL.md",
    "handoff": SKILLS / "productivity/handoff/SKILL.md",
    "ask-matt": SKILLS / "engineering/ask-matt/SKILL.md",
}

FORBIDDEN_ACTIVE_PHRASES = (
    'Spin up a **background agent**',
    'Both axes run as **parallel sub-agents**',
    'Spawn both sub-agents in parallel',
    '/setup-matt-pocock-skills',
    'Call the Skill tool twice, for "grilling" and "domain-modeling"',
    'Resolved by a subagent that calls the Skill tool with "research"',
    'spin up a subagent that calls the Skill tool with "research"',
    'Call the Skill tool with "codebase-design"',
    'scripts/hitl-loop.template.sh',
    '[template.sh](template.sh)',
    'naming which skills the next agent should call the Skill tool for',
    '實體 `.agents/skills/**/SKILL.md` 是存在性 authority',
)


def _active_skill_texts() -> dict[str, str]:
    active = {row.path for row in inventory() if row.active}
    return {
        rel: (ROOT / rel).read_text(encoding="utf-8")
        for rel in sorted(active)
    }


def test_t6_targets_are_active_canonical_and_not_retired_reference_or_beta() -> None:
    active = {row.path: row.classification for row in inventory() if row.active}
    for path in TARGETS.values():
        rel = path.relative_to(ROOT).as_posix()
        assert active.get(rel) == "canonical", rel


def test_active_canonical_skills_have_no_known_broken_runtime_instructions() -> None:
    offenders: list[str] = []
    for rel, text in _active_skill_texts().items():
        for phrase in FORBIDDEN_ACTIVE_PHRASES:
            if phrase in text:
                offenders.append(f"{rel}: {phrase}")
    assert offenders == []


def test_repaired_skills_declare_capability_aware_inline_fallback() -> None:
    for name in ("research", "code-review", "wayfinder", "triage", "wizard", "diagnosing-bugs", "handoff"):
        text = TARGETS[name].read_text(encoding="utf-8")
        assert "RUNTIME_CAPABILITY_FALLBACK" in text, name
        assert "inline" in text.lower() or "同一執行者" in text, name


def test_canonical_skill_identities_replace_legacy_invocation_names() -> None:
    wayfinder = TARGETS["wayfinder"].read_text(encoding="utf-8")
    triage = TARGETS["triage"].read_text(encoding="utf-8")
    tdd = TARGETS["tdd"].read_text(encoding="utf-8")
    assert "深度質詢" in wayfinder and "領域建模" in wayfinder
    assert "深度質詢" in triage and "領域建模" in triage
    assert "程式碼庫設計" in tdd


def test_known_missing_support_files_are_not_required_by_active_skills() -> None:
    assert not (ROOT / "docs/agents/issue-tracker.md").exists()
    assert not (SKILLS / "engineering/wizard/template.sh").exists()
    assert not (ROOT / "scripts/hitl-loop.template.sh").exists()
    active_text = "\n".join(_active_skill_texts().values())
    for stale in (
        "docs/agents/issue-tracker.md",
        "wizard/template.sh",
        "scripts/hitl-loop.template.sh",
    ):
        assert stale not in active_text


def test_ask_matt_uses_catalog_for_active_status_not_filesystem_presence() -> None:
    text = TARGETS["ask-matt"].read_text(encoding="utf-8")
    assert "skill_catalog.json" in text
    assert "inventory" in text.lower()
    assert "classification" in text.lower()
    assert "Only `canonical`" in text or "只有 `canonical`" in text


def test_ai_skill_governance_has_active_runtime_capability_contract() -> None:
    text = (ROOT / "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md").read_text(encoding="utf-8")
    assert "Active Skill runtime capability contract" in text
    for phrase in (
        "inline fallback",
        "supporting file",
        "canonical identity",
        "skill_catalog.json",
    ):
        assert phrase in text
