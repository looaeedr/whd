# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from shapely.geometry import Point

import fold_designer_bridge as bridge
from ae_engine.assembly_collision import (
    _divider_front_fold_segments,
    build_divider_front_fold_relief_candidate,
    project_joint_interference_to_relief_owner,
)
from tests.test_issue39_divider_relief import (
    _body_part,
    _divider_insert_joint,
    _divider_part,
    _snapshot,
)


def _merge_intervals(intervals, *, tolerance=1.0e-6):
    merged = []
    for start, end in sorted((min(a, b), max(a, b)) for a, b in intervals):
        if not merged or start > merged[-1][1] + tolerance:
            merged.append([float(start), float(end)])
        else:
            merged[-1][1] = max(float(end), merged[-1][1])
    return tuple((a, b) for a, b in merged)


def _disconnected_gap_witness(segments, material, core_start, *, tolerance=1.0e-6):
    """Derive a non-collision witness from the physical projected linework.

    This test never supplies a manufacturing dimension to production.  It only
    asks the backprojection itself whether one Y slice contains two disconnected
    collision intervals and returns a point in the gap between them.
    """
    by_y = {}
    for a, b in tuple(segments or ()):
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        if abs(ay - by) > tolerance:
            continue
        if abs(ax - bx) <= tolerance:
            continue
        y = round((ay + by) / 2.0, 6)
        by_y.setdefault(y, []).append((ax, bx))

    candidates = []
    for y, intervals in by_y.items():
        merged = _merge_intervals(intervals, tolerance=tolerance)
        for left, right in zip(merged, merged[1:]):
            gap = float(right[0]) - float(left[1])
            if gap <= tolerance * 100.0:
                continue
            x = (float(left[1]) + float(right[0])) / 2.0
            point = Point(x, float(y))
            if x >= float(core_start) - tolerance:
                continue
            if not material.buffer(tolerance).covers(point):
                continue
            candidates.append((gap, point, merged))

    assert candidates, "fixture must expose a disconnected physical backprojection gap"
    _gap, point, merged = max(candidates, key=lambda row: row[0])
    return point, merged


@pytest.mark.parametrize("source_key", ("box_body:left_side", "box_body:right_side"))
def test_issue71_divider_relief_does_not_bridge_disconnected_backprojection_regions(source_key):
    snap = _snapshot()
    body = _body_part(snap)
    divider, divider_part = _divider_part(snap)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), (snap["w"], snap["h"], snap["d"]), snap["t"]
    )
    joint = _divider_insert_joint(divider.stable_id)
    core_start = float(
        divider_part.render_data.metadata["physical_geometry_contract"]
        ["core_physical_segment"]["flat_band"][0]
    )
    material = world["flat_material_by_part"][divider.stable_id]

    projected = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        source_geometry_key=source_key,
    )
    front = _divider_front_fold_segments(
        projected.projection, core_start=core_start
    )
    witness, intervals = _disconnected_gap_witness(
        front, material, core_start
    )

    candidate = build_divider_front_fold_relief_candidate(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        core_start=core_start,
        source_geometry_keys=(source_key,),
        clearance=0.0,
        sheet_thickness=float(divider.thickness),
    )
    assert candidate is not None

    print("ISSUE71_DISCONNECTED_RELIEF_GAP=", {
        "source": source_key,
        "witness": (float(witness.x), float(witness.y)),
        "intervals": intervals,
        "candidate_bounds": tuple(map(float, candidate.cut_polygon_2d.bounds)),
        "evidence": candidate.evidence,
    })

    assert not candidate.cut_polygon_2d.covers(witness), (
        "Divider relief bridged a gap that physical backprojection says is not "
        "collision material; one global convex hull must not merge disconnected "
        "collision regions",
        source_key,
        (float(witness.x), float(witness.y)),
        intervals,
    )
