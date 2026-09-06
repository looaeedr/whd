from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="需要 Tk 顯示環境",
)


def _pump(root):
    root.update_idletasks()
    root.update()


def _open_medium_unlocked_head():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("受電箱")
    _pump(root)
    designer = app.open_original_fold_designer()
    designer._ui_text_size_change_callback = lambda value: app._apply_ui_text_size_preference(
        value, persist=False, notify_designer=False
    )
    designer.root.deiconify()
    designer.root.geometry("1120x720+0+0")
    designer.activate_part("head")
    designer.ui_text_size_var.set("中")
    _pump(root)
    if not bool(getattr(designer, "_phase6_parameters_unlocked", False)):
        designer.parameter_lock_button.invoke()
    _pump(root)
    return root, app, designer


def _close(root, designer):
    try:
        designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def test_medium_unlocked_settings_uses_real_vertical_scroll_owner_and_scrollable_viewport():
    from tkinter import ttk

    root, _app, designer = _open_medium_unlocked_head()
    try:
        panel = designer.settings_panel
        scrollbar = getattr(panel, "settings_scrollbar", None)
        canvas = getattr(panel, "settings_scroll_canvas", None)
        assert isinstance(scrollbar, ttk.Scrollbar), "settings panel requires a real ttk vertical Scrollbar"
        assert canvas is not None, "settings panel requires a Canvas scroll viewport"
        assert str(scrollbar.cget("orient")) == "vertical"
        assert scrollbar.winfo_manager(), "vertical Scrollbar must be managed when parameters are unlocked"

        region = canvas.cget("scrollregion")
        assert region not in ("", None), "settings Canvas scrollregion must be configured"
        bbox = canvas.bbox("all")
        assert bbox is not None
        content_height = int(bbox[3] - bbox[1])
        viewport_height = int(canvas.winfo_height())
        assert content_height > viewport_height > 0, (
            f"Medium unlocked settings must actually overflow the viewport; "
            f"content={content_height}, viewport={viewport_height}"
        )

        page = panel.page_cache[panel.settings_context]["frame"]
        canvas.yview_moveto(1.0)
        _pump(root)
        page_bottom = page.winfo_rooty() + page.winfo_height()
        viewport_bottom = canvas.winfo_rooty() + canvas.winfo_height()
        assert page_bottom <= viewport_bottom + 3, (
            f"last settings rows are not reachable by scrolling: "
            f"page_bottom={page_bottom}, viewport_bottom={viewport_bottom}"
        )
    finally:
        _close(root, designer)


def test_settings_scroll_owner_survives_resize_part_switch_and_lock_unlock():
    root, _app, designer = _open_medium_unlocked_head()
    try:
        panel = designer.settings_panel
        canvas = getattr(panel, "settings_scroll_canvas", None)
        scrollbar = getattr(panel, "settings_scrollbar", None)
        assert canvas is not None and scrollbar is not None

        designer.root.geometry("960x650+0+0")
        _pump(root)
        assert canvas.bbox("all") is not None
        assert canvas.winfo_height() > 0

        designer.activate_part("tail")
        _pump(root)
        assert panel.settings_context == "tail"
        assert panel.settings_scroll_canvas is canvas
        assert panel.settings_scrollbar is scrollbar
        assert canvas.bbox("all") is not None

        designer.parameter_lock_button.invoke()
        _pump(root)
        assert not bool(getattr(designer, "_phase6_parameters_unlocked", False))
        designer.parameter_lock_button.invoke()
        _pump(root)
        assert bool(getattr(designer, "_phase6_parameters_unlocked", False))
        assert panel.settings_context == "tail"
        assert panel.settings_scroll_canvas is canvas
        assert panel.settings_scrollbar is scrollbar

        renderer_widget = designer.renderer.canvas.get_tk_widget()
        assert renderer_widget.winfo_height() >= 80, (
            f"3D canvas lost usable height after settings scroll layout: {renderer_widget.winfo_height()}"
        )
    finally:
        _close(root, designer)
