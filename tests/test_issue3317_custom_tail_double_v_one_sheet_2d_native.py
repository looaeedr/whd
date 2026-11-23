"""#3317 Custom Tail ROUND_R same-material two-V single 2D CHECK.

True native Main Tk / source / Save→.p6fold→new Main Tk Open→View.
The one sheet is a Factory-backed *candidate* only; the raw CUTTING/BEND
remain unmodified, and there is explicitly NO combined 3D or DXF.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import tkinter as tk
from tkinter import filedialog, messagebox

import pytest
from shapely.geometry import LineString, Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry_core import Vec2, GeometryError
from gui import BoxCalculatorGUI
from gui_modules.application.endcap_live_v_check_consumer import (
    ATTR, KEY, _selected_source,
)
from gui_modules.application.endcap_live_v_check_view import close_saved_live_check_window
from phase6_project_file import read_project
from tests.test_issue3317_custom_tail_bottom_pair_native import CORNERS, _make_tail_pair


def _native_replays(app, *, mode="ROUND_R"):
    snapshot = app._make_original_fold_designer_snapshot()
    part, corner, spec, render = _selected_source(app, snapshot)
    assert (part, corner) == ("tail", "bottom")
    result = {
        key: api.project_operator_v_miter_live_corner_check(
            spec, render, key, first_bend_axis="x", relief_mode=mode,
        )
        for key in CORNERS
    }
    return spec, render, result


def _check_polygon(scene):
    outlines = [
        p for p in scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CHECK" and p.closed
    ]
    assert len(outlines) == 1
    geom = Polygon([(p.x, p.y) for p in outlines[0].points])
    assert geom.geom_type == "Polygon"
    assert geom.is_valid and not geom.interiors
    return geom


def test_engine_same_real_custom_tail_one_sheet_round_r_signed_delta_and_original_finite_bends():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        spec, render, replays = _native_replays(app)
        original_scene = deepcopy(render.scene)
        original_mat = render.material
        combined = api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
            spec, render, replays,
        )
        original = Polygon([
            (p.x, p.y) for primitive in render.scene.primitives
            if isinstance(primitive, PolylinePrimitive) and primitive.layer == "CUTTING"
            for p in primitive.points
        ])
        shape = _check_polygon(combined.scene)
        assert shape.is_valid and not shape.interiors
        assert shape.area == pytest.approx(combined.combined_area_mm2, abs=1e-6)
        signed = dict(combined.corner_signed_area_deltas_mm2)
        assert set(signed) == set(CORNERS)
        # These are real Sample W400/D250/T2 Factory-cut area changes,
        # NOT a universal width threshold or stock that can be physically
        # added to the original already-cut material.
        for value in signed.values():
            assert value == pytest.approx(31.859668843, abs=2e-5)
        assert shape.area == pytest.approx(
            original.area + sum(signed.values()), abs=2e-5
        )
        left, right = (replays[key] for key in CORNERS)
        assert left.first_physical_bend is not right.first_physical_bend
        assert left.second_physical_bend is right.second_physical_bend
        assert tuple(sorted(
            (p.y for p in (
                left.first_physical_bend.p1, left.first_physical_bend.p2
            ))
        )) == pytest.approx((16, 257))
        assert tuple(sorted(
            (p.y for p in (
                right.first_physical_bend.p1, right.first_physical_bend.p2
            ))
        )) == pytest.approx((16, 257))
        assert tuple(sorted(
            (p.x for p in (
                left.second_physical_bend.p1, left.second_physical_bend.p2
            ))
        )) == pytest.approx((16, 406))
        assert left.second_physical_bend.p1.y == pytest.approx(15)
        # Exactly ONE original shared Y BEND, no extended 'V90 Y16→0' axis.
        original_bends = [
            p for p in render.scene.primitives
            if isinstance(p, LinePrimitive) and p.layer == "BEND"
        ]
        assert sum(p is left.second_physical_bend for p in original_bends) == 1
        assert len(combined.original_finite_bends) == len(original_bends)
        datums = [
            p for p in combined.scene.primitives
            if isinstance(p, LinePrimitive) and p.layer == "DATUM"
        ]
        assert len(datums) == len(original_bends)
        for before, after in zip(original_bends, datums):
            assert (before.p1, before.p2) == (after.p1, after.p2)
            line = LineString([(before.p1.x,before.p1.y),(before.p2.x,before.p2.y)])
            assert line.difference(shape.buffer(1e-7)).length < 1e-7
        assert render.scene == original_scene
        assert render.material.symmetric_difference(original_mat).area == 0
        assert not any(p.layer == "CUTTING" for p in combined.scene.primitives)
        assert not any(p.layer == "BEND" for p in combined.scene.primitives)
    finally:
        root.destroy()


def test_native_main_save_open_shows_one_verified_2d_plus_both_original_independent_canvases(
    tmp_path, monkeypatch,
):
    messages = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: messages.append(("info", a)))
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: messages.append(("error", a)))
    path = tmp_path / "authentic-custom-tail-pair-roundr.p6fold"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **k: str(path))
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **k: str(path))
    root = tk.Tk()
    root.withdraw()
    new_root = None
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        messages.clear()
        app.v_miter_capture_live_source_button.invoke()
        assert not any(k == "error" for k,_ in messages), messages
        original_records = deepcopy(getattr(app, ATTR)["tail"])
        messages.clear()
        app.project_save_as_button.invoke()
        assert path.is_file() and not any(k == "error" for k,_ in messages), messages
        project_bytes = path.read_bytes()
        disk = read_project(path)["snapshot"]
        assert disk[KEY]["tail"] == original_records

        new_root = tk.Tk()
        new_root.withdraw()
        opened = BoxCalculatorGUI(new_root)
        messages.clear()
        opened.project_open_button.invoke()
        assert not any(k == "error" for k,_ in messages), messages
        opened.workspace_controller.set_active_part("tail")
        opened.select_manual_corner("bottom")
        messages.clear()
        opened.v_miter_check_source_button.invoke()
        assert not any(k == "error" for k,_ in messages), messages
        win = opened._endcap_live_saved_check_window
        win.update()
        assert win.winfo_viewable() == 1 and win.grab_status() == "local"
        candidate = win._saved_endcap_pair_combined_check
        assert candidate is not None
        assert candidate.manufacturing_status.endswith("UNCERTIFIED")
        contour = _check_polygon(win._saved_endcap_pair_combined_scene)
        assert contour.area == pytest.approx(candidate.combined_area_mm2, abs=1e-6)
        assert len(win._saved_endcap_pair_2d_canvases) == 2
        assert len(win._saved_endcap_pair_combined_canvas.find_all()) > 5
        assert win._saved_endcap_pair_2d_notebook.tabs()
        assert len(win._saved_endcap_pair_2d_notebook.tabs()) == 2
        assert "單片雙角 2D CHECK" in win._saved_endcap_pair_2d_notebook.tab(0, "text")
        assert win._saved_endcap_pair_3d_figure is None
        assert "不提供雙角合成 3D" in win._saved_endcap_pair_3d_warning.cget("text")
        assert path.read_bytes() == project_bytes
        close_saved_live_check_window(opened)
        # A source-only width change invalidates BOTH old records and cannot
        # leave an independently correct-looking combined old sheet visible.
        opened.w_var.set("410")
        messages.clear()
        opened.v_miter_check_source_button.invoke()
        assert any(k == "error" for k,_ in messages)
        assert getattr(opened, "_endcap_live_saved_check_window", None) is None
        assert path.read_bytes() == project_bytes
    finally:
        if new_root is not None:
            new_root.destroy()
        root.destroy()


def test_pair_2d_rejects_hole_mode_and_existing_real_hole_without_fake_merge(monkeypatch):
    messages = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *a,**kw: messages.append(("info", a)))
    monkeypatch.setattr(messagebox, "showerror", lambda *a,**kw: messages.append(("error", a)))
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "RELIEF_HOLE")
        spec, render, replays = _native_replays(app, mode="RELIEF_HOLE")
        with pytest.raises(GeometryError, match="ROUND_R_SOURCE_REQUIRED"):
            api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
                spec, render, replays,
            )
        # Preserve prior #3419 separate views for supported corner CHECK,
        # but explicitly decline the unsupported one-piece sketch.
        messages.clear()
        app.v_miter_capture_live_source_button.invoke()
        assert not any(k=="error" for k,_ in messages), messages
        app.v_miter_check_source_button.invoke()
        win = app._endcap_live_saved_check_window
        assert win._saved_endcap_pair_combined_check is None
        assert win._saved_endcap_pair_combined_canvas is None
        assert len(win._saved_endcap_pair_2d_canvases) == 2
        close_saved_live_check_window(app)

        app.v_miter_gui_relief_modes["tail"] = dict.fromkeys(CORNERS, "ROUND_R")
        part = CircleFeature(
            diameter=6, anchor=FeatureAnchor.PANEL_CENTER,
            offset=Vec2(0, 0), layer="CUTTING",
        )
        app.surface_features["tail"] = [part]
        features = app.workspace_controller.part_features_snapshot()
        features["tail"] = [part]
        app.workspace_controller.replace_part_features(features)
        # Material now comes from the one genuine Tail Hole Editor owner.
        spec, render, replays = _native_replays(app)
        assert render.material.interiors
        with pytest.raises(GeometryError, match="HOLE_OR_MATERIAL_UNSUPPORTED"):
            api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
                spec, render, replays,
            )
        # Existing-circle local CHECK may still be displayed individually,
        # but no claimed single perimeter or hole-free thick 3D exists.
        messages.clear()
        app.v_miter_capture_live_source_button.invoke()
        assert not any(k=="error" for k,_ in messages), messages
        app.v_miter_check_source_button.invoke()
        win = app._endcap_live_saved_check_window
        assert win._saved_endcap_pair_combined_check is None
        assert len(win._saved_endcap_pair_2d_canvases) == 2
        close_saved_live_check_window(app)
    finally:
        root.destroy()


def test_pair_2d_forged_or_repeated_delta_is_not_accepted():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        spec, render, replays = _native_replays(app)
        left, right = (replays[key] for key in CORNERS)
        forged = replace(
            right,
            factory_bottom_relief_check=left.factory_bottom_relief_check,
        )
        with pytest.raises(GeometryError, match="REPLAY_SOURCE_CHANGED|FACTORY_CORNER"):
            api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
                spec, render, {"bottom_left": left, "bottom_right": forged},
            )
        with pytest.raises(GeometryError, match="AUTHENTIC_SOURCE_REQUIRED"):
            api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
                spec, render, {"bottom_left": left},
            )
    finally:
        root.destroy()
