"""#3317 CHECK-only single-piece V-trim reprojection: real original stock and 3D parity."""
from __future__ import annotations

import math

import ezdxf
import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project


def _scene(mode="RELIEF_HOLE"):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    source = dict(thickness_mm=2, first_flange_height_mm=20,
                  second_flange_height_mm=30, second_fold_angle_deg=90,
                  relief_mode=mode, relief_t_factor=1.5)
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **source)
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    outline = PolylinePrimitive((
        Vec2(-100, a.y), Vec2(b.x, a.y), Vec2(b.x, 0),
        Vec2(30, 10), Vec2(30, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    calibration = dict(
        first_inner_radius_mm=.5, second_inner_radius_mm=.5,
        first_bend_allowance_mm=math.pi / 2 * 1.3,
        second_bend_allowance_mm=math.pi / 2 * 1.3,
        max_permitted_edge_trim_mm=12,
    )
    return DrawingScene([outline, first, second]), first, second, source, calibration


def test_hole_tip_full_sheet_reprojection_preserves_second_flange_and_real_source_area(tmp_path):
    scene, first, second, params, calibration = _scene("RELIEF_HOLE")
    before = tuple(scene.primitives)
    out = manufacturing_api.project_v_miter_radius_ba_full_sheet_check(
        scene, first, second, **params, **calibration)
    assert out.manufacturing_status.endswith("UNCERTIFIED")
    assert out.trial.manufacturing_status.endswith("UNCERTIFIED")
    assert out.full_source_area_mm2 >= out.full_corrected_area_mm2
    assert out.actual_removed_trim_area_mm2 == pytest.approx(
        out.full_source_area_mm2 - out.full_corrected_area_mm2)
    assert out.actual_removed_trim_area_mm2 == pytest.approx(
        out.trial.first_flat_source_area_mm2 - out.trial.first_flat_trimmed_area_mm2)
    assert out.trial.second_flat_source_area_mm2 > 0
    corrected = Polygon([(p.x, p.y) for p in out.corrected_check_outline])
    assert corrected.is_valid and not corrected.interiors
    assert corrected.area == pytest.approx(out.full_corrected_area_mm2)
    assert out.trial.no_detected_noncoplanar_crossings

    # There is one whole-sheet CHECK contour; not just a local flange patch.
    preview = manufacturing_api.build_v_miter_radius_ba_full_sheet_check_scene(
        scene, first, second, **params, **calibration)
    assert [row.layer for row in preview.primitives] == [
        "DATUM", "CHECK", "DATUM", "DATUM"]
    assert preview.primitives[1].points == out.corrected_check_outline
    file = tmp_path / "calibrated_v_CHECK_only.dxf"
    save_scene_dxf(file, preview)
    reopened = list(ezdxf.readfile(file).modelspace())
    assert [row.dxf.layer for row in reopened] == [
        "DATUM", "CHECK", "DATUM", "DATUM"]
    assert not any(row.dxf.layer in {"CUTTING", "BEND", "MARKING"} for row in reopened)
    assert tuple(scene.primitives) == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_true_saved_source_recomputes_same_r_ba_2d_3d_after_project_reload(tmp_path, family):
    from ae_engine.receiving_layout import new_receiving_layout

    scene, first, second, params, calibration = _scene()
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **params)
    snapshot = {
        "model": family, "w": 800, "h": 1600, "d": 350, "t": 2,
        "v_miter_trial_preview": captured,
        # These are operator-supplied trial inputs, not a manufacturing
        # policy or certified geometry serialized as source truth.
        "v_miter_r_ba_trial_inputs": calibration,
    }
    if family == "受電箱":
        snapshot["active_mode"] = "set_bay"
        snapshot["receiving_layout"] = new_receiving_layout(
            width=800, height=1600, depth=350)
    filename = write_project(tmp_path / "v_miter_r_ba.p6fold", {
        "schema": PROJECT_SCHEMA_V1, "snapshot": snapshot})
    saved = read_project(filename)["snapshot"]
    assert saved["v_miter_trial_preview"] == captured
    assert saved["v_miter_r_ba_trial_inputs"] == calibration
    rebuilt = DrawingScene([
        PolylinePrimitive(tuple(Vec2(p.x, p.y) for p in scene.primitives[0].points),
                          "CUTTING", closed=True),
        LinePrimitive(first.p1, first.p2, "BEND"),
        LinePrimitive(second.p1, second.p2, "BEND"),
    ])
    assert rebuilt.primitives[1] is not first
    replay = manufacturing_api.replay_v_miter_relief_trial_snapshot(
        rebuilt, saved["v_miter_trial_preview"])
    assert replay.manufacturing_status.endswith("UNCERTIFIED")
    old = manufacturing_api.project_v_miter_radius_ba_full_sheet_check(
        scene, first, second, **params, **calibration)
    new = manufacturing_api.project_v_miter_radius_ba_full_sheet_check(
        rebuilt, rebuilt.primitives[1], rebuilt.primitives[2],
        **saved["v_miter_trial_preview"]["parameters"],
        **saved["v_miter_r_ba_trial_inputs"])
    assert old.corrected_check_outline == new.corrected_check_outline
    assert old.trial.trimmed_surface_interference_pairs == new.trial.trimmed_surface_interference_pairs
    assert old.trial.first_thick_solid_triangles == new.trial.first_thick_solid_triangles


def test_r_tip_source_preserving_trial_does_not_hide_remaining_true_T_overlap():
    # This real R/BA/T specimen cannot satisfy the volume diagnostic with
    # the original actual R-tip stock intact. An infinite offset used to
    # discard that stock, producing a split full sheet; preserving the root
    # must NOT promote an apparent zero-collision result.
    scene, first, second, args, calib = _scene("ROUND_R")
    before = tuple(scene.primitives)
    with pytest.raises(GeometryError, match="ROUND_R source-preserving trim still has detected"):
        manufacturing_api.project_v_miter_radius_ba_full_sheet_check(
            scene, first, second, **args, **calib)
    with pytest.raises(GeometryError, match="ROUND_R source-preserving trim still has detected"):
        manufacturing_api.build_v_miter_radius_ba_full_sheet_check_scene(
            scene, first, second, **args, **calib)
    assert tuple(scene.primitives) == before


def test_progressive_edge_trim_starts_only_after_actual_relief_contact_source():
    # Unit-test the physical 2D trim operator on one actual positive-area
    # flange. The open R/hole root lies on the unmodified side of the
    # measured cutback; do not invent new material or leave disconnected
    # islands while interpolating towards the diagnostic offset.
    from shapely.geometry import Point, box
    from ae_engine.v_miter_radius_ba_interface_trial import _trim_one_v_edge

    patch = box(0, 0, 20, 12)
    apex, tip = Vec2(0, 0), Vec2(20, 0)
    cutback, trim = 3.0, 2.0
    corrected = _trim_one_v_edge(
        patch, apex, tip, trim, relief_open_length_mm=cutback,
    )
    removed = patch.difference(corrected)
    assert corrected.is_valid and corrected.geom_type == "Polygon"
    assert not corrected.interiors
    assert 0 < corrected.area < patch.area
    assert removed.area == pytest.approx(patch.area - corrected.area)
    assert corrected.difference(patch).area == 0
    assert removed.intersection(box(0, 0, cutback, 12)).area < 1e-8
    assert removed.intersection(Point(apex.x, apex.y).buffer(cutback - 1e-4)).area < 1e-8
    # Beyond the finite transition the full requested trim is applied.
    assert not corrected.contains(Point(19, 1))
    assert corrected.contains(Point(19, 3))
    with pytest.raises(GeometryError, match="relief cutback exhausts"):
        _trim_one_v_edge(
            patch, apex, tip, trim, relief_open_length_mm=21,
        )


def test_invalid_source_or_unset_trim_limit_does_not_emit_check_geometry():
    scene, first, second, args, calib = _scene()
    fake = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.build_v_miter_radius_ba_full_sheet_check_scene(
            scene, fake, second, **args, **calib)
    # R/BA can naturally eliminate some overlaps at zero additional edge
    # trim. A small *positive* trim limit is therefore NOT proof of failure.
    # Zero itself is an invalid operator source and must always be rejected.
    no_trim = dict(calib, max_permitted_edge_trim_mm=0)
    with pytest.raises(GeometryError, match="max_permitted_edge_trim_mm"):
        manufacturing_api.project_v_miter_radius_ba_full_sheet_check(
            scene, first, second, **args, **no_trim)



def test_real_source_single_sheet_gate_rejects_split_and_second_flange_shortening():
    from shapely.geometry import box
    from ae_engine.v_miter_radius_ba_interface_trial import _checked_full_source_from_trim
    source = box(0, 0, 10, 10)
    first = box(3, 0, 7, 10)
    second = box(8, 0, 10, 10)
    # A local candidate can remain a perfectly valid polygon yet turn
    # the single source sheet into two disconnected pieces after a 2D cut.
    with pytest.raises(GeometryError, match="cannot keep one closed sheet"):
        _checked_full_source_from_trim(source, first, box(3, 0, 4, 10), second)
    # A clearance cut that crosses second-flange material is not allowed,
    # even if both source and result remain mathematically connected.
    with pytest.raises(GeometryError, match="shorten the unmodified second flange"):
        _checked_full_source_from_trim(
            source, box(7, 0, 10, 4), box(7, 2, 10, 4), box(8, 0, 10, 4),
        )
    # A genuine boundary-connected trim conserves every source coordinate
    # outside the removed patch, and cannot invent cut material.
    keep, removed = _checked_full_source_from_trim(
        source, box(0, 0, 3, 4), box(1, 0, 3, 4), second,
    )
    assert keep.is_valid and keep.geom_type == "Polygon"
    assert not keep.interiors
    assert source.area == pytest.approx(keep.area + removed.area)
    assert keep.intersection(second).area == pytest.approx(second.area)



def test_permitted_maximum_is_not_required_to_be_a_destructive_trim():
    # A physical allowed maximum may overshoot all material. The SEARCH
    # must still find a smaller single-sheet candidate with zero detected
    # crossings, never use the invalid high candidate as evidence.
    from ae_engine.v_miter_radius_ba_interface_trial import _search_source_safe_edge_trim

    evaluated = []

    def evaluate(trim):
        evaluated.append(trim)
        if trim > 7:
            raise GeometryError("V-miter R/BA correction cannot keep one closed sheet")
        return ("source_checked", "skin", "solid", 0 if trim >= 4 else 3)

    original, best, selected = _search_source_safe_edge_trim(
        evaluate, 20, failure_message="no qualifying source-preserving trim",
    )
    assert original[3] == 3
    assert best[3] == 0
    assert 4 <= selected <= 7
    assert 20 in evaluated
    assert selected in evaluated
    assert best[0] == "source_checked"


def test_no_valid_source_preserving_candidate_never_reports_clearance():
    from ae_engine.v_miter_radius_ba_interface_trial import _search_source_safe_edge_trim

    def evaluate(trim):
        if trim > 3:
            raise GeometryError("V-miter trial trim destroys the single source flange patch")
        return ("source_checked", "skin", "solid", 1)

    with pytest.raises(GeometryError, match="cannot eliminate overlap"):
        _search_source_safe_edge_trim(
            evaluate, 18, failure_message="V-miter cannot eliminate overlap",
        )


def test_search_rejects_nonmonotone_source_invalidity_inside_valid_bracket():
    from ae_engine.v_miter_radius_ba_interface_trial import _search_source_safe_edge_trim

    def evaluate(trim):
        if 3.9 < trim < 4.1:
            raise GeometryError("V-miter R/BA correction cannot keep one closed sheet")
        return ("source_checked", "skin", "solid", 1 if trim < 6 else 0)

    with pytest.raises(GeometryError, match="cannot keep one closed sheet"):
        _search_source_safe_edge_trim(
            evaluate, 8, failure_message="V-miter cannot eliminate overlap",
        )


def test_round_r_source_scaled_transition_trims_the_colliding_edge_without_touching_root():
    from shapely.geometry import box
    from ae_engine.v_miter_radius_ba_interface_trial import _trim_one_v_edge

    patch = box(0, 0, 20, 12)
    apex, tip = Vec2(0, 0), Vec2(20, 0)
    cutback, edge_offset = 3.0, 4.0
    legacy = _trim_one_v_edge(
        patch, apex, tip, edge_offset, relief_open_length_mm=cutback,
    )
    local = _trim_one_v_edge(
        patch, apex, tip, edge_offset,
        relief_open_length_mm=cutback, transition_run_mm=cutback,
    )
    # The actual original R tangency and all stock before the real cutback
    # remain unchanged. Only the post-R V-edge ramp becomes steeper.
    untouched = box(0, 0, cutback, 12)
    assert patch.intersection(untouched).symmetric_difference(
        legacy.intersection(untouched)
    ).area < 1e-9
    assert patch.intersection(untouched).symmetric_difference(
        local.intersection(untouched)
    ).area < 1e-9
    assert 0 < local.area < legacy.area < patch.area
    assert local.is_valid and local.geom_type == "Polygon" and not local.interiors
    assert local.difference(patch).area == pytest.approx(0)
    assert local.intersection(box(0, 8, 20, 12)).area == pytest.approx(
        legacy.intersection(box(0, 8, 20, 12)).area
    )

    with pytest.raises(GeometryError, match="transition_run_mm"):
        _trim_one_v_edge(
            patch, apex, tip, edge_offset,
            relief_open_length_mm=cutback, transition_run_mm=0,
        )
    with pytest.raises(GeometryError, match="cannot exceed"):
        _trim_one_v_edge(
            patch, apex, tip, edge_offset,
            relief_open_length_mm=cutback, transition_run_mm=5,
        )


def test_shifted_round_r_retains_actual_radius_and_second_flange_source():
    # Independent physical CUTTING perimeter, not a guessed whole rectangle:
    # original V rays end at two real exterior points; a virtual one-sided
    # asymmetry keeps the second ray and R=3 while the first cut moves 4 mm.
    from shapely.geometry import box
    from ae_engine.v_miter_relief_trial import _rounded_v_notch_polygon
    from ae_engine.v_miter_radius_ba_interface_trial import (
        _retarget_round_r_first_v_edge, _checked_full_source_profile,
    )

    material = Polygon((
        (-100, -20), (20, -20), (20, 0),
        (30, 10), (30, 100), (-100, 100),
    ))
    apex, first_tip, second_tip = Vec2(0, 0), Vec2(0, -20), Vec2(20, 0)
    original_cut, tangency = _rounded_v_notch_polygon(
        apex, first_tip, second_tip,
        ((0, -20), (20, -20), (20, 0)), 3.0,
    )
    assert tangency == pytest.approx(3)
    remaining = material.difference(original_cut)
    first_source = remaining.intersection(box(-100, -20, 0, 0))
    second_source = remaining.intersection(box(0, 0, 30, 100))

    corrected = _retarget_round_r_first_v_edge(
        material, remaining, first_source,
        apex, first_tip, second_tip, radius=3, offset=4,
    )
    first_corrected = corrected.intersection(box(-100, -20, 0, 0))
    whole, removed = _checked_full_source_profile(
        remaining, corrected, first_source, first_corrected, second_source,
    )
    assert whole.geom_type == "Polygon" and whole.is_valid and not whole.interiors
    assert removed.area > 0
    assert whole.difference(remaining).area < 1e-7
    assert remaining.area - whole.area == pytest.approx(removed.area)
    assert whole.intersection(second_source).area == pytest.approx(second_source.area)
    assert first_corrected.area < first_source.area

    # The relocated tangent arc is the SAME circular R=3, centred at
    # (-offset+R, -R) relative to the unchanged physical BEND intersection.
    # No wedge was filled in and no second V cut boundary was moved.
    cut = material.difference(whole)
    same_r_arc = [
        (x, y) for x, y in cut.exterior.coords
        if -4.00001 <= x <= -0.99999 and -3.00001 <= y <= 0.00001
    ]
    assert len(same_r_arc) >= 10
    for x, y in same_r_arc:
        assert math.hypot(x - (-1.0), y - (-3.0)) == pytest.approx(3.0, abs=1e-6)
    with pytest.raises(GeometryError, match="outside source"):
        _retarget_round_r_first_v_edge(
            material, remaining, first_source,
            apex, first_tip, second_tip, radius=3, offset=200,
        )
    assert material.is_valid  # real source was not mutated
