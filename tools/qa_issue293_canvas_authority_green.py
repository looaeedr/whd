from pathlib import Path

VIEW = Path("gui_modules/editors/hole_editor_view.py")
GUI = Path("gui.py")

view = VIEW.read_text(encoding="utf-8")
import_anchor = "from phase6_hole_editor_session import HoleEditorAction\n"
canvas_import = "from phase6_hole_editor_canvas_view import Phase6HoleEditorCanvasView\n"
if canvas_import not in view:
    if view.count(import_anchor) != 1:
        raise SystemExit(f"view canvas import anchor mismatch: {view.count(import_anchor)}")
    view = view.replace(import_anchor, import_anchor + canvas_import, 1)

factory = '''class HoleEditorCanvasViewFactory:
    """Construct the existing canvas view authority; owns no render state."""

    @staticmethod
    def create(canvas, **kwargs):
        return Phase6HoleEditorCanvasView(canvas, **kwargs)


'''
class_anchor = "class HoleEditorCatalogControls:\n"
if "class HoleEditorCanvasViewFactory:" not in view:
    if view.count(class_anchor) != 1:
        raise SystemExit(f"view factory anchor mismatch: {view.count(class_anchor)}")
    view = view.replace(class_anchor, factory + class_anchor, 1)
VIEW.write_text(view, encoding="utf-8")

gui = GUI.read_text(encoding="utf-8")
old_canvas_import = "from phase6_hole_editor_canvas_view import HoleEditorCanvasFrame, Phase6HoleEditorCanvasView\n"
new_canvas_import = "from phase6_hole_editor_canvas_view import HoleEditorCanvasFrame\n"
if old_canvas_import in gui:
    gui = gui.replace(old_canvas_import, new_canvas_import, 1)
elif new_canvas_import not in gui:
    raise SystemExit("root canvas import anchor missing")

view_import_anchor = "    HoleEditorCatalogControls as _HoleEditorCatalogControls,\n"
factory_import = "    HoleEditorCanvasViewFactory as _HoleEditorCanvasViewFactory,\n"
if factory_import not in gui:
    if gui.count(view_import_anchor) != 1:
        raise SystemExit(f"GUI canvas factory import anchor mismatch: {gui.count(view_import_anchor)}")
    gui = gui.replace(view_import_anchor, factory_import + view_import_anchor, 1)

old_ctor = "        canvas_view = Phase6HoleEditorCanvasView(\n"
new_ctor = "        canvas_view = _HoleEditorCanvasViewFactory.create(\n"
if old_ctor in gui:
    gui = gui.replace(old_ctor, new_ctor, 1)
elif new_ctor not in gui:
    raise SystemExit("unified canvas constructor anchor missing")
GUI.write_text(gui, encoding="utf-8")
