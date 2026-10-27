# -*- coding: utf-8 -*-
"""#1503: actual formed EAR vertical flange contact on the SIDE inner skin.

Read the revised T2/BEND23 signed formed WORLD mesh. Do not approximate from
the flat blank, copy target XY/Z, write NFB DXF, or invent side-panel MARKING.
This world rectangle is only a verified contact *candidate* for later genuine
Box Body side-piece world-to-UV backprojection and welding certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, isclose
from typing import Mapping

_TOL = 1e-6


@dataclass(frozen=True)
class ReceivingEarSideContactSurface:
    ear_part_id: str
    base_part_id: str
    side_piece_id: str
    nfb_layer_index: int
    side_inside_skin_world_x_mm: float
    world_surface_boundary: tuple[tuple[float, float, float], ...]
    contact_height_world_z_mm: float
    contact_length_world_y_mm: float
    # Authoritative installation line: BOTTOM of this actual parent BasePlate.
    # Never infer its Z from the EAR's folded/free-weld-leg length.
    base_lower_world_z_mm: float
    source_bend_verified: bool = True
    formed_source_skin_verified: bool = True
    side_flat_uv_backprojection_verified: bool = False
    weld_contact_verified: bool = False
    manufacturing_ready: bool = False


def derive_receiving_ear_side_contact_from_formed_skin(
    formed,
) -> ReceivingEarSideContactSurface:
    """Extract the actual vertical T2 flange skin, never guessed UV MARKING."""
    side = str(getattr(formed, "side", ""))
    if (side not in {"left", "right"}
            or not formed.source_bend_verified
            or not formed.side_wall_skin_contact_x_verified
            or not formed.actual_signed_forming_constructed
            or formed.weld_contact_verified
            or formed.manufacturing_ready
            or abs(float(formed.source_sheet_t_mm)-2.0) > _TOL
            or abs(float(formed.source_bend_y_mm)-23.0) > _TOL):
        raise ValueError("EAR_SIDE_CONTACT_SOURCE_FORMING_NOT_VERIFIED")
    x = float(formed.side_wall_inside_world_x_mm)
    hinge = float(formed.actual_mid_surface_hinge_y_mm)
    # Use only the actual side-facing physical skin: its triangles are
    # vertical and lie on the cabinet's inside side-wall X plane.
    faces = []
    for triangle in tuple(formed.mapped_world_skins or ()):
        uv = tuple(triangle.flat)
        points = tuple(triangle.world)
        if (len(uv) == len(points) == 3
                and all(float(point[1]) <= hinge + _TOL for point in uv)
                and all(abs(float(point[0])-x) <= _TOL for point in points)):
            faces.append(points)
    if not faces:
        raise ValueError("EAR_SIDE_CONTACT_NO_PHYSICAL_FLANGE_FACE")
    vertices = [p for tri in faces for p in tri]
    ys = [float(p[1]) for p in vertices]
    zs = [float(p[2]) for p in vertices]
    lo_y, hi_y = min(ys), max(ys)
    lo_z, hi_z = min(zs), max(zs)
    if (not all(isfinite(v) for v in (x, lo_y, hi_y, lo_z, hi_z))
            or not isclose(hi_y-lo_y, 256.0, rel_tol=0, abs_tol=0.02)
            or not isclose(hi_z-lo_z, 22.0, rel_tol=0, abs_tol=0.02)
            or not isclose(hi_z,
                           float(formed.parent_base_back_skin_world_z_mm)-1.0,
                           rel_tol=0, abs_tol=0.02)):
        raise ValueError("EAR_SIDE_CONTACT_TRUE_SKIN_ENVELOPE_DRIFT")
    return ReceivingEarSideContactSurface(
        ear_part_id=str(formed.part_id),
        base_part_id=str(formed.base_part_id),
        side_piece_id=f"box_body:{side}_side",
        nfb_layer_index=int(formed.layer_index),
        side_inside_skin_world_x_mm=x,
        world_surface_boundary=(
            (x, lo_y, lo_z), (x, hi_y, lo_z),
            (x, hi_y, hi_z), (x, lo_y, hi_z),
        ),
        contact_height_world_z_mm=hi_z-lo_z,
        contact_length_world_y_mm=hi_y-lo_y,
        base_lower_world_z_mm=float(formed.parent_base_back_skin_world_z_mm),
    )


def receiving_ear_installation_world_segment(contact: ReceivingEarSideContactSurface):
    """Single upper installation MARKING, at parent BasePlate's bottom skin.

    The lower edge of the EAR's folded weld leg is not an installation mark.
    Its real 3D contact face stays available for independent full-skin checks.
    """
    if not isinstance(contact, ReceivingEarSideContactSurface):
        raise TypeError("EAR_INSTALLATION_REQUIRES_PHYSICAL_CONTACT")
    z = float(contact.base_lower_world_z_mm)
    x = float(contact.side_inside_skin_world_x_mm)
    boundary = tuple(contact.world_surface_boundary or ())
    if len(boundary) != 4:
        raise ValueError("EAR_INSTALLATION_CONTACT_BOUNDARY_INVALID")
    y_values = tuple(float(p[1]) for p in boundary)
    z_values = tuple(float(p[2]) for p in boundary)
    if (not all(isfinite(v) for v in (x, z, *y_values, *z_values))
            or max(y_values)-min(y_values) < _TOL
            or not isclose(z-max(z_values), 1.0, rel_tol=0., abs_tol=0.02)):
        # The physical T2 surface is 1 mm behind the BasePlate's lower skin.
        # This verifies contact only; it MUST NOT compute the installation Z.
        raise ValueError("EAR_INSTALLATION_BASE_LOWER_EDGE_CONTACT_MISMATCH")
    return ((x, min(y_values), z), (x, max(y_values), z))


# Visualization / SIDE marking only. This 20 mm is an illustrative short fold
# leg, NOT a source bend position, CUTTING dimension, or assembled Z datum.
EAR_FOLD_HINT_LENGTH_MM = 20.0


def receiving_ear_positioning_world_segments(contact: ReceivingEarSideContactSurface):
    """Installation top + two short side hints; no bottom-edge marking.

    The actual 256x22 physical contact and the source part's BEND23 are
    verified separately and remain unchanged. The hint length is cosmetic:
    it never participates in placement, forming, holes or manufacturing BOM.
    """
    top_left, top_right = receiving_ear_installation_world_segment(contact)
    hint = float(EAR_FOLD_HINT_LENGTH_MM)
    min_skin_z = min(float(p[2]) for p in contact.world_surface_boundary)
    if hint <= 0.0 or top_left[2] - hint < min_skin_z - _TOL:
        raise ValueError("EAR_FOLD_HINT_OUTSIDE_VERIFIED_CONTACT")
    return (
        (top_left, top_right),
        (top_left, (top_left[0], top_left[1], top_left[2] - hint)),
        (top_right, (top_right[0], top_right[1], top_right[2] - hint)),
    )


def resolve_receiving_ear_side_contact_surfaces(
    snapshot: Mapping[str, object],
) -> tuple[ReceivingEarSideContactSurface, ...]:
    """Re-run one/two-tier source owners with the SAME source formed T2 mesh."""
    from .receiving_fixed_plate_formed_skins import (
        build_receiving_formed_fixing_plate_skins,
    )
    from .receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy

    owners = resolve_receiving_tier_ear_mating_xy(snapshot)
    if len(owners) not in (2, 4):
        raise ValueError("EAR_SIDE_CONTACT_INCOMPLETE_PHYSICAL_OWNERS")
    result = tuple(
        derive_receiving_ear_side_contact_from_formed_skin(
            build_receiving_formed_fixing_plate_skins(snapshot, entry.ear_id)
        ) for entry in owners
    )
    if (len({r.ear_part_id for r in result}) != len(result)
            or {r.base_part_id for r in result}
               != {entry.parent_base_id for entry in owners}):
        raise ValueError("EAR_SIDE_CONTACT_OWNER_OR_TIER_DRIFT")
    return result
