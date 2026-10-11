# -*- coding: utf-8 -*-
"""#1502 witness NFB middle-plate shadow UV on the actual folded 3D skin.

This uses the existing final-material folding and assembly placement engine,
not a second world-coordinate model. A witness proves what a *candidate*
flat point becomes in the cabinet, not that the NFB aperture's depth is the
correct engineering mounting position. It grants no manufacturing permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .assembly_geometry import (
    folded_mesh_with_flat_uv_from_polygon,
    place_assembly_triangles,
)
from .assembly_placement import resolve_divider_placement
from .door_dividers import BoxBodyDividerPart
from .manufacturing_render_data import PartRenderData

WITNESS_ONLY = "MFG2_MIDDLE_3D_FLAT_UV_WITNESSED_NOT_DEPTH_CERTIFIED"


@dataclass(frozen=True)
class NfbMiddle3DWitness:
    part_id: str
    uv_xy: tuple[float, float]
    world_xyz: tuple[float, float, float]
    placement_kind: str
    matched_triangles: int
    status: str = WITNESS_ONLY
    manufacturing_ready: bool = False


def _barycentric(point, triangle):
    """Return inclusive barycentric weights or None for a point outside."""
    ax, ay = triangle[0]
    bx, by = triangle[1]
    cx, cy = triangle[2]
    px, py = point
    v0x, v0y = bx - ax, by - ay
    v1x, v1y = cx - ax, cy - ay
    v2x, v2y = px - ax, py - ay
    det = v0x * v1y - v1x * v0y
    if abs(det) <= 1e-9:
        return None
    b = (v2x * v1y - v1x * v2y) / det
    c = (v0x * v2y - v2x * v0y) / det
    a = 1.0 - b - c
    if min(a, b, c) < -1e-7 or max(a, b, c) > 1.0 + 1e-7:
        return None
    return a, b, c


def witness_middle_plate_uv_on_folded_assembly(
    snapshot: Mapping[str, object],
    divider: BoxBodyDividerPart,
    baseline: PartRenderData,
    *,
    uv_xy: tuple[float, float],
    expected_world_x_mm: float,
) -> NfbMiddle3DWitness:
    """Map a candidate flat UV into world XYZ via current FinalScene + 3D.

    Geometry is from the uncut baseline, so point-to-triangle correspondence
    remains stable before the preview NFB aperture is subtracted. The
    placement is exactly the viewer/collision placement, including inward
    core orientation and full folded material-envelope centering.
    """
    if not isinstance(divider, BoxBodyDividerPart) or divider.axis != "HORIZONTAL":
        raise ValueError("NFB 3D witness requires actual horizontal divider")
    if not isinstance(baseline, PartRenderData):
        raise TypeError("NFB 3D witness requires actual final baseline render")
    if not isinstance(snapshot, Mapping) or baseline.material is None:
        raise ValueError("NFB 3D witness requires current cabinet and final material")
    if len(uv_xy) != 2 or not all(isfinite(float(v)) for v in uv_xy):
        raise ValueError("NFB UV witness point must be finite")
    uv = float(uv_xy[0]), float(uv_xy[1])
    if not isfinite(float(expected_world_x_mm)):
        raise ValueError("NFB existing verified position must be finite")
    topology = baseline.unfolded_topology
    if topology is None or topology.piece_id != divider.stable_id:
        raise ValueError("NFB 3D witness physical unfold identity mismatch")
    if not baseline.material.buffer(-1e-6).covers(
        __import__("shapely.geometry", fromlist=["Point"]).Point(*uv)
    ):
        raise ValueError("NFB UV center is not inside actual baseline material")
    placement = resolve_divider_placement(snapshot, divider.stable_id)
    if (placement.stable_id != divider.stable_id
            or not placement.placement_kind.startswith("divider_horizontal")):
        raise ValueError("NFB 3D witness requires canonical divider placement")
    mapped = folded_mesh_with_flat_uv_from_polygon(
        baseline.material, divider.fold_profile, ({"len": float(divider.span)},),
        fold_guides=tuple(baseline.fold_guides or ()),
    )
    if not mapped:
        raise ValueError("NFB current physical divider fold has no mapped material")
    worlds = place_assembly_triangles(
        tuple(item.local for item in mapped),
        placement.placement_kind,
        (float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
        placement.world_offset,
    )
    if len(worlds) != len(mapped):
        raise ValueError("NFB folded 3D material and UV triangles differ")
    hits = []
    for flat, world in zip(mapped, worlds):
        weights = _barycentric(uv, flat.flat)
        if weights is None:
            continue
        xyz = tuple(
            sum(weights[i] * float(world[i][axis]) for i in range(3))
            for axis in range(3)
        )
        if all(isfinite(v) for v in xyz):
            hits.append(xyz)
    if not hits:
        raise ValueError("NFB candidate UV not on actual folded divider skin")
    first = hits[0]
    if any(
        max(abs(a-b) for a,b in zip(first, other)) > 1e-4
        for other in hits[1:]
    ):
        raise ValueError("NFB middle UV hits inconsistent physical folded faces")
    if abs(first[0] - float(expected_world_x_mm)) > 1e-4:
        raise ValueError("NFB middle 3D assembled X contradicts existing verified hole")
    if abs(first[1] - float(placement.world_offset[1])) > 1e-4:
        raise ValueError("NFB middle 3D opening is outside the divider assembly plane")
    return NfbMiddle3DWitness(
        part_id=divider.stable_id, uv_xy=uv, world_xyz=first,
        placement_kind=placement.placement_kind,
        matched_triangles=len(hits),
    )
