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


def _turn_off_real_factory_render_cache(app, monkeypatch):
    """Use the existing WHD Factory on EVERY query, without cache reuse."""
    original_query = app._query_fold_designer_render_data
    owner_reads, builds = [], []

    def real_cold_factory(spec, context=None):
        # Exactly the public Engine builder used by the original cache
        # implementation. This deliberately creates a fresh PartRenderData.
        native = api.build_operator_part_render_data(spec, context)
        builds.append((spec, context, native))
        return native

    def counted_real_query(part, payload):
        native = original_query(part, payload)
        if part == "tail":
            owner_reads.append(native)
        return native

    monkeypatch.setattr(app, "_authoritative_render_data", real_cold_factory)
    monkeypatch.setattr(app, "_query_fold_designer_render_data", counted_real_query)
    return owner_reads, builds


@pytest.mark.parametrize("mode,has_one_sheet", (
    ("ROUND_R", True),
    ("RELIEF_HOLE", False),
))
def test_real_main_saved_tail_view_cold_factory_rebuilds_source_once(
    tmp_path, monkeypatch, mode, has_one_sheet,
):
    """#3422 independent RED: no RenderData cache, true Save/Open/button.

    The original broken viewer rebuilt the SAME native scene twice.
    Those values matched but the new BEND objects made Engine correctly
    refuse the combined candidate as REPLAY_SOURCE_CHANGED. The new GUI
    route must retain the FIRST exact owned render through both projections.
    """
    messages = []
    monkeypatch.setattr(
        messagebox, "showinfo", lambda *a, **k: messages.append(("info", a))
    )
    monkeypatch.setattr(
        messagebox, "showerror", lambda *a, **k: messages.append(("error", a))
    )
    path = tmp_path / f"custom-tail-cold-cache-{mode}.p6fold"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **k: str(path))
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **k: str(path))
    root = tk.Tk()
    root.withdraw()
    new_root = None
    try:
        old = BoxCalculatorGUI(root)
        _make_tail_pair(old, mode)
        messages.clear()
        old.v_miter_capture_live_source_button.invoke()
        assert not any(k == "error" for k, _ in messages), messages
        original_records = deepcopy(getattr(old, ATTR)["tail"])
        messages.clear()
        old.project_save_as_button.invoke()
        assert path.is_file() and not any(k == "error" for k, _ in messages)
        saved_bytes = path.read_bytes()
        assert read_project(path)["snapshot"][KEY]["tail"] == original_records

        new_root = tk.Tk()
        new_root.withdraw()
        fresh = BoxCalculatorGUI(new_root)
        messages.clear()
        fresh.project_open_button.invoke()
        assert not any(k == "error" for k, _ in messages), messages
        fresh.workspace_controller.set_active_part("tail")
        fresh.select_manual_corner("bottom")

        # Patch the actual render owner, NOT _selected_source or Engine CHECK.
        # Every call executes the real public Factory; unlike the ordinary
        # GUI, no cache or prior RenderData instance is reused.
        reads, builds = _turn_off_real_factory_render_cache(fresh, monkeypatch)
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert not any(k == "error" for k, _ in messages), messages
        assert len(reads) == len(builds) == 1, (
            "one Main View must read Tail exactly once even with cache OFF",
            len(reads), len(builds),
        )
        win = fresh._endcap_live_saved_check_window
        assert win is not None
        win.update()
        assert win.winfo_viewable() == 1 and win.grab_status() == "local"
        envelope = win._saved_endcap_pair_source_envelope
        assert envelope is not None
        assert envelope.render_data is reads[0] is builds[0][2]
        assert set(envelope.replays) == set(CORNERS)
        assert set(envelope.saved_rows) == set(CORNERS)
        for side in CORNERS:
            assert dict(envelope.saved_rows[side]) == original_records[side]
            with pytest.raises(TypeError):
                envelope.saved_rows[side]["source_fold_sha256"] = "0" * 64

        first = envelope.render_data
        # Two fresh Factory runs do have identical values but distinct
        # BEND owners, proving this test actually disables source reuse.
        second = api.build_operator_part_render_data(builds[0][0], builds[0][1])
        assert first is not second
        assert first.scene == second.scene
        first_bends = [
            p for p in first.scene.primitives
            if isinstance(p, LinePrimitive) and p.layer == "BEND"
        ]
        next_bends = [
            p for p in second.scene.primitives
            if isinstance(p, LinePrimitive) and p.layer == "BEND"
        ]
        assert len(first_bends) == len(next_bends) >= 3
        assert all(a is not b and (a.p1, a.p2) == (b.p1, b.p2)
                   for a, b in zip(first_bends, next_bends))
        left, right = (envelope.replays[key] for key in CORNERS)
        assert left.first_physical_bend is not right.first_physical_bend
        assert left.second_physical_bend is right.second_physical_bend
        assert sum(p is left.second_physical_bend for p in first_bends) == 1
        assert not any(p is left.second_physical_bend for p in next_bends)
        assert len(win._saved_endcap_pair_2d_canvases) == 2
        assert (win._saved_endcap_pair_combined_check is not None) is has_one_sheet
        assert (win._saved_endcap_pair_combined_canvas is not None) is has_one_sheet
        if has_one_sheet:
            assert len(win._saved_endcap_pair_2d_notebook.tabs()) == 2
            result = win._saved_endcap_pair_combined_check
            assert tuple(result.original_finite_bends) == tuple(first_bends)
            contour = _check_polygon(win._saved_endcap_pair_combined_scene)
            assert contour.area == pytest.approx(result.combined_area_mm2, abs=1e-6)
            datum_lines = [
                p for p in win._saved_endcap_pair_combined_scene.primitives
                if isinstance(p, LinePrimitive) and p.layer == "DATUM"
            ]
            assert len(datum_lines) == len(first_bends)
            assert [(p.p1, p.p2) for p in datum_lines] == [
                (p.p1, p.p2) for p in first_bends
            ]
        else:
            assert len(win._saved_endcap_pair_2d_notebook.tabs()) == 1
        assert win._saved_endcap_pair_3d_figure is None
        assert "不提供雙角合成 3D" in win._saved_endcap_pair_3d_warning.cget("text")
        assert path.read_bytes() == saved_bytes
        close_saved_live_check_window(fresh)

        # Source drift still rejects both records, never an old single page.
        fresh.w_var.set("410")
        messages.clear()
        fresh.v_miter_check_source_button.invoke()
        assert any(k == "error" for k, _ in messages)
        assert getattr(fresh, "_endcap_live_saved_check_window", None) is None
        assert path.read_bytes() == saved_bytes
    finally:
        if new_root is not None:
            new_root.destroy()
        root.destroy()


