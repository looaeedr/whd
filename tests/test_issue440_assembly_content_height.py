# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#440 assembly height census requires Xvfb"
)


def _snapshot():
    return {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    }


def _pump(root, cycles=5):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def test_issue440_measure_assembly_surface_height_census():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, _snapshot())
    try:
        bridge._phase6_show_assembly(app)
        _pump(root)

        owner = app._phase6_assembly_panel_owner
        print(f"ASSEMBLY_HOST_REQHEIGHT={owner.host.winfo_reqheight()}")
        print(f"ASSEMBLY_HOST_HEIGHT={owner.host.winfo_height()}")
        print(f"ASSEMBLY_CANVAS_REQHEIGHT={owner.canvas.winfo_reqheight()}")
        print(f"ASSEMBLY_CANVAS_HEIGHT={owner.canvas.winfo_height()}")
        print(f"ASSEMBLY_CONTENT_REQHEIGHT={owner.content.winfo_reqheight()}")
        print(f"ASSEMBLY_CONTENT_HEIGHT={owner.content.winfo_height()}")
        print(f"ASSEMBLY_CONTENT_BBOX={owner.canvas.bbox('all')}")
        print(f"ASSEMBLY_SECTION_COUNT={len(owner.sections)}")
        print(f"ASSEMBLY_GROUP_COUNT={len(owner.group_sections)}")
        print(f"ASSEMBLY_BOX_PIECE_COUNT={len(owner.box_piece_sections)}")

        assert owner.canvas.winfo_reqheight() == owner.content.winfo_reqheight()
        assert owner.host.winfo_reqheight() >= owner.content.winfo_reqheight()
        assert owner.host.winfo_height() >= owner.content.winfo_reqheight()
        assert owner.host.winfo_height() > 44
    finally:
        root.destroy()


def test_issue440_assembly_surface_tracks_expand_collapse_content_height():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, _snapshot())
    try:
        bridge._phase6_show_assembly(app)
        _pump(root)
        owner = app._phase6_assembly_panel_owner

        target = "head" if "head" in owner.detail_frames else next(iter(owner.detail_frames))
        before_content = owner.content.winfo_reqheight()
        before_host = owner.host.winfo_height()

        owner.set_part_details_open(target, True)
        _pump(root)

        expanded_content = owner.content.winfo_reqheight()
        expanded_host = owner.host.winfo_height()
        assert expanded_content > before_content
        assert int(float(owner.canvas.cget("height"))) == expanded_content
        assert expanded_host >= expanded_content
        assert expanded_host > before_host

        owner.set_part_details_open(target, False)
        _pump(root)

        collapsed_content = owner.content.winfo_reqheight()
        collapsed_host = owner.host.winfo_height()
        assert collapsed_content < expanded_content
        assert int(float(owner.canvas.cget("height"))) == collapsed_content
        assert collapsed_host >= collapsed_content
    finally:
        root.destroy()
