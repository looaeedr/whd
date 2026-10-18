"""#1959: invoke actual Hole Editor Tk CADCraft command button.

The old preview and editor canvas stay intact; CLI execution is injected so
this exercises real Tk worker/poll/dialog wiring, not manufacturing or user UAT.
"""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import tkinter as tk

from ae_engine.sheetmetal_features import Vec2, feature_surface_from_rect
from gui_modules.editors.hole_editor_composition import _bind_editor_events
from gui_modules.editors.hole_editor_view import (
    HoleEditorCenterWorkspaceBuilder, HoleEditorWindowShellBuilder,
)
from phase6_hole_editor_session import Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import CadcraftCommandProofError


def _tk_shell():
    root = tk.Tk()
    root.geometry("1300x850+0+0")
    root.update_idletasks()
    host = SimpleNamespace(
        root=root, COLOR_BG="#202028", COLOR_PANEL="#303038",
        COLOR_TEXT="#ffffff", COLOR_TEXT_MUTED="#b0b0b0",
        COLOR_CANVAS_BG="#111118",
    )
    shell = HoleEditorWindowShellBuilder(host).build(
        "板件", part_key="door", door_indicator_state=None,
        indicator_component_context_provider=None, baseline_status_text=None,
    )
    editor, center = shell[0], shell[5]
    canvas = HoleEditorCenterWorkspaceBuilder(host).build(center=center)[4]
    surface = feature_surface_from_rect("1959-tk", Vec2(0, 0), Vec2(200, 200))
    features = []
    old = Phase6HoleEditorSession("1959-tk", features)
    msgs = []
    messages = SimpleNamespace(
        showinfo=lambda *args, **kwargs: msgs.append(("info", args, kwargs)),
        showerror=lambda *args, **kwargs: msgs.append(("error", args, kwargs)),
        showwarning=lambda *args, **kwargs: msgs.append(("warning", args, kwargs)),
        askyesno=lambda *args, **kwargs: (msgs.append(("ask", args, kwargs)), True)[1],
    )
    noop = lambda *args, **kwargs: None
    context = SimpleNamespace(
        feature_list=features, surface=surface, width=200., height=200.,
        baseline_scene=None,
    )
    s = SimpleNamespace(
        editor=editor, d=SimpleNamespace(messagebox=messages),
        hole_session=old, live_context=context, canvas=canvas,
        catalog_list=tk.Listbox(center), pipe_catalog_list=tk.Listbox(center),
        created_list=tk.Listbox(center),
        redraw=noop, refresh_created=noop, toggle_fullscreen=noop,
        undo_last_action=noop, on_escape=noop, cancel_all=noop,
        on_catalog_select=noop, on_catalog_double_click=noop,
        on_created_select=noop, toggle_created_process=noop,
        on_canvas_down=noop, on_canvas_drag=noop, on_canvas_up=noop,
        on_canvas_right=noop,
    )
    _bind_editor_events(s)
    return root, editor, canvas, old, features, msgs


