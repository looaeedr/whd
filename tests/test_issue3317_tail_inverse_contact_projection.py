"""#3317 inverse formed R/BA contact into original flat material, CHECK only.

Independent unit test: this explicitly does not certify the actual Tail V.
"""
import math
import pytest

from ae_engine.sheetmetal_geometry_core import Vec2
from ae_engine.v_miter_tail_dual_source_check import (
    _inverse_straight_90_fold_contact,
    _apex_ray_side_exit_least_squares,
)


def test_straight_90_fold_inverse_reuses_real_rba_and_source_apex():
    apex = Vec2(15.0, 48.0)
    inner_r, thickness, ba = 2.0, 2.0, 4.178318229274424
    mid_r = inner_r + thickness / 2.0
    target = (12.0, 45.0)
    fractions = (0.25, 0.50, 0.75, 0.95)
    reach = 15.0 - ba + mid_r
    zs = [mid_r + f * (reach - mid_r) for f in fractions]
    side = tuple(_inverse_straight_90_fold_contact(
        target, z, apex=apex,
        axis=(0, 1, 0), outside=(-1, 0, 0),
        bend_allowance_mm=ba, mid_radius_mm=mid_r,
    ) for z in zs)
    bottom = tuple(_inverse_straight_90_fold_contact(
        target, z, apex=apex,
        axis=(1, 0, 0), outside=(0, -1, 0),
        bend_allowance_mm=ba, mid_radius_mm=mid_r,
    ) for z in zs)
    for z, s, b in zip(zs, side, bottom):
        flat_u = ba + z - mid_r
        assert (s.x, s.y) == pytest.approx((15-flat_u, 45.0))
        assert (b.x, b.y) == pytest.approx((12.0, 48-flat_u))
        # Side stock's ORIGINAL BEND only starts at y=49. This inverse
        # witness is outside that span; never fill the missing stock.
        assert s.y < 49.0
    side_exit, side_residual = _apex_ray_side_exit_least_squares(
        apex, side, side_x=0.0,
    )
    bottom_exit, bottom_residual = _apex_ray_side_exit_least_squares(
        apex, bottom, side_x=0.0,
    )
    assert math.isfinite(side_exit) and math.isfinite(bottom_exit)
    assert side_exit < apex.y  # NOT the required upper V outer opening
    assert side_residual > 0  # straight ray cannot cover curved-root offset
    assert bottom_residual > 0


def test_one_sided_source_tip_extension_preserves_original_other_end():
    from ae_engine.assembly_geometry_folded_mesh import _fold_tip_weights
    from ae_engine.manufacturing_render_data import FoldGuide
    source_profile = ({"len": 15.0}, {"len": 200.0})
    actual_guide = (FoldGuide("x", 15.0, 49.0, 290.0),)
    assert _fold_tip_weights(source_profile,"x",48.75,actual_guide) == (False,)
    assert _fold_tip_weights(
        source_profile,"x",48.75,actual_guide,
        (("x",15.0,48.0,290.0),),
    ) == (True,)
    assert _fold_tip_weights(
        source_profile,"x",47.0,actual_guide,
        (("x",15.0,48.0,290.0),),
    ) == (False,)
    assert _fold_tip_weights(
        source_profile,"x",291.0,actual_guide,
        (("x",15.0,48.0,290.0),),
    ) == (False,)


def test_root_triangle_pair_count_does_not_imply_volume_penetration():
    from ae_engine.v_miter_tail_dual_source_check import (
        _root_intersection_topology,
    )
    # Four triangles overlap on a SINGLE physical common Z edge; it
    # must not be called four distinct volumetric collisions.
    same_edge = (
        ((0,0,-1),(0,0,0)),
        ((0,0,-0.5),(0,0,0.5)),
        ((0,0,0),(0,0,1)),
        ((0,0,-1),(0,0,1)),
    )
    assert _root_intersection_topology(same_edge,1e-6) == (
        "COLLINEAR_SHARED_ROOT_EDGE_CANDIDATE_NOT_PENETRATION"
    )
    assert _root_intersection_topology(
        (((0,0,0),(1,0,0)),((0,0,0),(0,1,0))),1e-6,
    ) == "ROOT_SURFACE_INTERSECTION_NOT_YET_CLASSIFIED_AS_PENETRATION"
    assert _root_intersection_topology((),1e-6) == (
        "NO_ROOT_SURFACE_INTERSECTION"
    )


def test_inverse_rejects_missing_straight_section_or_ray():
    from ae_engine.sheetmetal_geometry_core import GeometryError
    with pytest.raises(GeometryError, match="NOT_ON_STRAIGHT"):
        _inverse_straight_90_fold_contact(
            (12, 45), 2.0, apex=Vec2(15, 48),
            axis=(0, 1, 0), outside=(-1, 0, 0),
            bend_allowance_mm=4.178318229274424, mid_radius_mm=3.0,
        )
    with pytest.raises(GeometryError, match="NOT_DETERMINED"):
        _apex_ray_side_exit_least_squares(
            Vec2(15, 48), (Vec2(15, 47), Vec2(15, 46)), 0.0,
        )



def test_tail_corrected_full_side_bend_overlapping_uv_depends_on_fold_order():
    """The user's Y=0 side BEND makes the original lower corners TWO-fold.

    This supersedes the old Y=49 disjoint source-partition assumption:
    first-stage AND final-stage coordinates must reflect the selected order.
    Source parameters match the 522x233 illustrated Factory check and the
    existing T2/R2/BA physical CHECK, not a manufacturing certification.
    """
    from ae_engine.v_miter_tail_sequential_fold_check import (
        _advance_same_source_uv,
    )
    params=(15.,507.,48.,0.,522.,190.,4.178318229274424,3.)
    retained=((7.5,55.5),(7.5,40.5),(514.5,55.5),
              (514.5,40.5),(15.,48.),(507.,48.),
              (1.,15.),(521.,15.),(100.,100.),(100.,40.))
    first_different=0
    final_different=0
    for uv in retained:
        sx,fx,_,_=_advance_same_source_uv(uv,"x",params)
        sy,fy,_,_=_advance_same_source_uv(uv,"y",params)
        if math.dist(sx,sy)>1e-6:
            first_different+=1
        if math.dist(fx,fy)>1e-6:
            final_different+=1
        if uv==(100.,100.):
            assert fx==pytest.approx(fy,abs=1e-9)
    assert first_different>=4
    assert final_different>=2, "Both bends must actually move lower side stock"
