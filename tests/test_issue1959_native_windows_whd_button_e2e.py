"""#1959 true Windows native WHD Tk button -> CADCraft GUI -> live return.

Only runs explicitly after downloading the publisher-verified v0.8.0 native
binaries in hosted Windows CI. This is NOT R5-2600 operator UAT.
"""
from __future__ import annotations

import os
from pathlib import Path
import time

import ezdxf
import pytest

from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, Vec2,
)
from gui_modules.editors.cadcraft_control_bridge import (
    CadcraftControlClient, CadcraftControlError,
)
from gui_modules.editors import cadcraft_command_preview_bridge as bridge
from gui_modules.editors import cadcraft_preview_bridge as preview
from phase6_hole_editor_session import HoleEditorAction
from test_issue1959_cadcraft_command_button_live_tk import _pump, _tk_shell


@pytest.mark.parametrize("confirmed", [True, False], ids=["confirm", "cancel"])
def test_whd_real_tk_button_opens_real_native_cadcraft_and_returns_unsaved_hole(
    monkeypatch, confirmed,
):
    cli = Path(os.environ["CADCRAFT_CLI"]).resolve(strict=True)
    gui = Path(os.environ["CADCRAFT_GUI"]).resolve(strict=True)
    assert cli.name.lower() == "cadcraft-cli.exe"
    assert gui.name.lower() == "cadcraft.exe"
    root, editor, canvas, session, features, dialogs = _tk_shell(confirm=confirmed)
    original = CircleFeature(
        10, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(40, 40)
    )
    features.append(original)
    before = tuple(features)
    original_id = id(features)
    monkeypatch.setattr(bridge, "find_cadcraft_cli", lambda: str(cli))
    monkeypatch.setattr(preview, "find_cadcraft_gui", lambda **kw: str(gui))
    # Native focus management is verified by separate Windows tests; keep
    # this test exclusively on actual GUI launch/TCP/Session provenance.
    monkeypatch.setattr(bridge, "focus_started_cadcraft_window", lambda pid: True)
    process = None
    try:
        launch_button = editor._hole_header_cadcraft_draw
        return_button = editor._hole_header_cadcraft_return
        assert launch_button.cget("text") == "CADCraft 開孔編輯"
        assert str(return_button.cget("state")) == "disabled"
        launch_button.invoke()

        def launched():
            nonlocal process
            process = getattr(editor, "_hole_cadcraft_gui_process", None)
            return (process is not None
                    and callable(getattr(process, "poll", None))
                    and getattr(editor, "_hole_cadcraft_control_port", None) is not None)

        _pump(root, launched, timeout=60)
        assert process.poll() is None
        assert str(return_button.cget("state")) == "normal"
        port = editor._hole_cadcraft_control_port
        client = CadcraftControlClient(port, timeout=1)

        def opened():
            if process.poll() is not None:
                raise AssertionError("CADCRAFT_GUI_EXITED_BEFORE_WHD_OPEN")
            try:
                current = client.inspect()
            except CadcraftControlError:
                return False
            ticket = editor._hole_cadcraft_return_ticket
            return (current.path is not None
                    and Path(current.path).resolve() == ticket.output.resolve()
                    and len(current.entities) == 1)

        _pump(root, opened, timeout=45)
        ticket = editor._hole_cadcraft_return_ticket
        bytes_before = ticket.output.read_bytes()
        original_doc = ezdxf.readfile(ticket.output)
        source = list(original_doc.modelspace())
        assert len(source) == 1 and source[0].dxftype() == "CIRCLE"

        # Edit the *real* native CADCraft GUI document, with NO file Save.
        client.request("engine.execute", {
            "command": "circle",
            "params": {"center": [90.0, 95.0], "radius": 6.0},
        })
        assert len(client.inspect().entities) == 2
        assert ticket.output.read_bytes() == bytes_before

        return_button.invoke()
        _pump(root, lambda: any(m[0] == "ask" or m[0] == "error"
                                 for m in dialogs), timeout=45)
        errors = [str(item[1]) for item in dialogs if item[0] == "error"]
        assert not errors, "Real Tk live capture failed: " + " / ".join(errors)
        assert any(m[0] == "ask" for m in dialogs)
        assert id(features) == original_id
        assert not session.has_active_edit
        assert ticket.output.read_bytes() == bytes_before
        assert canvas.winfo_exists()
        if confirmed:
            assert len(features) == 2
            assert features[0] == original
            assert features[1].offset == Vec2(90, 95)
            assert str(return_button.cget("state")) == "disabled"
            session.execute(HoleEditorAction.undo())
            assert tuple(features) == before
        else:
            # The native CADCraft in-memory circle was valid, but WHD's
            # original confirmation dialog rejected it. No Feature survives.
            assert tuple(features) == before
            assert str(return_button.cget("state")) == "normal"
            assert editor._hole_cadcraft_return_ticket is ticket
            assert "已取消" in editor._hole_header_cadcraft_status.cget("text")
            assert not any(kind == "info" and "孔位已送回" in str(args)
                           for kind, args, _ in dialogs)
    finally:
        if process is None:
            process = getattr(editor, "_hole_cadcraft_gui_process", None)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=6)
            except Exception:
                process.kill()
                process.wait(timeout=6)
        root.destroy()
