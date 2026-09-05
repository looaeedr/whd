import pytest

from ae_engine.sheetmetal_geometry import (
    FourSideFlangeGeometry,
    RectCornerReliefPolicy,
    build_four_side_outline,
    build_four_side_bend_segments,
)


def xy(points):
    return [(p.x, p.y) for p in points]


def lines(segments):
    return [((s.p1.x, s.p1.y), (s.p2.x, s.p2.y)) for s in segments]


def test_four_side_outline_supports_asymmetric_corner_trims():
    g = FourSideFlangeGeometry(
        total_width=200,
        total_height=120,
        thickness=2,
        left_fold=20,
        right_fold=15,
        top_fold=12,
        bottom_fold=10,
    )
    policy = RectCornerReliefPolicy(
        bottom_left_x=18,
        bottom_right_x=13,
        top_left_x=17,
        top_right_x=11,
        bottom_y=10,
        top_y=12,
    )

    assert xy(build_four_side_outline(g, policy)) == [
        (18.0, 0.0),
        (187.0, 0.0),
        (187.0, 10.0),
        (200.0, 10.0),
        (200.0, 108.0),
        (189.0, 108.0),
        (189.0, 120.0),
        (17.0, 120.0),
        (17.0, 108.0),
        (0.0, 108.0),
        (0.0, 10.0),
        (18.0, 10.0),
        (18.0, 0.0),
    ]


def test_four_side_bends_are_clipped_to_remaining_material():
    g = FourSideFlangeGeometry(
        total_width=200,
        total_height=120,
        thickness=2,
        left_fold=20,
        right_fold=15,
        top_fold=12,
        bottom_fold=10,
    )
    policy = RectCornerReliefPolicy(
        bottom_left_x=18,
        bottom_right_x=13,
        top_left_x=17,
        top_right_x=11,
        bottom_y=10,
        top_y=12,
    )

    assert lines(build_four_side_bend_segments(g, policy)) == [
        ((20.0, 0.0), (20.0, 120.0)),
        ((185.0, 0.0), (185.0, 120.0)),
        ((18.0, 10.0), (187.0, 10.0)),
        ((17.0, 108.0), (189.0, 108.0)),
    ]
