import math

import pytest
import ae_engine.ae as ae
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature,
    ResolvedProfile,
    FeatureAnchor,
    box_body_face_dimensions,
    box_body_face_contexts_from_strip,
    resolve_box_body_face_features,
    placement_from_finished_point,
)
from ae_engine.sheetmetal_part_adapters import build_box_body_result


def _result(w=500, h=600, d=200, t=2, fw=25):
    return build_box_body_result(
        w=w, h=h, d=d, t=t, fw=fw,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
    )


def _circle(x, y, *, width, height, diameter=10, layer="CUTTING"):
    placement = placement_from_finished_point(Vec2(x, y), width, height)
    return CircleFeature(
        diameter=diameter,
        anchor=placement.anchor,
        offset=placement.offset,
        layer=layer,
        source_type="test",
    )


def test_box_body_face_dimensions_are_direct_whd_not_finished_flat_dimensions():
    dims = box_body_face_dimensions(w=500, h=600, d=200)
    assert dims == {
        "left": (200.0, 600.0),
        "back": (500.0, 600.0),
        "right": (200.0, 600.0),
    }


def test_box_body_face_context_maps_outer_whd_coordinates_to_authoritative_strip_segments():
    result = _result()
    contexts = box_body_face_contexts_from_strip(
        result.topology, w=500, h=600, d=200, t=2,
    )

    expected_segment = {"left": "depth_left", "back": "front", "right": "depth_right"}
    segment_starts = {}
    x = 0.0
    for seg in result.topology.segments:
        span = seg.length + seg.compensation
        segment_starts[seg.name] = (x, x + span)
        x += span

    for face, segment_name in expected_segment.items():
        ctx = contexts[face]
        seg_start, seg_end = segment_starts[segment_name]
        outer_w = 500.0 if face == "back" else 200.0
        assert ctx.outer_width == outer_w
        assert ctx.outer_height == 600.0
        assert ctx.segment_name == segment_name
        assert ctx.local_to_unfolded(Vec2(2, 2)) == Vec2(seg_start, 0.0)
        mapped_max = ctx.local_to_unfolded(Vec2(outer_w - 2, 598))
        assert math.isclose(mapped_max.x, seg_end)
        assert math.isclose(mapped_max.y, result.height)
        round_trip = ctx.unfolded_to_local(mapped_max)
        assert math.isclose(round_trip.x, outer_w - 2)
        assert math.isclose(round_trip.y, 598)


def test_box_body_face_features_resolve_into_their_own_unfolded_segments():
    result = _result()
    contexts = box_body_face_contexts_from_strip(
        result.topology, w=500, h=600, d=200, t=2,
    )
    features = {
        "left": [_circle(80, 250, width=200, height=600)],
        "back": [_circle(120, 300, width=500, height=600)],
        "right": [_circle(140, 350, width=200, height=600)],
    }
    resolved = resolve_box_body_face_features(contexts, features)
    assert len(resolved) == 3

    for face, resolved_feature in zip(("left", "back", "right"), resolved):
        ctx = contexts[face]
        assert ctx.unfolded_min_x < resolved_feature.center.x < ctx.unfolded_max_x
        assert 0.0 < resolved_feature.center.y < result.height


def test_real_box_body_baseline_can_be_split_into_face_local_whd_features():
    face_features = ae.get_box_body_baseline_face_features(
        "金庫型", w=500, h=600, d=200, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
    )
    assert set(face_features) == {"left", "back", "right"}
    assert sum(len(v) for v in face_features.values()) > 0
    dims = box_body_face_dimensions(w=500, h=600, d=200)
    for face, items in face_features.items():
        fw, fh = dims[face]
        for item in items:
            points = (item.center,) if hasattr(item, "center") else item.points
            for point in points:
                assert 0.0 <= point.x <= fw
                assert 0.0 <= point.y <= fh


