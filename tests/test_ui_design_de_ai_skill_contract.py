from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "engineering" / "UI設計與去AI味" / "SKILL.md"
REGISTRY = ROOT / ".agents" / "skills" / "skill_registry.json"
README = ROOT / ".agents" / "skills" / "engineering" / "README.md"
AI08 = ROOT / "個人AI檔案庫" / "第二層_專案與SOP" / "08_WHD技能建立與修改規則.md"
RELEASE = ROOT / "release_required_artifacts.json"


def _text() -> str:
    assert SKILL.exists(), "R1: canonical UI設計與去AI味 Skill is missing"
    return SKILL.read_text(encoding="utf-8")


def _frontmatter_name(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    assert match, "R1: SKILL.md must start with YAML frontmatter"
    name = re.search(r"^name:\s*(.+?)\s*$", match.group(1), flags=re.M)
    assert name, "R1: frontmatter name is missing"
    return name.group(1).strip().strip('"\'')


def test_r1_canonical_identity_and_three_modes():
    text = _text()
    assert _frontmatter_name(text) == "UI設計與去AI味"
    assert "# UI設計與去AI味" in text
    for marker in ["Audit", "Rewrite", "New Design"]:
        assert marker in text, f"R1: missing mode {marker}"
    assert "Tkinter" in text and "ttk" in text
    assert "React" in text and "Tailwind" in text and "shadcn" in text
    assert ("不得" in text or "不能" in text) and ("硬相依" in text or "hard dependency" in text)


def test_r1_external_sources_are_input_not_canonical_authority():
    text = _text()
    assert "anthropics/skills@34040c9c568585f6929bedeaad110ad08f079624" in text
    assert "funboy322/avoid-ai-design@8337060636a8cf12e32e883eb367becd702aa526" in text
    assert "只作" in text and ("輸入" in text or "input" in text)
    assert "不建立第二套" in text and "canonical" in text


def test_r2_audit_is_read_only_and_rewrite_is_incremental():
    text = _text()
    assert "Audit" in text and "Rewrite" in text
    assert "不得改" in text or "不得寫" in text
    for unit in ["widget", "panel", "dialog", "toolbar", "sidebar", "workspace region"]:
        assert unit in text, f"R2: missing incremental rewrite unit {unit}"
    assert "全域" in text and ("Search/Replace" in text or "search/replace" in text or "取代" in text)
    assert "禁止" in text or "不得" in text


def test_r2_preserves_behavior_contract_and_domain_authority():
    text = _text()
    for marker in [
        "callback", "selection state", "project state", "Save→Reload", "2D/3D",
        "manufacturing", "geometry authority", "editable", "readonly", "keyboard",
        "accessibility", "scroll",
    ]:
        assert marker in text, f"R2: missing preserved behavior marker {marker}"
    assert "visual simplification" in text
    assert "semantic simplification" in text


def test_r2_requires_component_level_verify_loop():
    text = _text()
    for marker in ["讀目前元件", "功能 contract", "修改單一區域", "functional check", "layout regression"]:
        assert marker in text, f"R2: missing rewrite-loop marker {marker}"
    assert "才進下一" in text or "再進下一" in text


def test_r3_preserves_action_color_and_semantic_depth():
    text = _text()
    assert "Action Color" in text
    assert "Brand Color" in text or "品牌" in text
    assert "灰階" in text or "黑白灰" in text
    for surface in ["Modal", "Dropdown", "Toast"]:
        assert surface in text, f"R3: missing foreground surface {surface}"
    assert "elevation" in text
    assert "不是 AI 味" in text or "不是 AI味" in text or "不是一律禁止" in text


def test_r3_monospace_and_decoration_removal_have_layout_guards():
    text = _text()
    assert "monospace" in text
    for marker in ["width", "clipping", "換行"]:
        assert marker in text, f"R3: missing monospace/layout guard {marker}"
    for marker in ["gradient", "glow", "blur", "shadow"]:
        assert marker in text, f"R3: missing decoration marker {marker}"
    assert "1px" in text or "divider" in text or "border" in text
    assert "hierarchy" in text


def test_r3_text_scale_scroll_and_visual_capability_are_explicit():
    text = _text()
    for marker in ["小", "中", "大", "scroll"]:
        assert marker in text, f"R3: missing text-scale/scroll marker {marker}"
    assert "1.0" in text and "1.2" in text and "1.4" in text
    assert "inferred" in text
    assert "visual acceptance pending" in text
    assert "不得假裝" in text


def test_r4_registry_route_is_intent_scoped_and_readme_discovers_skill():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    route = next((r for r in data["routes"] if r.get("id") == "ui-design-de-ai"), None)
    assert route is not None, "R4: ui-design-de-ai registry route is missing"
    required_keywords = {
        "UI設計", "UI", "UX", "去AI味", "AI味", "AI slop", "不像AI", "介面設計",
        "介面重整", "視覺層級", "layout", "typography", "UI audit", "frontend design",
    }
    assert required_keywords.issubset(set(route.get("keywords", []))), "R4: route keywords incomplete"
    assert route.get("required_skills") == ["UI設計與去AI味"]
    assert "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md" in route.get("required_references", [])
    globs = route.get("file_globs", [])
    assert ".agents/skills/engineering/UI設計與去AI味/**" in globs
    assert not any(g == "gui.py" or g.endswith("/gui.py") or g == "**/gui.py" for g in globs), "R4: broad gui.py glob would over-trigger"
    readme = README.read_text(encoding="utf-8")
    assert "[UI設計與去AI味](./UI設計與去AI味/SKILL.md)" in readme, "R4: README canonical entry missing"


def test_r5_ai08_has_fifth_batch_durable_ui_rules():
    text = AI08.read_text(encoding="utf-8")
    assert "## 2026-09-11 第五批：UI設計與去AI味" in text, "R5: fifth-batch AI08 section missing"
    for marker in [
        "Tkinter", "ttk", "functionality", "全域", "逐元件", "Action Color",
        "monospace", "elevation", "1.0", "1.2", "1.4", "visual acceptance pending", "不得假裝",
    ]:
        assert marker in text, f"R5: durable UI rule missing {marker}"
    assert "frontend-design" in text and "avoid-ai-design" in text
    assert "只作" in text and ("input" in text or "輸入" in text)


def test_r6_release_manifest_requires_skill_and_contract():
    data = json.loads(RELEASE.read_text(encoding="utf-8"))
    mandatory = set(data.get("mandatory_update_files", []))
    assert ".agents/skills/engineering/UI設計與去AI味/SKILL.md" in mandatory, "R6: UI Skill missing from release manifest"
    assert "tests/test_ui_design_de_ai_skill_contract.py" in mandatory, "R6: UI contract missing from release manifest"


CHECKS = [
    test_r1_canonical_identity_and_three_modes,
    test_r1_external_sources_are_input_not_canonical_authority,
    test_r2_audit_is_read_only_and_rewrite_is_incremental,
    test_r2_preserves_behavior_contract_and_domain_authority,
    test_r2_requires_component_level_verify_loop,
    test_r3_preserves_action_color_and_semantic_depth,
    test_r3_monospace_and_decoration_removal_have_layout_guards,
    test_r3_text_scale_scroll_and_visual_capability_are_explicit,
    test_r4_registry_route_is_intent_scoped_and_readme_discovers_skill,
    test_r5_ai08_has_fifth_batch_durable_ui_rules,
    test_r6_release_manifest_requires_skill_and_contract,
]


if __name__ == "__main__":
    passed = 0
    failed = 0
    for check in CHECKS:
        try:
            check()
            print(f"[PASS] {check.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {check.__name__}: {exc}")
            failed += 1
    print(f"SUMMARY: {passed} passed / {failed} failed")
    raise SystemExit(1 if failed else 0)
