from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"toggle_fullscreen"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


class _FakeTk:
    class TclError(Exception):
        pass


def _fullscreen_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorFullscreenActions"), None)
    assert node is not None, "T5 RED: HoleEditorFullscreenActions is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"tk": _FakeTk}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorFullscreenActions"]


def test_fullscreen_callback_moves_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted fullscreen callback remains: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorFullscreenActions"), None)
    assert cls is not None, "T5 RED: HoleEditorFullscreenActions is missing"
    assert _span(cls) <= 80
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "toggle_fullscreen" in methods
    assert _span(methods["toggle_fullscreen"]) <= 40


def test_fullscreen_enter_exit_preserves_geometry_button_and_idle_redraw():
    cls = _fullscreen_class()
    calls: list[object] = []
    state = [False]
    restore = [None]
    redraw = object()

    class Editor:
        def __init__(self):
            self.native = False
            self.current_geometry = "800x600+10+20"
        def geometry(self, value=None):
            if value is None:
                calls.append(("geometry-get", self.current_geometry))
                return self.current_geometry
            self.current_geometry = value
            calls.append(("geometry-set", value))
        def attributes(self, key, value=None):
            if value is None:
                calls.append(("attributes-get", key, self.native))
                return self.native
            self.native = bool(value)
            calls.append(("attributes-set", key, bool(value)))
        def update_idletasks(self):
            calls.append("update-idle")
        def winfo_screenwidth(self):
            return 1920
        def winfo_screenheight(self):
            return 1080
        def after_idle(self, fn):
            calls.append(("after-idle", fn))

    class Button:
        def configure(self, **kwargs):
            calls.append(("button", kwargs))

    editor = Editor()
    actions = cls(
        editor=editor,
        fullscreen_button=Button(),
        fullscreen_state=state,
        restore_geometry=restore,
        redraw_provider=lambda: redraw,
    )

    assert actions.toggle_fullscreen() == "break"
    assert state == [True]
    assert restore == ["800x600+10+20"]
    assert ("button", {"text": "還原視窗"}) in calls
    assert ("after-idle", redraw) in calls
    assert not any(item == ("geometry-set", "1920x1080+0+0") for item in calls)

    calls.clear()
    assert actions.toggle_fullscreen() == "break"
    assert state == [False]
    assert editor.current_geometry == "800x600+10+20"
    assert ("attributes-set", "-fullscreen", False) in calls
    assert ("geometry-set", "800x600+10+20") in calls
    assert ("button", {"text": "全螢幕"}) in calls
    assert ("after-idle", redraw) in calls


def test_fullscreen_falls_back_to_screen_geometry_when_native_mode_is_unavailable():
    cls = _fullscreen_class()
    calls: list[object] = []

    class Editor:
        def geometry(self, value=None):
            if value is None:
                return "640x480+5+5"
            calls.append(("geometry-set", value))
        def attributes(self, key, value=None):
            if value is None:
                return False
            calls.append(("attributes-set", key, bool(value)))
        def update_idletasks(self):
            calls.append("update-idle")
        def winfo_screenwidth(self):
            return 2560
        def winfo_screenheight(self):
            return 1440
        def after_idle(self, fn):
            calls.append(("after-idle", fn))

    class Button:
        def configure(self, **kwargs):
            calls.append(("button", kwargs))

    actions = cls(
        editor=Editor(),
        fullscreen_button=Button(),
        fullscreen_state=[False],
        restore_geometry=[None],
        redraw_provider=lambda: None,
    )
    assert actions.toggle_fullscreen() == "break"
    assert ("geometry-set", "2560x1440+0+0") in calls
    assert ("button", {"text": "還原視窗"}) in calls
