# -*- coding: utf-8 -*-
import tkinter as tk

import gui


def _open_designer(width: int, height: int = 900):
    root = tk.Tk()
    root.geometry(f"{width}x{height}+0+0")
    root.update()
    app = gui.BoxCalculatorGUI(root)
    designer = app.open_original_fold_designer()
    root.update_idletasks()
    root.update()
    return root, designer


def _workspace_state_refs(designer):
    refs = {}
    for name, value in vars(designer).items():
        low = name.lower()
        if "workspace" in low or "shared_state" in low:
            refs[name] = id(value)
    return refs


def test_resize_is_presentation_only_and_does_not_create_workspace_state_owner():
    root, designer = _open_designer(1500)
    try:
        before = _workspace_state_refs(designer)
        designer.root.geometry("1800x1000+0+0")
        designer.root.update_idletasks()
        designer.root.update()
        after = _workspace_state_refs(designer)
        assert after == before
    finally:
        try:
            designer.root.destroy()
        except tk.TclError:
            pass
        root.destroy()


def test_sidebar_width_is_bounded_while_workspace_receives_majority_of_extra_width():
    root, designer = _open_designer(1300)
    try:
        designer.root.geometry("1300x900+0+0")
        designer.root.update_idletasks(); designer.root.update()
        actual_small = designer.root.winfo_width()
        left_small = designer.left.winfo_width()
        right_small = designer.right.winfo_width()

        designer.root.geometry("1800x900+0+0")
        designer.root.update_idletasks(); designer.root.update()
        actual_large = designer.root.winfo_width()
        left_large = designer.left.winfo_width()
        right_large = designer.right.winfo_width()

        # This is the legacy Fold Designer inspector, NOT the independent
        # draggable ~282px Receiving multi-Bay sidebar (tested elsewhere).
        # Its notebook has a natural width of roughly 430px, but must never
        # overwhelm the drawing workspace or grow unbounded on resize.
        assert left_large <= 480
        assert right_large >= 600
        assert right_large >= left_large * 1.4

        # Tk can clamp a requested 1800px window to a smaller remote
        # display. Compare actual mapped widths, not requested geometry.
        available_growth = actual_large - actual_small
        if available_growth >= 80:
            assert right_large - right_small >= int(available_growth * 0.80)
            assert left_large - left_small <= int(available_growth * 0.20)
        else:
            # On a screen-limited viewport there was no larger workspace:
            # keeping both pane widths stable is the real resize contract.
            assert abs(left_large - left_small) <= 12
            assert right_large >= right_small - 12
    finally:
        try:
            designer.root.destroy()
        except tk.TclError:
            pass
        root.destroy()


def test_workspace_remains_operable_at_compact_window_size():
    root, designer = _open_designer(1100, 760)
    try:
        designer.root.geometry("1100x760+0+0")
        designer.root.update_idletasks(); designer.root.update()
        assert designer.left.winfo_width() >= 260
        assert designer.right.winfo_width() >= 600
        canvases = [
            child for child in designer.right.winfo_children()
            if child.winfo_class() == "Canvas" and child.winfo_manager()
        ]
        assert canvases
        assert max(canvas.winfo_width() for canvas in canvases) >= 560
    finally:
        try:
            designer.root.destroy()
        except tk.TclError:
            pass
        root.destroy()
