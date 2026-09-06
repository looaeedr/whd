from __future__ import annotations

from pathlib import Path
import tempfile
import tkinter as tk

import gui
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2


def summarize(app, label):
    cols = app.get_door_layout_columns()
    cells = app.get_door_layout_cells()
    print(label, {
        "baseline": app.baseline_var.get(),
        "active_family": getattr(app, "_active_cabinet_type", None),
        "multi": bool(app.multi_door_enabled_var.get()),
        "columns": cols,
        "cells": [(c.column_index, c.row_index, c.start_width, c.start_height) for c in cells],
        "feature_keys": sorted(app.door_layout_features),
        "feature_counts": {k: len(v) for k, v in app.door_layout_features.items()},
        "dirty": sorted(getattr(app._phase6_update_scheduler, "dirty", set())),
    })
    return cells


def build_app():
    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    app.w_var.set("1100")
    app.h_var.set("1800")
    app.multi_door_enabled_var.set(True)
    app.set_door_layout_columns([
        (600, [600, 500, 700]),
        (500, [800, 1000]),
    ])
    app.baseline_var.set("")
    app.door_layout_features["0:0"] = [
        CircleFeature(30.0, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0))
    ]
    return root, app


root, app = build_app()
try:
    cells = summarize(app, "BEFORE_FLUSH")
    c0 = cells[0]
    r0 = app._door_layout_cell_result(c0, app.get_float_values())
    resolved = app._door_layout_cell_resolved_features(c0, r0, "0:0")
    print("RESOLVED_BEFORE_FLUSH", len(resolved), resolved)

    ctx = app._manufacturing_context(draw_stock=False)
    for cell in cells:
        key = app._door_layout_cell_key(cell)
        spec = app._door_layout_part_spec(cell, app.get_float_values())
        rd = app._authoritative_render_data(spec, ctx)
        print("RENDER", key, "pieces", len(tuple(getattr(rd, "pieces", ()) or ())), "bounds", tuple(float(v) for v in rd.material.bounds))

    flushed = app._flush_phase6_authoritative_state()
    print("FLUSH_RETURN", flushed)
    cells2 = summarize(app, "AFTER_FLUSH")
    c0 = cells2[0]
    r0 = app._door_layout_cell_result(c0, app.get_float_values())
    resolved2 = app._door_layout_cell_resolved_features(c0, r0, "0:0")
    print("RESOLVED_AFTER_FLUSH", len(resolved2), resolved2)

    with tempfile.TemporaryDirectory() as td:
        ret = app.export_multi_door_layout_dxfs(td, app.get_float_values(), draw_stock=False)
        print("EXPORT_ORIGINAL_RETURN", ret)
        print("EXPORT_ORIGINAL_FILES", sorted(p.name for p in Path(td).glob("*")))
finally:
    root.destroy()

root2, app2 = build_app()
try:
    summarize(app2, "NOFLUSH_BEFORE")
    app2._flush_phase6_authoritative_state = lambda: False
    with tempfile.TemporaryDirectory() as td:
        ret = app2.export_multi_door_layout_dxfs(td, app2.get_float_values(), draw_stock=False)
        print("EXPORT_NOFLUSH_RETURN", ret)
        print("EXPORT_NOFLUSH_FILES", sorted(p.name for p in Path(td).glob("*")))
    summarize(app2, "NOFLUSH_AFTER")
finally:
    root2.destroy()
