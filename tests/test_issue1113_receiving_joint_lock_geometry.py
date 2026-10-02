# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from shapely.geometry import Point, Polygon

import ae_engine.ae as ae
from ae_engine.box_body_structure import (
    resolve_box_body_piece_face_features,
    resolve_box_body_structure,
)
from ae_engine.cabinet_types import receiving
from ae_engine.receiving_joint_locks import (
    DIRECTION_CONTRACT,
    RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION,
    RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION,
    ReceivingJointLockPatternError,
    resolve_receiving_joint_lock_pattern,
)
from ae_engine.receiving_layout import (
    new_receiving_layout,
    resize_receiving_bays,
    update_receiving_bay,
    update_receiving_joint_alignment,
)
from ae_engine.sheetmetal_features import (
    ResolvedCircle,
    box_body_face_contexts_from_strip,
)
from ae_engine.sheetmetal_geometry import Vec2
from phase6_fold_profiles import build_box_body_profile


def _layout(*, left=(800, 1600, 400), right=(900, 1800, 500), depth_alignment="FRONT", height_alignment="BOTTOM"):
    layout = new_receiving_layout(
        width=left[0], height=left[1], depth=left[2], back_panel_mode="FULL"
    )
    layout = resize_receiving_bays(layout, set_index=0, bay_count=2)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1,
        width=right[0], height=right[1], depth=right[2],
    )
    layout = update_receiving_joint_alignment(
        layout, set_index=0, joint_index=0,
        depth_alignment=depth_alignment, height_alignment=height_alignment,
    )
    return layout


def _baseline_back_local_x(*, w, h, d, t, fw, u, side):
    result = ae.build_box_body_result(
        w=float(w), h=float(h), d=float(d), t=float(t), fw=float(fw),
        zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=-10.0,
        include_right_fw=True,
    )
    ctx = box_body_face_contexts_from_strip(
        result.topology, w=float(w), h=float(h), d=float(d), t=float(t)
    )["back"]
    unfolded_x = (
        float(ctx.unfolded_min_x) + float(u)
        if side == "left"
        else float(ctx.unfolded_max_x) - float(u)
    )
    return float(
        ctx.unfolded_to_local(Vec2(unfolded_x, float(ctx.unfolded_height) / 2.0)).x
    )


def _fake_certified_resolver(model_name, *, w, h, d, t, fw):
    assert model_name == "金庫型"
    assert t == pytest.approx(2.0)
    assert fw == pytest.approx(29.0)
    back = (
        ResolvedCircle(
            center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=40.0, side="left"), 100.0),
            radius=8.0, layer="CUTTING", source_type="baseline"
        ),
        ResolvedCircle(
            center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=120.0, side="left"), h - 100.0),
            radius=8.0, layer="CUTTING", source_type="baseline"
        ),
        ResolvedCircle(
            center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=120.0, side="right"), h - 100.0),
            radius=8.0, layer="CUTTING", source_type="baseline"
        ),
        ResolvedCircle(
            center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=40.0, side="right"), 100.0),
            radius=8.0, layer="CUTTING", source_type="baseline"
        ),
    )
    return {"left": (), "back": back, "right": ()}


def test_t008_t008a_canonical_joint_axes_and_participant_width_calls():
    calls = []

    def resolver(model_name, **kwargs):
        calls.append((float(kwargs["w"]), float(kwargs["d"]), float(kwargs["h"])))
        return _fake_certified_resolver(model_name, **kwargs)

    result = resolve_receiving_joint_lock_pattern(
        _layout(), set_index=0, joint_index=0, baseline_resolver=resolver
    )
    assert calls == [(800.0, 400.0, 1600.0), (900.0, 400.0, 1600.0)]
    assert result.effective_depth == pytest.approx(400.0)
    assert result.effective_height == pytest.approx(1600.0)
    assert [(row.u, row.v, row.diameter) for row in result.canonical_pattern] == [
        (40.0, 100.0, 16.0),
        (120.0, 1500.0, 16.0),
    ]
    assert result.direction_contract == DIRECTION_CONTRACT
    assert result.left_bay.face_key == "right"
    assert result.right_bay.face_key == "left"


def test_t009a_real_receiving_to_vault_certified_resolver_is_width_invariant():
    result = resolve_receiving_joint_lock_pattern(
        _layout(), set_index=0, joint_index=0
    )
    assert result.baseline_model == "金庫型"
    assert len(result.canonical_pattern) == 2
    assert {round(row.diameter, 6) for row in result.canonical_pattern} == {16.0}
    assert {row.layer for row in result.canonical_pattern} == {"CUTTING"}


