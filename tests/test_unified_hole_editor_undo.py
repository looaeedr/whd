from pathlib import Path

from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession


def test_session_undo_history_is_capped_at_50_and_restores_last_snapshot():
    features = []
    session = Phase6HoleEditorSession("door", features, max_undo_steps=50)
    for i in range(60):
        session.execute(HoleEditorAction.insert(i))
        session.execute(HoleEditorAction.commit_active())
    assert session.snapshot().undo_depth == 50
    session.execute(HoleEditorAction.undo())
    assert features == list(range(59))
    session.execute(HoleEditorAction.undo())
    assert features == list(range(58))


def test_session_undo_history_copies_list_container():
    state = [1, 2]
    session = Phase6HoleEditorSession("door", state, max_undo_steps=50)
    session.execute(HoleEditorAction.insert(3))
    session.execute(HoleEditorAction.commit_active())
    state.append(4)
    session.execute(HoleEditorAction.undo())
    assert state == [1, 2]


def test_gui_has_undo_button_and_ctrl_z_binding_via_session_owner():
    src = (Path(__file__).resolve().parents[1] / "gui.py").read_text(encoding="utf-8")
    assert "↶ 回上一步" in src
    assert '"<Control-z>"' in src or "'<Control-z>'" in src
    assert 'Phase6HoleEditorSession("door", feature_list, max_undo_steps=50)' in src
    assert "EditorUndoHistory(max_steps=50)" not in src
