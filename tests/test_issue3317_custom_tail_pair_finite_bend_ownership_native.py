"""#3317 Custom Tail two-bottom-V 3D HARD GATE: source-UV finite-tip owner.

This is *not* a new 3D or V solver. It uses one actual #3422 ROUND_R
flat/check, the original finite BEND and the existing WHD formed-profile
finite-guide mapper to expose a discontinuity if a source-connected panel
cannot be given exactly one rigid owner near the original endpoint.

No altered BEND/CUTTING, no assumed nominal D4 V90, no DXF or 3D export.
"""
from __future__ import annotations

from base64 import b85encode
from json import dumps
from math import hypot
import tkinter as tk
import warnings
import zlib

import pytest
from shapely.geometry import Point, Polygon

from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry_folded_mesh import _profile_map_with_guides
from ae_engine.manufacturing_render_data import fold_guides_from_final_scene
from ae_engine.sheetmetal_drawing import PolylinePrimitive
from gui import BoxCalculatorGUI
from gui_modules.application.endcap_live_v_check_consumer import _selected_source
from tests.test_issue3317_custom_tail_bottom_pair_native import (
    CORNERS, _make_tail_pair,
)


def test_true_custom_tail_round_r_finite_bend_tip_owner_before_any_3d():
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        _part, _target, spec, render = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        assert spec.is_tail and spec.model_name is None and not spec.holes
        checks = {
            side: api.project_operator_v_miter_live_corner_check(
                spec, render, side, first_bend_axis="x", relief_mode="ROUND_R",
            )
            for side in CORNERS
        }
        flat = api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
            spec, render, checks,
        )
        outline = next(p for p in flat.scene.primitives
                       if isinstance(p, PolylinePrimitive) and p.layer == "CHECK")
        original = next(p for p in render.scene.primitives
                        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING")
        stock = Polygon([(p.x,p.y) for p in outline.points])
        assert stock.is_valid and not stock.interiors
        assert flat.combined_area_mm2 > flat.source_area_mm2
        bends = fold_guides_from_final_scene(render.scene)
        assert len(bends) == len(flat.original_finite_bends)
        x_guides = sorted((b for b in bends if b.axis == "x"),key=lambda b:b.position)
        y_guides = sorted((b for b in bends if b.axis == "y"),key=lambda b:b.position)
        assert len(x_guides)==2 and len(y_guides)==3
        first_y = y_guides[0]
        assert checks["bottom_left"].second_physical_bend is checks[
            "bottom_right"].second_physical_bend
        assert all(any(row is physical for row in flat.original_finite_bends)
                   for physical in (
                       checks["bottom_left"].first_physical_bend,
                       checks["bottom_right"].first_physical_bend,
                       checks["bottom_left"].second_physical_bend,
                   ))
        # True first tip gap (NOT a W-specific constant or extended crease).
        left,right = x_guides
        assert abs(left.span_start-first_y.position)>1e-7
        assert abs(right.span_start-first_y.position)>1e-7
        # Internal, positive-area stock on both sides of each finite tip.
        # The probe derives distance from the actual physical X/Y stations.
        gap=left.span_start-first_y.position
        xprobe=left.position-gap*0.40
        margin=gap*0.04
        side_samples=((xprobe,left.span_start-margin),
                      (xprobe,left.span_start+margin))
        lower_y=first_y.position-gap*0.40
        lower_samples=((first_y.span_start-margin,lower_y),
                       (first_y.span_start+margin,lower_y))
        for p in side_samples+lower_samples:
            assert stock.contains(Point(*p)), (
                "finite BEND tip is outside remaining real material: "+str(p)
            )
            assert stock.boundary.distance(Point(*p))>margin*0.5
        before=_profile_map_with_guides(
            xprobe,side_samples[0][1],spec.fold_profile_x,
            axis="x",fold_guides=bends,
        )
        after=_profile_map_with_guides(
            xprobe,side_samples[1][1],spec.fold_profile_x,
            axis="x",fold_guides=bends,
        )
        left_gap=hypot(before[0]-after[0],before[1]-after[1])
        bottom_before=_profile_map_with_guides(
            lower_y,lower_samples[0][0],spec.fold_profile_y,
            axis="y",fold_guides=bends,
        )
        bottom_after=_profile_map_with_guides(
            lower_y,lower_samples[1][0],spec.fold_profile_y,
            axis="y",fold_guides=bends,
        )
        bottom_gap=hypot(
            bottom_before[0]-bottom_after[0],
            bottom_before[1]-bottom_after[1],
        )
        # A nonzero limiting X-first jump on one connected source region
        # means this legacy finite guide cannot assign a unique rigid
        # planar owner here. Rendering a whole solid would hide a tear.
        assert left_gap>1e-5
        assert bottom_gap>1e-5

        # Render evidence is wholly measured from the original Engine source.
        # GitHub CI prints compressed compact polygon/bend/probe coordinates
        # for a real-source 2D obstruction diagram, NOT invented 3D mesh.
        def xy(points):
            return [[round(p.x,7),round(p.y,7)] for p in points]
        data={
            "source":"WHD_LOCALX_#3422_CUSTOM_TAIL_ROUND_R_TRUE_ENGINE",
            "dimensions":{k:getattr(spec,k) for k in (
                "width","depth","height","thickness","fold_left",
                "fold_right","fold_bottom","fold_top","frame_width"
            )},
            "original_flat_cutting":xy(original.points),
            "candidate_one_sheet_round_r_flat":xy(outline.points),
            "actual_finite_bends":[
                [g.axis,round(g.position,7),round(g.span_start,7),
                 round(g.span_end,7)] for g in bends
            ],
            "original_y_profile":[
                [seg.phase6_key,seg.length,seg.angle] for seg in spec.fold_profile_y
            ],
            "original_x_profile":[
                [seg.phase6_key,seg.length,seg.angle] for seg in spec.fold_profile_x
            ],
            "left_tip":{
                "side_samples":side_samples,"folded_x_before":before,
                "folded_x_after":after,"jump_mm":round(left_gap,9),
            },
            "bottom_tip":{
                "side_samples":lower_samples,"folded_y_before":bottom_before,
                "folded_y_after":bottom_after,"jump_mm":round(bottom_gap,9),
            },
            "original_area":round(flat.source_area_mm2,9),
            "one_sheet_area":round(flat.combined_area_mm2,9),
        }
        packed=b85encode(zlib.compress(dumps(data,separators=(",",":")).encode(),9)).decode()
        warnings.warn("WHD_3317_TRUE_SOURCE_UV_B85="+packed,stacklevel=1)
    finally:
        root.destroy()


def test_true_custom_tail_round_r_outer_edges_retain_source_length_after_both_folds():
    """RED until a real finite-tip same-sheet 3D map preserves the four 1-mm edges.

    Original Factory CUTTING/BEND and the ROUND_R CHECK source are read only.
    The two independent legacy profile masks are intentionally the thing under
    test; no fake extended BEND, patched polygon or relaxed edge tolerance.
    """
    from math import dist
    from shapely.geometry import LineString

    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        _, _, spec, render = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        original_wkb = render.material.wkb
        original_scene = tuple(render.scene.primitives)
        checks = {
            side: api.project_operator_v_miter_live_corner_check(
                spec, render, side, first_bend_axis="x", relief_mode="ROUND_R",
            )
            for side in CORNERS
        }
        flat = api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
            spec, render, checks,
        )
        candidate = next(p for p in flat.scene.primitives
                         if isinstance(p, PolylinePrimitive) and p.layer == "CHECK")
        stock = Polygon([(p.x, p.y) for p in candidate.points])
        assert stock.is_valid and not stock.interiors

        original = next(p for p in original_scene
                        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING")
        xmin = min(p.x for p in original.points)
        xmax = max(p.x for p in original.points)
        ymin = min(p.y for p in original.points)
        bends = fold_guides_from_final_scene(render.scene)
        left, right = sorted(
            (g for g in bends if g.axis == "x"), key=lambda g: g.position
        )
        bottom = min((g for g in bends if g.axis == "y"),
                     key=lambda g: g.position)
        assert (left.position, right.position, bottom.position) == pytest.approx(
            (15., 407., 15.)
        )
        assert (left.span_start, right.span_start,
                bottom.span_start, bottom.span_end) == pytest.approx(
            (16., 16., 16., 406.)
        )
        edges = {
            "side_left": ((xmin, bottom.position), (xmin, left.span_start)),
            "side_right": ((xmax, bottom.position), (xmax, right.span_start)),
            "bottom_left": ((left.position, ymin), (bottom.span_start, ymin)),
            "bottom_right": ((bottom.span_end, ymin), (right.position, ymin)),
        }

        def native_xyz(xy):
            x, y = xy
            ux, zx = _profile_map_with_guides(
                x, y, spec.fold_profile_x, axis="x", fold_guides=bends,
            )
            uy, zy = _profile_map_with_guides(
                y, x, spec.fold_profile_y, axis="y", fold_guides=bends,
            )
            return (ux, uy, zx + zy)

        measured = {}
        for name, (a, b) in edges.items():
            raw = hypot(a[0]-b[0], a[1]-b[1])
            mapped = dist(native_xyz(a), native_xyz(b))
            measured[name] = {
                "source_mm": round(raw, 8),
                "formed_mm": round(mapped, 8),
                "candidate_boundary_distance_mm": round(
                    stock.boundary.distance(LineString((a, b))), 8
                ),
            }
            assert raw == pytest.approx(1., abs=1e-8)
        assert render.material.wkb == original_wkb
        assert tuple(render.scene.primitives) == original_scene
        # The actual acceptance assertion, not a test that expects distortion.
        # Report ALL four measured edges before failing for easy repair.
        assert all(
            abs(row["formed_mm"] - row["source_mm"]) <= 1e-5
            for row in measured.values()
        ), ("CUSTOM_TAIL_FINITE_TIP_NON_ISOMETRIC_3D", measured)
    finally:
        root.destroy()


def test_true_custom_tail_relief_hole_still_refuses_unverified_one_sheet_3d():
    """Do not use a ROUND_R-only joined CHECK to fake RELIEF_HOLE or source."""
    from ae_engine.sheetmetal_geometry_core import GeometryError
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "RELIEF_HOLE")
        _, _, spec, render = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        before_material = render.material.wkb
        before_scene = tuple(render.scene.primitives)
        checks = {
            side: api.project_operator_v_miter_live_corner_check(
                spec, render, side, first_bend_axis="x",
                relief_mode="RELIEF_HOLE",
            )
            for side in CORNERS
        }
        with pytest.raises(
            GeometryError, match="V_MITER_TAIL_PAIR_2D_ROUND_R_SOURCE_REQUIRED"
        ):
            api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
                spec, render, checks,
            )
        assert render.material.wkb == before_material
        assert tuple(render.scene.primitives) == before_scene
    finally:
        root.destroy()


