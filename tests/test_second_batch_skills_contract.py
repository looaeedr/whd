from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parents[1]
MCP_SKILL = ROOT / ".agents" / "skills" / "productivity" / "MCP工具操作" / "SKILL.md"
WRITING_SKILL = ROOT / ".agents" / "skills" / "engineering" / "寫技能" / "SKILL.md"
PRODUCTIVITY_README = ROOT / ".agents" / "skills" / "productivity" / "README.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
AI_RULE = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD技能建立與修改規則.md"
RELEASE = ROOT / "release_required_artifacts.json"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_mcp_skill_has_chinese_canonical_identity():
    assert MCP_SKILL.is_file(), "第二批必須新增中文 canonical Skill：MCP工具操作"
    text = _text(MCP_SKILL)
    match = re.search(r"^name:\s*(.+?)\s*$", text, re.MULTILINE)
    assert match is not None
    assert MCP_SKILL.parent.name == "MCP工具操作"
    assert match.group(1).strip() == MCP_SKILL.parent.name
    assert "# MCP工具操作" in text


def test_mcp_skill_is_capability_adaptive_and_never_fakes_mcp_cli():
    text = _text(MCP_SKILL)
    for required in (
        "能力偵測",
        "原生 connector",
        "mcp-cli",
        "有就用，沒有就退化",
        "不得假裝",
        "沒有可用的 MCP",
    ):
        assert required in text
    assert "必須安裝 mcp-cli" not in text
    assert "一律使用 mcp-cli" not in text


def test_mcp_skill_preserves_discover_inspect_execute_order_and_schema_authority():
    text = _text(MCP_SKILL)
    stages = (
        "發現（Discover）",
        "探索（Explore）",
        "檢查 Schema（Inspect）",
        "執行（Execute）",
    )
    positions = [text.index(stage) for stage in stages]
    assert positions == sorted(positions)
    assert "先讀 schema" in text
    assert "不得猜" in text
    assert "server" in text
    assert "tool" in text
    assert "參數" in text


def test_mcp_skill_requires_real_results_and_preserves_cli_failure_semantics():
    text = _text(MCP_SKILL)
    for required in (
        "實際結果",
        "exit code",
        "`0`",
        "`1`",
        "`2`",
        "`3`",
        "不自動升格",
        "Source of Truth",
    ):
        assert required in text


def test_registry_routes_mcp_requests_to_chinese_skill():
    data = json.loads(_text(REGISTRY))
    route = next(route for route in data["routes"] if route.get("id") == "mcp-tool-operation")
    assert route["required_skills"] == ["MCP工具操作"]
    assert ".agents/skills/productivity/MCP工具操作/**" in route["file_globs"]
    keywords = {item.lower() for item in route["keywords"]}
    assert "mcp" in keywords
    assert "model context protocol" in keywords
    assert "mcp-cli" in keywords


def test_writing_skill_absorbs_template_metadata_without_creating_duplicate_authority():
    text = _text(WRITING_SKILL)
    for required in (
        "compatibility",
        "metadata",
        "allowed-tools",
        "templates/",
        "可編輯",
        "scaffold",
        "外部 Skill",
        "專案規則優先",
    ):
        assert required in text
    assert "allowed-tools" in text and "不得" in text
    assert "make-skill-template" in text
    assert not (ROOT / ".agents" / "skills" / "make-skill-template").exists()


def test_second_batch_is_durable_in_readme_ai_rule_and_release_policy():
    readme = _text(PRODUCTIVITY_README)
    ai_rule = _text(AI_RULE)
    release = json.loads(_text(RELEASE))
    assert "[MCP工具操作](./MCP工具操作/SKILL.md)" in readme
    assert "MCP工具操作" in ai_rule
    assert "make-skill-template" in ai_rule
    assert "不建立" in ai_rule or "不新增" in ai_rule
    mandatory = set(release["mandatory_update_files"])
    assert ".agents/skills/productivity/MCP工具操作/SKILL.md" in mandatory
    assert "tests/test_second_batch_skills_contract.py" in mandatory
