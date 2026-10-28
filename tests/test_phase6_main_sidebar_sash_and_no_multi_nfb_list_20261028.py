# -*- coding: utf-8 -*-
"""Operator acceptance: genuine Phase6 MAIN sash and no duplicate multi NFB list."""
import os
import tkinter as tk
import pytest

pytestmark = pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="Windows native Tk or Xvfb required",
)


def test_original_phase6_primary_sidebar_is_ten_percent_narrower_and_mouse_resizable():
    import gui
    import fold_designer_bridge as bridge
    root = tk.Tk()
    root.geometry("1700x980+0+0")
    root.update()
    try:
        app = gui.Phase6PrimaryApplication(root)
        designer = app.fold_designer_app
        for _ in range(3):
            root.update_idletasks()
            root.update()
        canvas = designer.left_scroll_canvas
        shell = designer._phase6_workspace_shell_owner
        sash = shell.left_resize_sash
        baseline = bridge._phase6_left_workspace_width(
            designer._settings_values.get("ui_text_size", "small")
        )
        initial = max(190, round(baseline * 0.9))
        print("BASELINE", baseline, "EXPECTED", initial, "ACTUAL", canvas.winfo_width(),
              "SASH", sash.winfo_width(), "RIGHT", designer.right.winfo_width(), flush=True)
        assert canvas.winfo_ismapped() and sash.winfo_ismapped()
        assert sash.cget("cursor") == "sb_h_double_arrow"
        assert abs(canvas.winfo_width()-initial) <= 5
        assert sash.winfo_width() >= 8
        before = canvas.winfo_width()
        # Tk's actual mouse event handlers, not a mocked width setter.
        xroot = sash.winfo_rootx() + 3
        yroot = sash.winfo_rooty() + 90
        sash.event_generate("<ButtonPress-1>", x=3, y=90, rootx=xroot, rooty=yroot)
        sash.event_generate("<B1-Motion>", x=82, y=90,
                            rootx=xroot+79, rooty=yroot)
        sash.event_generate("<ButtonRelease-1>", x=82, y=90,
                            rootx=xroot+79, rooty=yroot)
        root.update()
        dragged = canvas.winfo_width()
        assert dragged >= before + 60, (before, dragged)
        assert canvas._phase6_manual_width is True
        # Mode/UI style sync cannot erase the operator sash choice.
        bridge._phase6_update_left_workspace_width(designer)
        root.update()
        assert abs(canvas.winfo_width()-dragged) <= 3
        viewport = designer.renderer.canvas.get_tk_widget()
        assert viewport.winfo_ismapped() and viewport.winfo_width() >= 760
    finally:
        root.destroy()


def test_native_multi_inner_page_hides_nfb_list_without_removing_source_manifest():
    from types import SimpleNamespace
    from gui_modules.application.receiving_multi_settings_window import open_multi_settings
    from gui_modules.application.receiving_nfb_manifest_view import highlighted_nfb_manifest_lines
    from tkinter import ttk
    root = tk.Tk()
    root.geometry("920x680")
    root.update()
    win = None
    try:
        live = {"status": "BLOCKED", "reason": "NFB_WORLD_X_RECONFIRM_REQUIRED"}
        ports = {"manifest": lambda _si, _bi: live,
                 "state":lambda *_a: {"submitted": True, "can_submit":False,
                                      "can_copy":False, "can_restore":False,
                                      "can_undo":False, "reason":"source blocked"}}
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode":"set_bay"},
            get_switch=lambda:SimpleNamespace(connection_counts=lambda:(1,)),
            switch_mode=lambda _m:True, resize_connections=lambda *_a:False,
            get_settings_ports=lambda _: {
                "row":lambda: {"bays":[{"stable_id":"bay-a"}]},
                "select":lambda _bi:None,
            },
            get_nfb_transaction_ports=lambda:ports,
        )
        root.update()
        win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        stack=[win._receiving_multi_settings_host]
        labels=[]
        while stack:
            w=stack.pop()
            if isinstance(w,(ttk.Label,ttk.LabelFrame)) and w.winfo_ismapped():
                labels.append(str(w.cget("text")))
            stack.extend(w.winfo_children())
        assert not any("NFB 板件清單" in label for label in labels), labels
        assert any("NFB_WORLD_X_RECONFIRM_REQUIRED" in line
                   for line in highlighted_nfb_manifest_lines(ports,0,(0,)))
        # Previously updated multi-Bay splitter is retained independently.
        assert win._receiving_multi_splitter.winfo_exists()
        win._receiving_multi_close()
        root.update()
        assert not win.winfo_exists()
    finally:
        if win is not None and win.winfo_exists():
            win._receiving_multi_close()
        root.destroy()
