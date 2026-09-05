import math

from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CanvasTransform,
    CircleFeature,
    EndCapFeatureContext,
    FeatureAnchor,
    RectFeature,
    legacy_hole_to_feature,
    resolve_endcap_features,
)


def test_canvas_transform_round_trip():
    tx = CanvasTransform(scale=2.5, origin_x=40.0, origin_y=300.0)
    p = Vec2(12.0, 18.0)
    cx, cy = tx.world_to_canvas(p)
    assert (cx, cy) == (70.0, 255.0)
    assert tx.canvas_to_world(cx, cy) == p


def test_legacy_circle_and_pipe_preserve_layer_semantics():
    circle = legacy_hole_to_feature({
        'x': 100.0, 'y': 80.0, 'type': '圓形', 'params': {'diameter': 22.0}
    })
    pipe = legacy_hole_to_feature({
        'x': 100.0, 'y': 80.0, 'type': '管孔', 'params': {'diameter': 30.0, 'code': 'P1'}
    })
    assert isinstance(circle, CircleFeature)
    assert circle.anchor is FeatureAnchor.ABSOLUTE_FINISHED_FACE
    assert circle.layer == 'CUTTING'
    assert pipe.layer == 'BLIND_HOLE'
    assert pipe.add_centerline is True


def test_legacy_rectangle_converts_to_rect_feature():
    feature = legacy_hole_to_feature({
        'x': 50.0, 'y': 60.0, 'type': '方形', 'params': {'width': 20.0, 'height': 10.0}
    })
    assert isinstance(feature, RectFeature)
    assert feature.width == 20.0
    assert feature.height == 10.0


def test_endcap_resolver_matches_existing_linear_mapping_t2():
    ctx = EndCapFeatureContext(
        finished_width=400.0,
        finished_depth=250.0,
        thickness=2.0,
        left_fold=15.0,
        right_fold=15.0,
        bottom_fold=15.0,
        unfolded_width=422.0,
    )
    feature = CircleFeature(
        diameter=20.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(200.0, 125.0),
        layer='CUTTING',
    )
    [resolved] = resolve_endcap_features(ctx, [feature])
    bx1 = 15.0
    bx2 = 422.0 - 15.0
    by1 = 15.0
    by2 = 15.0 + (250.0 - 3 * 2.0)
    expected_x = bx1 + (200.0 - 2 * 2.0) / (400.0 - 4 * 2.0) * (bx2 - bx1)
    expected_y = by1 + (125.0 - 2 * 2.0) / (250.0 - 3 * 2.0) * (by2 - by1)
    assert math.isclose(resolved.center.x, expected_x)
    assert math.isclose(resolved.center.y, expected_y)


def test_endcap_resolver_supports_asymmetric_folds_and_t15():
    ctx = EndCapFeatureContext(
        finished_width=400.0,
        finished_depth=250.0,
        thickness=1.5,
        left_fold=12.0,
        right_fold=18.0,
        bottom_fold=14.0,
        unfolded_width=424.0,
    )
    feature = RectFeature(
        width=20.0,
        height=10.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100.0, 75.0),
        layer='CUTTING',
    )
    [resolved] = resolve_endcap_features(ctx, [feature])
    bx1 = 12.0
    bx2 = 424.0 - 18.0
    by1 = 14.0
    by2 = 14.0 + (250.0 - 3 * 1.5)
    expected_x = bx1 + (100.0 - 2 * 1.5) / (400.0 - 4 * 1.5) * (bx2 - bx1)
    expected_y = by1 + (75.0 - 2 * 1.5) / (250.0 - 3 * 1.5) * (by2 - by1)
    assert math.isclose(resolved.center.x, expected_x)
    assert math.isclose(resolved.center.y, expected_y)


def test_baseline_circle_normalization_preserves_center_radius_layer():
    from ae_engine.sheetmetal_features import resolved_circles_from_baseline
    mapped = [((12.5, 33.0), 3.2, 'CUTTING'), ((20.0, 40.0), 2.0, 'MARKING')]
    resolved = resolved_circles_from_baseline(mapped)
    assert [(r.center.x, r.center.y, r.radius, r.layer) for r in resolved] == [
        (12.5, 33.0, 3.2, 'CUTTING'),
        (20.0, 40.0, 2.0, 'MARKING'),
    ]


