from pathlib import Path

EDITOR = Path("gui_modules/editors/hole_editor.py")
GUI = Path("gui.py")

editor = EDITOR.read_text(encoding="utf-8")
action_import = "from phase6_hole_editor_session import HoleEditorAction\n"
session_import = "from phase6_hole_editor_session import Phase6HoleEditorSession\n"
combined_import = "from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession\n"
if combined_import in editor:
    editor = editor.replace(combined_import, action_import + session_import, 1)
elif session_import not in editor:
    if editor.count(action_import) != 1:
        raise SystemExit(f"session import anchor mismatch: {editor.count(action_import)}")
    editor = editor.replace(action_import, action_import + session_import, 1)

factory = '''class HoleEditorSessionFactory:
    """Construct the existing editor session authority; owns no session state."""

    @staticmethod
    def create(context_key, features, *, max_undo_steps=50):
        return Phase6HoleEditorSession(
            context_key, features, max_undo_steps=max_undo_steps
        )


'''
anchor = "class HoleEditorLiveContext:\n"
if "class HoleEditorSessionFactory:" not in editor:
    if editor.count(anchor) != 1:
        raise SystemExit(f"factory anchor mismatch: {editor.count(anchor)}")
    editor = editor.replace(anchor, factory + anchor, 1)
EDITOR.write_text(editor, encoding="utf-8")

gui = GUI.read_text(encoding="utf-8")
import_anchor = "    HoleEditorLiveContext as _HoleEditorLiveContext,\n"
factory_import = "    HoleEditorSessionFactory as _HoleEditorSessionFactory,\n"
if factory_import not in gui:
    if gui.count(import_anchor) != 1:
        raise SystemExit(f"GUI factory import anchor mismatch: {gui.count(import_anchor)}")
    gui = gui.replace(import_anchor, import_anchor + factory_import, 1)

old_ctor = '        hole_session = Phase6HoleEditorSession("door", feature_list, max_undo_steps=50)\n'
new_ctor = '        hole_session = _HoleEditorSessionFactory.create("door", feature_list, max_undo_steps=50)\n'
if old_ctor in gui:
    gui = gui.replace(old_ctor, new_ctor, 1)
elif new_ctor not in gui:
    raise SystemExit("unified session constructor anchor missing")
GUI.write_text(gui, encoding="utf-8")
