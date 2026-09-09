# -*- coding: utf-8 -*-
"""Canonical Divider placement, assembly-relief and final-material solve.

This module owns the physical solve. UI/renderer adapters may provide the
assembly refold callback, but may not interpret FW segments or manufacture a
second relief/final-material result.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Mapping


@dataclass(frozen=True)
class DividerPlacementEvidence:
    contract: str
    valid: bool
    fw_face_flush: bool
    core_inward: bool
    placement_kind: str
    tolerance: float
    fw_physical_face: Mapping[str, object]
    box_body_left_fw_planes: tuple[float, ...] = ()
    box_body_right_fw_planes: tuple[float, ...] = ()
    divider_fw_planes: tuple[float, ...] = ()
    box_body_left_fw_formed_occupation: float | None = None
    box_body_right_fw_formed_occupation: float | None = None
    expected_fw_formed_occupation: float | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "contract": self.contract,
            "valid": self.valid,
            "fw_face_flush": self.fw_face_flush,
            "core_inward": self.core_inward,
            "placement_kind": self.placement_kind,
            "tolerance": self.tolerance,
            "fw_physical_face": dict(self.fw_physical_face),
            "box_body_left_fw_planes": self.box_body_left_fw_planes,
            "box_body_right_fw_planes": self.box_body_right_fw_planes,
            "divider_fw_planes": self.divider_fw_planes,
            "box_body_left_fw_formed_occupation": self.box_body_left_fw_formed_occupation,
            "box_body_right_fw_formed_occupation": self.box_body_right_fw_formed_occupation,
            "expected_fw_formed_occupation": self.expected_fw_formed_occupation,
            **({"reason": self.reason} if self.reason else {}),
        }


@dataclass(frozen=True)
class DividerReliefEvidence:
    candidate_status: str
    core_start: float | None = None
    cut_depths: tuple[float, ...] = ()
    pre_pair_count: int = 0
    post_pair_count: int = 0
    retained_contact_segments: int = 0
    source_evidence: Mapping[str, object] | None = None
    post_evidence: Mapping[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_status": self.candidate_status,
            "core_start": self.core_start,
            "cut_depths": self.cut_depths,
            "pre_pair_count": self.pre_pair_count,
            "post_pair_count": self.post_pair_count,
            "retained_contact_segments": self.retained_contact_segments,
            "evidence": dict(self.source_evidence or {}),
            **({"post": dict(self.post_evidence or {})} if self.post_evidence is not None else {}),
        }


@dataclass(frozen=True)
class ResolvedDividerFinalGeometry:
    part_id: str
    placement_datum: Mapping[str, object]
    placement_evidence: DividerPlacementEvidence
    relief_evidence: DividerReliefEvidence
    final_material: object
    verified: bool
    solved_part: object
    illegal_penetration: bool


def _profile_flat_band(profile, *, phase6_key: str):
    cursor = 0.0
    for row in tuple(profile or ()):
        if isinstance(row, dict):
            length = float(row.get("len", row.get("length", 0.0)) or 0.0)
            key = str(row.get("phase6_key") or "")
        else:
            length = float(getattr(row, "length", 0.0) or 0.0)
            key = str(getattr(row, "phase6_key", "") or "")
        if key == phase6_key:
            return float(cursor), float(cursor + length)
        cursor += length
    raise ValueError(f"Fold Profile band not found: phase6_key={phase6_key!r}")


def _planar_skin_z_planes(skins, band, *, tolerance=1e-5):
    start, end = (float(v) for v in band)
    tol = float(tolerance)
    values = []
    for skin in tuple(skins or ()):
        flat = tuple(getattr(skin, "flat", ()) or ())
        world = tuple(getattr(skin, "world", ()) or ())
        if len(flat) != 3 or len(world) != 3:
            continue
        centroid_x = sum(float(point[0]) for point in flat) / 3.0
        if not (start + tol < centroid_x < end - tol):
            continue
        zs = tuple(float(point[2]) for point in world)
        if max(zs) - min(zs) > tol:
            continue
        values.append(sum(zs) / len(zs))
    unique = []
    for value in sorted(values):
        if not unique or abs(value - unique[-1]) > tol:
            unique.append(float(value))
    return tuple(unique)


def _planar_skin_axis_occupation(skins, band, *, axis=0, tolerance=1e-5):
    start, end = (float(v) for v in band)
    tol = float(tolerance)
    values = []
    for skin in tuple(skins or ()):
        flat = tuple(getattr(skin, "flat", ()) or ())
        world = tuple(getattr(skin, "world", ()) or ())
        if len(flat) != 3 or len(world) != 3:
            continue
        centroid_x = sum(float(point[0]) for point in flat) / 3.0
        if not (start + tol < centroid_x < end - tol):
            continue
        values.extend(float(point[int(axis)]) for point in world)
    if not values:
        raise ValueError("physical FW formed occupation unavailable")
    return float(max(values) - min(values))


def _physical_contract(part) -> dict[str, object]:
    metadata = dict(getattr(getattr(part, "render_data", None), "metadata", {}) or {})
    return dict(metadata.get("physical_geometry_contract") or {})


def _core_start(part) -> float:
    contract = _physical_contract(part)
    core = dict(contract.get("core_physical_segment") or {})
    band = tuple(core.get("flat_band") or ())
    if len(band) != 2:
        raise ValueError(f"Divider core physical segment unavailable: {part.part_key}")
    return float(band[0])


def _source_fold_bands_by_geometry_key(box_body) -> dict[str, tuple[tuple[str, float, float], ...]]:
    """Expose authoritative physical BoxBody Fold bands to Divider collision.

    Stage identity comes from each real side piece's Fold profile.  The returned
    cumulative UV bounds are geometry authority, not validation measurements.
    """
    result = {}
    for piece in tuple(getattr(box_body.render_data, "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "").strip().lower()
        if not role:
            continue
        cursor = 0.0
        bands = []
        for index, row in enumerate(tuple(getattr(piece, "fold_profile", ()) or ())):
            end = cursor + float(getattr(row, "length", 0.0) or 0.0)
            key = str(getattr(row, "phase6_key", "") or f"segment_{index}")
            if end > cursor:
                bands.append((key, float(cursor), float(end)))
            cursor = end
        result[f"box_body:{role}"] = tuple(bands)
    return result


def resolve_divider_placement_evidence(divider, box_body, world, *, tolerance=1e-5) -> DividerPlacementEvidence:
    tol = float(tolerance)
    contract = _physical_contract(divider)
    fw_face = dict(contract.get("fw_physical_face") or {})
    divider_band = tuple(fw_face.get("flat_band") or ())
    placement_kind = str(getattr(divider, "placement", "") or "")
    core_inward = placement_kind.endswith("_inward")

    def fail(
        reason: str, *, left=(), right=(), divider_planes=(),
        left_occupation=None, right_occupation=None, expected_occupation=None,
    ):
        return DividerPlacementEvidence(
            contract="DIVIDER_FW_FACE_FLUSH_V1", valid=False,
            fw_face_flush=False, core_inward=core_inward,
            placement_kind=placement_kind, tolerance=tol,
            fw_physical_face=fw_face,
            box_body_left_fw_planes=tuple(left),
            box_body_right_fw_planes=tuple(right),
            divider_fw_planes=tuple(divider_planes),
            box_body_left_fw_formed_occupation=left_occupation,
            box_body_right_fw_formed_occupation=right_occupation,
            expected_fw_formed_occupation=expected_occupation,
            reason=reason,
        )

    if len(divider_band) != 2:
        return fail("Divider physical contract has no FW physical flat band")
    pieces = tuple(getattr(box_body.render_data, "pieces", ()) or ())
    by_role = {str(getattr(piece, "role", "") or ""): piece for piece in pieces}
    if "left_side" not in by_role or "right_side" not in by_role:
        return fail("Receiving BoxBody lacks left/right physical side pieces")
    try:
        left_band = _profile_flat_band(by_role["left_side"].fold_profile, phase6_key="fw_left")
        right_band = _profile_flat_band(by_role["right_side"].fold_profile, phase6_key="fw_right")
        mapped = dict(world.get("mapped_skin_triangles_by_part") or {})
        left_skins = mapped.get("box_body:left_side", ())
        right_skins = mapped.get("box_body:right_side", ())
        left = _planar_skin_z_planes(left_skins, left_band, tolerance=tol)
        right = _planar_skin_z_planes(right_skins, right_band, tolerance=tol)
        divider_planes = _planar_skin_z_planes(mapped.get(str(divider.part_key), ()), divider_band, tolerance=tol)
        expected_occupation = float(fw_face.get("outside_dimension"))
        left_occupation = _planar_skin_axis_occupation(left_skins, left_band, axis=0, tolerance=tol)
        right_occupation = _planar_skin_axis_occupation(right_skins, right_band, axis=0, tolerance=tol)
    except Exception as exc:
        return fail(f"FW placement evidence unavailable: {exc}")
    formed_match = (
        abs(left_occupation - expected_occupation) <= tol
        and abs(right_occupation - expected_occupation) <= tol
    )
    if not formed_match:
        return fail(
            "Receiving BoxBody FW formed occupation does not match authoritative outside FW",
            left=left, right=right, divider_planes=divider_planes,
            left_occupation=left_occupation,
            right_occupation=right_occupation,
            expected_occupation=expected_occupation,
        )
    same_count = bool(left) and len(left) == len(right) == len(divider_planes)
    body_match = same_count and all(abs(a - b) <= tol for a, b in zip(left, right))
    divider_match = same_count and all(abs(a - b) <= tol for a, b in zip(divider_planes, left))
    flush = bool(body_match and divider_match)
    valid = bool(flush and core_inward)
    reason = None if valid else (
        "Divider FW physical skins are not flush with BoxBody FW skins"
        if not flush else "Divider core orientation is not inward"
    )
    return DividerPlacementEvidence(
        contract="DIVIDER_FW_FACE_FLUSH_V1", valid=valid,
        fw_face_flush=flush, core_inward=core_inward,
        placement_kind=placement_kind, tolerance=tol,
        fw_physical_face=fw_face,
        box_body_left_fw_planes=left,
        box_body_right_fw_planes=right,
        divider_fw_planes=divider_planes,
        box_body_left_fw_formed_occupation=left_occupation,
        box_body_right_fw_formed_occupation=right_occupation,
        expected_fw_formed_occupation=expected_occupation,
        reason=reason,
    )


def _apply_cut_to_part(part, cut_polygon):
    from .assembly_collision import _scene_with_replaced_primary_cutting
    from .manufacturing_api import (
        material_polygon_from_final_scene,
        fold_guides_from_final_scene,
        _scene_with_authoritative_fold_profiles,
    )
    material = part.render_data.material.difference(cut_polygon)
    if not material.is_valid:
        material = material.buffer(0)
    if material.is_empty:
        raise ValueError("Divider assembly relief removed all material")
    scene = _scene_with_replaced_primary_cutting(part.render_data.scene, material)
    scene = _scene_with_authoritative_fold_profiles(scene, part.x_profile, part.y_profile)
    render_data = replace(
        part.render_data,
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
    )
    return replace(part, render_data=render_data)


def resolve_divider_final_geometry(
    *, divider, box_body, joint, world, source_geometry_keys,
    refold_world: Callable[[object], Mapping[str, object]], clearance: float = 0.0,
    sheet_thickness: float = 0.0,
) -> ResolvedDividerFinalGeometry:
    """Resolve one Divider's placement, collision relief and verified final material.

    Placement is proved first from physical FW skins. Only a valid placement may
    enter collision/backprojection. Any cut is then refolded and verified before
    it can become canonical final material.
    """
    from .assembly_collision import (
        build_divider_front_fold_relief_candidate,
        verify_divider_front_fold_relief,
    )
    from .manufacturing_api import apply_divider_endcap_shared_6p4_datum

    contract = _physical_contract(divider)
    placement_datum = dict(contract.get("placement_datum") or {})
    placement = resolve_divider_placement_evidence(divider, box_body, world)
    original_material = divider.render_data.material
    if not placement.valid:
        return ResolvedDividerFinalGeometry(
            part_id=str(divider.part_key), placement_datum=placement_datum,
            placement_evidence=placement,
            relief_evidence=DividerReliefEvidence("INVALID_DIVIDER_FW_PLACEMENT"),
            final_material=original_material, verified=False, solved_part=divider,
            illegal_penetration=True,
        )

    core_start = _core_start(divider)
    source_fold_bands = _source_fold_bands_by_geometry_key(box_body)
    candidate = build_divider_front_fold_relief_candidate(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        core_start=core_start,
        source_geometry_keys=tuple(source_geometry_keys),
        source_fold_bands_by_key=source_fold_bands,
        clearance=float(clearance),
        sheet_thickness=max(0.0, float(sheet_thickness)),
    )
    if candidate is None:
        return ResolvedDividerFinalGeometry(
            part_id=str(divider.part_key), placement_datum=placement_datum,
            placement_evidence=placement,
            relief_evidence=DividerReliefEvidence(
                "NO_FRONT_FOLD_PENETRATION", core_start=core_start,
            ),
            final_material=original_material, verified=True, solved_part=divider,
            illegal_penetration=False,
        )

    solved = _apply_cut_to_part(divider, candidate.cut_polygon_2d)
    solved = replace(solved, render_data=apply_divider_endcap_shared_6p4_datum(solved.render_data))
    solved_world = refold_world(solved)
    verification = verify_divider_front_fold_relief(
        joint,
        world_triangles_by_part=solved_world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=solved_world["mapped_skin_triangles_by_part"],
        flat_material_by_part=solved_world["flat_material_by_part"],
        core_start=core_start,
        source_geometry_keys=tuple(source_geometry_keys),
        source_fold_bands_by_key=source_fold_bands,
        physical_footprints_by_source=dict(
            candidate.physical_footprints_by_source or {}
        ),
    )
    verified = bool(verification["verified"])
    relief = DividerReliefEvidence(
        "PROVISIONAL_3D_VERIFIED" if verified else "DIVIDER_RELIEF_REPLAY_FAILED",
        core_start=core_start,
        cut_depths=tuple(candidate.cut_depths),
        pre_pair_count=int(candidate.pre_pair_count),
        post_pair_count=int(verification["pair_count"]),
        retained_contact_segments=int(verification["retained_contact_segments"]),
        source_evidence=dict(candidate.evidence or {}),
        post_evidence=dict(verification),
    )
    if not verified:
        return ResolvedDividerFinalGeometry(
            part_id=str(divider.part_key), placement_datum=placement_datum,
            placement_evidence=placement, relief_evidence=relief,
            final_material=original_material, verified=False, solved_part=divider,
            illegal_penetration=True,
        )

    metadata = dict(getattr(solved.render_data, "metadata", {}) or {})
    metadata["divider_assembly_relief"] = {
        "trust_level": "PROVISIONAL_3D",
        "verified": True,
        **relief.as_dict(),
        "evidence": {
            **dict(candidate.evidence or {}),
            "placement": placement.as_dict(),
        },
    }
    metadata["resolved_divider_physical_geometry"] = {
        "part_id": str(divider.part_key),
        "placement_datum": placement_datum,
        "placement_evidence": placement.as_dict(),
        "relief_evidence": relief.as_dict(),
        "verified": True,
    }
    solved = replace(solved, render_data=replace(solved.render_data, metadata=metadata))
    return ResolvedDividerFinalGeometry(
        part_id=str(divider.part_key), placement_datum=placement_datum,
        placement_evidence=placement, relief_evidence=relief,
        final_material=solved.render_data.material, verified=True,
        solved_part=solved, illegal_penetration=False,
    )
