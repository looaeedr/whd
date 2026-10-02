from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "Python測試實務" / "SKILL.md"
README = ROOT / ".agents" / "skills" / "engineering" / "README.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
AI_RULE = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD技能建立與修改規則.md"
RELEASE = ROOT / "release_required_artifacts.json"
TDD = ROOT / ".agents" / "skills" / "engineering" / "tdd" / "SKILL.md"
DIAG = ROOT / ".agents" / "skills" / "engineering" / "diagnosing-bugs" / "SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_python_testing_practices_has_chinese_canonical_identity():
    assert SKILL.is_file(), "第三批必須新增中文 canonical Skill：Python測試實務"
    text = _text(SKILL)
    assert re.search(r"(?m)^name:\s*Python測試實務\s*$", text)
    assert "# Python測試實務" in text
    assert "python-testing-patterns" in text


def test_skill_keeps_tdd_and_debugging_as_separate_authorities():
    text = _text(SKILL)
    for token in ("tdd", "diagnosing-bugs", "seam", "RED", "GREEN"):
        assert token in text
    assert "不取代" in text
    assert "pytest" in text
    # Existing authorities must remain present; this batch adds a mechanics layer, not replacements.
    assert TDD.is_file() and DIAG.is_file()


def test_skill_requires_test_isolation_and_repo_invariants():
    text = _text(SKILL)
    for token in ("tmp_path", "config.ini", "基準檔", "tracked", "isolation"):
        assert token in text
    assert "污染" in text
    assert "前後" in text and ("hash" in text.lower() or "SHA" in text)


def test_skill_keeps_validation_authority_one_way():
    text = _text(SKILL)
    for token in ("fixture", "expected", "counterexample", "tolerance", "Source of Truth"):
        assert token in text
    assert "不得回灌" in text or "不能回灌" in text
    assert "production" in text


def test_mock_parameterization_and_property_rules_preserve_real_seams():
    text = _text(SKILL)
    for token in (
        "mock",
        "monkeypatch",
        "parameterization",
        "property-based",
        "geometry",
        "DXF",
        "Save→Reload",
        "2D/3D",
    ):
        assert token in text
    assert "外部邊界" in text
    assert "mock 掉" in text or "mock掉" in text
    assert "invariant" in text


def test_skip_markers_and_acceptance_semantics_are_fail_closed():
    text = _text(SKILL)
    for token in ("skip", "xfail", "SKIP", "PASS", "focused GREEN", "final acceptance"):
        assert token in text
    assert "SKIP" in text and "不" in text


def test_registry_routes_python_pytest_work_to_chinese_skill():
    data = json.loads(_text(REGISTRY))
    route = next(route for route in data["routes"] if route.get("id") == "python-testing-practices")
    assert route["required_skills"] == ["Python測試實務"]
    assert ".agents/skills/engineering/Python測試實務/**" in route["file_globs"]
    keywords = " ".join(route["keywords"])
    for token in ("pytest", "fixture", "parameterization", "mock", "monkeypatch", "async", "property-based"):
        assert token in keywords


def test_third_batch_is_durable_in_readme_ai_rule_and_release_policy():
    readme = _text(README)
    ai_rule = _text(AI_RULE)
    release = json.loads(_text(RELEASE))

    assert "[Python測試實務](./Python測試實務/SKILL.md)" in readme
    for token in (
        "Python測試實務",
        "tmp_path",
        "fixture",
        "mock",
        "SKIP",
        "focused GREEN",
        "production",
    ):
        assert token in ai_rule

    required = set(release["mandatory_update_files"])
    assert ".agents/skills/engineering/Python測試實務/SKILL.md" in required
    assert "tests/test_python_testing_practices_skill_contract.py" in required