def test_true_custom_tail_engine_rejects_joined_3d_from_source_edge_measurement():
    """The original 2D/3D survives; joined V-3D is NOT claimed repaired."""
    from ae_engine.sheetmetal_geometry_core import GeometryError
    from ae_engine.assembly_geometry_folded_mesh import folded_mesh_from_polygon

    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        _, _, spec, render = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        before = render.material.wkb, tuple(render.scene.primitives)
        guides = fold_guides_from_final_scene(render.scene)
        original_formed = folded_mesh_from_polygon(
            render.material, spec.fold_profile_x, spec.fold_profile_y,
            fold_guides=guides,
        )
        assert original_formed
        checks = {
            side: api.project_operator_v_miter_live_corner_check(
                spec, render, side, first_bend_axis="x", relief_mode="ROUND_R",
            )
            for side in CORNERS
        }
        pair = api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
            spec, render, checks,
        )
        assert pair.formed_3d_rejection == (
            "V_MITER_TAIL_PAIR_3D_FINITE_TIP_STRETCH_REJECTED"
        )
        assert [name for name, _, _ in pair.finite_tip_edge_lengths_mm] == [
            "side_left", "side_right", "bottom_left", "bottom_right"
        ]
        for name, before_mm, after_mm in pair.finite_tip_edge_lengths_mm:
            assert before_mm == pytest.approx(1., abs=1e-7), name
            assert after_mm == pytest.approx(21.23676058, abs=1e-6), name
        with pytest.raises(
            GeometryError, match="V_MITER_TAIL_PAIR_3D_FINITE_TIP_STRETCH_REJECTED"
        ):
            pair.require_formed_3d_check()
        assert (render.material.wkb, tuple(render.scene.primitives)) == before
        assert folded_mesh_from_polygon(
            render.material, spec.fold_profile_x, spec.fold_profile_y,
            fold_guides=guides,
        ) == original_formed
    finally:
        root.destroy()