def test_box_body_baseline_status_reports_fixed_feature_mapping_when_present():
    assert ae.box_body_baseline_source_label("金庫型") == "基準檔：金庫型/箱身.dxf（固定特徵映射）"
    assert ae.box_body_baseline_source_label("") == "未使用基準檔（程式計算生成）"


def test_box_body_export_maps_each_face_feature_into_one_single_unfolded_dxf(tmp_path):
    import ezdxf

    w, h, d, t, fw = 500.0, 600.0, 200.0, 2.0, 25.0
    result = _result(w=w, h=h, d=d, t=t, fw=fw)
    contexts = box_body_face_contexts_from_strip(result.topology, w=w, h=h, d=d, t=t)
    face_features = {
        "left": [_circle(80, 250, width=d, height=h, diameter=10)],
        "back": [_circle(120, 300, width=w, height=h, diameter=12)],
        "right": [_circle(140, 350, width=d, height=h, diameter=14)],
    }
    output = tmp_path / "box_body_z.dxf"
    ae.export_box_body_dxf(
        str(output), W_val=w, H_val=h, D_val=d, T_val=t, FW_val=fw,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
        model_name=None, face_features=face_features,
    )

    doc = ezdxf.readfile(output)
    circles = [e for e in doc.modelspace() if e.dxftype() == "CIRCLE"]
    by_radius = {round(float(e.dxf.radius), 6): e for e in circles}
    assert {5.0, 6.0, 7.0}.issubset(by_radius)
    for face, radius in (("left", 5.0), ("back", 6.0), ("right", 7.0)):
        cx = float(by_radius[radius].dxf.center.x)
        cy = float(by_radius[radius].dxf.center.y)
        ctx = contexts[face]
        assert ctx.unfolded_min_x < cx < ctx.unfolded_max_x
        assert 0.0 < cy < result.height


def test_real_box_body_baseline_maps_color_211_linework_into_face_local_marking_geometry():
    from ae_engine.sheetmetal_features import ResolvedProfile
    face_features = ae.get_box_body_baseline_face_features(
        "金庫型", w=500, h=600, d=200, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
    )
    linework = [
        feature
        for features in face_features.values()
        for feature in features
        if isinstance(feature, ResolvedProfile) and feature.layer == "MARKING"
    ]
    assert linework
    assert any(len(profile.points) == 2 for profile in linework)


def _profile_bbox(profiles):
    xs = [p.x for f in profiles for p in f.points]
    ys = [p.y for f in profiles for p in f.points]
    return min(xs), min(ys), max(xs), max(ys)


def test_box_body_depth_placeholder_is_replaced_by_current_depth_marking_value():
    """The vector '150' in the baseline is a placeholder for current D, not fixed linework."""
    features_200 = ae.get_box_body_baseline_unfolded_features(
        "金庫型", 1010.0, 596.0,
        15, 20, 15, 20, 2,
        500, 200, 2, 25,
    )
    generated_200 = [
        f for f in features_200
        if isinstance(f, ResolvedProfile) and f.source_type == "baseline_depth_value"
    ]
    assert generated_200, "current D must be regenerated as MARKING vector linework"
    assert all(f.layer == "MARKING" for f in generated_200)

    # The depth value keeps the baseline placeholder's mapped position and 30 mm height.
    x1, y1, x2, y2 = _profile_bbox(generated_200)
    assert (y2 - y1) == pytest.approx(30.0, abs=0.05)
    assert ((x1 + x2) / 2.0) == pytest.approx(497.97571, abs=0.2)

    # Changing D must change the actual vector marking while preserving its anchor/height.
    result_350 = build_box_body_result(
        w=500, h=600, d=350, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
    )
    features_350 = ae.get_box_body_baseline_unfolded_features(
        "金庫型", result_350.width, result_350.height,
        15, 20, 15, 20, 2,
        500, 350, 2, 25,
    )
    generated_350 = [
        f for f in features_350
        if isinstance(f, ResolvedProfile) and f.source_type == "baseline_depth_value"
    ]
    assert generated_350
    assert tuple(tuple((round(p.x, 4), round(p.y, 4)) for p in f.points) for f in generated_200) != tuple(
        tuple((round(p.x, 4), round(p.y, 4)) for p in f.points) for f in generated_350
    )
    bx1, by1, bx2, by2 = _profile_bbox(generated_350)
    back_200 = box_body_face_contexts_from_strip(
        _result(d=200).topology, w=500, h=600, d=200, t=2
    )["back"]
    back_350 = box_body_face_contexts_from_strip(
        result_350.topology, w=500, h=600, d=350, t=2
    )["back"]
    offset_200 = ((x1 + x2) / 2.0) - (back_200.unfolded_min_x + back_200.unfolded_max_x) / 2.0
    offset_350 = ((bx1 + bx2) / 2.0) - (back_350.unfolded_min_x + back_350.unfolded_max_x) / 2.0
    assert offset_350 == pytest.approx(offset_200, abs=0.2)
    assert (by2 - by1) == pytest.approx(30.0, abs=0.05)