def test_door_indicator_resolver_one_group_matches_legacy_positions():
    from ae_engine.sheetmetal_features import DoorIndicatorContext, resolve_door_indicator_features
    ctx = DoorIndicatorContext(
        finished_width=600.0,
        finished_height=800.0,
        left_fold=25.0,
        bottom_fold=25.0,
    )
    features = resolve_door_indicator_features(ctx, [1], Vec2(0.0, 0.0))
    cutting = [f for f in features if f.layer == 'CUTTING']
    marking = [f for f in features if f.layer == 'MARKING']
    assert len(cutting) == 5  # 3 lamps + 2 nameplate holes
    assert len(marking) == 1
    # Legacy group center: fl + W/2 - 28; one-group local lamp x=191-W_box/2 with W_box=326.
    expected_x = 25.0 + 600.0/2.0 - 28.0 + (191.0 - 326.0/2.0)
    lamp_centers = [f.center for f in cutting if math.isclose(f.radius, 15.5)]
    assert len(lamp_centers) == 3
    assert all(math.isclose(p.x, expected_x) for p in lamp_centers)


def test_door_indicator_offset_moves_all_features_once():
    from ae_engine.sheetmetal_features import DoorIndicatorContext, resolve_door_indicator_features
    ctx = DoorIndicatorContext(600.0, 800.0, 25.0, 25.0)
    base = resolve_door_indicator_features(ctx, [2, 1], Vec2(0.0, 0.0))
    shifted = resolve_door_indicator_features(ctx, [2, 1], Vec2(12.0, -7.0))
    assert len(base) == len(shifted)
    for a, b in zip(base, shifted):
        assert math.isclose(b.center.x - a.center.x, 12.0)
        assert math.isclose(b.center.y - a.center.y, -7.0)


def test_baseline_circle_normalization_accepts_legacy_four_tuple_shape():
    from ae_engine.sheetmetal_features import resolved_circles_from_baseline
    [resolved] = resolved_circles_from_baseline([(12.5, 33.0, 3.2, 'CUTTING')])
    assert (resolved.center.x, resolved.center.y, resolved.radius, resolved.layer) == (12.5, 33.0, 3.2, 'CUTTING')


def test_door_indicator_layout_exposes_legacy_interaction_bounds_and_hit_test():
    from ae_engine.sheetmetal_features import DoorIndicatorContext, resolve_door_indicator_layout
    ctx = DoorIndicatorContext(600.0, 800.0, 25.0, 25.0)
    layout = resolve_door_indicator_layout(ctx, [1], Vec2(0.0, 0.0))
    assert math.isclose(layout.interaction_bounds.min_x, 285.0)
    assert math.isclose(layout.interaction_bounds.max_x, 365.0)
    assert math.isclose(layout.interaction_bounds.min_y, 292.25)
    assert math.isclose(layout.interaction_bounds.max_y, 542.25)
    assert layout.hit_test(Vec2(325.0, 417.25), padding=15.0)
    assert not layout.hit_test(Vec2(500.0, 700.0), padding=15.0)


def test_door_indicator_layout_clamps_offset_to_finished_face():
    from ae_engine.sheetmetal_features import DoorIndicatorContext, resolve_door_indicator_layout
    ctx = DoorIndicatorContext(600.0, 800.0, 25.0, 25.0)
    layout = resolve_door_indicator_layout(ctx, [1], Vec2(0.0, 0.0))
    clamped = layout.clamp_offset(Vec2(999.0, 999.0))
    assert math.isclose(clamped.x, 260.0)
    assert math.isclose(clamped.y, 282.75)


def test_door_indicator_position_dimensions_round_trip_offset():
    from ae_engine.sheetmetal_features import (
        DoorIndicatorContext,
        door_indicator_offset_for_position,
        measure_door_indicator_position,
        resolve_door_indicator_layout,
    )
    ctx = DoorIndicatorContext(600.0, 800.0, 25.0, 25.0)
    original_offset = Vec2(12.0, -7.0)
    layout = resolve_door_indicator_layout(ctx, [2, 1], original_offset)
    dims = measure_door_indicator_position(
        layout,
        ctx,
        frame_width=62.0,
        thickness=2.0,
        use_box_distance=False,
    )
    recovered = door_indicator_offset_for_position(
        ctx,
        [2, 1],
        x_distance=dims.distance_x,
        y_distance=dims.distance_y,
        frame_width=62.0,
        thickness=2.0,
        use_box_distance=False,
    )
    assert math.isclose(recovered.x, original_offset.x)
    assert math.isclose(recovered.y, original_offset.y)