@pytest.mark.parametrize("x", (1.0, 421.0))
@pytest.mark.parametrize("uv_span", (0.2, 0.02, 0.002))
def test_custom_tail_finite_tip_public_engine_map_is_discontinuous_inside_source(x, uv_span):
    """Real Tk, actual candidate UV and PUBLIC Engine: a mesh cannot fix this.

    Red geometry acceptance remains separately enforced. This is positive
    counterexample evidence that the current mapper has a finite jump even
    on a vanishingly short line of continuous interior material. No virtual
    crease, assumed radius or altered Factory stock.
    """
    from math import dist
    from shapely.geometry import LineString

    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        _, _, spec, render = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        source = (render.material.wkb, tuple(render.scene.primitives))
        checks = {
            side: api.project_operator_v_miter_live_corner_check(
                spec, render, side, first_bend_axis="x", relief_mode="ROUND_R",
            )
            for side in CORNERS
        }
        combined = api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
            spec, render, checks,
        )
        outline = next(
            p for p in combined.scene.primitives
            if isinstance(p, PolylinePrimitive) and p.layer == "CHECK"
        )
        stock = Polygon([(p.x, p.y) for p in outline.points])
        guides = fold_guides_from_final_scene(render.scene)
        left, right = sorted(
            (g for g in guides if g.axis == "x"), key=lambda g: g.position
        )
        selected = left if x == 1. else right
        assert (selected.position, selected.span_start) == pytest.approx(
            (15., 16.) if x == 1. else (407., 16.)
        )
        a = (x, selected.span_start - uv_span / 2)
        b = (x, selected.span_start + uv_span / 2)
        segment = LineString((a, b))
        assert segment.length == pytest.approx(uv_span, abs=1e-10)
        assert stock.contains(Point(*a)) and stock.contains(Point(*b))
        assert stock.covers(segment), (a, b)
        before = api.fold_profile_map_with_guides(
            a[0], a[1], spec.fold_profile_x, axis="x", fold_guides=guides,
        )
        after = api.fold_profile_map_with_guides(
            b[0], b[1], spec.fold_profile_x, axis="x", fold_guides=guides,
        )
        formed = dist(before, after)
        # Dot's direct source samples are W400/D250/T2 regression evidence,
        # not universal dimensions or allowable material stretching.
        assert 19.7 < formed < 20.1, (x, uv_span, formed)
        # With a correct continuous two-V map, this assertion will have to
        # change to an actual near-zero limiting jump, not a test waiver.
        if uv_span == 0.002:
            assert formed / uv_span > 9000
        assert source == (render.material.wkb, tuple(render.scene.primitives))
    finally:
        root.destroy()