def test_t009a_width_invariant_mismatch_fails_closed():
    def resolver(model_name, **kwargs):
        rows = _fake_certified_resolver(model_name, **kwargs)
        if float(kwargs["w"]) > 800.0:
            rows = dict(rows)
            w = float(kwargs["w"])
            h = float(kwargs["h"])
            d = float(kwargs["d"])
            t = float(kwargs["t"])
            fw = float(kwargs["fw"])
            rows["back"] = (
                ResolvedCircle(
                    center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=45.0, side="left"), 100.0),
                    radius=8.0, layer="CUTTING", source_type="baseline"
                ),
                ResolvedCircle(
                    center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=120.0, side="left"), h - 100.0),
                    radius=8.0, layer="CUTTING", source_type="baseline"
                ),
                ResolvedCircle(
                    center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=120.0, side="right"), h - 100.0),
                    radius=8.0, layer="CUTTING", source_type="baseline"
                ),
                ResolvedCircle(
                    center=Vec2(_baseline_back_local_x(w=w, h=h, d=d, t=t, fw=fw, u=40.0, side="right"), 100.0),
                    radius=8.0, layer="CUTTING", source_type="baseline"
                ),
            )
        return rows

    with pytest.raises(ReceivingJointLockPatternError) as exc:
        resolve_receiving_joint_lock_pattern(
            _layout(), set_index=0, joint_index=0, baseline_resolver=resolver
        )
    assert exc.value.code == RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION


@pytest.mark.parametrize("depth_alignment", ["FRONT", "REAR"])
@pytest.mark.parametrize("height_alignment", ["BOTTOM", "TOP"])
def test_t009_all_alignment_combinations_project_identical_joint_world_centers(
    depth_alignment, height_alignment
):
    result = resolve_receiving_joint_lock_pattern(
        _layout(depth_alignment=depth_alignment, height_alignment=height_alignment),
        set_index=0, joint_index=0, baseline_resolver=_fake_certified_resolver,
    )
    assert result.left_bay.joint_world_centers == result.right_bay.joint_world_centers
    assert result.left_bay.joint_world_centers == (
        (0.0, 100.0, -40.0),
        (0.0, 1500.0, -120.0),
    )

    # FRONT/BOTTOM choose the participant origin; REAR/TOP shift only the
    # larger participant while preserving the same shared Joint world points.
    left_xy = result.left_bay.finished_centers
    right_xy = result.right_bay.finished_centers
    if depth_alignment == "FRONT":
        assert left_xy[0][0] == pytest.approx(400.0 - 40.0)
        assert right_xy[0][0] == pytest.approx(40.0)
    else:
        assert left_xy[0][0] == pytest.approx(400.0 - 40.0)
        assert right_xy[0][0] == pytest.approx((500.0 - 400.0) + 40.0)
    if height_alignment == "BOTTOM":
        assert left_xy[0][1] == pytest.approx(100.0)
        assert right_xy[0][1] == pytest.approx(100.0)
    else:
        assert left_xy[0][1] == pytest.approx(100.0)
        assert right_xy[0][1] == pytest.approx((1800.0 - 1600.0) + 100.0)


def _assert_projection_inside_physical_piece(projection):
    snap = receiving.apply_family_defaults({"t": 2.0})
    snap.update({
        "w": projection.width,
        "h": projection.height,
        "d": projection.depth,
    })
    state = receiving.resolve_box_body_structure_state(None)
    structure = resolve_box_body_structure(
        build_box_body_profile(snap),
        w=snap["w"], h=snap["h"], d=snap["d"], t=snap["t"],
        structure_state=state,
    )
    stores = resolve_box_body_piece_face_features(
        structure,
        face_features={projection.face_key: projection.features},
        w=snap["w"], h=snap["h"], d=snap["d"], t=snap["t"],
    )
    role = f"{projection.face_key}_side"
    piece = next(row for row in structure.pieces if row.role == role)
    resolved = tuple(stores[piece.key])
    assert len(resolved) == len(projection.features)
    material = Polygon([(float(p.x), float(p.y)) for p in piece.structural.outline])
    for feature in resolved:
        assert isinstance(feature, ResolvedCircle)
        footprint = Point(float(feature.center.x), float(feature.center.y)).buffer(
            float(feature.radius), resolution=32
        )
        assert material.covers(footprint)


def test_t010_physical_side_piece_flat_projection_keeps_whole_holes_without_clipping():
    result = resolve_receiving_joint_lock_pattern(
        _layout(depth_alignment="REAR", height_alignment="TOP"),
        set_index=0, joint_index=0, baseline_resolver=_fake_certified_resolver,
    )
    _assert_projection_inside_physical_piece(result.left_bay)
    _assert_projection_inside_physical_piece(result.right_bay)


def test_t011_undersized_effective_panel_fails_closed_without_clipping():
    def out_of_bounds_resolver(model_name, *, w, h, d, t, fw):
        del model_name, d, t, fw
        return {
            "left": (),
            "back": (
                ResolvedCircle(
                    center=Vec2(_baseline_back_local_x(w=w, h=h, d=20.0, t=2.0, fw=29.0, u=5.0, side="left"), 5.0),
                    radius=8.0, layer="CUTTING"
                ),
                ResolvedCircle(
                    center=Vec2(_baseline_back_local_x(w=w, h=h, d=20.0, t=2.0, fw=29.0, u=5.0, side="right"), 5.0),
                    radius=8.0, layer="CUTTING"
                ),
            ),
            "right": (),
        }

    with pytest.raises(ReceivingJointLockPatternError) as exc:
        resolve_receiving_joint_lock_pattern(
            _layout(left=(800, 20, 20), right=(900, 30, 30)),
            set_index=0, joint_index=0, baseline_resolver=out_of_bounds_resolver,
        )
    assert exc.value.code == RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION
