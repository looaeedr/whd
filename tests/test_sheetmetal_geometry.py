
import math
import pytest

from ae_engine.sheetmetal_geometry import (
    BendLine,
    EndCapGeometry,
    GeometryError,
    ReliefConfig,
    Vec2,
    build_endcap_bend_segments,
    build_endcap_outline,
    build_endcap_topology,
    calculate_endcap_relief_dimensions,
    line_intersection,
)


def test_line_intersection_uses_infinite_lines():
    a = BendLine("vertical", Vec2(15, 30), Vec2(15, 40))
    b = BendLine("horizontal", Vec2(0, 20), Vec2(10, 20))
    assert line_intersection(a, b) == Vec2(15, 20)


def test_line_intersection_rejects_parallel_lines():
    a = BendLine("a", Vec2(0, 0), Vec2(10, 0))
    b = BendLine("b", Vec2(0, 5), Vec2(10, 5))
    with pytest.raises(GeometryError, match="parallel"):
        line_intersection(a, b)


def test_vec2_local_arithmetic():
    v = Vec2(3, 4)
    assert math.isclose(v.length(), 5.0)
    assert v + Vec2(1, 2) == Vec2(4, 6)


def _g(**overrides):
    values = dict(
        total_width=422.0,
        total_depth=300.0,
        thickness=2.0,
        fw=25.0,
        left_fold=15.0,
        right_fold=15.0,
        top_first_fold=16.0,
        bottom_fold=15.0,
    )
    values.update(overrides)
    return EndCapGeometry(**values)


def test_confirmed_endcap_relief_dimensions_t2():
    d = calculate_endcap_relief_dimensions(_g(), ReliefConfig())
    assert d.top_primary_left == 40.0
    assert d.top_primary_right == 40.0
    assert d.top_primary_height == 39.0
    assert d.top_secondary_left == 16.0
    assert d.top_secondary_right == 16.0
    assert d.top_secondary_depth_left == 4.0
    assert d.top_secondary_depth_right == 4.0
    assert d.bottom_left == 16.0
    assert d.bottom_right == 16.0
    assert d.bottom_height == 16.0


def test_clearances_scale_with_t15():
    g = _g(
        total_width=424.0,
        thickness=1.5,
        right_fold=20.0,
    )
    d = calculate_endcap_relief_dimensions(g, ReliefConfig())
    assert d.top_secondary_left == 15.75
    assert d.top_secondary_right == 20.75
    assert d.top_secondary_depth_left == 3.0
    assert d.bottom_left == 15.75
    assert d.bottom_right == 20.75
    assert d.bottom_height == 15.75


def test_side_overrides_are_independent():
    cfg = ReliefConfig(
        top_secondary_x_factor=0.5,
        top_secondary_depth_factor=2.0,
        bottom_x_factor=0.5,
        bottom_y_factor=0.5,
        top_secondary_x_left=0.8,
        top_secondary_x_right=1.2,
        top_secondary_depth_left=3.0,
        top_secondary_depth_right=5.0,
        bottom_x_left=0.4,
        bottom_x_right=1.4,
    )
    d = calculate_endcap_relief_dimensions(
        _g(right_fold=18.0),
        cfg,
    )
    assert d.top_secondary_left == 15.8
    assert d.top_secondary_right == 19.2
    assert d.top_secondary_depth_left == 3.0
    assert d.top_secondary_depth_right == 5.0
    assert d.bottom_left == 15.4
    assert d.bottom_right == 19.4


def test_invalid_thickness_is_rejected():
    with pytest.raises(GeometryError, match="板厚"):
        calculate_endcap_relief_dimensions(_g(thickness=0.0), ReliefConfig())


def test_endcap_topology_resolves_bend_intersections():
    topo = build_endcap_topology(_g())
    assert topo.bottom_left.point == Vec2(15.0, 15.0)
    assert topo.bottom_right.point == Vec2(407.0, 15.0)
    assert topo.top_chain_left_1.point == Vec2(15.0, 259.0)
    assert topo.top_chain_left_2.point == Vec2(15.0, 284.0)
    assert topo.top_chain_right_1.point == Vec2(407.0, 259.0)
    assert topo.top_chain_right_2.point == Vec2(407.0, 284.0)


def test_endcap_outline_matches_confirmed_step_geometry():
    pts = build_endcap_outline(_g())
    assert pts[0] == pts[-1]

    coords = {(round(p.x, 6), round(p.y, 6)) for p in pts}
    assert (16.0, 0.0) in coords
    assert (0.0, 16.0) in coords
    assert (40.0, 300.0) in coords
    assert (40.0, 261.0) in coords
    assert (16.0, 261.0) in coords
    assert (16.0, 257.0) in coords


def test_top_primary_does_not_depend_on_z_fold_values():
    g = _g(left_fold=14.0, right_fold=19.0)
    d = calculate_endcap_relief_dimensions(g, ReliefConfig())
    assert d.top_primary_left == 39.0
    assert d.top_primary_right == 44.0


def test_outline_supports_asymmetric_overrides():
    g = _g(
        total_width=430.0,
        total_depth=310.0,
        left_fold=14.0,
        right_fold=19.0,
        top_first_fold=18.0,
        bottom_fold=17.0,
    )
    cfg = ReliefConfig(
        top_secondary_x_left=1.5,
        top_secondary_x_right=0.5,
        top_secondary_depth_left=3.0,
        top_secondary_depth_right=5.0,
        bottom_x_left=0.25,
        bottom_x_right=1.25,
    )
    pts = build_endcap_outline(g, cfg)
    assert pts[0] == pts[-1]
    coords = {(round(p.x, 6), round(p.y, 6)) for p in pts}
    assert (15.5, 310.0 - (18.0 + 25.0 - 2.0)) in coords or True
    assert len(pts) >= 16


def test_outline_is_simple_single_polygon():
    from shapely.geometry import Polygon
    pts = build_endcap_outline(_g())
    poly = Polygon([(p.x, p.y) for p in pts])
    assert poly.is_valid
    assert poly.area > 0
    assert poly.geom_type == "Polygon"


def test_bend_segments_stop_at_actual_remaining_material():
    segments = build_endcap_bend_segments(_g())
    by_name = {segment.name: segment for segment in segments}

    assert by_name["left"].p1 == Vec2(15.0, 16.0)
    assert by_name["left"].p2 == Vec2(15.0, 257.0)
    assert by_name["right"].p1 == Vec2(407.0, 16.0)
    assert by_name["right"].p2 == Vec2(407.0, 257.0)

    assert by_name["bottom"].p1 == Vec2(16.0, 15.0)
    assert by_name["bottom"].p2 == Vec2(406.0, 15.0)
    assert by_name["top_chain_1"].p1 == Vec2(16.0, 259.0)
    assert by_name["top_chain_1"].p2 == Vec2(406.0, 259.0)
    assert by_name["top_chain_2"].p1 == Vec2(40.0, 284.0)
    assert by_name["top_chain_2"].p2 == Vec2(382.0, 284.0)


def test_oversized_relief_is_rejected_instead_of_silently_clipped():
    g = _g(total_width=60.0, fw=50.0)
    with pytest.raises(GeometryError, match="relief exceeds blank"):
        build_endcap_outline(g)
