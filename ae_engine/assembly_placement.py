# -*- coding: utf-8 -*-
"""Authoritative assembly placement contracts for topology-derived parts.

Placement is assembly data, not GUI state.  This module resolves divider and
inner-door shared-boundary placement from the same Door topology used to derive
physical divider parts.  It deliberately fails closed when a stable identity
cannot be mapped to authoritative topology instead of returning an origin
fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .sheetmetal_part_adapters import derive_door_layout_cells


@dataclass(frozen=True)
class AssemblyPlacement:
    """Resolved world placement contract for one physical assembly part."""

    stable_id: str
    parent_assembly_node: str
    anchor: str
    world_offset: tuple[float, float, float]
    rotation: tuple[float, float, float]
    mate_target: str
    relationship: str
    placement_kind: str
    semantic_position: tuple[float, float, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "stable_id": self.stable_id,
            "parent_assembly_node": self.parent_assembly_node,
            "anchor": self.anchor,
            "world_offset": list(self.world_offset),
            "rotation": list(self.rotation),
            "mate_target": self.mate_target,
            "relationship": self.relationship,
            "placement_kind": self.placement_kind,
            "semantic_position": list(self.semantic_position),
        }


_DIVIDER_RE = re.compile(
    r"^box_body:divider:(?P<scope>[^:]+):(?P<axis>VERTICAL|HORIZONTAL):(?P<boundary>.+)$"
)
_FRAME_RE = re.compile(r"^inner_door:(?P<door>[^:]+):(?P<side>top|bottom|left|right)_frame$")


def _topology(snapshot: Mapping[str, object]):
    columns = tuple(snapshot.get("door_layout_columns") or ())
    if not columns:
        raise ValueError("authoritative Door layout topology is missing")
    normalized = tuple(
        (float(row[0]), tuple(float(value) for value in row[1]))
        for row in columns
    )
    return normalized, tuple(derive_door_layout_cells(normalized))


def _dimensions(snapshot: Mapping[str, object], columns):
    total_w = float(snapshot.get("w", sum(width for width, _ in columns)))
    total_h = float(snapshot.get("h", max(sum(heights) for _, heights in columns)))
    return total_w, total_h


def _divider_position(snapshot: Mapping[str, object], axis: str, boundary: str):
    columns, cells = _topology(snapshot)
    total_w, total_h = _dimensions(snapshot, columns)

    if axis == "VERTICAL":
        match = re.fullmatch(r"C(\d+)\|C(\d+)", boundary)
        if match is None:
            raise ValueError(f"invalid authoritative vertical divider boundary: {boundary}")
        left_col, right_col = (int(match.group(1)), int(match.group(2)))
        if right_col != left_col + 1:
            raise ValueError(f"non-adjacent vertical divider boundary: {boundary}")
        if not (0 <= left_col < len(columns) - 0 and right_col < len(columns)):
            raise ValueError(f"vertical divider boundary outside Door topology: {boundary}")
        x = -total_w / 2.0 + sum(width for width, _ in columns[:right_col])
        # Divider folded X-profile is the physical depth direction; the
        # semantic placement itself is on the cabinet center Y plane.
        return (x, 0.0, 0.0)

    match = re.fullmatch(r"C(\d+):R(\d+)\|R(\d+)", boundary)
    if match is None:
        raise ValueError(f"invalid authoritative horizontal divider boundary: {boundary}")
    col, upper_row, lower_row = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    column_cells = [cell for cell in cells if cell.column_index == col]
    if not any(cell.row_index == upper_row for cell in column_cells):
        raise ValueError(f"horizontal divider upper cell outside Door topology: {boundary}")
    if not any(cell.row_index == lower_row for cell in column_cells):
        raise ValueError(f"horizontal divider lower cell outside Door topology: {boundary}")
    if lower_row != upper_row + 1:
        raise ValueError(f"non-adjacent horizontal divider boundary: {boundary}")
    y_before = sum(columns[col][1][:lower_row])
    upper_height = float(columns[col][1][upper_row])
    y = total_h / 2.0 - y_before - upper_height
    return (0.0, y, 0.0)


def resolve_divider_placement(snapshot: Mapping[str, object], stable_id: str) -> AssemblyPlacement:
    """Resolve one divider's placement from authoritative Door topology."""
    stable_id = str(stable_id or "").strip()
    match = _DIVIDER_RE.fullmatch(stable_id)
    if match is None:
        raise ValueError(f"not an authoritative Box Body divider stable id: {stable_id!r}")
    axis = match.group("axis")
    boundary = match.group("boundary")
    position = _divider_position(snapshot, axis, boundary)
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body",
        anchor=f"door_layout_boundary:{boundary}",
        world_offset=position,
        rotation=(0.0, 0.0, 0.0),
        mate_target="box_body:door_layout",
        relationship="SHARED_STRUCTURAL_DIVIDER",
        placement_kind="divider_vertical" if axis == "VERTICAL" else "divider_horizontal",
        semantic_position=position,
    )


def resolve_inner_door_lower_frame_placement(
    snapshot: Mapping[str, object],
    inner_door_id: str,
) -> AssemblyPlacement:
    """Resolve the inner-door lower frame to the exact shared divider identity."""
    from .door_dividers import derive_box_body_dividers, resolve_inner_door_lower_frame_role

    columns, _cells = _topology(snapshot)
    dividers = derive_box_body_dividers(
        columns,
        depth=float(snapshot.get("d", 0.0)),
        thickness=float(snapshot.get("t", 0.0)),
        layout_scope=str(snapshot.get("door_layout_scope") or "main").strip() or "main",
        handle_edges=dict(snapshot.get("door_handle_edges") or {}),
    )
    role = resolve_inner_door_lower_frame_role(inner_door_id, dividers)
    if role is None:
        raise ValueError(
            f"inner door {inner_door_id!r} has no unambiguous authoritative shared divider"
        )
    return resolve_divider_placement(snapshot, role.divider_stable_id).__class__(
        stable_id=f"inner_door:{str(inner_door_id).strip()}:bottom_frame",
        parent_assembly_node="box_body:door_layout:inner_door",
        anchor=f"shared_divider:{role.divider_stable_id}",
        world_offset=resolve_divider_placement(snapshot, role.divider_stable_id).world_offset,
        rotation=(0.0, 0.0, 0.0),
        mate_target=role.divider_stable_id,
        relationship="SHARED_LOWER_FRAME",
        placement_kind="inner_door_shared_divider",
        semantic_position=resolve_divider_placement(snapshot, role.divider_stable_id).semantic_position,
    )


def resolve_assembly_placement(snapshot: Mapping[str, object], stable_id: str) -> AssemblyPlacement:
    """Resolve supported authoritative assembly placements; never origin-fallback."""
    key = str(stable_id or "").strip()
    if _DIVIDER_RE.fullmatch(key):
        return resolve_divider_placement(snapshot, key)
    frame = _FRAME_RE.fullmatch(key)
    if frame and frame.group("side") == "bottom":
        return resolve_inner_door_lower_frame_placement(snapshot, frame.group("door"))
    raise ValueError(f"no authoritative placement contract for stable id: {key!r}")
