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


def test_r_tip_disconnected_full_sheet_must_fail_closed_instead_of_faking_cutting():
    # A valid local R/BA mesh preview need not result in one manufacturable
    # whole-sheet contour. Its detached topology is an actual manufacturing
    # blocker, not a reason to silently discard the extra material island.
    scene, first, second, args, calib = _scene("ROUND_R")
    before = tuple(scene.primitives)
    with pytest.raises(GeometryError, match="cannot keep one closed sheet"):
        manufacturing_api.build_v_miter_radius_ba_full_sheet_check_scene(
            scene, first, second, **args, **calib)
    assert tuple(scene.primitives) == before


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
