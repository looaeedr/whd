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

