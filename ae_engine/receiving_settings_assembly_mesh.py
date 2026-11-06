# -*- coding: utf-8 -*-
"""Canonical Receiving settings 2D inspection's source physical world meshes.

Only already-resolved Manufacturing/Assembly DTOs enter this API. World
placement, true multi-piece skins, EndCap mating and surface thickening belong
to Engine; GUI decides only role labels, visibility and canvas painting.
These triangles are read-only inspection data, not CUTTING/DXF certification.
"""
from __future__ import annotations

from dataclasses import dataclass

from .assembly_geometry import (
    build_joint_world_geometry,
    folded_mesh_from_polygon,
    place_assembly_triangles,
    place_box_body_structure_points,
    place_endcap_against_box_body,
    thicken_triangle_surface,
)
from .box_body_world_datum import resolve_box_body_formed_width_datum


def _contract_profile_rows(profile):
    """Use the original resolved physical fold segments without recomputation."""
    rows = []
    for seg in profile or ():
        row = {"len": float(getattr(seg, "length", 0.0))}
        angle = getattr(seg, "angle", None)
        if angle is not None:
            row["angle"] = float(angle)
        core = getattr(seg, "core", None)
        if core:
            row["core"] = str(core)
        key = getattr(seg, "phase6_key", None)
        if key:
            row["phase6_key"] = str(key)
        rows.append(row)
    return rows


def _structure_meshes(render_data, *, thickness):
    """Resolve original Box Body piece-local mid-surfaces in assembly position."""
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if not pieces:
        return ()
    total_w = resolve_box_body_formed_width_datum(pieces)
    if total_w is None:
        return ()
    out = []
    for piece in pieces:
        data = piece.render_data
        x_profile = _contract_profile_rows(piece.fold_profile)
        minx, miny, maxx, maxy = map(float, data.material.bounds)
        y_profile = [{"len": maxy - miny}]
        local = folded_mesh_from_polygon(
            data.material, x_profile, y_profile,
            fold_guides=tuple(getattr(data, "fold_guides", ()) or ()),
        )
        transformed = [
            tuple(
                place_box_body_structure_points(
                    (point,), piece, total_w=total_w,
                    thickness=thickness, x_profile=x_profile,
                )[0]
                for point in tri
            )
            for tri in local
        ]
        out.append((piece, tuple(transformed)))
    return tuple(out)


def resolve_box_body_structure_mid_meshes(render_data, *, thickness):
    """Public Engine read-only physical Box Body mid-surface projection."""
    return _structure_meshes(render_data, thickness=thickness)


def _true_world_piece_meshes(part, *, dimensions, thickness):
    """Use canonical real-T world skins, never a reprojected preview substitute."""
    pieces = tuple(getattr(getattr(part, "render_data", None), "pieces", ()) or ())
    if not pieces:
        return ()
    if resolve_box_body_formed_width_datum(pieces) is None:
        return ()
    if str(getattr(part, "part_key", "")) != "box_body":
        raise ValueError("multi-piece world skins must originate in box_body")
    if dimensions is None or len(dimensions) != 3:
        raise ValueError("box_body true-world mesh requires assembled W/H/D")
    world = build_joint_world_geometry(
        (part,), tuple(float(value) for value in dimensions), float(thickness),
    )["world_triangles_by_part"]
    rows = []
    for piece in pieces:
        key = "box_body:" + str(getattr(piece, "role", "") or "")
        actual = tuple(world.get(key, ()) or ())
        if not actual:
            raise ValueError(f"missing physical mesh for {key}")
        rows.append((piece, actual))
    return tuple(rows)


def resolve_box_body_true_world_piece_meshes(part, *, dimensions, thickness):
    """Public Engine true-T world skins for an already-resolved Box Body.

    Uses the canonical joint world geometry and source piece identities.
    For preview stubs returns empty; for incomplete physical provenance
    fails closed. Does not create manufacturing authorization.
    """
    return _true_world_piece_meshes(
        part, dimensions=dimensions, thickness=thickness,
    )


