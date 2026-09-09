# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict

import pytest
from shapely.affinity import translate
from shapely.geometry import Polygon, box as shapely_box
from shapely.ops import unary_union
import fold_designer_bridge as bridge
from ae_engine.assembly_collision import (
    _barycentric_world_to_flat,
    _triangle_pair_crossing_segment,
)
from tests.test_issue39_divider_relief import _body_part, _divider_part, _snapshot


def _piece_bands(body):
    result = {}
    for piece in tuple(body.render_data.pieces or ()):
        key = f"box_body:{piece.role}"
        cursor = 0.0
        bands = []
        for row in tuple(piece.fold_profile or ()):
            end = cursor + float(row.length)
            bands.append((str(row.phase6_key or ""), cursor, end))
            cursor = end
        result[key] = tuple(bands)
    return result


def _crossing_sides_by_source_band(world, divider_key, source_key, bands, *, tolerance=1e-7):
    """Independent validation: classify source Fold bands by physical skin crossings.

    This intentionally does not call the production Divider relief classifier.
    A source Fold band is a true-thickness penetration witness only when both
    physical skins of that source band cross the retained Divider physical skins.
    """
    targets = tuple(world["mapped_skin_triangles_by_part"][divider_key])
    sources = tuple(world["mapped_skin_triangles_by_part"][source_key])
    result = {}
    for name, u0, u1 in bands:
        sides = defaultdict(int)
        divider_points = []
        for source in sources:
            source_u = [float(point[0]) for point in source.flat]
            if max(source_u) < u0 - tolerance or min(source_u) > u1 + tolerance:
                continue
            for target in targets:
                crossing = _triangle_pair_crossing_segment(
                    source.world, target.world, tolerance=tolerance
                )
                if crossing is None:
                    continue
                try:
                    source_uv = [
                        _barycentric_world_to_flat(point, source.world, source.flat)
                        for point in crossing
                    ]
                    target_uv = [
                        _barycentric_world_to_flat(point, target.world, target.flat)
                        for point in crossing
                    ]
                except ValueError:
                    continue
                midpoint_u = sum(float(point[0]) for point in source_uv) / len(source_uv)
                if midpoint_u < u0 - 1e-5 or midpoint_u > u1 + 1e-5:
                    continue
                sides[int(source.side)] += 1
                divider_points.extend(target_uv)
        bounds = None if not divider_points else (
            min(float(point[0]) for point in divider_points),
            max(float(point[0]) for point in divider_points),
            min(float(point[1]) for point in divider_points),
            max(float(point[1]) for point in divider_points),
        )
        through = bool(sides.get(-1) and sides.get(1))
        footprint = None
        if through and bounds is not None:
            x0, x1, y0, y1 = map(float, bounds)
            if x1 > x0 and y1 > y0:
                footprint = shapely_box(x0, y0, x1, y1)
        result[name] = {
            "sides": dict(sides),
            "through": bool(through and footprint is not None),
            "divider_uv_bounds": bounds,
            "physical_footprint": footprint,
        }
    return result


def test_issue74_post_solve_has_zero_positive_area_in_source_solid_footprints():
    """Post-refold world collision must have zero positive-area penetration.

    Boundary skin crossings are legal. This intentionally does not rebuild the
    superseded pre-cut target-T/2 UV footprint.
    """
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    assert diagnostics
    diagnostic = diagnostics[0]
    post = dict(diagnostic.evidence["post"])
    print("ISSUE74_POST_REFOLD_TRUE_THICKNESS=", post)

    assert diagnostic.illegal_penetration is False
    assert post["verified"] is True
    assert int(post["true_thickness_penetrating_band_count"]) == 0
    minx, miny, maxx, maxy = map(float, divider_part.render_data.material.bounds)
    assert float(post["positive_overlap_area"]) <= max(
        1.0e-12,
        1.0e-6 * max(maxx - minx, maxy - miny, 1.0),
    )
    for row in dict(post["by_source"]).values():
        assert tuple(row["true_thickness_penetrating_bands"]) == ()

def test_issue74_presolve_mating_fw_and_d_are_single_skin_contacts():
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    bands = _piece_bands(body)
    left = _crossing_sides_by_source_band(
        world, divider.stable_id, "box_body:left_side", bands["box_body:left_side"]
    )
    right = _crossing_sides_by_source_band(
        world, divider.stable_id, "box_body:right_side", bands["box_body:right_side"]
    )
    print("ISSUE74_PRESOLVE_CONTACT_CLASS=", {"left": left, "right": right})

    # Semantic keys come from the authoritative source Fold profiles; no measured
    # UV value is used as an oracle. These mating bands must not be promoted just
    # because one physical skin intersects the Divider.
    for row in (left["fw_left"], left["d_left"], right["fw_right"], right["d_right"]):
        assert row["through"] is False

    # The actual regression witnesses are likewise identified by source Fold
    # identity + both-skin physical crossing, never by hard-coded 62/61/57.
    assert left["zl1"]["through"] is True
    assert left["zl2"]["through"] is True
    assert right["zr2"]["through"] is True


def test_issue74_cutting_is_derived_from_fw_inside_face_and_source_collision_span():
    """CURRENT: manufacturing dimensions come from FW contact + collision backprojection."""
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])

    raw_world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), dims, snap["t"]
    )
    bands = _piece_bands(body)
    pre = {
        source_key: _crossing_sides_by_source_band(
            raw_world, divider.stable_id, source_key, bands[source_key]
        )
        for source_key in ("box_body:left_side", "box_body:right_side")
    }

    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=dims,
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    assert diagnostics and diagnostics[0].illegal_penetration is False
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    evidence = dict(relief["evidence"])
    by_source = dict(evidence["projection_by_source"])

    assert evidence["manufacturing_dimensions_source"] == (
        "PHYSICAL_FW_CONTACT_AND_SOURCE_COLLISION_BACKPROJECTION"
    )

    # Independent FW contact on the Divider supplies primary depth.
    left_fw = pre["box_body:left_side"]["fw_left"]["divider_uv_bounds"]
    right_fw = pre["box_body:right_side"]["fw_right"]["divider_uv_bounds"]
    assert left_fw is not None and right_fw is not None
    miny, maxy = map(float, divider_part.render_data.material.bounds[1::2])
    left_contact_depth = float(left_fw[3]) - miny
    right_contact_depth = maxy - float(right_fw[2])

    left_stages = dict(by_source["box_body:left_side"]["physical_stages"])
    right_stages = dict(by_source["box_body:right_side"]["physical_stages"])
    assert float(left_stages["zl2"]["primary_cutting_depth"]) == pytest.approx(
        left_contact_depth, abs=1.0e-5
    )
    assert float(right_stages["zr2"]["primary_cutting_depth"]) == pytest.approx(
        right_contact_depth, abs=1.0e-5
    )

    # Secondary stage size comes from the source-solid collision span. Its 2D
    # material anchor is the same physical FW inside-face boundary as the
    # primary stage; no test value and no target-T/2 translation participates.
    zl1 = pre["box_body:left_side"]["zl1"]["physical_footprint"]
    assert zl1 is not None
    x0, y0, x1, y1 = map(float, zl1.bounds)
    stage = left_stages["zl1"]
    assert float(stage["stage_u_span"]) == pytest.approx(x1 - x0, abs=1.0e-5)
    assert float(stage["stage_v_span"]) == pytest.approx(y1 - y0, abs=1.0e-5)
    assert tuple(map(float, stage["cut_bounds"])) == pytest.approx(
        (x0, y0, x1, y1), abs=1.0e-5
    )
    assert float(stage["primary_inside_face_boundary"]) == pytest.approx(
        left_contact_depth, abs=1.0e-5
    )
    assert stage["dimension_source"] == "PHYSICAL_FW_INSIDE_FACE_PLUS_SOURCE_COLLISION_SPAN"
    assert "target_half_thickness" not in stage
    assert "solid_depth" not in stage

def test_receiving_boxbody_fw_world_occupation_matches_formed_contract():
    """Receiving 3D FW must occupy formed outside width, not raw material length."""
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    contract = dict(divider_part.render_data.metadata["physical_geometry_contract"])
    expected_formed_fw = float(contract["fw_physical_face"]["outside_dimension"])
    bands = _piece_bands(body)

    observed = {}
    for source_key, fw_name in (
        ("box_body:left_side", "fw_left"),
        ("box_body:right_side", "fw_right"),
    ):
        u0, u1 = next(
            (u0, u1) for name, u0, u1 in bands[source_key] if name == fw_name
        )
        points = []
        for tri in tuple(world["mapped_skin_triangles_by_part"][source_key]):
            centroid_u = sum(float(point[0]) for point in tri.flat) / 3.0
            if u0 - 1.0e-7 <= centroid_u <= u1 + 1.0e-7:
                points.extend(tuple(map(float, point)) for point in tri.world)
        assert points, f"no physical FW geometry for {source_key}"
        x0 = min(point[0] for point in points)
        x1 = max(point[0] for point in points)
        occupation = x1 - x0
        observed[source_key] = {
            "world_x_bounds": (x0, x1),
            "formed_occupation": occupation,
            "expected_formed_fw": expected_formed_fw,
        }
        assert occupation == pytest.approx(expected_formed_fw, abs=1.0e-6), (
            "Receiving 3D FW uses material length instead of formed outside occupation",
            observed,
        )

    print("RECEIVING_FW_FORMED_OCCUPATION=", observed)


def test_receiving_reference_fixture_independently_matches_22_27_step_oracle():
    """Validation-only oracle for the approved Receiving reference fixture.

    IMPORTANT: 22/27 are acceptance values only. Production geometry must never
    import/read this test or derive collision dimensions from these constants.
    The test measures independently reconstructed world/collision geometry and
    only judges whether production inputs/placement produced the approved shape.
    """
    REFERENCE_ZL1_STEP_LENGTH = 22.0
    REFERENCE_FW_OVERLAP = 27.0

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    bands = _piece_bands(body)

    # Independent collision witness for the narrow left stage.
    left = _crossing_sides_by_source_band(
        world,
        divider.stable_id,
        "box_body:left_side",
        bands["box_body:left_side"],
    )
    zl1 = left["zl1"]["physical_footprint"]
    assert zl1 is not None
    _x0, y0, _x1, y1 = map(float, zl1.bounds)
    observed_zl1_step = y1 - y0

    def band_world_x_bounds(source_key, band_name):
        u0, u1 = next(
            (u0, u1) for name, u0, u1 in bands[source_key] if name == band_name
        )
        xs = []
        for skin in tuple(world["mapped_skin_triangles_by_part"][source_key]):
            centroid_u = sum(float(point[0]) for point in skin.flat) / 3.0
            if u0 + 1.0e-6 < centroid_u < u1 - 1.0e-6:
                xs.extend(float(point[0]) for point in skin.world)
        assert xs, f"no world FW geometry for {source_key}:{band_name}"
        return min(xs), max(xs)

    divider_x = [
        float(point[0])
        for skin in tuple(world["mapped_skin_triangles_by_part"][divider.stable_id])
        for point in skin.world
    ]
    assert divider_x
    divider_bounds = (min(divider_x), max(divider_x))

    left_fw = band_world_x_bounds("box_body:left_side", "fw_left")
    right_fw = band_world_x_bounds("box_body:right_side", "fw_right")

    def overlap_1d(a, b):
        return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))

    observed_left_overlap = overlap_1d(left_fw, divider_bounds)
    observed_right_overlap = overlap_1d(right_fw, divider_bounds)

    observed = {
        "zl1_step_length": observed_zl1_step,
        "divider_x_bounds": divider_bounds,
        "left_fw_x_bounds": left_fw,
        "right_fw_x_bounds": right_fw,
        "left_fw_divider_overlap": observed_left_overlap,
        "right_fw_divider_overlap": observed_right_overlap,
    }
    print("RECEIVING_REFERENCE_22_27_ORACLE=", observed)

    assert observed_zl1_step == pytest.approx(
        REFERENCE_ZL1_STEP_LENGTH, abs=1.0e-5
    )
    assert observed_left_overlap == pytest.approx(
        REFERENCE_FW_OVERLAP, abs=1.0e-5
    )
    assert observed_right_overlap == pytest.approx(
        REFERENCE_FW_OVERLAP, abs=1.0e-5
    )


def test_receiving_reference_fixture_final_cutting_matches_independent_notch_oracle():
    """Validation-only final OUTER CUTTING oracle for the approved fixture."""
    LEFT_PRIMARY_W = 61.0
    LEFT_PRIMARY_D = 27.0
    LEFT_STEP_W = 2.0
    LEFT_STEP_D = 22.0
    RIGHT_PRIMARY_W = 57.0
    RIGHT_PRIMARY_D = 27.0

    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    dims = (snap["w"], snap["h"], snap["d"])

    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=dims,
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    assert diagnostics and diagnostics[0].illegal_penetration is False
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)

    # Compare only the structural outer CUTTING. Hole/datum changes are a
    # separate feature oracle and must not pollute notch-area comparison.
    nominal_shell = Polygon(divider_part.render_data.material.exterior)
    retained_shell = Polygon(solved.render_data.material.exterior)
    removed = nominal_shell.difference(retained_shell)
    minx, miny, maxx, maxy = map(float, nominal_shell.bounds)

    left_primary = shapely_box(
        minx, miny,
        minx + LEFT_PRIMARY_W, miny + LEFT_PRIMARY_D,
    )
    # Independent product topology, confirmed by the user: the secondary
    # material notch is 2x22 at Y=27..49. These coordinates are validation-only
    # and are never read by production.
    LEFT_STEP_START = 27.0
    left_secondary = shapely_box(
        minx + LEFT_PRIMARY_W - 1.0,
        miny + LEFT_STEP_START,
        minx + LEFT_PRIMARY_W - 1.0 + LEFT_STEP_W,
        miny + LEFT_STEP_START + LEFT_STEP_D,
    )

    right_primary = shapely_box(
        minx, maxy - RIGHT_PRIMARY_D,
        minx + RIGHT_PRIMARY_W, maxy,
    )
    expected = unary_union((left_primary, left_secondary, right_primary))

    missing = expected.difference(removed)
    extra = removed.difference(expected)
    print("RECEIVING_FINAL_CUTTING_ORACLE=", {
        "removed_area": float(removed.area),
        "expected_area": float(expected.area),
        "missing_area": float(missing.area),
        "extra_area": float(extra.area),
        "approved": {
            "left_primary": (LEFT_PRIMARY_W, LEFT_PRIMARY_D),
            "left_step": (LEFT_STEP_W, LEFT_STEP_D),
            "right_primary": (RIGHT_PRIMARY_W, RIGHT_PRIMARY_D),
        },
        "left_step_expected_bounds": tuple(map(float, left_secondary.bounds)),
    })

    assert float(missing.area) <= 1.0e-4
    assert float(extra.area) <= 1.0e-4

def test_receiving_operator_inputs_are_authority_and_material_fold_is_one_way_derived():
    """Operator/outside inputs are authority; material Fold is one-way derived."""
    from phase6_fold_profiles import build_box_body_profile, read_box_body_profile

    snap = _snapshot()
    assert (
        float(snap["zl1"]),
        float(snap["zl2"]),
        float(snap["fw"]),
        float(snap["zr2"]),
    ) == (-24.0, 24.0, 29.0, 18.0)

    profile = build_box_body_profile(snap)
    by_key = {
        str(row.get("phase6_key") or ""): row
        for row in profile
        if str(row.get("phase6_key") or "")
    }
    material = (
        float(by_key["zl1"]["len"]),
        float(by_key["zl2"]["len"]),
        float(by_key["fw_left"]["len"]),
        float(by_key["zr2"]["len"]),
    )
    assert material == (22.0, 20.0, 25.0, 16.0)

    roundtrip = read_box_body_profile(profile, snap)
    assert (
        float(roundtrip["zl1"]),
        float(roundtrip["zl2"]),
        float(roundtrip["fw"]),
        float(roundtrip["zr2"]),
    ) == (24.0, 24.0, 29.0, 18.0)

    print("RECEIVING_INPUT_AUTHORITY=", {
        "operator_outside": (-24.0, 24.0, 29.0, 18.0),
        "derived_material": material,
        "roundtrip_operator": (
            float(roundtrip["zl1"]),
            float(roundtrip["zl2"]),
            float(roundtrip["fw"]),
            float(roundtrip["zr2"]),
        ),
    })
