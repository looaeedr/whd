import pytest

from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature,
    RectFeature,
    FeatureAnchor,
    FeatureSurface,
    feature_is_within_surface,
    feature_surface_from_outline,
    move_feature_within_surface,
)


def circle(x, y, diameter=20.0):
    return CircleFeature(diameter=diameter, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(x, y))


def rect(x, y, width=20.0, height=10.0):
    return RectFeature(width=width, height=height, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(x, y))


def test_circle_requires_full_footprint_inside_surface():
    surface = feature_surface_from_outline('panel', [Vec2(0,0), Vec2(100,0), Vec2(100,60), Vec2(0,60)])
    assert feature_is_within_surface(surface, circle(50, 30), 100, 60)
    assert feature_is_within_surface(surface, circle(10, 30), 100, 60)  # tangent is allowed
    assert not feature_is_within_surface(surface, circle(9.9, 30), 100, 60)


def test_rectangle_requires_all_corners_inside_surface():
    surface = feature_surface_from_outline('panel', [Vec2(0,0), Vec2(100,0), Vec2(100,60), Vec2(0,60)])
    assert feature_is_within_surface(surface, rect(90, 50, 20, 20), 100, 60)
    assert not feature_is_within_surface(surface, rect(91, 50, 20, 20), 100, 60)


def test_non_rectangular_surface_rejects_feature_that_crosses_cut_corner():
    surface = feature_surface_from_outline('cut-corner', [
        Vec2(0,0), Vec2(100,0), Vec2(100,40), Vec2(80,60), Vec2(0,60)
    ])
    assert feature_is_within_surface(surface, circle(70, 45, 10), 100, 60)
    assert not feature_is_within_surface(surface, circle(88, 50, 10), 100, 60)


def test_surface_factory_is_generic_and_has_no_part_name_allowlist():
    surface = feature_surface_from_outline('anything-user-selected', [
        Vec2(0,0), Vec2(40,0), Vec2(40,20), Vec2(0,20)
    ])
    assert isinstance(surface, FeatureSurface)
    assert surface.surface_id == 'anything-user-selected'
    assert feature_is_within_surface(surface, circle(20, 10, 4), 40, 20)


def test_invalid_drag_keeps_last_valid_feature():
    surface = feature_surface_from_outline('panel', [Vec2(0,0), Vec2(100,0), Vec2(100,60), Vec2(0,60)])
    original = circle(50, 30, 20)
    moved = move_feature_within_surface(original, Vec2(95, 30), 100, 60, surface)
    assert moved == original


def test_valid_drag_updates_feature():
    surface = feature_surface_from_outline('panel', [Vec2(0,0), Vec2(100,0), Vec2(100,60), Vec2(0,60)])
    original = circle(50, 30, 20)
    moved = move_feature_within_surface(original, Vec2(70, 30), 100, 60, surface)
    assert moved != original
    from ae_engine.sheetmetal_features import feature_finished_point
    assert feature_finished_point(moved, 100, 60) == Vec2(70, 30)

def test_any_structural_result_can_become_feature_surface():
    from ae_engine.sheetmetal_part_adapters import build_door_result, build_base_plate_result
    from ae_engine.sheetmetal_features import feature_surface_from_structural_result

    door = build_door_result(
        w=800, h=1800, t=2, fw=25, gap_w=4, gap_h=4,
        fold_left=20, fold_right=20, fold_top=20, fold_bottom=20,
    )
    base = build_base_plate_result(
        w=800, h=600, t=2,
        shrink_top=10, shrink_bottom=10, shrink_left=10, shrink_right=10,
        bend=30,
    )

    for name, result in (("door", door), ("base", base)):
        surface = feature_surface_from_structural_result(name, result)
        assert surface.surface_id == name
        assert surface.polygon.area > 0

def test_endcap_export_resolver_rejects_hole_whose_footprint_crosses_face_boundary():
    import ae_engine.ae as ae
    from ae_engine.sheetmetal_part_adapters import build_endcap_result

    result = build_endcap_result(
        w=500, d=150, t=2, fw=25,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        relief_config=ae.RELIEF_CONFIG,
    )
    illegal = [{"type":"圓形", "x":5.0, "y":50.0, "params":{"diameter":20.0}}]
    with pytest.raises(ValueError, match="outside feature surface"):
        ae._resolve_user_holes(illegal, result.topology, 500, 150)

def test_resolve_surface_features_returns_world_space_resolved_features_and_validates():
    from ae_engine.sheetmetal_features import resolve_surface_features, ResolvedCircle
    surface = feature_surface_from_outline('panel', [Vec2(0,0), Vec2(100,0), Vec2(100,60), Vec2(0,60)])
    resolved = resolve_surface_features(surface, [circle(50,30,20)], 100, 60)
    assert len(resolved) == 1
    assert isinstance(resolved[0], ResolvedCircle)
    assert resolved[0].center == Vec2(50,30)
    with pytest.raises(ValueError, match='outside feature surface'):
        resolve_surface_features(surface, [circle(5,30,20)], 100, 60)