def test_finished_face_feature_hit_test_understands_circle_and_rectangle_extents():
    from ae_engine.sheetmetal_features import (
        hit_test_resolved_features,
        resolve_features_in_finished_face,
    )
    features = [
        CircleFeature(20.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(50.0, 50.0)),
        RectFeature(30.0, 10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100.0, 70.0)),
    ]
    resolved = resolve_features_in_finished_face(200.0, 100.0, features)
    assert hit_test_resolved_features(Vec2(59.0, 50.0), resolved, tolerance=0.0) == 0
    assert hit_test_resolved_features(Vec2(114.0, 74.0), resolved, tolerance=0.0) == 1
    assert hit_test_resolved_features(Vec2(130.0, 90.0), resolved, tolerance=0.0) is None


def test_base_plate_mounting_holes_match_existing_rule():
    from ae_engine.sheetmetal_features import resolve_base_plate_mounting_holes
    holes = resolve_base_plate_mounting_holes(500.0, 400.0, bend=25.0)
    assert [(h.center.x, h.center.y, h.radius, h.layer) for h in holes] == [
        (40.0, 40.0, 5.0, 'CUTTING'),
        (40.0, 360.0, 5.0, 'CUTTING'),
        (460.0, 40.0, 5.0, 'CUTTING'),
        (460.0, 360.0, 5.0, 'CUTTING'),
    ]


def test_endcap_finished_face_guide_matches_current_vault_rule():
    from ae_engine.sheetmetal_features import resolve_endcap_finished_face_guide
    guide = resolve_endcap_finished_face_guide(400.0, 250.0, 2.0)
    assert guide.min_point == Vec2(4.0, 4.0)
    assert guide.max_point == Vec2(396.0, 248.0)
    assert guide.role == 'endcap_finished_face'


def test_endcap_finished_face_guide_rejects_non_positive_thickness():
    import pytest
    from ae_engine.sheetmetal_features import resolve_endcap_finished_face_guide
    with pytest.raises(ValueError):
        resolve_endcap_finished_face_guide(400.0, 250.0, 0.0)


