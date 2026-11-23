"""#3415 native/Xorg stress: original marking + Tk ownership + original button E2E.

Selected by the ordinary focused CI after the real marking tests in the
same pytest Python interpreter. No GC controls, mocks of Tk source, or edits
to the original native tests; their own existing data-only test stubs remain.
"""
from __future__ import annotations

import test_issue1959_cadcraft_command_button_live_tk as native


def test_original_native_button_cases_after_marking_suite_same_python(
    monkeypatch, tmp_path,
):
    cases = (
        ("draw-worker", native.test_live_tk_command_button_runs_off_thread_and_preserves_original_editor, True),
        ("missing-cli", native.test_live_tk_missing_cli_fails_without_starting_draft_or_drawing, False),
        ("manual-return", native.test_live_tk_cadcraft_manual_position_return_uses_original_session, True),
        ("gui-launch-failure", native.test_live_tk_when_cadcraft_gui_cannot_launch_reports_error_without_losing_ticket, True),
        ("focus-retry", native.test_live_tk_gui_handoff_focuses_spawned_native_window_without_modal, True),
        ("live-unsaved-return", native.test_live_tk_cadcraft_tcp_return_without_user_save_reuses_original_session, True),
    )
    for label, original, needs_tmp in cases:
        folder = tmp_path / label
        folder.mkdir()
        with monkeypatch.context() as isolated:
            if needs_tmp:
                original(isolated, folder)
            else:
                original(isolated)
        print("WHD_3415_ORIGINAL_XORG_NATIVE_CASE_PASS", label, flush=True)
