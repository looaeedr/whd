from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PROPERTY = ROOT / ".agents/skills/engineering/性質導向測試/SKILL.md"
DIMENSION = ROOT / ".agents/skills/engineering/尺寸語意分析/SKILL.md"
README = ROOT / ".agents/skills/engineering/README.md"
REGISTRY = ROOT / ".agents/skills/skill_registry.json"
AI_RULE = ROOT / "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md"
RELEASE = ROOT / "release_required_artifacts.json"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_fourth_batch_has_two_chinese_canonical_skills():
    assert PROPERTY.is_file(), "第四批必須新增中文 canonical Skill：性質導向測試"
    assert DIMENSION.is_file(), "第四批必須新增中文 canonical Skill：尺寸語意分析"
    assert "name: 性質導向測試" in _text(PROPERTY)
    assert "# 性質導向測試" in _text(PROPERTY)
    assert "name: 尺寸語意分析" in _text(DIMENSION)
    assert "# 尺寸語意分析" in _text(DIMENSION)


def test_property_skill_is_property_design_not_pytest_or_tdd_replacement():
    text = _text(PROPERTY)
    for marker in ["Python測試實務", "tdd", "不取代", "roundtrip", "idempotence", "oracle", "invariant"]:
        assert marker in text
    assert "strongest" in text.lower() or "最強" in text


def test_property_skill_rejects_tautology_and_vacuity_and_designs_generators():
    text = _text(PROPERTY)
    for marker in ["tautology", "vacuity", "assume", "strategy", "@example", "counterexample"]:
        assert marker in text
    assert "constraint" in text.lower() or "約束" in text


def test_property_failure_must_be_classified_against_authority():
    text = _text(PROPERTY)
    for marker in ["property 寫錯", "spec", "code bug", "ambiguous", "authority"]:
        assert marker.lower() in text.lower()
    for marker in ["不能回灌 production", "不能建立新的 Source of Truth"]:
        assert marker in text


def test_property_library_dependency_is_capability_not_assumed():
    text = _text(PROPERTY)
    assert "Hypothesis" in text
    assert "dependency" in text.lower() or "相依" in text
    assert "使用者" in text
    assert "不得假裝" in text


def test_dimension_skill_defines_whd_semantic_dimension_vocabulary():
    text = _text(DIMENSION)
    for marker in [
        "material_length",
        "formed_outside_length",
        "FW_formed",
        "sheet_thickness",
        "flat_relief_length",
        "collision_envelope",
        "datum_offset",
    ]:
        assert marker in text
    for marker in ["料尺寸", "包外", "flat", "formed", "FW", "T"]:
        assert marker in text


def test_dimension_skill_says_same_mm_can_still_be_semantically_incompatible():
    text = _text(DIMENSION)
    assert "mm" in text
    assert "相同" in text
    assert "語意" in text
    assert "conversion" in text.lower() or "轉換" in text
    assert "authority" in text.lower()


def test_dimension_analysis_is_validation_only_not_formula_authority():
    text = _text(DIMENSION)
    for marker in ["只能", "分析", "驗證", "不能回灌 production", "offset", "formula"]:
        assert marker.lower() in text.lower()
    assert "Source of Truth" in text


def test_dimension_skill_is_capability_adaptive_not_fake_full_auto_subagents():
    text = _text(DIMENSION)
    for marker in ["capability", "subagent", "同一執行者", "不得假裝"]:
        assert marker.lower() in text.lower()
    assert "full-auto" in text
    assert "不" in text


def test_registry_routes_property_and_dimension_work_to_chinese_skills():
    data = json.loads(_text(REGISTRY))
    by_id = {route.get("id"): route for route in data["routes"]}

    prop = by_id["property-invariant-testing"]
    assert "性質導向測試" in prop["required_skills"]
    assert any("property" in keyword.lower() or "性質" in keyword for keyword in prop["keywords"])

    dim = by_id["dimension-semantics-analysis"]
    assert "尺寸語意分析" in dim["required_skills"]
    assert any("尺寸語意" in keyword or "dimensional analysis" in keyword.lower() for keyword in dim["keywords"])


def test_fourth_batch_is_durable_in_readme_ai_and_release_policy():
    readme = _text(README)
    ai_rule = _text(AI_RULE)
    release = json.loads(_text(RELEASE))
    required = set(release["mandatory_update_files"])

    assert "[性質導向測試](./性質導向測試/SKILL.md)" in readme
    assert "[尺寸語意分析](./尺寸語意分析/SKILL.md)" in readme
    assert "第四批" in ai_rule
    assert "性質導向測試" in ai_rule
    assert "尺寸語意分析" in ai_rule
    assert "不能回灌 production" in ai_rule

    assert ".agents/skills/engineering/性質導向測試/SKILL.md" in required
    assert ".agents/skills/engineering/尺寸語意分析/SKILL.md" in required
    assert "tests/test_fourth_batch_skills_contract.py" in required
