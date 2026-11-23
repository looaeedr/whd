"""#3317 first shared V CHECK slice: physical EndCap Bend/Fold source, not CNC.

These are explicit existing Head/Tail PartSpec/FinalScene source fixtures; they
are regression inputs and never certify a new fifth manufacturing CornerType.
"""
from dataclasses import replace

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec, FoldProfileSegment
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from ae_engine.v_miter_trial_snapshot import _bound_endcap_fold_sha256


def _source(second_angle=90, *, y_bottom=20, x_angle=90, tail=False):
    outline = (Vec2(0, 0), Vec2(200, 0), Vec2(200, 200), Vec2(0, 200))
    x1 = LinePrimitive(Vec2(20, 20), Vec2(20, 180), "BEND")
    x2 = LinePrimitive(Vec2(180, 20), Vec2(180, 180), "BEND")
    y1 = LinePrimitive(Vec2(20, y_bottom), Vec2(180, y_bottom), "BEND")
    y2 = LinePrimitive(Vec2(20, 180), Vec2(180, 180), "BEND")
    scene = DrawingScene([
        PolylinePrimitive(outline, "CUTTING", closed=True),
        x1, x2, y1, y2,
    ])
    render = PartRenderData(scene=scene, material=Polygon([(p.x, p.y) for p in outline]))
    spec = EndCapPartSpec(
        width=200, depth=200, thickness=2, frame_width=20,
        is_tail=tail, fold_left=20, fold_right=20,
        fold_bottom=y_bottom, fold_top=20,
        fold_profile_x=(
            FoldProfileSegment(20, angle=-x_angle),
            FoldProfileSegment(160, angle=-90),
            FoldProfileSegment(20),
        ),
        fold_profile_y=(
            FoldProfileSegment(y_bottom, angle=-second_angle),
            FoldProfileSegment(180-y_bottom, angle=-90),
            FoldProfileSegment(20),
        ),
    )
    return spec, render, x1, y1


@pytest.mark.parametrize("tail", (False, True))
@pytest.mark.parametrize("second_angle", (60, 90, 120))
@pytest.mark.parametrize("y_bottom", (20, 35))
def test_live_corner_uses_authored_actual_two_bends_and_angles(tail, second_angle, y_bottom):
    spec, render, real_x, real_y = _source(second_angle, y_bottom=y_bottom, tail=tail)
    before = tuple(render.scene.primitives)
    live = api.project_operator_v_miter_live_corner_check(
        spec, render, "bottom_left", first_bend_axis="x",
    )
    assert live.part_key == ("tail" if tail else "head")
    assert live.first_bend_axis == "x"
    assert live.second_bend_axis == "y"
    assert live.ideal.source.first_fold_angle_deg == 90
    assert live.second_fold_angle_deg == second_angle
    assert live.first_physical_bend is real_x
    assert live.second_physical_bend is real_y
    assert live.first_signed_fold_angle_deg == -90
    assert live.second_signed_fold_angle_deg == -second_angle
    assert live.first_flange_height_mm == 20
    assert live.second_flange_height_mm == y_bottom
    assert tuple(render.scene.primitives) == before
    assert live.manufacturing_status.endswith("UNCERTIFIED")


def test_explicit_y_first_with_non90_x_angle_follows_part_spec_not_x_fallback():
    spec, render, _, _ = _source(90, x_angle=60)
    chosen = api.project_operator_v_miter_live_corner_check(
        spec, render, "bottom_left", first_bend_axis="y",
    )
    assert chosen.first_bend_axis == "y"
    assert chosen.second_fold_angle_deg == 60
    with pytest.raises(GeometryError, match="SELECTED_FIRST_BEND_NOT_90"):
        api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", first_bend_axis="x",
        )


def test_no_explicit_first_and_bad_direction_are_rejected():
    spec, render, _, _ = _source(120)
    with pytest.raises(GeometryError, match="FIRST_BEND_REQUIRED"):
        api.project_operator_v_miter_live_corner_check(spec, render, "bottom_left")
    altered = replace(spec, fold_profile_y=(
        replace(spec.fold_profile_y[0], angle=120),
        *spec.fold_profile_y[1:],
    ))
    with pytest.raises(GeometryError, match="OPPOSITE_FOLD_SENSE"):
        api.project_operator_v_miter_live_corner_check(
            altered, render, "bottom_left", first_bend_axis="x",
        )


