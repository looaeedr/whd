# -*- coding: utf-8 -*-
"""#1503: source-side UV receipts for REAL formed T2 fixing-plate weld footprints.

Only the Box Body LEFT/RIGHT SIDE's own physical inside-skin mapping may
backproject an already established EAR world-space contact. This module does
not manufacture welds, create DXF marks, or authorize EAR production.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Mapping

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from .assembly_marking_geometry import backproject_mapped_skin_world_points
from .receiving_fixed_plate_side_contact import (
    ReceivingEarSideContactSurface, resolve_receiving_ear_side_contact_surfaces,
)

_TOL = 0.02
_UV_TOL = 1e-5


@dataclass(frozen=True)
class ReceivingEarSideUVReceipt:
    ear_part_id: str
    base_part_id: str
    side_piece_id: str
    nfb_layer_index: int
    world_boundary: tuple[tuple[float, float, float], ...]
    side_source_flat_boundary: tuple[tuple[float, float], ...]
    marking_segments: tuple[tuple[tuple[float, float], tuple[float, float]], ...]
    side_flat_uv_backprojection_verified: bool = True
    side_final_material_coverage_verified: bool = True
    side_bend_intersection_rejected: bool = True
    weld_contact_verified: bool = False
    manufacturing_ready: bool = False


def _physical_inside_side_mapping(contact, side_mapped_skins):
    x = contact.side_inside_skin_world_x_mm
    # World coordinates, not midplanes or the EAR's own UV. A source-side
    # triangle must lie wholly on the actual X +/-398-mm physical side skin.
    records = tuple(
        row for row in tuple(side_mapped_skins or ())
        if len(tuple(getattr(row, "world", ()) or ())) == 3
        and all(abs(float(point[0])-x) <= _TOL for point in row.world)
    )
    if not records:
        raise ValueError("EAR_SIDE_UV_NO_AUTHENTIC_INSIDE_SIDE_SKIN")
    return records


def _fold_guide_flat_segment(guide):
    axis = str(getattr(guide, "axis", ""))
    position = float(getattr(guide, "position"))
    lo, hi = float(getattr(guide, "span_start")), float(getattr(guide, "span_end"))
    if lo >= hi or axis not in {"x", "y"}:
        raise ValueError("EAR_SIDE_UV_INVALID_SIDE_BEND_GUIDE")
    return LineString(((position, lo), (position, hi))) if axis == "x" else LineString(((lo, position), (hi, position)))


def project_receiving_ear_contact_to_side_uv(
    contact: ReceivingEarSideContactSurface,
    *,
    side_mapped_skins,
    side_final_material,
    side_fold_guides=(),
) -> ReceivingEarSideUVReceipt:
    """Map one real T2 folded EAR wall contact into its SIDE source-flat UV.

    Require a single honest world->UV solution, authentic side physical-skin
    support, whole-footprint Final Material (incl. no source CUTTING holes),
    and no source side BEND crossing. This remains a read-only MARKING receipt
    until welding and manufacturing checks independently pass.
    """
    if not isinstance(contact, ReceivingEarSideContactSurface):
        raise TypeError("EAR_SIDE_UV_REQUIRES_CONTACT_RECEIPT")
    if (
        contact.side_piece_id not in {"box_body:left_side", "box_body:right_side"}
        or not contact.source_bend_verified
        or not contact.formed_source_skin_verified
        or contact.weld_contact_verified
        or contact.manufacturing_ready
        or contact.side_flat_uv_backprojection_verified
        or len(contact.world_surface_boundary) != 4
        or not isclose(contact.contact_length_world_y_mm, 256., abs_tol=_TOL)
        or not isclose(contact.contact_height_world_z_mm, 22., abs_tol=_TOL)
    ):
        raise ValueError("EAR_SIDE_UV_CONTACT_NOT_SOURCE_VERIFIED")
    x = float(contact.side_inside_skin_world_x_mm)
    # The actual SIDE physical skin mapping supplies X, not W800's +/-398.
    if (not (float("-inf") < x < float("inf"))
            or (contact.side_piece_id.endswith("left_side") and x >= 0)
            or (contact.side_piece_id.endswith("right_side") and x <= 0)):
        raise ValueError("EAR_SIDE_UV_SIDE_OWNER_SKIN_DRIFT")
    boundary = tuple(tuple(float(v) for v in p) for p in contact.world_surface_boundary)
    if any(len(p) != 3 or abs(p[0] - x) > _TOL for p in boundary):
        raise ValueError("EAR_SIDE_UV_WORLD_BOUNDARY_DRIFT")

    records = _physical_inside_side_mapping(contact, side_mapped_skins)
    result = backproject_mapped_skin_world_points(records, boundary)
    if result.status != "RESOLVED" or len(result.flat_points) != 4:
        raise ValueError("EAR_SIDE_UV_BACKPROJECTION_FAILED")
    flat = tuple(tuple(float(v) for v in point) for point in result.flat_points)
    patch = Polygon(flat)
    if not patch.is_valid or patch.is_empty or abs(float(patch.area) - 256. * 22.) > 1.0:
        raise ValueError("EAR_SIDE_UV_PHYSICAL_AREA_OR_TOPOLOGY_DRIFT")

    # The common mapping helper allows plane extrapolation. Do NOT accept
    # such extrapolation unless true SIDE mapped physical material covers the
    # entire contact, including folds, cutouts and source material boundaries.
    # Shapely 2 union_all requires a concrete sequence, not a generator.
    actual_mapped_patch = unary_union(tuple(
        Polygon(tuple(tuple(map(float, p)) for p in row.flat))
        for row in records
    ))
    if not actual_mapped_patch.buffer(_UV_TOL).covers(patch):
        raise ValueError("EAR_SIDE_UV_OUTSIDE_ACTUAL_SIDE_SKIN")
    if side_final_material is None or not side_final_material.covers(patch):
        raise ValueError("EAR_SIDE_UV_CUTTING_OR_MATERIAL_CONFLICT")

    for guide in tuple(side_fold_guides or ()):
        if patch.intersects(_fold_guide_flat_segment(guide)):
            raise ValueError("EAR_SIDE_UV_SIDE_BEND_INTERSECTION")

    segments = tuple((flat[i], flat[(i + 1) % 4]) for i in range(4))
    if any(LineString(pair).length <= _UV_TOL for pair in segments):
        raise ValueError("EAR_SIDE_UV_DEGENERATE_MARKING")
    return ReceivingEarSideUVReceipt(
        ear_part_id=contact.ear_part_id,
        base_part_id=contact.base_part_id,
        side_piece_id=contact.side_piece_id,
        nfb_layer_index=contact.nfb_layer_index,
        world_boundary=boundary,
        side_source_flat_boundary=flat,
        marking_segments=segments,
    )


def resolve_receiving_ear_side_uv_receipts(
    snapshot: Mapping[str, object], *, world_geometry, geometry,
) -> tuple[ReceivingEarSideUVReceipt, ...]:
    """All-or-nothing single/two-tier authentic side-owner UV readback."""
    from .manufacturing_scene_access import owner_render_data
    world = dict(world_geometry or {})
    mapping = dict(world.get("mapped_skin_triangles_by_part") or {})
    results = []
    for contact in resolve_receiving_ear_side_contact_surfaces(snapshot):
        side = contact.side_piece_id
        owner = owner_render_data(geometry, side)
        if owner is None:
            raise ValueError("EAR_SIDE_UV_SIDE_MANUFACTURING_OWNER_MISSING")
        results.append(project_receiving_ear_contact_to_side_uv(
            contact,
            side_mapped_skins=mapping.get(side),
            side_final_material=owner.material,
            side_fold_guides=tuple(owner.fold_guides or ()),
        ))
    if len(results) not in (2, 4) or len({r.ear_part_id for r in results}) != len(results):
        raise ValueError("EAR_SIDE_UV_TIER_OWNER_INCOMPLETE")
    return tuple(results)