def _pump(root, predicate, *, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("TK_BUTTON_WORKER_OR_POLL_TIMEOUT")


def test_live_tk_command_button_runs_off_thread_and_preserves_original_editor(
    monkeypatch, tmp_path,
):
    from gui_modules.editors import cadcraft_command_preview_bridge as bridge

    started = threading.Event()
    release = threading.Event()
    thread_ids = []
    calls = []
    root, editor, canvas, session, features, dialogs = _tk_shell()
    original_identity = id(features)
    try:
        instructions = (object(),)
        monkeypatch.setattr(
            bridge, "prepare_whd_cadcraft_commands",
            lambda **kw: (calls.append(kw), instructions)[1],
        )
        monkeypatch.setattr(bridge, "find_cadcraft_cli", lambda: "test-only-cli")

        def fake_draw(*, instructions, executable):
            thread_ids.append(threading.get_ident())
            assert executable == "test-only-cli"
            started.set()
            if not release.wait(15):
                raise RuntimeError("TEST_THREAD_NOT_RELEASED")
            return bridge.CadcraftCommandDrawingResult(
                output_dxf=tmp_path / "actual-output.dxf",
                preview_png=tmp_path / "actual-output.png",
                geometry_evidence={"status": "PASS"},
            )

        monkeypatch.setattr(bridge, "draw_whd_commands_with_cadcraft", fake_draw)
        old_preview = editor._hole_header_cadcraft
        button = editor._hole_header_cadcraft_draw
        assert button.winfo_exists() and old_preview.winfo_exists()
        assert old_preview.cget("text") == "CADCraft 試看"
        assert button.cget("text") == "CADCraft 指令繪圖試作"
        main_thread_id = threading.get_ident()

        button.invoke()
        _pump(root, started.is_set)
        assert str(button.cget("state")) == "disabled"
        assert thread_ids and thread_ids[0] != main_thread_id
        assert canvas.winfo_exists() and editor.winfo_exists()
        assert not dialogs
        assert len(calls) == 1
        assert calls[0]["surface"] is not None
        assert id(features) == original_identity and features == []
        assert not session.has_active_edit
        # Tk is responsive while CADCraft CLI worker is still blocked.
        root.update()
        assert canvas.winfo_exists()

        release.set()
        _pump(root, lambda: len(dialogs) > 0)
        assert dialogs[-1][0] == "info"
        assert "actual-output.dxf" in dialogs[-1][1][1]
        assert "不會修改 WHD 開孔或製造圖" in dialogs[-1][1][1]
        assert str(button.cget("state")) == "normal"
        assert old_preview.winfo_exists()
        assert features == [] and not session.has_active_edit
    finally:
        release.set()
        root.destroy()


def test_live_tk_missing_cli_fails_without_starting_draft_or_drawing(
    monkeypatch,
):
    from gui_modules.editors import cadcraft_command_preview_bridge as bridge
    root, editor, canvas, session, features, dialogs = _tk_shell()
    try:
        monkeypatch.setattr(
            bridge, "prepare_whd_cadcraft_commands",
            lambda **kw: (object(),),
        )

        def missing_cli():
            raise CadcraftCommandProofError("CADCRAFT_CLI_NOT_FOUND")

        monkeypatch.setattr(bridge, "find_cadcraft_cli", missing_cli)
        monkeypatch.setattr(
            bridge, "draw_whd_commands_with_cadcraft",
            lambda **kw: (_ for _ in ()).throw(
                AssertionError("MUST_NOT_START_CADCRAFT_WITHOUT_BINARY")
            ),
        )
        button = editor._hole_header_cadcraft_draw
        button.invoke()
        root.update()
        assert dialogs and dialogs[-1][0] == "error"
        assert "CADCRAFT_CLI_NOT_FOUND" in dialogs[-1][1][1]
        assert str(button.cget("state")) == "normal"
        assert features == [] and not session.has_active_edit
        assert canvas.winfo_exists() and editor._hole_header_cadcraft.winfo_exists()
    finally:
        root.destroy()


def test_live_tk_cadcraft_manual_position_return_uses_original_session(monkeypatch, tmp_path):
    """A real button invoke reviews a modified isolated DXF, not arbitrary CAD."""
    import ezdxf
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from gui_modules.editors import cadcraft_command_preview_bridge as bridge
    from phase6_hole_editor_session import HoleEditorAction

    root, editor, canvas, session, features, dialogs = _tk_shell()
    original = CircleFeature(10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40))
    features.append(original)
    target = tmp_path / "operator-exchange.dxf"
    image = tmp_path / "operator-preview.png"
    try:
        monkeypatch.setattr(bridge, "find_cadcraft_cli", lambda: "test-only-cli")
        # ezdxf.new allocates heavily. Build the fixture on the Tk thread:
        # cyclic GC of Tk widgets on the worker thread can abort Tcl on Win/Xvfb.
        doc = ezdxf.new("R2010", units=ezdxf.units.MM)
        doc.modelspace().add_circle((40, 40), 5)
        doc.saveas(target)
        image.write_bytes(b"not-a-real-png-test-only")
        def fake_draw(*, instructions, executable):
            assert instructions[0].points == ((40.0, 40.0),)
            assert instructions[0].radius == 5
            return bridge.CadcraftCommandDrawingResult(target, image, {"status": "PASS"})
        monkeypatch.setattr(bridge, "draw_whd_commands_with_cadcraft", fake_draw)
        draw_button = editor._hole_header_cadcraft_draw
        return_button = editor._hole_header_cadcraft_return
        assert str(return_button.cget("state")) == "disabled"
        draw_button.invoke()
        _pump(root, lambda: any(row[0] == "info" for row in dialogs))
        assert str(return_button.cget("state")) == "normal"
        doc = ezdxf.readfile(target)
        circle = list(doc.modelspace())[0]
        circle.dxf.center = (44, 37, 0)
        doc.saveas(target)
        return_button.invoke()
        assert any(row[0] == "ask" and "X +4.000" in row[1][1] for row in dialogs)
        assert features[0].offset == Vec2(44, 37)
        assert not session.has_active_edit
        assert str(return_button.cget("state")) == "disabled"
        assert canvas.winfo_exists()
        session.execute(HoleEditorAction.undo())
        assert features == [original]
    finally:
        root.destroy()