def test_custom_tail_original_finite_x_y_guides_still_move_without_new_bends():
    """Existing original source and both actual folds keep their own route."""
    from math import dist
    from ae_engine.assembly_geometry_folded_mesh import folded_mesh_from_polygon
    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        _, _, spec, render = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        original = (render.material.wkb, tuple(render.scene.primitives))
        guides = fold_guides_from_final_scene(render.scene)
        xs = sorted((g for g in guides if g.axis == "x"), key=lambda g:g.position)
        ys = sorted((g for g in guides if g.axis == "y"), key=lambda g:g.position)
        assert tuple(g.position for g in xs) == pytest.approx((15., 407.))
        assert tuple(g.span_start for g in xs) == pytest.approx((16., 16.))
        bottom = ys[0]
        assert (bottom.position, bottom.span_start, bottom.span_end) == pytest.approx(
            (15., 16., 406.)
        )
        for x, guide in ((1., xs[0]), (421., xs[1])):
            active = api.fold_profile_map_with_guides(
                x, (guide.span_start + guide.span_end)/2,
                spec.fold_profile_x, axis="x", fold_guides=guides,
            )
            inactive = api.fold_profile_map_with_guides(
                x, guide.span_start - 0.1,
                spec.fold_profile_x, axis="x", fold_guides=guides,
            )
            assert dist(active, inactive) > 19.7
        active_y = api.fold_profile_map_with_guides(
            1., (bottom.span_start + bottom.span_end)/2,
            spec.fold_profile_y, axis="y", fold_guides=guides,
        )
        inactive_y = api.fold_profile_map_with_guides(
            1., bottom.span_start - 0.1,
            spec.fold_profile_y, axis="y", fold_guides=guides,
        )
        assert dist(active_y, inactive_y) > 1.
        original_mesh = folded_mesh_from_polygon(
            render.material, spec.fold_profile_x, spec.fold_profile_y,
            fold_guides=guides,
        )
        assert original_mesh
        assert original == (render.material.wkb, tuple(render.scene.primitives))
        assert original_mesh == folded_mesh_from_polygon(
            render.material, spec.fold_profile_x, spec.fold_profile_y,
            fold_guides=guides,
        )
    finally:
        root.destroy()