@dataclass(frozen=True)
class AssembledEndcapWorldSkins:
    """Read-only actual world mid-surface and true-T sheet solid."""

    formed_surface: tuple
    solid_triangles: tuple


def resolve_assembled_endcap_world_skins(
    local_triangles, *, placement, box_body_world, thickness,
    offset=(0.0, 0.0, 0.0), preserve_core_origin=False,
):
    """Canonical Head/Tail world mating, then true-thickness physical skins.

    Caller owns resolved material and operator intent; no UI state, fallback
    preview geometry, manufacturing certification, or policy is introduced.
    """
    surface = place_endcap_against_box_body(
        local_triangles, placement, box_body_world, offset,
        sheet_thickness=thickness,
        preserve_core_origin=bool(preserve_core_origin),
    )
    return AssembledEndcapWorldSkins(
        formed_surface=tuple(surface),
        solid_triangles=tuple(thicken_triangle_surface(surface, thickness)),
    )


def resolve_receiving_settings_assembly_world_meshes(
    assembly_parts, *, finished_dimensions, thickness,
    preserve_endcap_core_origin=False,
):
    """Physical (source role, part key, world triangles) for Receiving 2D view.

    All transforms use existing canonical Engine primitives. No Tk, Phase6,
    user-viewport state, manufacturing permission or fallback rules live here.
    """
    box_body_world = None
    rows = []
    for part in tuple(assembly_parts or ()):
        data = part.render_data
        pieces = tuple(getattr(data, "pieces", ()) or ())
        physical_world = ()
        if pieces:
            meshes = resolve_box_body_structure_mid_meshes(data, thickness=thickness)
            physical_world = resolve_box_body_true_world_piece_meshes(
                part, dimensions=finished_dimensions, thickness=thickness,
            )
            local = [triangle for _piece, mesh in meshes for triangle in mesh]
        else:
            meshes = ()
            local = folded_mesh_from_polygon(
                data.material, tuple(dict(x) for x in part.x_profile),
                tuple(dict(y) for y in part.y_profile),
                fold_guides=tuple(getattr(data, "fold_guides", ()) or ()),
            )
        placement = str(getattr(part, "placement", "offset") or "offset")
        offset = getattr(part, "offset", (0, 0, 0))
        if placement in {"top", "head", "bottom", "tail"} and box_body_world:
            placed = resolve_assembled_endcap_world_skins(
                local, placement=placement, box_body_world=box_body_world,
                thickness=thickness, offset=offset,
                preserve_core_origin=preserve_endcap_core_origin,
            ).solid_triangles
        else:
            placed = place_assembly_triangles(
                local, placement, finished_dimensions, offset,
            )
        if str(part.part_key) == "box_body":
            box_body_world = tuple(placed)
        if not placed:
            continue
        if not pieces:
            rows.append((str(part.part_key), str(part.part_key), tuple(placed)))
            continue
        cursor = 0
        actual_by_role = {
            str(piece.role): world_mesh for piece, world_mesh in physical_world
        }
        for piece, piece_mesh in meshes:
            count = len(piece_mesh)
            world_piece = tuple(
                actual_by_role.get(str(piece.role), ())
                or placed[cursor:cursor + count]
            )
            cursor += count
            if world_piece:
                rows.append((str(piece.role), str(piece.key), world_piece))
    return tuple(rows)


def project_receiving_settings_physical_drawings(assembly_parts):
    """Return source-owned (role, stable key, DrawingScene) without flattening.

    The Receiving settings inspection sink must not infer physical multipart
    identity from GUI roles. Preserve every source part's native render data:
    these are not world meshes or approved manufacturing export requests.
    """
    rows = []
    for part in tuple(assembly_parts or ()):
        pieces = tuple(getattr(part.render_data, "pieces", ()) or ())
        if pieces:
            for piece in pieces:
                rows.append((str(piece.role), str(piece.key), piece.render_data))
        else:
            key = str(part.part_key)
            rows.append((key, key, part.render_data))
    return tuple(rows)
