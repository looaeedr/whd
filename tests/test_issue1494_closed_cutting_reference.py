"""#1494: user supplied closed CUTTING geometry witnesses the original A1 line.

A verified customer reference is not an authorized production datum or NFB model pivot.
The raw DXF remains outside the repository; this reduced fixture records its SHA.
"""
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def closed_reference():
    return load("tests/fixtures/receiving_nfb_closed_cutting_reference.json")


def original_reference():
    return load("tests/fixtures/receiving_nfb_w800_three_source.json")


def _source_line(handle):
    return next(row for row in original_reference()["entities"] if row["handle"] == handle)


def _contour_segments(points):
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        yield start, end


def test_source_a1_a0_identical_to_two_straight_cutting_segments():
    closed = closed_reference()
    src = original_reference()
    assert closed["source_sha256"] == (
        "f2a30d89a8127eb7296b9269fe464a3f6786674ee4ea9d6097a35cae5050604e"
    )
    assert closed["dxf_insunits"] == 4
    assert closed["layer"] == "CUTTING"
    assert closed["layer_aci"] == 3
    assert closed["all_entities"] == "CLOSED_LWPOLYLINE"
    assert closed["entity_count"] == 13
    assert closed["outer"]["closed"] is True
    assert len(closed["outer"]["vertices_xy_bulge"]) == 24

    segments = list(_contour_segments(closed["outer"]["vertices_xy_bulge"]))
    for handle in (src["blank_left_handle"], src["blank_right_handle"]):
        original = _source_line(handle)
        start, end = original["start"], original["end"]
        matched = [
            (a, b) for a, b in segments
            if a[2] == 0 and (
                (a[:2] == start[:2] and b[:2] == end[:2])
                or (a[:2] == end[:2] and b[:2] == start[:2])
            )
        ]
        assert len(matched) == 1, f"original {handle} must be same straight CUTTING edge"
    xs = [row[0] for row in closed["outer"]["vertices_xy_bulge"]]
    ys = [row[1] for row in closed["outer"]["vertices_xy_bulge"]]
    assert max(xs) - min(xs) == pytest.approx(723)
    assert max(ys) - min(ys) == pytest.approx(1075)
    # Width identity of a supplied reference does NOT certify that it is the
    # generated WHD panel's origin/part or a reversible formed face map.
    assert closed["physical_blank_to_face_box_transform_certified"] is False


def test_two_rows_each_three_28_by_58_openings_and_500_y_pitch():
    closed = closed_reference()
    assert closed["other_inner_contours"] == 6
    assert len(closed["rectangular_holes"]) == 6
    source_left = _source_line(original_reference()["blank_left_handle"])["start"][0]
    by_center_y = {}
    for item in closed["rectangular_holes"]:
        xmin, ymin, xmax, ymax = item["bbox"]
        assert item["closed"] and item["layer"] == "CUTTING"
        assert item["vertex_count"] == 4
        assert xmax - xmin == pytest.approx(28)
        assert ymax - ymin == pytest.approx(58)
        y = (ymin + ymax) / 2
        by_center_y.setdefault(y, []).append((xmin + xmax) / 2 - source_left)
    assert sorted(by_center_y) == [1573.0, 2073.0]
    for row_centers in by_center_y.values():
        assert sorted(row_centers) == pytest.approx([181.5, 361.5, 541.5])
    assert len(set(by_center_y)) == 2
    assert max(by_center_y) - min(by_center_y) == pytest.approx(500)
    assert closed["nfb_model_main_hole_certified"] is False


def test_closed_reference_improves_source_provenance_without_releasing_x():
    closed = closed_reference()
    evidence = load("docs/receiving-nfb-x-evidence.json")
    observed = evidence["w800_t2_three_hole_observation"]
    attachment = observed["closed_cutting_reference"]
    assert attachment["source_sha256"] == closed["source_sha256"]
    assert attachment["source_fixture"] == (
        "tests/fixtures/receiving_nfb_closed_cutting_reference.json"
    )
    assert attachment["a1_a0_straight_segments_match_closed_cutting"] is True
    assert attachment["two_rows_of_three_28_by_58_verified"] is True
    assert attachment["upper_lower_row_center_distance_mm"] == 500
    assert attachment["source_layer"] == "CUTTING"
    assert attachment["raw_customer_file_committed"] is False

    # CERTIFICATION REMAINS BLOCKED: no proven WHD blank→formed face→box
    # projection and no per-model NFB actual cutout center.
    assert observed["source_outline_is_723_cutting_left_verified"] is False
    assert observed["box_world_centers_mm"] is None
    assert observed["certified_x_revision"] is None
    assert observed["not_exportable_as_manufacturing_x"] is True
    row = next(item for item in evidence["records"]
               if (item["box_outer_width_mm"], item["nfb_count"]) == (800, 3))
    assert row["x_status"] == "PREVIEW_ONLY"
    assert row["finished_face_to_box_world_x"] is None


def test_closed_reference_bbox_matches_corrected_whd_inner_door_blank():
    """W800/T2 blank X/Y spans match, without certifying full cutout identity."""
    from ae_engine.cabinet_types.receiving import apply_family_defaults
    from ae_engine.cabinet_types import policy
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    state = apply_family_defaults({
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    state.update({
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{"stable_id": "upper", "cell_key": "0:0",
                         "included_frame_sides": ["top", "left", "right"]}],
    })
    panel = policy.derive_inner_door_panels(state)[0]
    actual = build_inner_door_panel_render_data(panel)
    cuts = [
        primitive for primitive in actual.scene.primitives
        if isinstance(primitive, PolylinePrimitive)
        and primitive.closed and primitive.layer.upper() == "CUTTING"
    ]
    assert len(cuts) == 1
    xs = [point.x for point in cuts[0].points]
    ys = [point.y for point in cuts[0].points]
    raw_outline = closed_reference()["outer"]["vertices_xy_bulge"]
    raw_xs = [point[0] for point in raw_outline]
    raw_ys = [point[1] for point in raw_outline]
    assert max(xs) - min(xs) == pytest.approx(max(raw_xs) - min(raw_xs))
    assert max(xs) - min(xs) == pytest.approx(723.0)
    assert max(ys) - min(ys) == pytest.approx(1075.0)
    assert max(raw_ys) - min(raw_ys) == pytest.approx(1075.0)
    assert (max(raw_ys) - min(raw_ys)) - (max(ys) - min(ys)) == pytest.approx(0.0)

    witness = load("docs/receiving-nfb-x-evidence.json")[
        "w800_t2_three_hole_observation"
    ]["closed_cutting_reference"]
    assert witness["canonical_whd_blank_height_mm"] == pytest.approx(1075.0)
    assert witness["reference_blank_height_mm"] == pytest.approx(1075)
    assert witness["height_mismatch_mm"] == pytest.approx(0.0)
    assert witness["wHD_manufacturing_cutting_identity_approved"] is False
