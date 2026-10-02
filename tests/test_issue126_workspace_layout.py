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
        left_small = designer.left.winfo_width()
        right_small = designer.right.winfo_width()

        designer.root.geometry("1800x900+0+0")
        designer.root.update_idletasks(); designer.root.update()
        left_large = designer.left.winfo_width()
        right_large = designer.right.winfo_width()

        # #126 contract: sidebar is an inspector, not a competing canvas.
        assert left_large <= 380
        extra_total = 500
        extra_workspace = right_large - right_small
        extra_sidebar = left_large - left_small
        assert extra_workspace >= int(extra_total * 0.80)
        assert extra_sidebar <= int(extra_total * 0.20)
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
