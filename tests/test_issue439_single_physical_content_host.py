# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#439 correction requires real Tk/Xvfb"
)


def _snapshot():
    return {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    }


def _pump(root, cycles=4):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, _snapshot())
    _pump(root)
    return root, app


def _bbox(root, widget):
    return (
        int(widget.winfo_rootx() - root.winfo_rootx()),
        int(widget.winfo_rooty() - root.winfo_rooty()),
        int(widget.winfo_width()),
        int(widget.winfo_height()),
    )


def test_issue439_original_input_host_is_the_only_physical_content_host():
    root, app = _open()
    try:
        assert app.shared_content_host is app.fold_editor_host, (
            "INTENDED_RED_EXTRA_SHARED_CONTENT_FRAME: shared_content_host must be "
            "a compatibility alias to the original fold_editor_host, not a new Frame"
        )
        assert app.fold_editor_host.master is app.left
        assert app.input_content_host.master is app.fold_editor_host
        assert app.assembly_parts_panel.master is app.fold_editor_host

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert app.corner_data_panel.master is app.fold_editor_host
    finally:
        root.destroy()


def test_issue439_outer_input_host_never_switches_and_keeps_one_physical_bbox():
    root, app = _open()
    try:
        outer = app.fold_editor_host
        assert outer.master is app.left
        assert outer.winfo_manager() != ""

        boxes = []
        inner_mapped = []

        app.activate_part("head")
        _pump(root)
        boxes.append(_bbox(root, outer))
        inner_mapped.append(
            sum(
                1
                for w in (
                    app.input_content_host,
                    app.assembly_parts_panel,
                    getattr(app, "corner_data_panel", None),
                )
                if w is not None and w.winfo_manager()
            )
        )

        bridge._phase6_show_assembly(app)
        _pump(root)
        assert outer.winfo_manager() != ""
        boxes.append(_bbox(root, outer))
        inner_mapped.append(
            sum(
                1
                for w in (
                    app.input_content_host,
                    app.assembly_parts_panel,
                    getattr(app, "corner_data_panel", None),
                )
                if w is not None and w.winfo_manager()
            )
        )

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert outer.winfo_manager() != ""
        boxes.append(_bbox(root, outer))
        inner_mapped.append(
            sum(
                1
                for w in (
                    app.input_content_host,
                    app.assembly_parts_panel,
                    app.corner_data_panel,
                )
                if w is not None and w.winfo_manager()
            )
        )

        assert boxes[0] == boxes[1] == boxes[2], (
            "OUTER_CONTENT_BBOX_IDENTICAL_ALL_MODES failed: "
            f"part={boxes[0]} assembly={boxes[1]} corner_data={boxes[2]}"
        )
        assert inner_mapped == [1, 1, 1]
    finally:
        root.destroy()
