"""#1901: native Hole Editor Confirm All may not close before live target validation."""
from types import SimpleNamespace

import gui_modules.editors.hole_editor as editor


def test_inner_door_invalid_precommit_keeps_original_editor_open(monkeypatch):
    errors, events = [], []
    monkeypatch.setattr(editor.messagebox, "showerror",
                        lambda *args, **kwargs: errors.append(args))
    hole_session = SimpleNamespace(
        finish=lambda **kwargs: events.append(("finish", kwargs)),
    )
    window = SimpleNamespace(
        destroy=lambda: events.append(("destroy",)),
    )
    lifecycle = editor.HoleEditorModalLifecycle(
        hole_session=hole_session,
        has_selected_feature=lambda: False,
        position_authority=[None],
        commit_active_edit=lambda **kwargs: None,
        sync_all=lambda: events.append(("sync",)),
        validate_current_indicator_fit=lambda **kwargs: True,
        door_indicator_state=None,
        collect_indicator_state=lambda: None,
        door_indicator_commit=None,
        editor_closed=[False],
        editor=window,
        on_close=None,
        insert_mode=[False],
        set_insert_mode=lambda _on: None,
        cancel_active_edit=lambda: None,
        before_commit=lambda: (_ for _ in ()).throw(
            ValueError("原始 DXF 已變更，不能提交")
        ),
    )
    lifecycle.confirm_all()
    assert errors and "原始 DXF" in errors[0][1]
    assert events == []
    assert lifecycle.editor_closed[0] is False


def test_inner_door_success_commits_once_then_closes_original_editor():
    events = []
    window = SimpleNamespace(destroy=lambda: events.append("destroy"))
    lifecycle = editor.HoleEditorModalLifecycle(
        hole_session=SimpleNamespace(
            finish=lambda **kwargs: events.append(("finish", kwargs["commit"])),
        ),
        has_selected_feature=lambda: False,
        position_authority=[None],
        commit_active_edit=lambda **kwargs: None,
        sync_all=lambda: events.append("sync"),
        validate_current_indicator_fit=lambda **kwargs: True,
        door_indicator_state=None,
        collect_indicator_state=lambda: None,
        door_indicator_commit=None,
        editor_closed=[False],
        editor=window,
        on_close=None,
        insert_mode=[False],
        set_insert_mode=lambda _on: None,
        cancel_active_edit=lambda: None,
        before_commit=lambda: events.append("write-live-or-candidate"),
    )
    lifecycle.confirm_all()
    assert events == ["write-live-or-candidate", ("finish", True), "sync", "destroy"]
    assert lifecycle.editor_closed[0] is True
