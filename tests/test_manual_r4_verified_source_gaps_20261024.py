# -*- coding: utf-8 -*-
"""Independent R4 live-source acceptance for fixes missing from current localX.

Only real product functions and Shapely geometry. This does NOT count the
remaining audit items as approved.
"""
import pytest
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon

from ae_engine.assembly_collision_corner import _polygon_parts
from ae_engine.corner_resolver import standard_corner_geometry
from ae_engine.receiving_hole_candidates import (
    create_candidate, normalize_candidates, update_candidate,
)
from ae_engine.receiving_shared_settings import validate_setting
from ae_engine.sheetmetal_drawing import (
    resolved_features_to_primitives, build_endcap_check,
)
from ae_engine.sheetmetal_feature_core import (
    _normalize_rotation, CircleFeature, FeatureAnchor, ResolvedProfile,
)
from ae_engine.sheetmetal_features import (
    DoorIndicatorContext, hit_test_resolved_features,
    indicator_box_outer_size, legacy_hole_to_feature,
    resolve_door_indicator_features, resolve_door_indicator_layout,
)
from ae_engine.sheetmetal_geometry import (
    EndCapGeometry, Vec2, calculate_endcap_relief_dimensions,
)
from ae_engine.sheetmetal_part_adapters import (
    complete_partition, derive_door_layout_cells, validate_door_layout_dimensions,
    calculate_door_finished_size, build_box_body_result_from_fold_profile,
)
from phase6_designer_workspace import Phase6DesignerWorkspace


def test_r4_rotation_does_not_round_invalid_operator_angle():
    for bad in (True, 30, 89.6, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="rotation"):
            _normalize_rotation(bad)
    assert _normalize_rotation(360) == 0
    for bad in (True, 30):
        with pytest.raises(ValueError, match="rotation"):
            legacy_hole_to_feature({
                "type": "方形", "x": 10., "y": 15.,
                "params": {"width": 20., "height": 10., "rotation_deg": bad},
            })


def test_r4_open_marking_is_not_closed_or_fake_single_point():
    p = ResolvedProfile(points=(Vec2(0., 0.), Vec2(40., 0.)), layer="MARKING")
    invalid = ResolvedProfile(points=(Vec2(5., 5.),), layer="MARKING")
    drawn = resolved_features_to_primitives((p, invalid))
    assert len(drawn) == 1
    assert drawn[0].closed is False
    assert len(drawn[0].points) == 2
    assert hit_test_resolved_features(Vec2(20., .5), (p,), tolerance=1.) == 0
    assert hit_test_resolved_features(Vec2(20., 20.), (p,), tolerance=1.) is None
    assert hit_test_resolved_features(Vec2(5., 5.), (invalid,), tolerance=1.) == 0


def test_r4_endcap_bend_check_comes_from_real_flat_fold_span():
    geom = EndCapGeometry(
        total_width=300., total_depth=150.,
        left_fold=20., right_fold=20.,
        top_first_fold=15., fw=25., bottom_fold=18., thickness=2.,
    )
    row = build_endcap_check(
        geometry=geom, relief=calculate_endcap_relief_dimensions(geom),
        finished_width=264., finished_depth=100., part_label="Top Cap",
    )[0]
    assert "折彎尺寸: 260*92" in row.text


def test_r4_corner_uses_real_mapping_fold_source_and_rejects_bad_name():
    with pytest.raises(ValueError, match="Unsupported corner_name"):
        standard_corner_geometry("top_unknown", (), ())
    result = standard_corner_geometry(
        "top_left",
        ({"phase6_key": "yl1", "len": -25.},),
        ({"phase6_key": "ytop1", "len": -30.},),
    )
    assert (result.primary_u, result.primary_v) == pytest.approx((25., 30.))


def test_r4_indicator_groups_are_positive_whole_counts():
    context = DoorIndicatorContext(500., 700., 19., 19.)
    for bad in (True, False, 0, -2, "abc", 2.5):
        for fn in (
            lambda: indicator_box_outer_size([bad]),
            lambda: resolve_door_indicator_features(context, [bad]),
            lambda: resolve_door_indicator_layout(context, [bad]),
        ):
            with pytest.raises(ValueError, match="group"):
                fn()


def test_r4_receiving_candidates_do_not_store_arbitrary_python_objects():
    bad = {
        "schema": "receiving-hole-candidates-v1",
        "head": {"next_number": 2, "versions": [
            {"id": "head-v1", "features": [{"bad": "not Feature"}]}]},
        "tail": {"next_number": 1, "versions": []},
    }
    with pytest.raises(ValueError, match="Feature"):
        normalize_candidates(bad)
    with pytest.raises(ValueError, match="Feature"):
        create_candidate(None, "head", ["not Feature"])
    good, ident = create_candidate(
        None, "head", [CircleFeature(
            diameter=10., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(0., 0.),
        )],
    )
    assert ident == "head-v1"
    with pytest.raises(ValueError, match="Feature"):
        update_candidate(good, "head", ident, [123])
    with pytest.raises(ValueError, match="feature"):
        validate_setting("head_features", [{"bad": "not Feature"}])