def test_custom_tail_original_vs_v_tip_material_and_triangle_control():
    """Real canonical original-vs-ROUND_R finite-tip source topology control.

    Compare the two source polygons and 3D tessellation without assuming the
    factory old corner is disconnected: perimeter parity alone does not prove
    an interior local 3D map continuous. Explicitly report original coverage.
    """
    from json import dumps
    from shapely.geometry import LineString
    from ae_engine.assembly_geometry_folded_mesh import folded_mesh_from_polygon

    root = tk.Tk()
    root.withdraw()
    try:
        app = BoxCalculatorGUI(root)
        _make_tail_pair(app, "ROUND_R")
        _, _, spec, render = _selected_source(
            app, app._make_original_fold_designer_snapshot(),
        )
        before = render.material.wkb, tuple(render.scene.primitives)
        checks = {
            side: api.project_operator_v_miter_live_corner_check(
                spec, render, side, first_bend_axis="x", relief_mode="ROUND_R",
            )
            for side in CORNERS
        }
        combined = api.project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
            spec, render, checks,
        )
        source_line = next(
            p for p in combined.scene.primitives
            if isinstance(p, PolylinePrimitive) and p.layer == "CHECK"
        )
        sheet = Polygon([(p.x, p.y) for p in source_line.points])
        guides = fold_guides_from_final_scene(render.scene)
        original_mesh = folded_mesh_from_polygon(
            render.material, spec.fold_profile_x, spec.fold_profile_y,
            fold_guides=guides,
        )
        candidate_mesh = folded_mesh_from_polygon(
            sheet, spec.fold_profile_x, spec.fold_profile_y,
            fold_guides=guides,
        )
        assert original_mesh and candidate_mesh
        assert sheet.is_valid and not sheet.interiors
        evidence = {
            "original_flat_area_mm2": round(render.material.area, 9),
            "candidate_flat_area_mm2": round(sheet.area, 9),
            "original_3d_triangles": len(original_mesh),
            "wrong_unverified_v_3d_triangles": len(candidate_mesh),
            "points": [],
        }
        for label, x in (("left", 1.), ("right", 421.)):
            for span in (0.2, 0.02, 0.002):
                segment = LineString(((x, 16.-span/2.), (x, 16.+span/2.)))
                evidence["points"].append({
                    "side": label,
                    "uv_mm": span,
                    "original_has_continuous_strip": render.material.covers(segment),
                    "new_v_has_continuous_strip": sheet.covers(segment),
                    "original_boundary_distance_mm": round(
                        render.material.boundary.distance(segment), 9),
                    "new_v_boundary_distance_mm": round(
                        sheet.boundary.distance(segment), 9),
                })
                # Verified exact sample: original Factory corner removes
                # this cross-tip bridge, while ROUND_R creates real material.
                # Original 3D perimeter parity is not a joined-V solution.
                assert not render.material.covers(segment)
                assert sheet.covers(segment)
        assert (render.material.wkb, tuple(render.scene.primitives)) == before
        warnings.warn(
            "WHD_3317_ORIGINAL_V_TOPOLOGY_CONTROL="+dumps(
                evidence, ensure_ascii=True, separators=(",", ":")),
            stacklevel=1,
        )
    finally:
        root.destroy()
