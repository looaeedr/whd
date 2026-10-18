# -*- coding: utf-8 -*-
"""#1503: true solid-skin contact witness for the source-formed T2 EAR flange.

A 3D rectangle alone cannot prove welding contact. Verify both sides'
AUTHORITATIVE world physical triangles, opposed outward skin normals,
full positive material overlap and no penetration through the SIDE skin.
This is a fit receipt, NOT weld workmanship or manufacturing certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
)
from .receiving_fixed_plate_side_contact import (
    derive_receiving_ear_side_contact_from_formed_skin,
    resolve_receiving_ear_side_contact_surfaces,
)

_X_TOL = 0.02
_AREA_TOL = 1.0


@dataclass(frozen=True)
class ReceivingEarSideSkinMatingWitness:
    ear_part_id: str
    base_part_id: str
    side_piece_id: str
    nfb_layer_index: int
    world_skin_x_mm: float
    physical_contact_area_mm2: float
    flange_skin_normal_opposed: bool = True
    panel_inside_skin_source_verified: bool = True
    full_contact_material_coverage_verified: bool = True
    no_through_side_skin_penetration_verified: bool = True
    welding_workmanship_certified: bool = False
    manufacturing_ready: bool = False


def _normal_of_skin(record):
    world = tuple(record.world)
    if len(world) != 3 or int(record.side) not in {-1, 1}:
        return None
    a, b, c = world
    v = tuple(float(b[i]) - float(a[i]) for i in range(3))
    w = tuple(float(c[i]) - float(a[i]) for i in range(3))
    cross = (
        v[1]*w[2]-v[2]*w[1],
        v[2]*w[0]-v[0]*w[2],
        v[0]*w[1]-v[1]*w[0],
    )
    length = sum(value*value for value in cross)**0.5
    if length <= 1e-9:
        return None
    return tuple(int(record.side)*value/length for value in cross)


def _outward_skin_faces(rows, *, x, expected_normal_x):
    found = []
    for skin in tuple(rows or ()):
        pts = tuple(getattr(skin, "world", ()) or ())
        if (len(pts) != 3
                or not all(abs(float(p[0])-x) <= _X_TOL for p in pts)):
            continue
        normal = _normal_of_skin(skin)
        if normal is not None and (
            abs(normal[0]-expected_normal_x) <= 1e-6
            and abs(normal[1]) <= 1e-6
            and abs(normal[2]) <= 1e-6
        ):
            found.append(skin)
    return tuple(found)


def _skin_yz_polygon(rows):
    triangles = tuple(
        Polygon(tuple((float(p[1]), float(p[2])) for p in skin.world))
        for skin in tuple(rows or ())
    )
    triangles = tuple(p for p in triangles if p.is_valid and p.area > 1e-8)
    if not triangles:
        raise ValueError("EAR_SIDE_MATING_NO_REAL_PHYSICAL_SKIN_TRIANGLES")
    return unary_union(triangles)


def verify_receiving_ear_side_skin_mating(
    contact, formed, side_mapped_skins,
) -> ReceivingEarSideSkinMatingWitness:
    """Prove authentic T2 flange skin meets actual side INNER source material."""
    if (contact.ear_part_id != formed.part_id
            or contact.base_part_id != formed.base_part_id
            or contact.nfb_layer_index != formed.layer_index
            or contact.side_piece_id != f"box_body:{formed.side}_side"
            or not contact.source_bend_verified
            or not contact.formed_source_skin_verified
            or not formed.actual_signed_forming_constructed
            or not formed.source_bend_verified
            or not formed.side_wall_skin_contact_x_verified
            or formed.weld_contact_verified or formed.manufacturing_ready
            or not isclose(float(formed.source_sheet_t_mm), 2., abs_tol=1e-6)
            or not isclose(float(formed.source_bend_y_mm), 23., abs_tol=1e-6)):
        raise ValueError("EAR_SIDE_MATING_FORM_OR_OWNER_UNVERIFIED")

    x = float(contact.side_inside_skin_world_x_mm)
    left = formed.side == "left"
    if (formed.side not in {"left", "right"}
            or not isclose(x, -398. if left else 398., abs_tol=_X_TOL)):
        raise ValueError("EAR_SIDE_MATING_WRONG_SIDE_DATUM")
    # Outward normal of the *inner physical side-wall skin* points INTO
    # the cabinet (+X left / -X right). EAR's wall-facing physical skin
    # must have the opposite outward normal, not merely share an X plane.
    mother_nx = 1 if left else -1
    mother = _outward_skin_faces(
        side_mapped_skins, x=x, expected_normal_x=mother_nx,
    )
    flange = _outward_skin_faces(
        formed.mapped_world_skins, x=x, expected_normal_x=-mother_nx,
    )
    if not mother or not flange:
        raise ValueError("EAR_SIDE_MATING_OPPOSED_NORMAL_OR_SKIN_MISSING")

    rect = Polygon(tuple(
        (float(p[1]), float(p[2])) for p in contact.world_surface_boundary
    ))
    if (not rect.is_valid or rect.is_empty
            or abs(rect.area-5632.) > _AREA_TOL):
        raise ValueError("EAR_SIDE_MATING_CONTACT_BOUNDARY_INVALID")

    actual_side = _skin_yz_polygon(mother)
    actual_flange = _skin_yz_polygon(flange)
    if (not actual_side.buffer(_X_TOL).covers(rect)
            or not actual_flange.buffer(_X_TOL).covers(rect)
            or abs(actual_side.intersection(actual_flange).intersection(rect).area
                   - rect.area) > _AREA_TOL):
        raise ValueError("EAR_SIDE_MATING_CONTACT_AREA_INCOMPLETE")

    # Any inward end of the 2mm folded leg must stay on the CABINET side
    # of the SIDE's inside physical skin. A folded flange penetrating the
    # material volume would have X smaller than -398 (left) or larger
    # than +398 (right), even if one incidental triangle were coplanar.
    physical_leg_points = tuple(
        p
        for skin in tuple(formed.mapped_world_skins or ())
        for uv,p in zip(skin.flat, skin.world)
        if float(uv[1]) <= float(formed.actual_mid_surface_hinge_y_mm) + 1e-6
    )
    if not physical_leg_points:
        raise ValueError("EAR_SIDE_MATING_LEG_SOLID_MISSING")
    leg_x = tuple(float(p[0]) for p in physical_leg_points)
    if (left and (min(leg_x) < x-_X_TOL or max(leg_x) > x+2.+_X_TOL)) or (
        not left and (max(leg_x) > x+_X_TOL or min(leg_x) < x-2.-_X_TOL)
    ):
        raise ValueError("EAR_SIDE_MATING_THROUGH_WALL_PENETRATION")

    return ReceivingEarSideSkinMatingWitness(
        ear_part_id=contact.ear_part_id, base_part_id=contact.base_part_id,
        side_piece_id=contact.side_piece_id,
        nfb_layer_index=contact.nfb_layer_index, world_skin_x_mm=x,
        physical_contact_area_mm2=float(rect.area),
    )


def resolve_receiving_ear_side_skin_mating_witnesses(
    snapshot, *, world_geometry,
) -> tuple[ReceivingEarSideSkinMatingWitness, ...]:
    """All signed one/two NFB tier owners require independent physical proof."""
    world = dict(world_geometry or {})
    mappings = dict(world.get("mapped_skin_triangles_by_part") or {})
    contacts = resolve_receiving_ear_side_contact_surfaces(snapshot)
    results = []
    for contact in contacts:
        formed = build_receiving_formed_fixing_plate_skins(
            snapshot, contact.ear_part_id,
        )
        # The side contact must correspond exactly to this re-derived source.
        original = derive_receiving_ear_side_contact_from_formed_skin(formed)
        if original != contact:
            raise ValueError("EAR_SIDE_MATING_CONTACT_SOURCE_DRIFT")
        results.append(verify_receiving_ear_side_skin_mating(
            contact, formed, mappings.get(contact.side_piece_id),
        ))
    if (len(results) not in (2, 4)
            or len({r.ear_part_id for r in results}) != len(results)
            or set(r.side_piece_id for r in results)
            != {"box_body:left_side", "box_body:right_side"}):
        raise ValueError("EAR_SIDE_MATING_TIER_OR_SIDE_INCOMPLETE")
    return tuple(results)
