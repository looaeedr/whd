import os
import tkinter as tk

import pytest

import gui


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="Issue186 requires real Tk/Xvfb"
)


def _open_designer():
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.BoxCalculatorGUI(root)
    designer = app.open_original_fold_designer()
    root.update_idletasks()
    root.update()
    return root, app, designer


def _close(root):
    try:
        root.destroy()
    except Exception:
        pass


def test_issue186_red_sheetmetal_tree_is_visible_in_initial_left_viewport():
    """The real operator navigator must be on-screen, not merely constructed."""
    root, _app, designer = _open_designer()
    try:
        canvas = designer.left_scroll_canvas
        tree = designer.structure_tree
        host = designer.structure_tree_host

        root.update_idletasks()
        root.update()

        assert canvas.winfo_ismapped(), "left scroll viewport itself must be mapped"
        assert tree.winfo_ismapped(), "sheet-metal Structure Tree must be mapped"
        assert tree.exists("mode:assembly"), "assembly row must exist in the real navigator"
        assert tree.exists("mode:corner_data"), "Corner Data row must exist in the real navigator"

        content_top = float(canvas.canvasy(0))
        content_bottom = content_top + float(canvas.winfo_height())
        tree_top = float(host.winfo_y() + tree.winfo_y())
        tree_bottom = tree_top + float(tree.winfo_height())
        overlap = max(0.0, min(content_bottom, tree_bottom) - max(content_top, tree_top))

        print(
            "ISSUE186_SELECTOR_GEOMETRY",
            f"canvas_h={canvas.winfo_height()}",
            f"yview={canvas.yview()}",
            f"tree_y={tree_top:.1f}",
            f"tree_h={tree.winfo_height()}",
            f"visible_overlap={overlap:.1f}",
        )

        # A critical selector that is mapped but initially clipped below the
        # viewport is still missing from the operator's screen. Require a
        # meaningful visible portion without the user first guessing to scroll.
        assert overlap >= min(120.0, float(tree.winfo_height())), (
            "sheet-metal/part selector is constructed but not visibly present "
            "in the initial left workspace viewport"
        )
    finally:
        _close(root)
