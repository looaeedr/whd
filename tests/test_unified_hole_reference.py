import math
import pytest

from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, FeatureAnchor,
    ReferenceAnchor, feature_reference_point, reference_edge_directions,
    find_reference_neighbor, reference_distances, feature_surface_from_rect,
    move_feature_by_reference_distance, feature_finished_point,
)


def circle(x, y, d=20.0):
    return CircleFeature(diameter=d, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(x, y))


def rect(x, y, w=40.0, h=20.0, rot=0):
    return RectFeature(width=w, height=h, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(x, y), rotation_deg=rot)


def test_reference_points_cover_all_nine_anchors():
    f = rect(100, 100, 40, 20)
    expected = {
        ReferenceAnchor.CENTER: (100, 100),
        ReferenceAnchor.TOP_CENTER: (100, 110),
        ReferenceAnchor.BOTTOM_CENTER: (100, 90),
        ReferenceAnchor.LEFT_CENTER: (80, 100),
        ReferenceAnchor.RIGHT_CENTER: (120, 100),
        ReferenceAnchor.TOP_LEFT: (80, 110),
        ReferenceAnchor.BOTTOM_LEFT: (80, 90),
        ReferenceAnchor.TOP_RIGHT: (120, 110),
        ReferenceAnchor.BOTTOM_RIGHT: (120, 90),
    }
    for anchor, xy in expected.items():
        p = feature_reference_point(f, anchor, 300, 200)
        assert (p.x, p.y) == xy


def test_center_edge_direction_uses_nearest_and_ties_left_bottom():
    s = feature_surface_from_rect("s", Vec2(0, 0), Vec2(200, 100))
    f = circle(100, 50)
    assert reference_edge_directions(s, f, ReferenceAnchor.CENTER, 200, 100) == ("left", "bottom")
    assert reference_edge_directions(s, circle(160, 80), ReferenceAnchor.CENTER, 200, 100) == ("right", "top")


def test_middle_anchor_unspecified_axis_uses_nearest_edge():
    s = feature_surface_from_rect("s", Vec2(0, 0), Vec2(200, 100))
    assert reference_edge_directions(s, circle(160, 50), ReferenceAnchor.TOP_CENTER, 200, 100) == ("right", "top")
    assert reference_edge_directions(s, circle(100, 20), ReferenceAnchor.LEFT_CENTER, 200, 100) == ("left", "bottom")


def test_x_neighbor_ranks_distance_to_horizontal_reference_line_first():
    current = circle(200, 100)
    # A is much closer in X but 20 mm off the horizontal reference line.
    a = circle(190, 120)
    # B is farther in X but only 2 mm off the reference line, so B must win.
    b = circle(150, 102)
    n = find_reference_neighbor([current, a, b], 0, ReferenceAnchor.CENTER, "x", "left", 300, 200)
    assert n is not None and n.index == 2
    assert math.isclose(n.perpendicular_distance, 2.0)


def test_neighbor_tie_on_reference_line_uses_axis_distance():
    current = circle(200, 100)
    a = circle(170, 95)
    b = circle(180, 105)
    n = find_reference_neighbor([current, a, b], 0, ReferenceAnchor.CENTER, "x", "left", 300, 200)
    assert n is not None and n.index == 2


def test_reference_distances_report_edge_and_neighbor_by_selected_anchor():
    s = feature_surface_from_rect("s", Vec2(0, 0), Vec2(300, 200))
    features = [rect(200, 100, 40, 20), rect(120, 102, 40, 20)]
    d = reference_distances(s, features, 0, ReferenceAnchor.TOP_LEFT, 300, 200)
    assert d.x_side == "left" and d.y_side == "top"
    assert math.isclose(d.x_edge_distance, 180.0)  # top-left anchor x = 180
    assert math.isclose(d.y_edge_distance, 90.0)   # top-left anchor y = 110 -> top 200
    assert d.x_neighbor_index == 1
    # other top-left anchor x=100; current=180
    assert math.isclose(d.x_neighbor_distance, 80.0)


def test_move_by_edge_distance_round_trip_and_surface_rejection():
    s = feature_surface_from_rect("s", Vec2(0, 0), Vec2(300, 200))
    features = [circle(100, 100, 20)]
    moved = move_feature_by_reference_distance(s, features, 0, ReferenceAnchor.CENTER, 300, 200, axis="x", mode="edge", value=40)
    assert math.isclose(feature_finished_point(moved, 300, 200).x, 40.0)
    # impossible because radius would leave the surface -> original feature returned
    blocked = move_feature_by_reference_distance(s, features, 0, ReferenceAnchor.CENTER, 300, 200, axis="x", mode="edge", value=5)
    assert blocked == features[0]


def test_reference_distances_can_use_finished_guide_outside_feature_surface():
    from ae_engine.sheetmetal_features import RectGuide
    s = feature_surface_from_rect("s", Vec2(10, 10), Vec2(190, 90))
    guide = RectGuide(Vec2(0, 0), Vec2(200, 100), role="finished_boundary")
    features = [circle(50, 40, 20)]
    d = reference_distances(s, features, 0, ReferenceAnchor.CENTER, 200, 100, reference_guide=guide)
    assert d.x_side == "left" and d.y_side == "bottom"
    assert d.x_edge_distance == pytest.approx(50.0)
    assert d.y_edge_distance == pytest.approx(40.0)


def test_move_by_finished_guide_distance_is_inverse_but_still_surface_constrained():
    from ae_engine.sheetmetal_features import RectGuide
    s = feature_surface_from_rect("s", Vec2(10, 10), Vec2(190, 90))
    guide = RectGuide(Vec2(0, 0), Vec2(200, 100), role="finished_boundary")
    features = [circle(60, 40, 20)]
    moved = move_feature_by_reference_distance(
        s, features, 0, ReferenceAnchor.CENTER, 200, 100,
        axis="x", mode="edge", value=50, reference_guide=guide,
    )
    assert feature_finished_point(moved, 200, 100).x == pytest.approx(50.0)
    blocked = move_feature_by_reference_distance(
        s, features, 0, ReferenceAnchor.CENTER, 200, 100,
        axis="x", mode="edge", value=5, reference_guide=guide,
    )
    assert blocked == features[0]
