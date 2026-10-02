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
    root = Path(__file__).resolve().parents[1]
    view = (root / "gui_modules/editors/hole_editor_view.py").read_text(encoding="utf-8")
    composition = (root / "gui_modules/editors/hole_editor_composition.py").read_text(encoding="utf-8")
    editor = (root / "gui_modules/editors/hole_editor.py").read_text(encoding="utf-8")
    joined = "\n".join((view, composition, editor))
    assert "↶ 回上一步" in view
    assert '"<Control-z>"' in composition or "'<Control-z>'" in composition
    assert "_HoleEditorSessionFactory.create(" in composition
    assert "max_undo_steps=50" in composition
    assert "EditorUndoHistory(max_steps=50)" not in joined
