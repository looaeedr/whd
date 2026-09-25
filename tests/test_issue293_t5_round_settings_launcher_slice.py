from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"_open_round_settings"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _launcher_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorRoundSettingsLauncher"), None)
    assert node is not None, "T5 RED: HoleEditorRoundSettingsLauncher is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorRoundSettingsLauncher"]


def test_round_settings_launcher_moves_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted round-settings callback remains: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorRoundSettingsLauncher"), None)
    assert cls is not None, "T5 RED: HoleEditorRoundSettingsLauncher is missing"
    assert _span(cls) <= 70
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "open" in methods
    assert _span(methods["open"]) <= 30


def test_launcher_uses_live_editor_context_each_open_and_delegates_modal_authority():
    cls = _launcher_class()
    calls = []
    current = [{"feature_list": ["door"], "surface": "door-surface", "width": 100.0, "height": 80.0}]
    sentinels = {
        "editor": object(), "hole_session": object(), "round_window": object(),
        "position_authority": object(), "refresh_created": object(),
        "refresh_reference_fields": object(), "redraw": object(), "sync_all": object(),
    }
    theme = {"bg": "b", "panel": "p", "text": "t", "input_bg": "i", "muted": "m"}

    def open_impl(**kwargs):
        calls.append(kwargs)
        return "opened"

    launcher = cls(
        editor=sentinels["editor"],
        theme=theme,
        hole_session=sentinels["hole_session"],
        context_provider=lambda: current[0],
        round_window=sentinels["round_window"],
        position_authority=sentinels["position_authority"],
        refresh_created=sentinels["refresh_created"],
        refresh_reference_fields=sentinels["refresh_reference_fields"],
        redraw=sentinels["redraw"],
        sync_all=sentinels["sync_all"],
        open_round_hole_settings=open_impl,
    )

    assert launcher.open() == "opened"
    assert calls[-1]["feature_list"] == ["door"]
    assert calls[-1]["surface"] == "door-surface"
    assert calls[-1]["width"] == 100.0 and calls[-1]["height"] == 80.0
    assert calls[-1]["theme"] is theme
    for key, value in sentinels.items():
        assert calls[-1][key] is value

    current[0] = {"feature_list": ["indicator"], "surface": "indicator-surface", "width": 44.0, "height": 33.0}
    assert launcher.open() == "opened"
    assert calls[-1]["feature_list"] == ["indicator"]
    assert calls[-1]["surface"] == "indicator-surface"
    assert calls[-1]["width"] == 44.0 and calls[-1]["height"] == 33.0
