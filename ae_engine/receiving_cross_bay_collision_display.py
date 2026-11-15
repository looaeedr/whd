# -*- coding: utf-8 -*-
"""Receiving cross-Bay physical-world collision *diagnostic*, Engine-owned.

Unlike single-Bay collision display, every real assembled sheet of two or
more Bays in ONE Set is independently meshed, joint-positioned and compared
against every sheet of each other Bay. No UI geometry, false clean-collision
certificate, cross-Set mating, or DXF/manufacturing eligibility is produced.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import isfinite

from .assembly_all_parts_collision import (
    AssemblyPhysicalPair, audit_all_physical_part_pairs,
)
from .assembly_geometry import build_joint_world_geometry
from .contracts import ResolvedManufacturingGeometry
from .manufacturing_export import receiving_instance_namespace
from .receiving_bay_preview_source import (
    project_receiving_bay_preview_assembly_members,
)
from .receiving_layout import normalize_receiving_layout


@dataclass(frozen=True)
class ReceivingSetCrossBayCollisionAudit:
    """Cross-Bay surface crossings only; never a solid-penetration certificate."""

    set_id: str
    bay_ids: tuple[str, ...]
    bay_offsets: tuple[tuple[float, float, float], ...]
    physical_keys_by_bay: tuple[tuple[str, ...], ...]
    pairs: tuple[AssemblyPhysicalPair, ...]

    @property
    def evaluated_pair_count(self) -> int:
        return len(self.pairs)

    @property
    def unresolved(self) -> tuple[AssemblyPhysicalPair, ...]:
        return tuple(p for p in self.pairs if p.status == "UNRESOLVED_CROSSING")

    def require_no_unresolved(self) -> bool:
        """Refuse unresolved crossings; a clean display still is NOT MFG approval."""
        if self.unresolved:
            names = "; ".join(f"{p.left} ↔ {p.right}" for p in self.unresolved)
            raise ValueError("RECEIVING_CROSS_BAY_CROSSING_UNVERIFIED: " + names)
        return True


def project_receiving_set_cross_bay_collision_display_audit(
    layout, physical_bay_geometry_provider, *, set_index, thickness_mm,
    tolerance=1e-5,
) -> ReceivingSetCrossBayCollisionAudit:
    """Cross-check ALL physically assembled sheets in one Set's real Joint space.

    The provider must independently return the *current, confirmed* canonical
    ResolvedManufacturingGeometry for each (set_index, bay_index). This API is
    read-only collision-display evidence, never proof of the provider's source
    identity or a path to certify entire-cabinet manufacturing/solid penetration.

    Each Bay's 3D skins are generated from its own actual FinalScene using the
    Bay's W/H/D and T. Only then does the Engine apply the same Joint-centre
    offset used by the original Receiving GUI preview. Composite BoxBody
    envelopes and unassembled standalone source flats are not physical pairs.
    Cross-Bay pairs never inherit a single Bay's certified relief exceptions.
    """
    normalized = normalize_receiving_layout(layout)
    sets = normalized["sets"]
    if type(set_index) is not int or not 0 <= set_index < len(sets):
        raise IndexError("RECEIVING_CROSS_BAY_SET_INDEX_INVALID")
    selected = sets[set_index]
    bays = selected["bays"]
    if len(bays) < 2:
        raise ValueError("RECEIVING_CROSS_BAY_AT_LEAST_TWO_BAYS_REQUIRED")
    if not callable(physical_bay_geometry_provider):
        raise TypeError("RECEIVING_CROSS_BAY_RESOLVER_REQUIRED")
    if isinstance(thickness_mm, bool):
        raise ValueError("RECEIVING_CROSS_BAY_THICKNESS_INVALID")
    try:
        thickness = float(thickness_mm)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("RECEIVING_CROSS_BAY_THICKNESS_INVALID") from exc
    if not isfinite(thickness) or thickness <= 0:
        raise ValueError("RECEIVING_CROSS_BAY_THICKNESS_INVALID")

    by_bay = []
    offsets = []
    all_keys = set()
    for bi, bay in enumerate(bays):
        canonical = physical_bay_geometry_provider(set_index, bi)
        if (not isinstance(canonical, ResolvedManufacturingGeometry)
                or not canonical.parts):
            raise ValueError("RECEIVING_CROSS_BAY_FINALSCENE_REQUIRED")
        projection = project_receiving_bay_preview_assembly_members(
            normalized, canonical.parts, set_index=set_index, bay_index=bi,
        )
        members = tuple(part for part, _world in projection.part_placements)
        if not any(part.part_key == "box_body" for part in members):
            raise ValueError("RECEIVING_CROSS_BAY_PHYSICAL_BODY_REQUIRED")
        world = build_joint_world_geometry(
            members, (bay["width"], bay["height"], bay["depth"]), thickness,
        )["world_triangles_by_part"]
        # A Receiving BoxBody must retain its actual individually meshed
        # side/back material; its aggregate proxy may not hide missing sheets.
        piece_roles = {
            key for key in world if key.startswith("box_body:")
            and not key.startswith("box_body:divider:")
        }
        if not {"box_body:left_side", "box_body:back", "box_body:right_side"} <= piece_roles:
            raise ValueError("RECEIVING_CROSS_BAY_PHYSICAL_BODY_PIECES_REQUIRED")
        namespace = receiving_instance_namespace(
            set_id=selected["stable_id"], bay_id=bay["stable_id"],
        )
        translated = {}
        anchor = projection.bay_offset
        for part_key, triangles in world.items():
            if part_key == "box_body":
                continue  # composite proxy, NOT a physical sheet
            key = f"{namespace}::{part_key}"
            if key in all_keys:
                raise ValueError("RECEIVING_CROSS_BAY_DUPLICATE_PHYSICAL_KEY")
            if not triangles:
                raise ValueError("RECEIVING_CROSS_BAY_MISSING_PHYSICAL_WORLD_MESH")
            shifted = []
            for tri in triangles:
                if len(tri) != 3:
                    raise ValueError("RECEIVING_CROSS_BAY_INVALID_WORLD_MESH")
                xyz = []
                for vertex in tri:
                    if (len(vertex) != 3 or
                            any(isinstance(v, bool) for v in vertex)):
                        raise ValueError("RECEIVING_CROSS_BAY_INVALID_WORLD_MESH")
                    try:
                        point = tuple(float(v) + anchor[axis] for axis, v in enumerate(vertex))
                    except (TypeError, ValueError, OverflowError) as exc:
                        raise ValueError("RECEIVING_CROSS_BAY_INVALID_WORLD_MESH") from exc
                    if not all(isfinite(v) for v in point):
                        raise ValueError("RECEIVING_CROSS_BAY_INVALID_WORLD_MESH")
                    xyz.append(point)
                shifted.append(tuple(xyz))
            translated[key] = tuple(shifted)
            all_keys.add(key)
        if not translated:
            raise ValueError("RECEIVING_CROSS_BAY_MISSING_PHYSICAL_WORLD_MESH")
        by_bay.append(translated)
        offsets.append(anchor)

    crossing_pairs = []
    for first, second in combinations(range(len(bays)), 2):
        left, right = by_bay[first], by_bay[second]
        # Reuse the original Engine world-interference classifier. Restrict
        # results to cross-Bay pairs; no same-Bay relief/contact exemption can
        # certify a contact between two independent physical cabinets.
        audit = audit_all_physical_part_pairs(
            {**left, **right}, tolerance=tolerance,
        )
        for pair in audit.pairs:
            if ((pair.left in left and pair.right in right)
                    or (pair.left in right and pair.right in left)):
                crossing_pairs.append(pair)
    return ReceivingSetCrossBayCollisionAudit(
        set_id=str(selected["stable_id"]),
        bay_ids=tuple(str(b["stable_id"]) for b in bays),
        bay_offsets=tuple(offsets),
        physical_keys_by_bay=tuple(tuple(sorted(x)) for x in by_bay),
        pairs=tuple(crossing_pairs),
    )
