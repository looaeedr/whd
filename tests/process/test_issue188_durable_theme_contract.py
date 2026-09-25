from pathlib import Path


UI_SKILL = Path(".agents/skills/engineering/UI設計與去AI味/SKILL.md")
ISSUE188_PITFALL = Path("個人AI檔案庫/踩坑庫/issue188_dark_theme_runtime_pitfall.md")


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_ui_skill_owns_shared_dark_theme_runtime_contract():
    text = _read(UI_SKILL)
    assert "ISSUE188_SHARED_DARK_THEME_RUNTIME" in text
    for marker in (
        "single shared WHD theme token/style provider",
        "不得複製第二套 raw palette truth",
        "tk.Menu",
        "normal / active / disabled",
        "ax.clear()",
        "render refresh",
        "#0d0d0f",
        "Corner Data / unfold",
        "#000000",
        "primary operator text",
        "semantic colors",
        "1.0 / 1.2 / 1.4",
        "persist=False",
        "config.ini",
    ):
        assert marker in text, f"missing #188 UI runtime marker: {marker}"


def test_issue188_pitfall_records_runtime_visual_failure_modes_without_geometry_authority():
    text = _read(ISSUE188_PITFALL)
    assert "ISSUE188_DARK_THEME_RUNTIME_PITFALL" in text
    for marker in (
        "shared theme",
        "tk.Menu",
        "ax.clear()",
        "Corner Data",
        "#000000",
        "text scale 1.0 / 1.2 / 1.4",
        "real Tk/Xvfb",
        "config.ini",
        "presentation-only",
        "不得成為 manufacturing / geometry / DXF authority",
    ):
        assert marker in text, f"missing issue188 pitfall marker: {marker}"
