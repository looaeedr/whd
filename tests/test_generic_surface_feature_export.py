import pytest

import ae_engine.ae as ae
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_drawing import CirclePrimitive


def user_circle(x, y, diameter=10.0):
    return CircleFeature(
        diameter=diameter,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y),
        layer='CUTTING',
        source_type='圓形',
    )


def _count_user_circle(scene, x, y, radius=5.0):
    return sum(
        1 for p in scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.layer == 'CUTTING'
        and abs(p.center.x-x) < 1e-6
        and abs(p.center.y-y) < 1e-6
        and abs(p.radius-radius) < 1e-6
    )


def test_door_builder_accepts_generic_surface_user_feature():
    scene = ae._build_door_scene(
        w=800, h=1800, t=2, fw=25, gw=4, gh=4,
        fl=20, fr=20, ft=20, fb=20,
        user_features=[user_circle(100,100)],
    )
    assert _count_user_circle(scene, 100, 100) == 1


def test_box_body_builder_accepts_generic_surface_user_feature():
    scene = ae._build_box_body_scene(
        w=500, h=600, d=150, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=-10,
        user_features=[user_circle(100,100)],
    )
    assert _count_user_circle(scene, 100, 100) == 1


def test_base_plate_builder_accepts_generic_surface_user_feature():
    scene = ae._build_base_plate_scene(
        w=800, h=600, t=2, st=10, sb=10, sl=10, sr=10, bend=30,
        user_features=[user_circle(100,100)],
    )
    assert _count_user_circle(scene, 100, 100) == 1


def test_indicator_box_builder_accepts_generic_surface_user_feature():
    scene = ae._build_indicator_box_scene([2], 2.0, user_features=[user_circle(100,100)])
    assert _count_user_circle(scene, 100, 100) == 1


def test_generic_builder_rejects_feature_crossing_outline():
    with pytest.raises(ValueError, match='outside feature surface'):
        ae._build_base_plate_scene(
            w=800, h=600, t=2, st=10, sb=10, sl=10, sr=10, bend=30,
            user_features=[user_circle(1, 1, 20)],
        )
