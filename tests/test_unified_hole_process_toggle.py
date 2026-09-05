from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature, ProfileFeature, FeatureAnchor,
    feature_with_process, resolve_surface_features, feature_surface_from_rect,
)


def test_circle_process_toggle_cutting_blind():
    f = CircleFeature(20, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(50,50), layer="CUTTING")
    blind = feature_with_process(f, "BLIND_HOLE")
    assert blind.layer == "BLIND_HOLE"
    assert feature_with_process(blind, "CUTTING").layer == "CUTTING"


def test_profile_process_override_rewrites_all_profile_layers():
    f = ProfileFeature(
        points=(Vec2(-5,-5),Vec2(5,-5),Vec2(5,5),Vec2(-5,5)),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(50,50),
        layer="FROM_DXF",
        layered_profiles=(
            ("CUTTING", (Vec2(-5,-5),Vec2(5,-5),Vec2(5,5),Vec2(-5,5)), True),
            ("DATUM", (Vec2(-5,0),Vec2(5,0)), False),
        ),
    )
    blind = feature_with_process(f, "BLIND_HOLE")
    assert blind.layer == "BLIND_HOLE"
    assert {layer for layer, _, _ in blind.layered_profiles} == {"BLIND_HOLE"}
    s = feature_surface_from_rect("s", Vec2(0,0), Vec2(100,100))
    r = resolve_surface_features(s, [blind], 100, 100)[0]
    assert {layer for layer, _, _ in r.layered_profiles} == {"BLIND_HOLE"}
