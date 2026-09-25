from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents" / "skills"
CJK = re.compile(r"[\u3400-\u9fff]")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_name(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    frontmatter = text[4:end]
    match = re.search(r"(?m)^name:\s*(.+?)\s*$", frontmatter)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def _chinese_skill_files() -> list[Path]:
    return sorted(
        path
        for path in SKILLS_ROOT.rglob("SKILL.md")
        if CJK.search(path.parent.name)
    )


def test_all_chinese_skill_folders_use_folder_name_as_frontmatter_name():
    files = _chinese_skill_files()
    assert files, "no Chinese skill folders discovered"
    mismatches = []
    for path in files:
        actual = _frontmatter_name(_text(path))
        expected = path.parent.name
        if actual != expected:
            mismatches.append(f"{path.relative_to(ROOT)}: expected name={expected!r}, got {actual!r}")
    assert not mismatches, "\n" + "\n".join(mismatches)


def test_current_audited_chinese_skill_set_is_present():
    discovered = {path.parent.name for path in _chinese_skill_files()}
    expected = {
        "執行開發任務",
        "寫成規格書",
        "寫技能",
        "拆解任務工單",
        "拷問邊建立文件",
        "掃描深模組",
        "派工",
        "程式碼庫設計",
        "領域建模",
        "驗證板件與DXF",
        "深度質詢",
    }
    assert expected <= discovered


def test_grill_with_docs_is_a_real_capability_adaptive_workflow():
    text = _text(SKILLS_ROOT / "engineering" / "拷問邊建立文件" / "SKILL.md")
    assert "深度質詢" in text
    assert "領域建模" in text
    assert "CONTEXT.md" in text
    assert "ADR" in text
    assert "能力" in text or "可用工具" in text
    assert "Call the Skill tool twice" not in text


def test_deep_questioning_does_not_require_a_fake_background_subagent():
    text = _text(SKILLS_ROOT / "productivity" / "深度質詢" / "SKILL.md")
    assert "沒有真正" in text and "Subagent" in text
    assert "inline" in text or "同一執行者" in text
    assert "不得" in text and ("等待" in text or "假裝" in text)


def test_design_it_twice_has_non_subagent_fallback():
    text = _text(SKILLS_ROOT / "engineering" / "程式碼庫設計" / "DESIGN-IT-TWICE.md")
    assert "Subagent" in text
    assert "沒有" in text
    assert "inline" in text or "依序" in text
    assert "不得假裝" in text


def test_deep_module_scan_uses_canonical_chinese_skill_references():
    text = _text(SKILLS_ROOT / "engineering" / "掃描深模組" / "SKILL.md")
    for rel in (
        ".agents/skills/engineering/程式碼庫設計/SKILL.md",
        ".agents/skills/productivity/深度質詢/SKILL.md",
        ".agents/skills/engineering/領域建模/SKILL.md",
    ):
        assert rel in text


def test_receiving_divider_validation_keeps_cross_parameters_as_manufacturing_authority():
    text = _text(SKILLS_ROOT / "engineering" / "驗證板件與DXF" / "SKILL.md")
    assert "CROSS（十字截角）＋參數" in text
    assert "Registry HIT" in text
    assert "shadow" in text.lower()
    assert "不得覆蓋" in text


def test_skill_readmes_do_not_link_to_nonexistent_legacy_chinese_skill_paths():
    engineering = _text(SKILLS_ROOT / "engineering" / "README.md")
    productivity = _text(SKILLS_ROOT / "productivity" / "README.md")
    stale_engineering = (
        "./grill-with-docs/SKILL.md",
        "./improve-codebase-architecture/SKILL.md",
        "./to-spec/SKILL.md",
        "./to-tickets/SKILL.md",
        "./implement/SKILL.md",
        "./domain-modeling/SKILL.md",
        "./codebase-design/SKILL.md",
    )
    for token in stale_engineering:
        assert token not in engineering
    assert "./grilling/SKILL.md" not in productivity
    for token in (
        "./拷問邊建立文件/SKILL.md",
        "./掃描深模組/SKILL.md",
        "./寫成規格書/SKILL.md",
        "./拆解任務工單/SKILL.md",
        "./執行開發任務/SKILL.md",
        "./領域建模/SKILL.md",
        "./程式碼庫設計/SKILL.md",
    ):
        assert token in engineering
    assert "./深度質詢/SKILL.md" in productivity


def test_ask_matt_routes_to_canonical_chinese_skill_names():
    text = _text(SKILLS_ROOT / "engineering" / "ask-matt" / "SKILL.md")
    for canonical in (
        "拷問邊建立文件",
        "寫成規格書",
        "拆解任務工單",
        "執行開發任務",
        "掃描深模組",
        "程式碼庫設計",
        "領域建模",
        "深度質詢",
    ):
        assert canonical in text
    for legacy in (
        "/grill-with-docs",
        "/to-spec",
        "/to-tickets",
        "/implement",
        "/improve-codebase-architecture",
        "/codebase-design",
        "/domain-modeling",
        "/grilling",
    ):
        assert legacy not in text
