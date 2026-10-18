"""True Tk/Xvfb regression: CADCraft is opt-in, original Hole Editor survives.

This is GUI wiring acceptance, complementing the real CADCraft CLI DXF
roundtrip; it does not claim a Windows CADCraft desktop/UAT run.
"""
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk

from ae_engine.sheetmetal_features import Vec2, feature_surface_from_rect
from gui_modules.editors.hole_editor_composition import _bind_editor_events
from gui_modules.editors.hole_editor_view import (
    HoleEditorWindowShellBuilder, HoleEditorCenterWorkspaceBuilder,
)


def test_cadcraft_preview_is_real_header_action_and_keeps_existing_2d_canvas(monkeypatch):
    from gui_modules.editors import cadcraft_preview_bridge

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    host = SimpleNamespace(
        root=root,
        COLOR_BG="#202028", COLOR_PANEL="#303038",
        COLOR_TEXT="#ffffff", COLOR_TEXT_MUTED="#b0b0b0",
        COLOR_CANVAS_BG="#111118",
    )
    try:
        shell = HoleEditorWindowShellBuilder(host).build(
            "門板", part_key="door", door_indicator_state=None,
            indicator_component_context_provider=None, baseline_status_text=None,
        )
        editor, center = shell[0], shell[5]
        original = HoleEditorCenterWorkspaceBuilder(host).build(center=center)
        toolbar, rotation_buttons, fullscreen_button, undo_button, canvas = original[:5]

        assert len(rotation_buttons) == 4
        assert host.last_hole_editor_canvas is canvas
        assert canvas.winfo_exists()
        assert fullscreen_button.winfo_exists() and undo_button.winfo_exists()
        assert toolbar.winfo_exists()
        cadcraft_button = editor._hole_header_cadcraft
        assert cadcraft_button.winfo_exists()
        assert cadcraft_button.winfo_parent() != str(toolbar)
        assert cadcraft_button.cget("text") == "CADCraft 試看"

        features = []
        surface = feature_surface_from_rect(
            "test-panel", Vec2(0, 0), Vec2(100, 80)
        )
        live = SimpleNamespace(
            feature_list=features, surface=surface, width=100.0,
            height=80.0, baseline_scene=None,
        )
        calls, dialogs, drawing = [], [], []
        def preview(**kwargs):
            calls.append(kwargs)
            return Path("external-inspection-only.dxf")
        monkeypatch.setattr(cadcraft_preview_bridge,
                            "open_hole_editor_cadcraft_preview", preview)
        msg = SimpleNamespace(
            showinfo=lambda *a, **kw: dialogs.append(("info", a, kw)),
            showerror=lambda *a, **kw: dialogs.append(("error", a, kw)),
        )
        noop = lambda *args, **kwargs: None
        s = SimpleNamespace(
            editor=editor, d=SimpleNamespace(messagebox=msg),
            live_context=live, canvas=canvas,
            catalog_list=tk.Listbox(center),
            pipe_catalog_list=tk.Listbox(center),
            created_list=tk.Listbox(center),
            redraw=lambda: drawing.append("draw"),
            refresh_created=noop, toggle_fullscreen=noop, undo_last_action=noop,
            on_escape=noop, cancel_all=noop,
            on_catalog_select=noop, on_catalog_double_click=noop,
            on_created_select=noop, toggle_created_process=noop,
            on_canvas_down=noop, on_canvas_drag=noop,
            on_canvas_up=noop, on_canvas_right=noop,
        )

        # Real Tk binding cannot start a CAD process or mutate the draft.
        _bind_editor_events(s)
        assert not calls and not dialogs
        assert features == [] and drawing == []
        cadcraft_button.invoke()
        assert len(calls) == 1 and calls[0] == {
            "surface": surface, "features": features,
            "width": 100.0, "height": 80.0, "baseline_scene": None,
        }
        assert dialogs[-1][0] == "info"
        assert "不會回寫 WHD" in dialogs[-1][1][1]
        assert features == [] and canvas.winfo_exists()

        # Context switches are read on demand, not captured at construction.
        live.width = 120.0
        live.height = 95.0
        cadcraft_button.invoke()
        assert len(calls) == 2
        assert calls[-1]["width"] == 120.0
        assert calls[-1]["height"] == 95.0
        assert features == []

        # Missing/broken CADCraft does not close the original editor.
        def unavailable(**kwargs):
            raise ValueError("找不到 CADCraft")
        monkeypatch.setattr(cadcraft_preview_bridge,
                            "open_hole_editor_cadcraft_preview", unavailable)
        cadcraft_button.invoke()
        assert dialogs[-1][0] == "error"
        assert "找不到 CADCraft" in dialogs[-1][1][1]
        assert canvas.winfo_exists() and editor.winfo_exists()
    finally:
        root.destroy()