def test_grouped_replay_plain_dict_and_legacy_view_still_supported(monkeypatch):
    """An ordinary pre-envelope dict caller remains exactly the old API."""
    from gui_modules.application.endcap_live_v_check_consumer import (
        replay_current, project_current_tail_pair_one_sheet_2d,
    )
    from gui_modules.application.endcap_live_v_check_view import (
        show_saved_endcap_live_bottom_pair_window,
    )
    messages = []
    monkeypatch.setattr(
        messagebox, "showinfo", lambda *a, **k: messages.append(("info", a))
    )
    monkeypatch.setattr(
        messagebox, "showerror", lambda *a, **k: messages.append(("error", a))
    )
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        app.v_miter_capture_live_source_button.invoke()
        assert not any(k == "error" for k, _ in messages), messages
        snapshot = app._make_original_fold_designer_snapshot()
        plain = replay_current(app, snapshot)
        assert type(plain) is dict and set(plain) == set(CORNERS)
        # Old helper keeps its old direct dict caller behavior with the
        # normal authoritative cache; it must not require a new envelope.
        candidate = project_current_tail_pair_one_sheet_2d(
            app, snapshot, plain,
        )
        assert candidate.manufacturing_status.endswith("UNCERTIFIED")
        legacy = show_saved_endcap_live_bottom_pair_window(
            app, plain, getattr(app, ATTR)["tail"],
        )
        assert legacy._saved_endcap_pair_source_envelope is None
        assert len(legacy._saved_endcap_pair_2d_canvases) == 2
        assert legacy._saved_endcap_pair_combined_canvas is None
        close_saved_live_check_window(app)
        assert not legacy.winfo_exists()
    finally:
        root.destroy()
