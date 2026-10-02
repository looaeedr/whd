import math
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    FeatureAnchor, RectFeature, ProfileFeature,
    feature_surface_from_rect, feature_is_within_surface,
    resolve_surface_features,
)


def test_rect_rotation_90_swaps_resolved_extent():
    f = RectFeature(90, 50, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100,100), rotation_deg=90)
    r = resolve_surface_features(feature_surface_from_rect('s', Vec2(0,0), Vec2(300,300)), [f], 300, 300)[0]
    xs = [p.x for p in r.points]
    ys = [p.y for p in r.points]
    assert math.isclose(max(xs)-min(xs), 50, abs_tol=1e-6)
    assert math.isclose(max(ys)-min(ys), 90, abs_tol=1e-6)


def test_profile_rotation_270_rotates_points_about_center():
    f = ProfileFeature((Vec2(-10,-5), Vec2(10,-5), Vec2(10,5), Vec2(-10,5)), FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100,100), rotation_deg=270)
    r = resolve_surface_features(feature_surface_from_rect('s', Vec2(0,0), Vec2(300,300)), [f], 300, 300)[0]
    xs = [round(p.x, 6) for p in r.points]
    ys = [round(p.y, 6) for p in r.points]
    assert max(xs)-min(xs) == 10
    assert max(ys)-min(ys) == 20


def test_rotated_rectangle_full_footprint_must_stay_inside_surface():
    s = feature_surface_from_rect('s', Vec2(0,0), Vec2(100,100))
    unrotated = RectFeature(70,20,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(50,15),rotation_deg=360)
    rotated = RectFeature(70,20,FeatureAnchor.ABSOLUTE_FINISHED_FACE,Vec2(50,15),rotation_deg=90)
    assert feature_is_within_surface(s, unrotated, 100, 100)
    assert not feature_is_within_surface(s, rotated, 100, 100)


def test_rotation_180_and_360_are_quadrant_consistent():
    base = (Vec2(-10,-5), Vec2(10,-5), Vec2(10,5), Vec2(-10,5))
    s = feature_surface_from_rect('s', Vec2(0,0), Vec2(300,300))
    f180 = ProfileFeature(base, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100,100), rotation_deg=180)
    f360 = ProfileFeature(base, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100,100), rotation_deg=360)
    r180 = resolve_surface_features(s,[f180],300,300)[0]
    r360 = resolve_surface_features(s,[f360],300,300)[0]
    assert r180.points[0] == Vec2(110,105)
    assert r360.points[0] == Vec2(90,95)
