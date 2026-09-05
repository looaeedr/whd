# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import pytest
from copy import deepcopy

def _has_tk_display() -> bool:
    return os.name == "nt" or bool(os.environ.get("DISPLAY"))

@pytest.mark.skipif(not _has_tk_display(), reason="需要 Tk 顯示環境")
def test_endcap_four_direction_edge_selectors_are_narrowed_and_preserve_semantics():
    import tkinter as tk
    import gui
    from ae_engine.assembly_joint import edge_relation_for_part, AssemblyJointRelation

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        designer.activate_part("head")
        root.update_idletasks(); root.update()

        hosts = getattr(designer, "drawing_edge_hosts", None)
        assert hosts is not None
        assert tuple(designer.endcap_joint_widgets.keys()) == ("TOP", "BOTTOM", "LEFT", "RIGHT")

        for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
            widget = designer.endcap_joint_widgets[edge]
            # 規格 4.7：封頭尾四向選擇框 widget 可縮窄（原寬度為 9，縮窄後必須 <= 7）
            width_attr = int(widget.cget("width"))
            assert width_attr <= 7, f"Edge {edge} menubutton width {width_attr} exceeds narrowed limit 7"

        # 驗證語意完整性：選擇不同選項時正確生效
        editable_edges = [edge for edge, allowed in designer.endcap_joint_allowed.items() if len(allowed) > 1]
        assert editable_edges, "Must have editable edges on head"
        target_edge = editable_edges[0]
        allowed_values = designer.endcap_joint_allowed[target_edge]
        current_val = designer.endcap_joint_vars[target_edge].get()
        alt_val = next(v for v in allowed_values if v != current_val)

        designer.endcap_joint_vars[target_edge].set(alt_val)
        rel = designer._phase6_on_endcap_edge_relation_selected("head", target_edge)
        assert rel is not None
        assert edge_relation_for_part(designer._phase6_input_snapshot, "head", target_edge) == rel
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass


@pytest.mark.skipif(not _has_tk_display(), reason="需要 Tk 顯示環境")
def test_main_gui_left_panel_rescales_under_medium_and_large_text():
    import tkinter as tk
    import gui
    from ui_text_scale import TextScaleController

    root = tk.Tk()
    root.geometry("1100x750")
    root.update()
    try:
        app = gui.BoxCalculatorGUI(root)
        root.update()

        # 預設 small: left_container 寬度 320
        paned = getattr(app, "main_paned", None)
        left = getattr(app, "left_container", None)
        assert paned is not None and left is not None
        initial_width = int(paned.paneconfig(left, "width")[-1])
        assert initial_width == 320

        # 切換到 medium: 規格 4.6，UI layout 必須讓 widget minimum size 與 layout geometry 一致縮放
        app._apply_ui_text_size_preference("medium", persist=False)
        root.update()
        medium_width = int(paned.paneconfig(left, "width")[-1])
        assert medium_width >= int(round(320 * 1.15)), f"Medium width {medium_width} not scaled from 320"

        # 切換到 large
        app._apply_ui_text_size_preference("large", persist=False)
        root.update()
        large_width = int(paned.paneconfig(left, "width")[-1])
        assert large_width >= int(round(320 * 1.35)), f"Large width {large_width} not scaled from 320"

        # 切回 small
        app._apply_ui_text_size_preference("small", persist=False)
        root.update()
        reset_width = int(paned.paneconfig(left, "width")[-1])
        assert reset_width == 320
    finally:
        try:
            root.destroy()
        except Exception:
            pass


@pytest.mark.skipif(not _has_tk_display(), reason="需要 Tk 顯示環境")
def test_fold_designer_controls_and_edge_selectors_update_on_text_size_changed():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1100x750")
    root.update()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.root.geometry("1120x720")
        designer.activate_part("head")
        root.update_idletasks(); root.update()

        # 切換文字大小為 medium
        designer.ui_text_size_var.set("中")
        root.update_idletasks(); root.update()

        # 驗證四向選擇框存在且處於 mapped 狀態
        hosts = getattr(designer, "drawing_edge_hosts", None)
        assert hosts is not None
        for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
            host = getattr(hosts, edge.lower())
            assert host.winfo_ismapped(), f"Host for {edge} should be mapped"
            widget = designer.endcap_joint_widgets[edge]
            assert int(widget.cget("width")) <= 7
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass