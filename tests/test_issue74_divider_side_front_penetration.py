# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict

import pytest
from shapely.affinity import translate
from shapely.geometry import box as shapely_box
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
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)

    # Independent pre-solve physical evidence.  The test reconstructs source
    # Fold-band footprints from real world skins; it does not call production's
    # Divider classifier and does not hard-code any runtime cut dimension.
    raw_world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    bands = _piece_bands(body)
    pre = {
        source_key: _crossing_sides_by_source_band(
            raw_world, divider.stable_id, source_key, bands[source_key]
        )
        for source_key in ("box_body:left_side", "box_body:right_side")
    }
    material = divider_part.render_data.material
    minx, miny, maxx, maxy = map(float, material.bounds)
    half_t = float(snap["t"]) / 2.0
    physical_footprints = {}
    for source_key, rows in pre.items():
        required = []
        for row in rows.values():
            footprint = row["physical_footprint"]
            if footprint is None:
                continue
            _x0, y0, _x1, y1 = map(float, footprint.bounds)
            low_depth = max(0.0, y1 - miny)
            high_depth = max(0.0, maxy - y0)
            yoff = half_t if low_depth <= high_depth else -half_t
            target_solid = unary_union((footprint, translate(footprint, yoff=yoff))).intersection(material)
            required.append(target_solid)
        physical_footprints[source_key] = tuple(required)
    assert physical_footprints["box_body:left_side"]
    assert physical_footprints["box_body:right_side"]

    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    retained = solved.render_data.material

    overlaps = {}
    for source_key, footprints in physical_footprints.items():
        overlaps[source_key] = tuple(
            float(retained.intersection(footprint).area)
            for footprint in footprints
        )
    print("ISSUE74_POST_SOLVE_POSITIVE_AREA=", {
        "diagnostic_status": diagnostics[0].candidate_status,
        "diagnostic_illegal": diagnostics[0].illegal_penetration,
        "overlaps": overlaps,
        "pre": {
            key: {
                name: {
                    "through": row["through"],
                    "bounds": row["divider_uv_bounds"],
                }
                for name, row in rows.items()
            }
            for key, rows in pre.items()
        },
        "material_bounds": tuple(map(float, retained.bounds)),
    })

    assert all(
        area <= 1.0e-9
        for rows in overlaps.values()
        for area in rows
    ), (
        "retained Divider material still has positive area inside a physical "
        "source-solid + target-T/2 collision footprint",
        overlaps,
    )


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


def test_issue74_cut_depth_is_derived_from_physical_collision_plus_target_half_thickness():
    """Cut depth comes from actual collision footprint + Divider T/2, not W/FW formulas."""
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

    solved_parts, _diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=dims,
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    evidence = dict(relief["evidence"])
    by_source = dict(evidence["projection_by_source"])

    minx, miny, maxx, maxy = map(float, divider_part.render_data.material.bounds)
    half_t = float(snap["t"]) / 2.0
    observed = {}

    for source_key, rows in pre.items():
        stages = dict(by_source[source_key]["physical_stages"])
        observed[source_key] = {}
        for band_name, row in rows.items():
            footprint = row["physical_footprint"]
            if footprint is None:
                continue
            assert band_name in stages
            stage = dict(stages[band_name])
            _x0, y0, _x1, y1 = map(float, footprint.bounds)
            low_depth = max(0.0, y1 - miny)
            high_depth = max(0.0, maxy - y0)
            skin_depth = min(low_depth, high_depth)
            expected_solid_depth = skin_depth + half_t

            assert float(stage["skin_depth"]) == pytest.approx(skin_depth, abs=1.0e-5)
            assert float(stage["target_half_thickness"]) == pytest.approx(half_t, abs=1.0e-9)
            assert float(stage["solid_depth"]) == pytest.approx(expected_solid_depth, abs=1.0e-5)
            assert stage["dimension_source"] == "PHYSICAL_COLLISION_PLUS_TARGET_T_OVER_2"

            observed[source_key][band_name] = {
                "skin_depth": skin_depth,
                "target_half_thickness": half_t,
                "solid_depth": float(stage["solid_depth"]),
                "source_footprint": tuple(map(float, footprint.bounds)),
                "target_solid_footprint": tuple(map(float, stage["target_solid_footprint_bounds"])),
                "cut_bounds": tuple(map(float, stage["cut_bounds"])),
            }

    assert evidence["manufacturing_dimensions_source"] == (
        "PHYSICAL_COLLISION_PLUS_TARGET_T_OVER_2"
    )
    print("ISSUE74_PHYSICAL_SOLID_DEPTH=", observed)



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
