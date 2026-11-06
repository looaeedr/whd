# -*- coding: utf-8 -*-
"""Headless physical dimension evidence for already-resolved assembly parts.

Material/canonical Fold is the authority; this never derives manufacturing
dimensions from a projected 3D bounding box or exposes a new DXF capability.
"""
from __future__ import annotations

from dataclasses import dataclass

from .box_body_fold_profile import apply_outside_dimension_compensation


@dataclass(frozen=True)
class AssemblyPhysicalDimensionEvidence:
    """Immutable dimensional values for a FinalScene UI presentation row."""

    role: str
    material_extent: tuple[float, float] | None = None
    fw_outside: object = None
    core_outside: object = None
    fold_outside: tuple[float, ...] = ()


def project_assembly_physical_dimension_evidence(part, *, thickness):
    """Read original physical metadata and Engine's adjacent-BEND rule.

    The request contains an already resolved physical assembly part. Ordering,
    formed_length overrides and missing/empty source behavior match the
    original Phase6 presentation. This function never mutates source DTOs.
    """
    key = str(getattr(part, "part_key", "") or "")
    if key != "box_body":
        if not key.startswith("box_body:divider:"):
            return ()
        data = getattr(part, "render_data", None)
        material = getattr(data, "material", None)
        if material is None or getattr(material, "is_empty", True):
            return ()
        minx, miny, maxx, maxy = map(float, material.bounds)
        contract = dict(
            (getattr(data, "metadata", {}) or {}).get("physical_geometry_contract") or {}
        )
        return (AssemblyPhysicalDimensionEvidence(
            role="divider",
            material_extent=(maxx - minx, maxy - miny),
            fw_outside=dict(contract.get("fw_physical_face") or {}).get("outside_dimension"),
            core_outside=dict(contract.get("core_physical_segment") or {}).get("outside_dimension"),
        ),)

    result = []
    for piece in tuple(getattr(getattr(part, "render_data", None), "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "")
        if role not in ("left_side", "right_side"):
            continue
        segments = tuple(getattr(piece, "fold_profile", None) or ())
        if not segments:
            continue
        rows = [{
            "len": float(segment.length),
            **({"angle": float(segment.angle)}
               if segment.angle is not None else {}),
        } for segment in segments]
        apply_outside_dimension_compensation(rows, thickness)
        outside = tuple(
            float(segment.formed_length)
            if segment.formed_length is not None
            else float(row["len"]) + float(row.get("ui_len_add", 0.0))
            for segment, row in zip(segments, rows)
        )
        result.append(AssemblyPhysicalDimensionEvidence(
            role=role, fold_outside=outside,
        ))
    return tuple(result)
