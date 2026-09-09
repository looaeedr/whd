# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict

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
        result[name] = {
            "sides": dict(sides),
            "through": bool(sides.get(-1) and sides.get(1)),
            "divider_uv_bounds": None if not divider_points else (
                min(float(point[0]) for point in divider_points),
                max(float(point[0]) for point in divider_points),
                min(float(point[1]) for point in divider_points),
                max(float(point[1]) for point in divider_points),
            ),
        }
    return result


def test_issue74_post_solve_has_zero_true_thickness_side_front_penetration():
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)

    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snap["w"], snap["h"], snap["d"]),
        sheet_thickness=snap["t"],
        clearance=0.0,
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    world = bridge._phase6_build_joint_world_geometry(
        tuple(solved_parts), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    bands = _piece_bands(body)
    observed = {
        source_key: _crossing_sides_by_source_band(
            world, divider.stable_id, source_key, bands[source_key]
        )
        for source_key in ("box_body:left_side", "box_body:right_side")
    }
    penetrations = {
        source_key: tuple(
            name for name, item in rows.items() if bool(item["through"])
        )
        for source_key, rows in observed.items()
    }
    print("ISSUE74_POST_SOLVE_TRUE_THICKNESS=", {
        "diagnostic_status": diagnostics[0].candidate_status,
        "diagnostic_illegal": diagnostics[0].illegal_penetration,
        "penetrations": penetrations,
        "observed": observed,
        "material_bounds": tuple(map(float, solved.render_data.material.bounds)),
    })

    assert penetrations == {
        "box_body:left_side": (),
        "box_body:right_side": (),
    }, (
        "Divider verifier accepted retained material while a BoxBody source Fold "
        "band still crosses both physical skins; core_start is not a valid "
        "true-thickness penetration boundary",
        penetrations,
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
