# -*- coding: utf-8 -*-
"""Engine-owned 3D inspection projection for an independent physical part.

Only read existing canonical PartRenderData, validated source profiles and
Factory geometry; never rewrite manufacturing CUTTING/BEND/DXF source.
"""
from __future__ import annotations

from dataclasses import dataclass

from .assembly_geometry import (
    folded_mesh_from_polygon, folded_mesh_with_flat_uv_from_polygon,
    thicken_triangle_surface,
)
from .assembly_geometry_folded_mesh import fit_receiving_left_zl1_formed_outside
from .receiving_fixed_plate_formed_skins import verified_receiving_fixing_plate_local_fold


@dataclass(frozen=True)
class IndependentPartViewMesh:
    triangles: tuple
    x_profile: object
    y_profile: object
    fold_guides: tuple
    fixed_plate_hinge_y: float | None = None


def project_independent_part_view_mesh(
    part_key: str, render_data, *, x_profile, y_profile, thickness: float,
) -> IndependentPartViewMesh:
    """Resolve actual standalone 3D skin in the same domain as assembly.

    For certified EAR fixing plate the physical 3D MID-skin hinge and true T
    are taken from source-verified Engine metadata (never a GUI guessed fold).
    For Receiving left side use the source-owned formed/outside correction.
    Every other part keeps the established canonical flat-UV folded surface.
    """
    material = render_data.material
    guides = tuple(getattr(render_data, "fold_guides", ()) or ())
    metadata = getattr(render_data, "metadata", None) or {}
    if (str(part_key).startswith("base_plate:fixing_plate:")
            and metadata.get("source_profile") == "large"):
        hinge_y, x_profile, y_profile, guides = (
            verified_receiving_fixing_plate_local_fold(render_data)
        )
        mapped = folded_mesh_with_flat_uv_from_polygon(
            material, x_profile, y_profile, fold_guides=guides,
        )
        tris = thicken_triangle_surface(
            tuple(face.local for face in mapped),
            float(metadata["thickness"]),
        )
        return IndependentPartViewMesh(
            tuple(tris), x_profile, y_profile, tuple(guides),
            fixed_plate_hinge_y=float(hinge_y),
        )
    if str(part_key) == "box_body:left_side":
        mapped = folded_mesh_with_flat_uv_from_polygon(
            material, x_profile, y_profile, fold_guides=guides,
        )
        formed = fit_receiving_left_zl1_formed_outside(
            x_profile, mapped, tuple(item.local for item in mapped),
            thickness=thickness, axis=2,
        )
        tris = thicken_triangle_surface(formed, thickness)
        return IndependentPartViewMesh(
            tuple(tris), x_profile, y_profile, guides,
        )
    return IndependentPartViewMesh(
        tuple(folded_mesh_from_polygon(
            material, x_profile, y_profile, fold_guides=guides,
        )),
        x_profile, y_profile, guides,
    )