def test_vault_endcap_fixed_features_match_current_head_and_tail_rules():
    from ae_engine.sheetmetal_geometry import EndCapGeometry, ReliefConfig
    from ae_engine.sheetmetal_features import resolve_vault_endcap_fixed_features, ResolvedCircle, ResolvedRect, VaultEndCapFeaturePolicy
    g = EndCapGeometry(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    policy = VaultEndCapFeaturePolicy(
        hanging_hole_radius=3.2,
        hanging_hole_y_from_top_bend=6.0,
        square_hole_origin=Vec2(3.0, 5.0),
        square_hole_size=Vec2(12.0, 8.0),
        tail_bottom_hole_radius=2.5,
        tail_bottom_hole_y=5.0,
    )
    head = resolve_vault_endcap_fixed_features(g, relief_config=ReliefConfig(), policy=policy, is_tail=False)
    tail = resolve_vault_endcap_fixed_features(g, relief_config=ReliefConfig(), policy=policy, is_tail=True)
    assert len(head) == 3
    assert len(tail) == 4
    circles = [f for f in head if isinstance(f, ResolvedCircle)]
    rects = [f for f in head if isinstance(f, ResolvedRect)]
    assert [(c.center.x, c.center.y, c.radius) for c in circles] == [
        (50.5, 290.0, 3.2),
        (371.5, 290.0, 3.2),
    ]
    assert len(rects) == 1
    assert rects[0].center == Vec2(9.0, 9.0)
    assert rects[0].width == 12.0
    assert rects[0].height == 8.0
    tail_bottom = [f for f in tail if isinstance(f, ResolvedCircle) and f.source_type == 'vault_tail_bottom']
    assert len(tail_bottom) == 1
    assert tail_bottom[0].center == Vec2(211.0, 5.0)


def test_vault_endcap_fixed_hanging_y_tracks_t15_geometry():
    from ae_engine.sheetmetal_geometry import EndCapGeometry, ReliefConfig
    from ae_engine.sheetmetal_features import resolve_vault_endcap_fixed_features, ResolvedCircle, VaultEndCapFeaturePolicy
    g = EndCapGeometry(
        total_width=424.0,
        total_depth=301.5,
        thickness=1.5,
        fw=25.0,
        left_fold=12.0,
        right_fold=18.0,
        top_first_fold=16.0,
        bottom_fold=14.0,
    )
    policy = VaultEndCapFeaturePolicy(
        hanging_hole_radius=3.2,
        hanging_hole_y_from_top_bend=6.0,
        square_hole_origin=Vec2(3.0, 5.0),
        square_hole_size=Vec2(12.0, 8.0),
        tail_bottom_hole_radius=2.5,
        tail_bottom_hole_y=5.0,
    )
    features = resolve_vault_endcap_fixed_features(
        g, relief_config=ReliefConfig(), policy=policy, is_tail=False
    )
    circles = [f for f in features if isinstance(f, ResolvedCircle)]
    assert all(math.isclose(c.center.y, 301.5 - 16.0 + 6.0) for c in circles)


def test_door_indicator_dimension_guides_wrap_existing_position_geometry():
    from ae_engine.sheetmetal_features import (
        DoorIndicatorContext,
        measure_door_indicator_position,
        resolve_door_indicator_dimension_guides,
        resolve_door_indicator_layout,
    )
    ctx = DoorIndicatorContext(600.0, 800.0, 25.0, 25.0)
    layout = resolve_door_indicator_layout(ctx, [2, 1], Vec2(12.0, -7.0))
    position = measure_door_indicator_position(
        layout, ctx, frame_width=62.0, thickness=2.0, use_box_distance=False
    )
    x_guide, y_guide = resolve_door_indicator_dimension_guides(position)
    assert x_guide.axis == 'x'
    assert x_guide.start == Vec2(position.reference_x, position.target_y)
    assert x_guide.end == Vec2(position.target_x, position.target_y)
    assert math.isclose(x_guide.value, position.distance_x)
    assert y_guide.axis == 'y'
    assert y_guide.start == Vec2(position.target_x, position.reference_y)
    assert y_guide.end == Vec2(position.target_x, position.target_y)
    assert math.isclose(y_guide.value, position.distance_y)


def test_vault_endcap_feature_policy_owns_hanging_offset_default():
    from ae_engine.sheetmetal_features import VaultEndCapFeaturePolicy
    policy = VaultEndCapFeaturePolicy(
        hanging_hole_radius=3.2,
        hanging_hole_y_from_top_bend=6.0,
        square_hole_origin=Vec2(3.0, 18.0),
        square_hole_size=Vec2(4.0, 4.0),
        tail_bottom_hole_radius=2.5,
        tail_bottom_hole_y=5.0,
    )
    assert policy.hanging_hole_offset_from_primary == 10.5


def test_choose_feature_anchor_prefers_center_and_nearest_corner():
    from ae_engine.sheetmetal_features import choose_feature_anchor
    assert choose_feature_anchor(Vec2(200.0, 125.0), 400.0, 250.0) is FeatureAnchor.PANEL_CENTER
    assert choose_feature_anchor(Vec2(5.0, 245.0), 400.0, 250.0) is FeatureAnchor.TOP_LEFT
    assert choose_feature_anchor(Vec2(395.0, 245.0), 400.0, 250.0) is FeatureAnchor.TOP_RIGHT
    assert choose_feature_anchor(Vec2(5.0, 5.0), 400.0, 250.0) is FeatureAnchor.BOTTOM_LEFT
    assert choose_feature_anchor(Vec2(395.0, 5.0), 400.0, 250.0) is FeatureAnchor.BOTTOM_RIGHT


def test_placement_round_trip_reconstructs_absolute_point():
    from ae_engine.sheetmetal_features import placement_from_finished_point
    p = Vec2(73.5, 211.25)
    placement = placement_from_finished_point(p, 400.0, 250.0)
    assert math.isclose(placement.absolute_point.x, p.x)
    assert math.isclose(placement.absolute_point.y, p.y)


def test_reanchor_preserves_finished_face_center():
    from ae_engine.sheetmetal_features import feature_finished_point, reanchor_feature
    feature = CircleFeature(22.0, FeatureAnchor.TOP_LEFT, Vec2(80.0, -40.0), layer='CUTTING', source_type='圓形')
    before = feature_finished_point(feature, 400.0, 250.0)
    changed = reanchor_feature(feature, FeatureAnchor.BOTTOM_RIGHT, 400.0, 250.0)
    after = feature_finished_point(changed, 400.0, 250.0)
    assert after == before
    assert changed.anchor is FeatureAnchor.BOTTOM_RIGHT
    assert changed.diameter == feature.diameter
    assert changed.layer == feature.layer
    assert changed.source_type == feature.source_type


def test_move_feature_preserves_shape_semantics_and_updates_offset():
    from ae_engine.sheetmetal_features import feature_finished_point, move_feature_to_finished_point
    feature = RectFeature(30.0, 10.0, FeatureAnchor.PANEL_CENTER, Vec2(0.0, 0.0), layer='CUTTING', source_type='方形')
    moved = move_feature_to_finished_point(feature, Vec2(250.0, 160.0), 400.0, 250.0)
    assert feature_finished_point(moved, 400.0, 250.0) == Vec2(250.0, 160.0)
    assert (moved.width, moved.height, moved.layer, moved.source_type) == (30.0, 10.0, 'CUTTING', '方形')


def test_feature_placement_guides_report_anchor_relative_distances():
    from ae_engine.sheetmetal_features import build_feature_placement_guides
    feature = CircleFeature(20.0, FeatureAnchor.TOP_LEFT, Vec2(80.0, -40.0))
    guides = build_feature_placement_guides(feature, 400.0, 250.0)
    assert guides.anchor is FeatureAnchor.TOP_LEFT
    assert math.isclose(guides.horizontal.value, 80.0)
    assert math.isclose(guides.vertical.value, 40.0)
    assert guides.horizontal.axis == 'x'
    assert guides.vertical.axis == 'y'


def test_linear_and_grid_patterns_expand_features_in_world_space():
    from ae_engine.sheetmetal_features import expand_linear_pattern, expand_grid_pattern, feature_finished_point
    feature = CircleFeature(10.0, FeatureAnchor.BOTTOM_LEFT, Vec2(20.0, 30.0), source_type='圓形')
    horizontal = expand_linear_pattern(feature, count=3, pitch=25.0, axis='x')
    assert [feature_finished_point(f, 400.0, 250.0) for f in horizontal] == [
        Vec2(20.0,30.0), Vec2(45.0,30.0), Vec2(70.0,30.0)
    ]
    vertical = expand_linear_pattern(feature, count=2, pitch=-10.0, axis='y')
    assert [feature_finished_point(f, 400.0, 250.0) for f in vertical] == [Vec2(20.0,30.0), Vec2(20.0,20.0)]
    grid = expand_grid_pattern(feature, rows=2, columns=3, pitch_x=20.0, pitch_y=15.0)
    assert len(grid) == 6
    assert feature_finished_point(grid[-1], 400.0, 250.0) == Vec2(60.0, 45.0)


def test_legacy_feature_round_trip_preserves_absolute_position_and_type():
    from ae_engine.sheetmetal_features import feature_to_legacy_hole
    legacy = {'x': 88.0, 'y': 66.0, 'type': '管孔', 'params': {'diameter': 30.0, 'code': 'P1'}}
    feature = legacy_hole_to_feature(legacy)
    out = feature_to_legacy_hole(feature, 400.0, 250.0)
    assert out == legacy


def test_drag_move_reselects_nearest_semantic_anchor():
    from ae_engine.sheetmetal_features import move_feature_to_finished_point
    feature = CircleFeature(20.0, FeatureAnchor.BOTTOM_LEFT, Vec2(10.0, 10.0), source_type='圓形')
    moved = move_feature_to_finished_point(feature, Vec2(395.0, 245.0), 400.0, 250.0)
    assert moved.anchor is FeatureAnchor.TOP_RIGHT


def test_feature_with_offset_changes_only_semantic_offset():
    from ae_engine.sheetmetal_features import feature_with_offset
    feature = RectFeature(20.0, 10.0, FeatureAnchor.TOP_LEFT, Vec2(5.0, -6.0), source_type='方形')
    changed = feature_with_offset(feature, Vec2(80.0, -40.0))
    assert changed.offset == Vec2(80.0, -40.0)
    assert (changed.anchor, changed.width, changed.height, changed.source_type) == (FeatureAnchor.TOP_LEFT, 20.0, 10.0, '方形')


def test_legacy_pipe_hole_is_blind_hole_not_marking():
    from ae_engine.sheetmetal_features import legacy_hole_to_feature
    f = legacy_hole_to_feature({'type':'管孔','x':10,'y':20,'params':{'code':'*D1','diameter':116}})
    assert f.layer == 'BLIND_HOLE'
    assert f.add_centerline is True


def test_profile_feature_legacy_roundtrip_preserves_rotation_and_layer():
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_features import ProfileFeature, FeatureAnchor, feature_to_legacy_hole, legacy_hole_to_feature
    f = ProfileFeature((Vec2(-5,-2),Vec2(5,-2),Vec2(5,2),Vec2(-5,2)), FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(30,40), layer='CUTTING', source_type='AS&VS', rotation_deg=90)
    raw = feature_to_legacy_hole(f, 100, 100)
    restored = legacy_hole_to_feature(raw)
    assert restored == f
