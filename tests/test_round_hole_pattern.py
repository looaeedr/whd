import pytest

from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, feature_surface_from_rect, feature_finished_point,
    circle_center_distance_from_gap, circle_gap_from_center_distance,
    align_circle_to_neighbor, generate_round_fill, generate_round_refill,
)


def circle(x, y, d=20.0):
    return CircleFeature(diameter=d, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(x, y))


def centers(items, w=200, h=100):
    return [(round(feature_finished_point(f, w, h).x, 6), round(feature_finished_point(f, w, h).y, 6)) for f in items]


def test_center_and_gap_are_two_views_of_same_spacing_for_mixed_diameters():
    assert circle_center_distance_from_gap(20, 30, 50) == pytest.approx(60)
    assert circle_gap_from_center_distance(60, 30, 50) == pytest.approx(20)


def test_center_distance_smaller_than_combined_radii_reports_negative_gap():
    assert circle_gap_from_center_distance(30, 40, 40) == pytest.approx(-10)


def test_align_circle_to_neighbor_center_top_bottom_for_horizontal_row():
    seed = circle(100, 40, 20)
    neighbor = circle(60, 60, 40)
    assert feature_finished_point(align_circle_to_neighbor(seed, neighbor, 'center', 'x', 200, 100), 200, 100).y == pytest.approx(60)
    assert feature_finished_point(align_circle_to_neighbor(seed, neighbor, 'top', 'x', 200, 100), 200, 100).y == pytest.approx(70)
    assert feature_finished_point(align_circle_to_neighbor(seed, neighbor, 'bottom', 'x', 200, 100), 200, 100).y == pytest.approx(50)


def test_fill_right_uses_seed_and_stops_before_feature_surface_boundary():
    surface = feature_surface_from_rect('s', Vec2(0, 0), Vec2(100, 60))
    seed = circle(20, 30, 20)
    result = generate_round_fill(seed, surface, width=100, height=60, direction='right', driver='center', value=25)
    assert centers(result, 100, 60) == [(20, 30), (45, 30), (70, 30)]


def test_fill_left_and_bidirectional_use_gap_as_driver():
    surface = feature_surface_from_rect('s', Vec2(0, 0), Vec2(100, 60))
    seed = circle(50, 30, 20)
    left = generate_round_fill(seed, surface, width=100, height=60, direction='left', driver='gap', value=5)
    both = generate_round_fill(seed, surface, width=100, height=60, direction='both_horizontal', driver='gap', value=5)
    assert sorted(centers(left, 100, 60)) == [(25, 30), (50, 30)]
    assert sorted(centers(both, 100, 60)) == [(25, 30), (50, 30), (75, 30)]


def test_fill_up_down_and_bidirectional_vertical():
    surface = feature_surface_from_rect('s', Vec2(0, 0), Vec2(60, 100))
    seed = circle(30, 50, 20)
    up = generate_round_fill(seed, surface, width=60, height=100, direction='up', driver='center', value=25)
    down = generate_round_fill(seed, surface, width=60, height=100, direction='down', driver='center', value=25)
    both = generate_round_fill(seed, surface, width=60, height=100, direction='both_vertical', driver='center', value=25)
    assert centers(up, 60, 100) == [(30, 50), (30, 75)]
    assert sorted(centers(down, 60, 100), key=lambda p: p[1]) == [(30, 25), (30, 50)]
    assert sorted(centers(both, 60, 100), key=lambda p: p[1]) == [(30, 25), (30, 50), (30, 75)]


def test_refill_right_repositions_run_to_directional_boundary():
    surface = feature_surface_from_rect('s', Vec2(0, 0), Vec2(100, 60))
    seed = circle(43, 30, 20)
    result = generate_round_refill(seed, surface, width=100, height=60, direction='right', driver='center', value=25)
    assert centers(result, 100, 60) == [(15, 30), (40, 30), (65, 30), (90, 30)]


def test_refill_both_horizontal_centers_run_in_available_span():
    surface = feature_surface_from_rect('s', Vec2(0, 0), Vec2(100, 60))
    seed = circle(23, 30, 20)
    result = generate_round_refill(seed, surface, width=100, height=60, direction='both_horizontal', driver='center', value=25)
    xs = [p[0] for p in centers(result, 100, 60)]
    assert xs == [12.5, 37.5, 62.5, 87.5]
