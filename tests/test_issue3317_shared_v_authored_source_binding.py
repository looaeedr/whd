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
    # Internal readonly CHECK remains compatible; only the real GUI
    # requires an explicit first-fold operator choice.
    readonly = api.project_operator_v_miter_live_corner_check(
        spec, render, "bottom_left",
    )
    assert readonly.first_bend_axis == "x"
    assert readonly.manufacturing_status.endswith("UNCERTIFIED")
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
    # Adding an extra finite BEND makes keyless source ambiguous by design.
    # This test instead supplies the true X role to prove the decoy cannot
    # steal a *named* source. Separate test asserts keyless 3+ is rejected.
    spec = replace(spec, fold_profile_x=tuple(
        replace(row, phase6_key=key) for row, key in zip(
            spec.fold_profile_x, ("yl1", "endcap_w_core", "yr1"),
        )
    ))
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
        second_angle_deg=second_angle, thickness_mm=2,
        first_flange_height_mm=20, second_flange_height_mm=20,
    )
    assert len(sha) == 64
    changed = replace(spec, fold_profile_y=(
        replace(spec.fold_profile_y[0], angle=-90 if second_angle != 90 else -120),
        *spec.fold_profile_y[1:],
    ))
    with pytest.raises(GeometryError, match="AUTHORED_FOLD_ANGLE_MISMATCH"):
        _bound_endcap_fold_sha256(
            changed, render.scene, real_x, real_y, "bottom_left",
            second_angle_deg=second_angle, thickness_mm=2,
            first_flange_height_mm=20, second_flange_height_mm=20,
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


def _named_head_tail_source(*, tail=False, y_angle=90, x_left=20):
    """Real Engine EndCap Fold role order, including Head Y return third BEND.

    Physical BENDs are deliberately finite and all three Y stations share
    this same FinalScene; none can be selected by proximity.
    """
    y_bottom = 20
    frame = 25
    ret = 16
    core_y = 200 - y_bottom - frame - ret
    if tail:
        y_rows = (
            FoldProfileSegment(y_bottom, angle=-y_angle, phase6_key="ybottom1"),
            FoldProfileSegment(core_y, angle=-90, phase6_key="endcap_d_core"),
            FoldProfileSegment(frame, angle=-90, phase6_key="fw"),
            FoldProfileSegment(ret, phase6_key="ytop1"),
        )
        lower_y, upper_y, return_y = y_bottom, y_bottom + core_y, y_bottom + core_y + frame
    else:
        y_rows = (
            FoldProfileSegment(ret, angle=-90, phase6_key="ytop1"),
            FoldProfileSegment(frame, angle=-y_angle, phase6_key="fw"),
            FoldProfileSegment(core_y, angle=-90, phase6_key="endcap_d_core"),
            FoldProfileSegment(y_bottom, phase6_key="ybottom1"),
        )
        return_y, lower_y, upper_y = ret, ret + frame, ret + frame + core_y
    width = 200
    x_core = width - 2*x_left
    spec = EndCapPartSpec(
        width=200, depth=200, thickness=2, frame_width=frame,
        is_tail=tail, fold_left=x_left, fold_right=x_left,
        fold_top=ret, fold_bottom=y_bottom,
        fold_profile_x=(
            FoldProfileSegment(x_left, angle=-90, phase6_key="yl1"),
            FoldProfileSegment(x_core, angle=-90, phase6_key="endcap_w_core"),
            FoldProfileSegment(x_left, phase6_key="yr1"),
        ),
        fold_profile_y=y_rows,
    )
    rect=(Vec2(0,0),Vec2(200,0),Vec2(200,200),Vec2(0,200))
    x1=LinePrimitive(Vec2(x_left, 16),Vec2(x_left, 180),"BEND")
    x2=LinePrimitive(Vec2(200-x_left,16),Vec2(200-x_left,180),"BEND")
    y_return=LinePrimitive(Vec2(x_left,return_y),Vec2(200-x_left,return_y),"BEND")
    y_lower=LinePrimitive(Vec2(x_left,lower_y),Vec2(200-x_left,lower_y),"BEND")
    y_upper=LinePrimitive(Vec2(x_left,upper_y),Vec2(200-x_left,upper_y),"BEND")
    scene=DrawingScene([
        PolylinePrimitive(rect,"CUTTING",closed=True),
        x1,x2,y_return,y_lower,y_upper,
    ])
    return spec, PartRenderData(scene=scene,material=Polygon((p.x,p.y) for p in rect)), x1, y_lower, y_return


@pytest.mark.parametrize("tail", (False, True))
@pytest.mark.parametrize("angle", (60, 90, 120))
def test_named_multifold_head_tail_source_ignores_return_and_rejects_illegal_first(tail, angle):
    spec, render, x1, real_y, return_y = _named_head_tail_source(tail=tail, y_angle=angle)
    original = tuple(render.scene.primitives)
    live = api.project_operator_v_miter_live_corner_check(
        spec, render, "bottom_left", first_bend_axis="x",
    )
    assert live.first_physical_bend is x1
    assert live.second_physical_bend is real_y
    assert live.second_physical_bend is not return_y
    assert live.second_fold_angle_deg == angle
    assert live.second_signed_fold_angle_deg == -angle
    assert tuple(render.scene.primitives) == original
    if angle != 90:
        with pytest.raises(GeometryError, match="SELECTED_FIRST_BEND_NOT_90"):
            api.project_operator_v_miter_live_corner_check(
                spec, render, "bottom_left", first_bend_axis="y",
            )


def test_head_keyless_three_crease_sources_must_not_guess():
    spec, render, _, _, _ = _named_head_tail_source()
    unkeyed=replace(
        spec,
        fold_profile_y=tuple(replace(row,phase6_key=None) for row in spec.fold_profile_y),
    )
    with pytest.raises(GeometryError, match="KEYLESS_MULTIFOLD_AMBIGUOUS"):
        api.project_operator_v_miter_live_corner_check(
            unkeyed, render, "bottom_left", first_bend_axis="x",
        )


@pytest.mark.parametrize("field,bad", (
    ("thickness_mm", 3),
    ("first_flange_height_mm", 25),
    ("second_flange_height_mm", 25),
))
def test_bound_snapshot_rejects_changed_physical_T_or_flange_on_capture_and_replay(field,bad):
    spec, render, first, second = _source(90)
    args=dict(
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=20, second_fold_angle_deg=90,
        relief_mode="RELIEF_HOLE", relief_t_factor=1,
    )
    saved = api.capture_v_miter_relief_trial_snapshot(
        render.scene, first, second, **args,
        part_spec=spec, corner_key="bottom_left",
    )
    assert saved["source_fold_sha256"]
    tampered=dict(saved, parameters=dict(saved["parameters"]))
    tampered["parameters"][field]=bad
    with pytest.raises(GeometryError, match="SOURCE_(THICKNESS|FLANGE_HEIGHT)_MISMATCH"):
        api.replay_v_miter_relief_trial_snapshot(
            render.scene, tampered, part_spec=spec,
        )
    bad_args=dict(args)
    bad_args[field]=bad
    with pytest.raises(GeometryError, match="SOURCE_(THICKNESS|FLANGE_HEIGHT)_MISMATCH"):
        api.capture_v_miter_relief_trial_snapshot(
            render.scene, first, second, **bad_args,
            part_spec=spec, corner_key="bottom_left",
        )


@pytest.mark.parametrize("tail", (False, True))
@pytest.mark.parametrize("corner", ("bottom_left", "bottom_right", "top_left", "top_right"))
def test_named_multifold_roles_bind_all_four_corners_not_nearest_return(tail, corner):
    spec, render, _, lower, return_bend = _named_head_tail_source(tail=tail)
    original = tuple(render.scene.primitives)
    live = api.project_operator_v_miter_live_corner_check(
        spec, render, corner, first_bend_axis="x",
    )
    expected_x = original[1] if corner.endswith("left") else original[2]
    expected_y = lower if corner.startswith("bottom") else original[5]
    assert live.first_physical_bend is expected_x
    assert live.second_physical_bend is expected_y
    assert live.second_physical_bend is not return_bend
    assert live.first_signed_fold_angle_deg == -90
    assert live.second_signed_fold_angle_deg == -90
    assert tuple(render.scene.primitives) == original


def test_real_multifold_head_bound_snapshot_reopens_and_refuses_stale_return_source():
    from copy import deepcopy

    # With X left at 41, the real Head lower fw crease at 16+25=41 has
    # equal physical flange reaches; the ideal 90-degree CHECK rays actually
    # reach the genuine rectangular CUTTING perimeter.
    spec, render, real_x, real_y, return_y = _named_head_tail_source(
        x_left=41,
    )
    assert real_y is not return_y
    args = dict(
        thickness_mm=2, first_flange_height_mm=41,
        second_flange_height_mm=41, second_fold_angle_deg=90,
        relief_mode="RELIEF_HOLE", relief_t_factor=1,
    )
    saved = api.capture_v_miter_relief_trial_snapshot(
        render.scene, real_x, real_y, **args,
        part_spec=spec, corner_key="bottom_left",
    )
    reloaded = deepcopy(render.scene)
    assert reloaded.primitives[1] is not real_x
    replay = api.replay_v_miter_relief_trial_snapshot(
        reloaded, saved, part_spec=spec,
    )
    assert replay.manufacturing_status.endswith("UNCERTIFIED")
    # Head's Y16 return is physically unrelated to the chosen Y41 corner.
    # A change to this nonselected original BEND must still stale the saved
    # source digest; it may never reselect the nearest fold.
    drifted = deepcopy(reloaded)
    old_return = drifted.primitives[3]
    drifted.primitives[3] = LinePrimitive(
        Vec2(old_return.p1.x, old_return.p1.y + 0.5),
        Vec2(old_return.p2.x, old_return.p2.y + 0.5),
        "BEND",
    )
    with pytest.raises(GeometryError, match="source geometry has changed"):
        api.replay_v_miter_relief_trial_snapshot(
            drifted, saved, part_spec=spec,
        )