def test_decoy_and_drift_cannot_reselect_nearest_or_ambiguous_bend():
    spec, render, real_x, real_y = _source(60)
    decoy = LinePrimitive(Vec2(19.9, 20), Vec2(19.9, 180), "BEND")
    render.scene.primitives.append(decoy)
    live = api.project_operator_v_miter_live_corner_check(
        spec, render, "bottom_left", first_bend_axis="x",
    )
    assert live.second_fold_angle_deg == 60
    render.scene.primitives.remove(real_x)
    with pytest.raises(GeometryError, match="PARTSPEC_BEND_SOURCE_MISMATCH"):
        api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", first_bend_axis="x",
        )
    render.scene.primitives.append(real_x)
    render.scene.primitives.append(LinePrimitive(real_x.p1, real_x.p2, "BEND"))
    with pytest.raises(GeometryError, match="AMBIGUOUS_BOUND_BEND_SOURCE"):
        api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", first_bend_axis="x",
        )


@pytest.mark.parametrize("second_angle", (60, 90, 120))
def test_new_snapshot_fold_fingerprint_detects_same_scene_but_changed_authored_angle(second_angle):
    spec, render, real_x, real_y = _source(second_angle)
    sha = _bound_endcap_fold_sha256(
        spec, render.scene, real_x, real_y, "bottom_left",
        second_angle_deg=second_angle,
    )
    assert len(sha) == 64
    changed = replace(spec, fold_profile_y=(
        replace(spec.fold_profile_y[0], angle=-90 if second_angle != 90 else -120),
        *spec.fold_profile_y[1:],
    ))
    with pytest.raises(GeometryError, match="AUTHORED_FOLD_ANGLE_MISMATCH"):
        _bound_endcap_fold_sha256(
            changed, render.scene, real_x, real_y, "bottom_left",
            second_angle_deg=second_angle,
        )


@pytest.mark.parametrize("angle", (90,))
def test_source_bound_v1_trial_replay_rejects_fold_drift_and_unbound_legacy(angle):
    # Only this fixture's 90-degree rays hit the real rectangular perimeter;
    # 60/120 is covered by live real-source and authored fingerprint tests.
    spec, render, real_x, real_y = _source(angle)
    kwargs = dict(
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=20, second_fold_angle_deg=angle,
        relief_mode="RELIEF_HOLE", relief_t_factor=1,
    )
    saved = api.capture_v_miter_relief_trial_snapshot(
        render.scene, real_x, real_y, **kwargs,
        part_spec=spec, corner_key="bottom_left",
    )
    assert saved["source_fold_sha256"]
    assert saved["source_corner_key"] == "bottom_left"
    rebuilt = api.replay_v_miter_relief_trial_snapshot(
        render.scene, saved, part_spec=spec,
    )
    assert rebuilt.manufacturing_status.endswith("UNCERTIFIED")
    with pytest.raises(GeometryError, match="CURRENT_PARTSPEC_REQUIRED"):
        api.replay_v_miter_relief_trial_snapshot(render.scene, saved)
    changed = replace(spec, fold_profile_y=(
        replace(spec.fold_profile_y[0], angle=-120 if angle != 120 else -60),
        *spec.fold_profile_y[1:],
    ))
    with pytest.raises(GeometryError, match="AUTHORED_FOLD"):
        api.replay_v_miter_relief_trial_snapshot(
            render.scene, saved, part_spec=changed,
        )
    old = api.capture_v_miter_relief_trial_snapshot(
        render.scene, real_x, real_y, **kwargs,
    )
    assert "source_fold_sha256" not in old
    with pytest.raises(GeometryError, match="LEGACY_FOLD_UNBOUND"):
        api.replay_v_miter_relief_trial_snapshot(
            render.scene, old, part_spec=spec,
        )
