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

from .sheetmetal_part_adapters import (
    calculate_door_finished_size,
    derive_door_layout_cells,
    door_layout_part_key,
)


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
_DOOR_RE = re.compile(r"^door_c(?P<column>\d+)_r(?P<row>\d+)$")
_FRAME_RE = re.compile(r"^inner_door:(?P<door>[^:]+):(?P<side>top|bottom|left|right)_frame$")
_PANEL_RE = re.compile(r"^inner_door:(?P<door>[^:]+):panel$")


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


def _door_cell_center(snapshot: Mapping[str, object], cell, columns) -> tuple[float, float]:
    total_w, total_h = _dimensions(snapshot, columns)
    x_before = sum(float(columns[index][0]) for index in range(cell.column_index))
    y_before = sum(float(v) for v in columns[cell.column_index][1][:cell.row_index])
    return (
        -total_w / 2.0 + x_before + float(cell.start_width) / 2.0,
        total_h / 2.0 - y_before - float(cell.start_height) / 2.0,
    )


def _door_cell_from_part_key(snapshot: Mapping[str, object], stable_id: str):
    match = _DOOR_RE.fullmatch(str(stable_id or ""))
    if match is None:
        raise ValueError(f"not an authoritative Door stable id: {stable_id!r}")
    columns, cells = _topology(snapshot)
    wanted_col = int(match.group("column")) - 1
    wanted_row = int(match.group("row")) - 1
    cell = next(
        (item for item in cells if item.column_index == wanted_col and item.row_index == wanted_row),
        None,
    )
    if cell is None:
        raise ValueError(f"Door stable id outside authoritative topology: {stable_id!r}")
    return columns, cell


def _receiving_coordinate_contract(snapshot: Mapping[str, object]) -> dict[str, object]:
    from .cabinet_types import policy as cabinet_family_policy

    contract = cabinet_family_policy.assembly_coordinate_contract(
        snapshot,
        depth=float(snapshot.get("d", 0.0)),
        thickness=float(snapshot.get("t", 0.0)),
    )
    if contract is None:
        raise ValueError("cabinet family has no authoritative assembly coordinate contract")
    if str(contract.get("front_axis") or "").upper() != "Z":
        raise ValueError("unsupported authoritative front axis")
    return contract


def _outer_door_plane(snapshot: Mapping[str, object]) -> float:
    contract = _receiving_coordinate_contract(snapshot)
    return float(contract["outer_door_plane"])


def resolve_outer_door_placement(snapshot: Mapping[str, object], stable_id: str) -> AssemblyPlacement:
    """Resolve a formal Door cell from topology plus the family front datum."""
    columns, cell = _door_cell_from_part_key(snapshot, stable_id)
    x, y = _door_cell_center(snapshot, cell, columns)
    z = _outer_door_plane(snapshot)
    position = (float(x), float(y), float(z))
    return AssemblyPlacement(
        stable_id=str(stable_id),
        parent_assembly_node="box_body",
        anchor=f"door_layout_cell:{cell.column_index}:{cell.row_index}",
        world_offset=position,
        rotation=(0.0, 0.0, 0.0),
        mate_target="box_body:front_opening",
        relationship="OUTER_DOOR",
        placement_kind="receiving_outer_door",
        semantic_position=position,
    )


def _inner_door_item(snapshot: Mapping[str, object], inner_door_id: str) -> dict[str, object]:
    wanted = str(inner_door_id or "").strip()
    for raw in tuple(snapshot.get("inner_doors") or ()):
        if isinstance(raw, Mapping) and str(raw.get("stable_id") or "").strip() == wanted:
            return dict(raw)
    raise ValueError(f"inner door stable id is missing from authoritative state: {wanted!r}")


def _cell_from_cell_key(snapshot: Mapping[str, object], cell_key: str):
    match = re.fullmatch(r"(\d+):(\d+)", str(cell_key or "").strip())
    if match is None:
        raise ValueError(f"invalid authoritative inner-door cell_key: {cell_key!r}")
    columns, cells = _topology(snapshot)
    col, row = int(match.group(1)), int(match.group(2))
    cell = next((item for item in cells if item.column_index == col and item.row_index == row), None)
    if cell is None:
        raise ValueError(f"inner-door cell outside authoritative Door topology: {cell_key!r}")
    return columns, cell


