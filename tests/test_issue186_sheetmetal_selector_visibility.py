import os
import tkinter as tk

import pytest

import gui


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="Issue186 requires real Tk/Xvfb"
)


def _open_designer():
    """Open the exact production direct-3D application path."""
    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    root.update_idletasks()
    root.update()
    return root, app, designer


def _pump(root, cycles=3):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _close(root):
    try:
        root.destroy()
    except Exception:
        pass


def _tree_visible_overlap(designer):
    canvas = designer.left_scroll_canvas
    tree = designer.structure_tree
    host = designer.structure_tree_host
    content_top = float(canvas.canvasy(0))
    content_bottom = content_top + float(canvas.winfo_height())
    tree_top = float(host.winfo_y() + tree.winfo_y())
    tree_bottom = tree_top + float(tree.winfo_height())
    return max(0.0, min(content_bottom, tree_bottom) - max(content_top, tree_top))


def _menu_values(designer):
    menu = designer.part_choice_menu
    end = menu.index("end")
    if end is None:
        return ()
    values = []
    for index in range(end + 1):
        try:
            values.append((index, str(menu.entrycget(index, "value"))))
        except tk.TclError:
            pass
    return tuple(values)


def _root_rect(widget):
    return (
        int(widget.winfo_rootx()),
        int(widget.winfo_rooty()),
        int(widget.winfo_rootx() + widget.winfo_width()),
        int(widget.winfo_rooty() + widget.winfo_height()),
    )


def _intersection(a, b):
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    return max(0, right - left), max(0, bottom - top)


def test_issue186_sheetmetal_compact_menu_is_operator_visible_and_live():
    """The existing sheet-metal Menubutton must be a real production control."""
    root, _app, designer = _open_designer()
    try:
        _pump(root)
        button = designer.part_choice_button
        values = _menu_values(designer)

        assert button.winfo_ismapped(), (
            "sheet-metal part_choice_button still exists but is hidden as a compatibility-only "
            "object instead of being restored to the production UI"
        )
        assert values, "visible sheet-metal menu must contain the current physical-part choices"

        current = str(designer.part_var.get())
        candidate = next(((index, value) for index, value in values if value != current), None)
        assert candidate is not None, f"sheet-metal menu has no alternate live selection: {values!r}"
        index, value = candidate
        designer.part_choice_menu.invoke(index)
        _pump(root)
        assert str(designer.part_var.get()) == value
    finally:
        _close(root)


def test_issue186_sheetmetal_compact_menu_has_real_unobscured_pixels():
    """Mapped is insufficient: the compact selector must occupy unobscured on-screen pixels."""
    root, app, designer = _open_designer()
    try:
        app._apply_ui_text_size_preference("large", persist=False, notify_designer=True)
        designer.root.geometry("760x420+0+0")
        _pump(root, 5)

        button = designer.part_choice_button
        canvas = designer.left_scroll_canvas
        button_rect = _root_rect(button)
        canvas_rect = _root_rect(canvas)
        visible_w, visible_h = _intersection(button_rect, canvas_rect)
        center_x = (button_rect[0] + button_rect[2]) // 2
        center_y = (button_rect[1] + button_rect[3]) // 2
        topmost = root.winfo_containing(center_x, center_y)

        print(
            "ISSUE186_COMPACT_MENU_PIXELS",
            f"button_rect={button_rect}",
            f"canvas_rect={canvas_rect}",
            f"visible={visible_w}x{visible_h}",
            f"button_size={button.winfo_width()}x{button.winfo_height()}",
            f"topmost={topmost}",
            f"tree_host_rect={_root_rect(designer.structure_tree_host)}",
        )

        assert button.winfo_ismapped()
        assert button.winfo_width() >= 120
        assert button.winfo_height() >= 20
        assert visible_w >= min(120, button.winfo_width())
        assert visible_h >= button.winfo_height()
        assert topmost is button, (
            "compact selector is mapped but another widget is stacked above its center: "
            f"{topmost!r}"
        )
    finally:
        _close(root)


def test_issue186_sheetmetal_tree_is_visible_in_initial_left_viewport():
    """The production operator navigator must be on-screen, not merely constructed."""
    root, _app, designer = _open_designer()
    try:
        canvas = designer.left_scroll_canvas
        tree = designer.structure_tree
        _pump(root)

        assert canvas.winfo_ismapped(), "left scroll viewport itself must be mapped"
        assert tree.winfo_ismapped(), "sheet-metal Structure Tree must be mapped"
        assert tree.exists("mode:assembly"), "assembly row must exist in the real navigator"
        assert tree.exists("mode:corner_data"), "Corner Data row must exist in the real navigator"

        overlap = _tree_visible_overlap(designer)
        print(
            "ISSUE186_SELECTOR_GEOMETRY_INITIAL",
            f"canvas_h={canvas.winfo_height()}",
            f"yview={canvas.yview()}",
            f"tree_h={tree.winfo_height()}",
            f"visible_overlap={overlap:.1f}",
        )
        assert overlap >= min(120.0, float(tree.winfo_height()))
    finally:
        _close(root)


def test_issue186_sheetmetal_tree_stays_available_while_inputs_need_scrolling():
    """The production Structure Tree must remain reachable while lower inputs scroll."""
    root, app, designer = _open_designer()
    try:
        designer.activate_part("head")
        app._apply_ui_text_size_preference("large", persist=False, notify_designer=True)
        designer.root.geometry("760x420")
        _pump(root, 5)

        canvas = designer.left_scroll_canvas
        tree = designer.structure_tree
        assert tree.winfo_ismapped()
        assert canvas.winfo_ismapped()
        assert canvas.bbox("all") is not None

        before = tuple(float(v) for v in canvas.yview())
        canvas.yview_moveto(1.0)
        _pump(root, 3)
        after = tuple(float(v) for v in canvas.yview())
        overlap = _tree_visible_overlap(designer)

        print(
            "ISSUE186_SELECTOR_GEOMETRY_SCROLLED",
            f"canvas_h={canvas.winfo_height()}",
            f"before={before}",
            f"after={after}",
            f"tree_h={tree.winfo_height()}",
            f"visible_overlap={overlap:.1f}",
        )
        assert after[0] > 0.0, "precondition: large-text input workspace must actually scroll"
        assert overlap >= min(120.0, float(tree.winfo_height())), (
            "critical Structure Tree disappeared from the production direct-3D viewport "
            "while scrolling lower operator inputs"
        )
    finally:
        _close(root)
