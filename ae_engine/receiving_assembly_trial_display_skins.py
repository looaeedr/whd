# -*- coding: utf-8 -*-
"""#2517 Headless display-only true-world EAR/PAD skin source projection.

This consumes existing source-verified Engine formed skins; it never makes
manufacturing parts, approves welding or NFB PAD, or writes BEND/CUTTING/DXF.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReceivingAssemblyTrialSkinMesh:
    """One existing formed trial source's immutable world triangle bundle."""

    role: str
    part_id: str
    world_triangles: tuple


def project_receiving_assembly_trial_world_skin_meshes(
    *, formed_fixing_plate_skins=(), formed_nfb_pad_skins=(),
    show_fixing_plate_mesh=True,
) -> tuple[ReceivingAssemblyTrialSkinMesh, ...]:
    """Only Engine validates and selects EAR/PAD world skins for assembly 3D.

    Hiding EAR removes its display mesh but not its separate side MARKING.
    PAD always uses its existing independently-derived visibility contract.
    Trial mesh presence never means manufacturing, weld or contact approval.
    """
    shown = []
    for formed in tuple(formed_fixing_plate_skins or ()):
        if not bool(show_fixing_plate_mesh):
            continue
        if (not getattr(formed, "source_bend_verified", False)
                or not getattr(formed, "actual_signed_forming_constructed", False)
                or getattr(formed, "manufacturing_ready", True)
                or getattr(formed, "weld_contact_verified", True)):
            raise ValueError("EAR_3D_SOURCE_OR_MANUFACTURING_GATE_FAILED")
        faces = tuple(
            tuple(tuple(float(value) for value in point) for point in face.world)
            for face in tuple(formed.mapped_world_skins or ())
        )
        if not faces:
            raise ValueError("EAR_3D_FORMED_SKIN_EMPTY")
        shown.append(ReceivingAssemblyTrialSkinMesh(
            "EAR", str(formed.part_id), faces,
        ))
    for pad in tuple(formed_nfb_pad_skins or ()):
        if (pad.manufacturing_ready or pad.assembly_contact_certified
                or not pad.source_flat_and_bend_verified
                or not pad.actual_base_squares_present):
            raise ValueError("PAD_3D_PREVIEW_SOURCE_OR_MFG_GATE_INVALID")
        faces = tuple(pad.world_triangles or ())
        if not faces:
            raise ValueError("PAD_3D_PREVIEW_EMPTY_MESH")
        shown.append(ReceivingAssemblyTrialSkinMesh(
            "PAD", str(pad.part_id), faces,
        ))
    return tuple(shown)