def _inner_door_geometry(snapshot: Mapping[str, object], inner_door_id: str) -> dict[str, object]:
    from .cabinet_types import policy as cabinet_family_policy

    item = _inner_door_item(snapshot, inner_door_id)
    columns, cell = _cell_from_cell_key(snapshot, str(item.get("cell_key") or ""))
    outer_key = door_layout_part_key(cell)
    outer = resolve_outer_door_placement(snapshot, outer_key)
    insets = cabinet_family_policy.inner_door_insets(snapshot)
    if insets is None:
        raise ValueError("cabinet family has no authoritative inner-door inset contract")
    left = float(insets.get("left", 0.0))
    right = float(insets.get("right", 0.0))
    top = float(insets.get("top", 0.0))
    bottom = float(insets.get("bottom", 0.0))
    t = float(snapshot.get("t", 0.0))
    fw = float(snapshot.get("fw", 0.0))
    gap_w = float(snapshot.get("door_gap_w", 3.5))
    gap_h = float(snapshot.get("door_gap_h", 3.5))
    outer_w, outer_h = calculate_door_finished_size(
        w=cell.start_width, h=cell.start_height, t=t, fw=fw,
        gap_w=gap_w, gap_h=gap_h, frame_edges=cell.edges,
    )
    panel_w = float(outer_w) - left - right
    panel_h = float(outer_h) - top - bottom
    if panel_w <= 0 or panel_h <= 0:
        raise ValueError("inner-door insets leave no valid authoritative panel area")
    center_x = float(outer.world_offset[0]) + (left - right) / 2.0
    center_y = float(outer.world_offset[1]) + (bottom - top) / 2.0
    center_z = float(outer.world_offset[2])
    return {
        "item": item,
        "outer_key": outer_key,
        "outer": outer,
        "panel_center": (center_x, center_y, center_z),
        "panel_width": panel_w,
        "panel_height": panel_h,
    }


def resolve_inner_door_panel_placement(snapshot: Mapping[str, object], inner_door_id: str) -> AssemblyPlacement:
    geometry = _inner_door_geometry(snapshot, inner_door_id)
    position = tuple(float(v) for v in geometry["panel_center"])
    outer_key = str(geometry["outer_key"])
    stable_id = f"inner_door:{str(inner_door_id).strip()}:panel"
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body:door_layout:inner_door",
        anchor=f"outer_door:{outer_key}",
        world_offset=position,
        rotation=(0.0, 0.0, 0.0),
        mate_target=outer_key,
        relationship="INNER_DOOR_PANEL",
        placement_kind="inner_door_panel",
        semantic_position=position,
    )


def resolve_inner_door_frame_placement(
    snapshot: Mapping[str, object], inner_door_id: str, side: str
) -> AssemblyPlacement:
    side = str(side or "").strip().lower()
    if side == "bottom":
        return resolve_inner_door_lower_frame_placement(snapshot, inner_door_id)
    if side not in {"top", "left", "right"}:
        raise ValueError(f"unsupported inner-door frame side: {side!r}")
    geometry = _inner_door_geometry(snapshot, inner_door_id)
    cx, cy, cz = (float(v) for v in geometry["panel_center"])
    panel_w = float(geometry["panel_width"])
    panel_h = float(geometry["panel_height"])
    if side == "top":
        position = (cx, cy + panel_h / 2.0, cz)
    elif side == "left":
        position = (cx - panel_w / 2.0, cy, cz)
    else:
        position = (cx + panel_w / 2.0, cy, cz)
    stable_id = f"inner_door:{str(inner_door_id).strip()}:{side}_frame"
    outer_key = str(geometry["outer_key"])
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body:door_layout:inner_door",
        anchor=f"inner_door_panel:{inner_door_id}:{side}",
        world_offset=tuple(float(v) for v in position),
        rotation=(0.0, 0.0, 0.0),
        mate_target=outer_key,
        relationship="INNER_DOOR_FRAME",
        placement_kind=f"inner_door_frame_{side}",
        semantic_position=tuple(float(v) for v in position),
    )