def test_box_body_depth_placeholder_raw_150_lines_are_not_copied_as_fixed_marking():
    features = ae.get_box_body_baseline_unfolded_features(
        "金庫型", 1010.0, 596.0,
        15, 20, 15, 20, 2,
        500, 200, 2, 25,
    )
    generated = [
        f for f in features
        if isinstance(f, ResolvedProfile) and f.source_type == "baseline_depth_value"
    ]
    assert generated
    gx1, gy1, gx2, gy2 = _profile_bbox(generated)

    raw_inside = []
    for f in features:
        if not isinstance(f, ResolvedProfile) or f.source_type != "baseline":
            continue
        if all(gx1 - 1 <= p.x <= gx2 + 1 and gy1 - 1 <= p.y <= gy2 + 1 for p in f.points):
            raw_inside.append(f)
    assert raw_inside == [], "the original vector 150 placeholder must be replaced, not duplicated"


def test_box_body_width_bend_markings_follow_width_bends_and_stay_out_of_face_editors():
    """The four 30 mm baseline marks belong to the two width-boundary BENDs, not a face."""
    result = _result(w=640, h=600, d=240, t=2, fw=25)
    features = ae.get_box_body_baseline_unfolded_features(
        "金庫型", result.width, result.height,
        15, 20, 15, 20, 2,
        640, 240, 2, 25,
    )
    bend_x = {
        b.name: float(b.p1.x)
        for b in result.bends
        if b.name in {"depth_left", "front"}
    }
    vertical_30 = []
    for f in features:
        if not isinstance(f, ResolvedProfile) or f.layer != "MARKING" or len(f.points) != 2:
            continue
        p1, p2 = f.points
        if abs(p1.x - p2.x) <= 1e-6 and abs(abs(p2.y - p1.y) - 30.0) <= 0.05:
            if any(abs(p1.x - x) <= 0.05 for x in bend_x.values()):
                vertical_30.append(f)

    assert len(vertical_30) == 4
    assert sorted(round(f.points[0].x, 4) for f in vertical_30) == sorted(
        [round(bend_x["depth_left"], 4)] * 2 + [round(bend_x["front"], 4)] * 2
    )

    face_features = ae.get_box_body_baseline_face_features(
        "金庫型", w=640, h=600, d=240, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=2,
    )
    face_vertical_30 = []
    for items in face_features.values():
        for f in items:
            if not isinstance(f, ResolvedProfile) or f.layer != "MARKING" or len(f.points) != 2:
                continue
            p1, p2 = f.points
            if abs(p1.x - p2.x) <= 1e-6 and abs(abs(p2.y - p1.y) - 30.0) <= 0.05:
                face_vertical_30.append(f)
    assert face_vertical_30 == [], "width-BEND locator MARKING belongs only to the unfolded sheet"
