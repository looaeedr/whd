"""#3415: real Tk native editor after owner, with no forced GC or vendor stub."""
from __future__ import annotations

from threading import Event
from unittest.mock import patch
from weakref import ref

from gui_modules.editors.hole_editor_composition import _HoleEditorAfterOwner
from gui_modules.editors import cadcraft_command_preview_bridge as cad
from test_issue1959_cadcraft_command_button_live_tk import _tk_shell, _pump


def test_finished_timer_drops_callback_and_own_reference_immediately():
    root, editor, *_ = _tk_shell()
    called = []
    try:
        owner = _HoleEditorAfterOwner(editor, lambda: called.append("done"))
        weak = ref(owner)
        owner.schedule(5)
        del owner
        _pump(root, lambda: bool(called))
        assert called == ["done"] and weak() is None
        assert not editor._hole_editor_after_owners
    finally:
        root.destroy()


def test_destroy_cancels_live_poll_and_releases_six_child_references():
    root, editor, canvas, session, features, dialogs = _tk_shell()
    started, release = Event(), Event()

    def draw_stub(*, instructions, executable):
        started.set()
        if not release.wait(15):
            raise RuntimeError("DIAGNOSTIC_WORKER_NOT_RELEASED")
        raise RuntimeError("DIAGNOSTIC_EXPECTED_FAILURE")

    with patch.object(cad, "find_cadcraft_cli", return_value="test-cli"), \
         patch.object(cad, "draw_whd_commands_with_cadcraft", side_effect=draw_stub):
        try:
            editor._hole_header_cadcraft_draw.invoke()
            _pump(root, started.is_set)
            owners = tuple(editor._hole_editor_after_owners)
            assert owners and any(task._token is not None for task in owners)
            root.destroy()
            assert not editor._hole_editor_after_owners
            assert all(task._closed and task._token is None and
                       task._callback is None and task._editor is None
                       for task in owners)
            for name in (
                "_hole_header_fullscreen", "_hole_header_cadcraft",
                "_hole_header_cadcraft_draw", "_hole_header_cadcraft_return",
                "_hole_header_cadcraft_status", "_hole_sidebar_scroll",
            ):
                assert name not in editor.__dict__
            assert not session.has_active_edit and not features
        finally:
            release.set()


def test_failed_draw_releases_poll_without_dropping_live_editor():
    root, editor, canvas, session, features, dialogs = _tk_shell()
    try:
        with patch.object(cad, "find_cadcraft_cli", return_value="test-cli"), \
             patch.object(cad, "draw_whd_commands_with_cadcraft",
                          side_effect=RuntimeError("DIAGNOSTIC_EXPECTED_FAILURE")):
            editor._hole_header_cadcraft_draw.invoke()
            _pump(root, lambda: bool(dialogs))
        assert any("DIAGNOSTIC_EXPECTED_FAILURE" in str(message) for message in dialogs)
        assert not editor._hole_editor_after_owners
        assert editor.winfo_exists() and canvas.winfo_exists()
        assert not session.has_active_edit and not features
    finally:
        root.destroy()