def _divider_position(snapshot: Mapping[str, object], axis: str, boundary: str):
    columns, cells = _topology(snapshot)
    total_w, total_h = _dimensions(snapshot, columns)

    if axis == "VERTICAL":
        match = re.fullmatch(r"C(\d+)\|C(\d+)", boundary)
        if match is None:
            raise ValueError(f"invalid authoritative divider topology for vertical divider boundary: {boundary}")
        left_col, right_col = (int(match.group(1)), int(match.group(2)))
        if right_col != left_col + 1:
            raise ValueError(f"non-adjacent vertical divider boundary: {boundary}")
        if not (0 <= left_col < len(columns) and right_col < len(columns)):
            raise ValueError(f"vertical divider boundary outside Door topology: {boundary}")
        # Stable IDs are zero-based column topology identities (C0|C1, C1|C2,
        # ...).  The physical boundary is the right edge of the left column,
        # not the right edge of the right column.  Using ``[:right_col]`` here
        # placed every divider one whole column too far right and made the 3D
        # part appear to jump as the adjacent column widths changed.
        x = -total_w / 2.0 + sum(width for width, _ in columns[:left_col + 1])
        return (x, 0.0, 0.0)

    match = re.fullmatch(r"C(\d+)[:_]R(\d+)\|R(\d+)", boundary)
    if match is None:
        raise ValueError(f"invalid authoritative divider topology for horizontal divider boundary: {boundary}")
    col, upper_row, lower_row = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if not (0 <= col < len(columns)):
        raise ValueError(f"horizontal divider column outside Door topology: {boundary}")
    column_cells = [cell for cell in cells if cell.column_index == col]
    if not any(cell.row_index == upper_row for cell in column_cells):
        raise ValueError(f"horizontal divider upper cell outside Door topology: {boundary}")
    if not any(cell.row_index == lower_row for cell in column_cells):
        raise ValueError(f"horizontal divider lower cell outside Door topology: {boundary}")
    if lower_row != upper_row + 1:
        raise ValueError(f"non-adjacent horizontal divider boundary: {boundary}")
    y = total_h / 2.0 - sum(columns[col][1][:upper_row + 1])
    col_left = -total_w / 2.0 + sum(width for width, _ in columns[:col])
    x = col_left + columns[col][0] / 2.0
    return (x, y, 0.0)


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
    divider_placement = resolve_divider_placement(snapshot, role.divider_stable_id)
    stable_id = f"inner_door:{str(inner_door_id).strip()}:bottom_frame"
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body:door_layout:inner_door",
        anchor=f"shared_divider:{role.divider_stable_id}",
        world_offset=divider_placement.world_offset,
        rotation=(0.0, 0.0, 0.0),
        mate_target=role.divider_stable_id,
        relationship="SHARED_LOWER_FRAME",
        placement_kind="inner_door_shared_divider",
        semantic_position=divider_placement.semantic_position,
    )


def resolve_assembly_placement(snapshot: Mapping[str, object], stable_id: str) -> AssemblyPlacement:
    """Resolve supported authoritative assembly placements; never origin-fallback."""
    key = str(stable_id or "").strip()
    if _DOOR_RE.fullmatch(key):
        return resolve_outer_door_placement(snapshot, key)
    if _DIVIDER_RE.fullmatch(key):
        return resolve_divider_placement(snapshot, key)
    panel = _PANEL_RE.fullmatch(key)
    if panel:
        return resolve_inner_door_panel_placement(snapshot, panel.group("door"))
    frame = _FRAME_RE.fullmatch(key)
    if frame:
        return resolve_inner_door_frame_placement(snapshot, frame.group("door"), frame.group("side"))
    raise ValueError(f"no authoritative placement contract for stable id: {key!r}")
