import pytest

from ae_engine.sheetmetal_geometry import ReliefConfig
from ae_engine.sheetmetal_part_adapters import (
    build_box_body_result,
    build_door_result,
    build_base_plate_result,
    build_indicator_box_result,
    build_endcap_result,
)


def test_box_body_result_has_eight_bends_and_expected_size():
    result = build_box_body_result(
        w=600, h=800, d=250, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
    )
    assert len(result.bends) == 8
    assert result.height == pytest.approx(796)
    assert result.width == pytest.approx(15+20+25+246+596+246+25+20+15+2)


def test_door_result_uses_thickness_dependent_corner_geometry():
    result = build_door_result(
        w=600, h=800, t=1.5, fw=25,
        gap_w=3, gap_h=3,
        fold_left=49, fold_right=49, fold_top=49, fold_bottom=49,
    )
    assert result.topology.__class__.__name__ == "FourSideFlangeGeometry"
    assert len(result.bends) == 4
    assert min(p.x for p in result.outline if p.y == pytest.approx(0)) == pytest.approx(47.5)


def test_base_plate_result_has_four_bends():
    result = build_base_plate_result(
        w=600, h=800, t=2,
        shrink_top=5, shrink_bottom=5, shrink_left=5, shrink_right=5,
        bend=25,
    )
    assert len(result.bends) == 4
    assert result.width == pytest.approx(640)
    assert result.height == pytest.approx(840)


def test_indicator_box_result_uses_fold_minus_t():
    result = build_indicator_box_result(total_width=326, total_height=445, t=1.5, fold=49)
    assert len(result.bends) == 4
    bottom_xs = [p.x for p in result.outline if p.y == pytest.approx(0)]
    assert min(bottom_xs) == pytest.approx(47.5)


def test_endcap_result_uses_shared_relief_config():
    cfg = ReliefConfig(
        top_secondary_x_factor=0.5,
        top_secondary_depth_factor=2.0,
        bottom_x_factor=0.5,
        bottom_y_factor=0.5,
    )
    result = build_endcap_result(
        w=600, d=250, t=2, fw=25,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        relief_config=cfg,
    )
    assert len(result.bends) == 5
    assert result.width == pytest.approx(622)
    assert result.height == pytest.approx(300)


def test_finished_reference_guide_door_uses_assembled_size_not_blank_or_bends():
    from ae_engine.sheetmetal_part_adapters import build_finished_reference_guide
    result = build_door_result(
        w=600, h=800, t=2, fw=25, gap_w=3, gap_h=3,
        fold_left=49, fold_right=45, fold_top=47, fold_bottom=43,
    )
    finished_w = 600 - (25 + 4) * 2 - 6
    finished_h = 800 - (25 + 4) * 2 - 6
    guide = build_finished_reference_guide("door", result, finished_width=finished_w, finished_height=finished_h)
    assert guide.width == pytest.approx(finished_w)
    assert guide.height == pytest.approx(finished_h)
    # It is centered on the flat face between bend lines, not on the blank bounds.
    face_cx = (49 + (result.width - 45)) / 2
    face_cy = (43 + (result.height - 47)) / 2
    assert (guide.min_point.x + guide.max_point.x) / 2 == pytest.approx(face_cx)
    assert (guide.min_point.y + guide.max_point.y) / 2 == pytest.approx(face_cy)


def test_finished_reference_guide_box_body_uses_front_assembled_w_by_h():
    from ae_engine.sheetmetal_part_adapters import build_finished_reference_guide
    result = build_box_body_result(
        w=600, h=800, d=250, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
    )
    guide = build_finished_reference_guide("box_body", result, finished_width=600, finished_height=800)
    assert guide.width == pytest.approx(600)
    assert guide.height == pytest.approx(800)
    segments = result.topology.segments
    front_i = next(i for i, seg in enumerate(segments) if seg.name == "front")
    front_start = sum(seg.length + seg.compensation for seg in segments[:front_i])
    front_span = segments[front_i].length + segments[front_i].compensation
    front_cx = front_start + front_span / 2
    assert (guide.min_point.x + guide.max_point.x) / 2 == pytest.approx(front_cx)


def test_finished_reference_guide_base_and_endcap_keep_authoritative_finished_dimensions():
    from ae_engine.sheetmetal_part_adapters import build_finished_reference_guide
    base = build_base_plate_result(
        w=600, h=800, t=2, shrink_top=5, shrink_bottom=7,
        shrink_left=8, shrink_right=10, bend=25,
    )
    base_guide = build_finished_reference_guide("base_plate", base, finished_width=582, finished_height=788)
    assert base_guide.width == pytest.approx(582)
    assert base_guide.height == pytest.approx(788)

    cfg = ReliefConfig(0.5, 2.0, 0.5, 0.5)
    cap = build_endcap_result(
        w=600, d=250, t=2, fw=25, yl1=15, yr1=15,
        ytop1=16, ybottom1=15, relief_config=cfg,
    )
    cap_guide = build_finished_reference_guide("head", cap, finished_width=600, finished_height=250)
    assert cap_guide.min_point.x == pytest.approx(0)
    assert cap_guide.min_point.y == pytest.approx(0)
    assert cap_guide.max_point.x == pytest.approx(600)
    assert cap_guide.max_point.y == pytest.approx(250)
