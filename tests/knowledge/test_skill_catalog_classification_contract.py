from __future__ import annotations

import fnmatch
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents/skills"
CATALOG_PATH = SKILLS / "skill_catalog.json"
AI_DISCOVERY = ROOT / "個人AI檔案庫/第二層_專案與SOP/07_WHD技能發現與掃描深模組規則.md"
ENGINEERING_README = SKILLS / "engineering/README.md"
PRODUCTIVITY_README = SKILLS / "productivity/README.md"
MISC_README = SKILLS / "misc/README.md"
IN_PROGRESS_README = SKILLS / "in-progress/README.md"
DEPRECATED_README = SKILLS / "deprecated/README.md"
LEGACY_GRILL = SKILLS / "productivity/grill-me/SKILL.md"
CANONICAL_GRILL = SKILLS / "productivity/深度質詢/SKILL.md"
VALID_CLASSES = {"canonical", "reference", "upstream-beta", "tool-specific", "retired"}


def _load_catalog() -> dict:
    assert CATALOG_PATH.is_file(), "WHD needs a machine-readable Skill classification catalog"
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _classification_for(path: Path, catalog: dict) -> str | None:
    rel = path.relative_to(ROOT).as_posix()
    for rule in catalog["ordered_rules"]:
        if fnmatch.fnmatchcase(rel, rule["glob"]):
            return rule["classification"]
    return None


def test_catalog_defines_exact_supported_classifications() -> None:
    catalog = _load_catalog()
    assert set(catalog["classifications"]) == VALID_CLASSES
    assert catalog["active_classifications"] == ["canonical"]
    assert catalog["inventory_source"] == ".agents/skills/**/SKILL.md"
    assert "classification" in catalog["authority"].lower()


def test_every_skill_file_is_classified_but_presence_does_not_imply_active() -> None:
    catalog = _load_catalog()
    discovered = sorted(SKILLS.rglob("SKILL.md"))
    assert discovered
    unresolved = [p.relative_to(ROOT).as_posix() for p in discovered if _classification_for(p, catalog) is None]
    assert unresolved == []

    for path in discovered:
        rel = path.relative_to(ROOT).as_posix()
        classification = _classification_for(path, catalog)
        if "/in-progress/" in f"/{rel}":
            assert classification == "upstream-beta"
        if "/deprecated/" in f"/{rel}":
            assert classification == "retired"


def test_known_wdh_internal_skills_remain_canonical_without_readme_dependency() -> None:
    catalog = _load_catalog()
    for rel in (
        ".agents/skills/engineering/截角資料入口收斂/SKILL.md",
        ".agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md",
        ".agents/skills/engineering/派工/SKILL.md",
        ".agents/skills/productivity/深度質詢/SKILL.md",
        ".agents/skills/misc/git-remote-sync-fallback/SKILL.md",
    ):
        path = ROOT / rel
        assert path.is_file(), rel
        assert _classification_for(path, catalog) == "canonical", rel


def test_misc_defaults_tool_specific_but_whd_override_is_canonical() -> None:
    catalog = _load_catalog()
    assert _classification_for(SKILLS / "misc/git-guardrails-claude-code/SKILL.md", catalog) == "tool-specific"
    assert _classification_for(SKILLS / "misc/migrate-to-shoehorn/SKILL.md", catalog) == "tool-specific"
    assert _classification_for(SKILLS / "misc/git-remote-sync-fallback/SKILL.md", catalog) == "canonical"


def test_legacy_grill_me_is_retired_in_favor_of_canonical_deep_interview() -> None:
    catalog = _load_catalog()
    assert CANONICAL_GRILL.is_file()
    assert not LEGACY_GRILL.exists(), "legacy grill-me entry must not remain invokable"
    retired = {entry["identity"]: entry for entry in catalog["retired_aliases"]}
    assert retired["grill-me"]["replacement_identity"] == "深度質詢"
    assert retired["grill-me"]["replacement_path"] == ".agents/skills/productivity/深度質詢/SKILL.md"
    assert "./grill-me/SKILL.md" not in PRODUCTIVITY_README.read_text(encoding="utf-8")


def test_docs_distinguish_inventory_from_active_classification_authority() -> None:
    ai = AI_DISCOVERY.read_text(encoding="utf-8")
    engineering = ENGINEERING_README.read_text(encoding="utf-8")
    productivity = PRODUCTIVITY_README.read_text(encoding="utf-8")
    misc = MISC_README.read_text(encoding="utf-8")
    in_progress = IN_PROGRESS_README.read_text(encoding="utf-8")
    deprecated = DEPRECATED_README.read_text(encoding="utf-8")

    assert "skill_catalog.json" in ai
    assert "inventory" in ai.lower()
    assert "檔案存在" in ai
    assert "不等於" in ai
    assert "active canonical" in ai.lower()
    assert "filesystem `SKILL.md` tree is the existence authority" not in engineering
    assert "navigation" in engineering.lower()
    assert "navigation" in productivity.lower()
    assert "tool-specific" in misc
    assert "upstream-beta" in in_progress
    assert "retired" in deprecated.lower()


def test_catalog_marks_reference_skill_without_promoting_second_governance_system() -> None:
    catalog = _load_catalog()
    setup_skill = SKILLS / "engineering/setup-matt-pocock-skills/SKILL.md"
    assert setup_skill.is_file()
    assert _classification_for(setup_skill, catalog) == "reference"