def test_r4_part_adapters_refuse_bool_nan_and_negative_size():
    for fn in (
        lambda: complete_partition((100.,), True),
        lambda: complete_partition((100.,), 500., tolerance=-.5),
        lambda: derive_door_layout_cells(((True, (800.,)),)),
        lambda: validate_door_layout_dimensions(
            ((600., (800.,)),), total_width=float("nan"), total_height=800.),
        lambda: calculate_door_finished_size(
            w=600., h=800., t=True, fw=25., gap_w=2., gap_h=2.),
        lambda: calculate_door_finished_size(
            w=600., h=800., t=1.5, fw=-1., gap_w=2., gap_h=2.),
    ):
        with pytest.raises(ValueError):
            fn()


def test_r4_fold_profile_mapping_rows_honor_explicit_len_when_length_none():
    res = build_box_body_result_from_fold_profile([
        {"len": 25., "angle": 90.},
        {"core": "D", "length": None, "len": 200., "angle": 90.},
        {"core": "W", "len": 400., "angle": 90.},
        {"core": "D", "len": 200., "angle": 90.},
        {"len": 25., "angle": None},
    ], h=500., t=1.5)
    assert res.width > 0 and res.height > 0


def test_r4_nested_collision_multipolygon_must_keep_all_components():
    p1 = Polygon(((0., 0.), (10., 0.), (10., 10.), (0., 10.)))
    p2 = Polygon(((20., 0.), (30., 0.), (30., 10.), (20., 10.)))
    assert len(_polygon_parts(GeometryCollection((MultiPolygon((p1, p2)),)))) == 2


def test_r4_removing_door_prunes_stale_child_assembly_placement():
    ws = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "door", "base_plate"],
        "active_part": "box_body",
        "assembly_placements": {
            "door": {"offset_x": 0.},
            "inner_door:1:panel": {"offset_x": 10., "parent_assembly_node": "door"},
            "base_plate": {"offset_x": 5.},
        },
    })
    assert ws.remove_part("door")
    placements = ws.snapshot()["assembly_placements"]
    assert "door" not in placements
    assert "inner_door:1:panel" not in placements
    assert "base_plate" in placements

def test_r4_70_incomplete_piece_width_does_not_enter_true_world_mesh(monkeypatch):
    """Preview stub has no formed-width datum: do not synthesize a box skin."""
    from types import SimpleNamespace
    import phase6_final_scene_projection as projection
    import phase6_manufacturing_geometry as manufacturing

    stub = SimpleNamespace(role="left")
    part = SimpleNamespace(part_key="box_body", render_data=SimpleNamespace(pieces=(stub,)))

    def forbidden_manufacturing(*_args, **_kwargs):
        raise AssertionError("missing formed_w_end cannot enter physical world geometry")

    monkeypatch.setattr(manufacturing, "_phase6_build_joint_world_geometry", forbidden_manufacturing)
    assert projection._phase6_box_body_true_world_piece_meshes(
        part, dimensions=(800., 1600., 350.), thickness=2.,
    ) == ()
    assert projection._phase6_box_body_structure_meshes(
        part.render_data, thickness=2.,
    ) == []


def test_r4_70_complete_piece_datum_keeps_physical_world_mesh(monkeypatch):
    from types import SimpleNamespace
    import phase6_final_scene_projection as projection
    import phase6_manufacturing_geometry as manufacturing

    triangle = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.))
    piece = SimpleNamespace(role="left", formed_w_end=800.)
    part = SimpleNamespace(part_key="box_body", render_data=SimpleNamespace(pieces=(piece,)))
    monkeypatch.setattr(
        manufacturing, "_phase6_build_joint_world_geometry",
        lambda *_args, **_kwargs: {"world_triangles_by_part": {"box_body:left": (triangle,)}},
    )
    assert projection._phase6_box_body_true_world_piece_meshes(
        part, dimensions=(800., 1600., 350.), thickness=2.,
    ) == ((piece, (triangle,)),)

@pytest.mark.parametrize("bad", ["23", "2,3", {2: 99}, None, True, 2, {2, 3}])
def test_r4_57_indicator_groups_require_real_sequence_not_string_or_mapping(bad):
    """A corrupt saved group source must not silently create extra manufacturing holes."""
    from ae_engine.sheetmetal_features import _normalize_indicator_groups, indicator_box_outer_size
    with pytest.raises(ValueError, match="indicator group"):
        _normalize_indicator_groups(bad)
    with pytest.raises(ValueError, match="indicator group"):
        indicator_box_outer_size(bad)


def test_r4_57_valid_indicator_groups_keep_original_formula():
    from ae_engine.sheetmetal_features import _normalize_indicator_groups, indicator_box_outer_size
    assert _normalize_indicator_groups([2, 3]) == (2, 3)
    assert indicator_box_outer_size([2, 3]) == (486., 725.)
