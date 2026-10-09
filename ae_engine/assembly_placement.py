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
_BASE_PLATE_RE = re.compile(r"^base_plate_c(?P<column>\d+)_r(?P<row>\d+)$")
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


def _base_plate_cell_from_part_key(snapshot: Mapping[str, object], stable_id: str):
    match = _BASE_PLATE_RE.fullmatch(str(stable_id or ""))
    if match is None:
        raise ValueError(f"not an authoritative Base Plate stable id: {stable_id!r}")
    door_id = f"door_c{match.group('column')}_r{match.group('row')}"
    return _door_cell_from_part_key(snapshot, door_id)


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


def _base_plate_center_plane(snapshot: Mapping[str, object]) -> float:
    """Return the Base Plate folded-envelope center on the rear inner datum.

    Base Plate is a vertical mounting tray. Its flat mounting face mates to the
    inner rear BoxBody skin and its edge bends project toward the cabinet front.
    Assembly geometry recenters the folded local Z envelope before placement, so
    the world offset is the rear-inner plane plus half the bend depth.
    """
    data = dict(snapshot or {})
    depth = float(data.get("d", 0.0))
    thickness = float(data.get("t", 0.0))
    bend = float(data.get("base_plate_bend", 20.0))
    if depth <= 0.0 or thickness <= 0.0 or bend < 0.0:
        raise ValueError("Base Plate placement requires valid D/T/bend")
    rear_inner_plane = -depth / 2.0 + thickness
    return rear_inner_plane + bend / 2.0


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


def resolve_base_plate_placement(snapshot: Mapping[str, object], stable_id: str) -> AssemblyPlacement:
    """Resolve one Base Plate from its authoritative owning datum.

    A topology-derived Base Plate is centered on its owning Door cell. The
    legacy single base_plate is the same contract with one whole-cabinet owning
    cell. Both keep vertical local orientation, while the folded mounting tray
    mates to the inner rear BoxBody plane instead of floating at cabinet Z=0.
    Neither may reintroduce the historical whole-box -H/2 renderer shift.
    """
    stable_id = str(stable_id or "").strip()
    if stable_id == "base_plate":
        position = (0.0, 0.0, _base_plate_center_plane(snapshot))
        return AssemblyPlacement(
            stable_id=stable_id,
            parent_assembly_node="box_body",
            anchor="box_body:center:base_plate",
            world_offset=position,
            rotation=(0.0, 0.0, 0.0),
            mate_target="box_body:base_plate_plane",
            relationship="BASE_PLATE",
            placement_kind="base_plate",
            semantic_position=position,
        )

    columns, cell = _base_plate_cell_from_part_key(snapshot, stable_id)
    x, y = _door_cell_center(snapshot, cell, columns)
    position = (float(x), float(y), _base_plate_center_plane(snapshot))
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body",
        anchor=f"door_layout_cell:{cell.column_index}:{cell.row_index}:base_plate",
        world_offset=position,
        rotation=(0.0, 0.0, 0.0),
        mate_target="box_body:base_plate_plane",
        relationship="BASE_PLATE",
        placement_kind="receiving_base_plate",
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
    """Inner-door opening from physical inner frames, never outer Door width.

    The outer Door remains a legitimate *depth* datum for the configurable
    80-mm inward offset. It is NOT the source of frame X/Y placement, opening
    width, nor finished inner-door dimensions.
    """
    from .cabinet_types import policy as cabinet_family_policy
    from .inner_door_frames import inner_door_frame_formed_occupation

    item = _inner_door_item(snapshot, inner_door_id)
    columns, cell = _cell_from_cell_key(snapshot, str(item.get("cell_key") or ""))
    outer_key = door_layout_part_key(cell)
    outer = resolve_outer_door_placement(snapshot, outer_key)
    t = float(snapshot.get("t", 0.0))
    frame_occupation = inner_door_frame_formed_occupation(t)
    gap_w = float(snapshot.get("door_gap_w", 3.5))
    gap_h = float(snapshot.get("door_gap_h", 3.5))

    aperture_width = float(cell.start_width) - 2.0 * frame_occupation
    panel_w = aperture_width - 2.0 * gap_w
    if panel_w <= 0:
        raise ValueError("inner-door framed width/door clearance is not positive")
    x_center, y_cell_center = _door_cell_center(snapshot, cell, columns)
    try:
        vertical = cabinet_family_policy.inner_door_vertical_frame_contract(
            snapshot, inner_door_id
        )
    except ValueError:
        # During topology editing no shared lower Divider may yet exist.
        # Keep only a transient panel envelope; physical vertical frame
        # manufacturing will fail closed until the Divider is resolved.
        upper_edge = y_cell_center + float(cell.start_height) / 2.0 - frame_occupation
        lower_edge = y_cell_center - float(cell.start_height) / 2.0
    else:
        upper_edge = float(vertical["top_terminal_y"])
        lower_edge = float(vertical["lower_terminal_y"])
    panel_h = (upper_edge - lower_edge) - 2.0 * gap_h
    if panel_h <= 0:
        raise ValueError("inner-door framed height/door clearance is not positive")

    contract = _receiving_coordinate_contract(snapshot)
    inward = tuple(float(v) for v in contract.get("inward_vector", ()))
    if len(inward) != 3:
        raise ValueError("authoritative inward vector must have three components")
    inward_offset = float(item.get(
        "inward_offset_mm",
        cabinet_family_policy.default_inner_door_inward_offset_mm(snapshot, default=0.0)
    ))
    if inward_offset < 0:
        raise ValueError("inner-door inward offset must be >= 0")
    center = (
        float(x_center) + inward[0] * inward_offset,
        (upper_edge + lower_edge) / 2.0 + inward[1] * inward_offset,
        float(outer.world_offset[2]) + inward[2] * inward_offset,
    )
    return {
        "item": item,
        "outer_key": outer_key,
        "outer": outer,
        "panel_center": center,
        "panel_width": panel_w,
        "panel_height": panel_h,
        "upper_frame_edge": upper_edge,
        "lower_frame_edge": lower_edge,
        "frame_occupation": frame_occupation,
        "inward_offset_mm": inward_offset,
        "cell": cell,
    }


def resolve_inner_door_panel_placement(snapshot: Mapping[str, object], inner_door_id: str) -> AssemblyPlacement:
    geometry = _inner_door_geometry(snapshot, inner_door_id)
    position = tuple(float(v) for v in geometry["panel_center"])
    stable_id = f"inner_door:{str(inner_door_id).strip()}:panel"
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body:door_layout:inner_door",
        anchor=f"inner_door_frame_opening:{inner_door_id}",
        world_offset=position,
        rotation=(0.0, 0.0, 0.0),
        mate_target=f"inner_door:{inner_door_id}:frame_opening",
        relationship="INNER_DOOR_PANEL",
        placement_kind="inner_door_panel",
        semantic_position=position,
    )


def resolve_inner_door_frame_placement(
    snapshot: Mapping[str, object], inner_door_id: str, side: str
) -> AssemblyPlacement:
    """Mate the last 22-mm folded flange to the corresponding mother plate.

    The frame's common 46+2T outside occupation is NOT a 50-mm outer Door
    inset. Frame offset compensates the last signed-fold segment's *actual*
    folded-envelope coordinate (which differs for the asymmetric left frame).
    Left U is reversed in place_assembly_points, while top U points +Y;
    right U points +X. Thus the last flange points OUT of the opening and
    its physical outside skin mates the Box Body/Head inside skin.
    """
    from .cabinet_types import policy as cabinet_family_policy
    from .inner_door_frames import derive_inner_door_frames
    from .assembly_geometry import folded_profile_segment_center_from_full_envelope

    side = str(side or "").strip().lower()
    if side == "bottom":
        return resolve_inner_door_lower_frame_placement(snapshot, inner_door_id)
    if side not in {"top", "left", "right"}:
        raise ValueError(f"unsupported inner-door frame side: {side!r}")
    geometry = _inner_door_geometry(snapshot, inner_door_id)
    cx, _cy, cz = (float(v) for v in geometry["panel_center"])
    t = float(snapshot.get("t", 0.0))
    w = float(snapshot.get("w", 0.0))
    h = float(snapshot.get("h", 0.0))
    if w <= 2.0 * t or h <= 2.0 * t:
        raise ValueError("frame-to-Box Body placement requires valid W/H/T")
    part = derive_inner_door_frames(
        inner_door_id, spans={side: 1.0}, thickness=t,
        included_sides=(side,),
    )[0]
    # Final 22-mm flange is at a constant folded U on each part. Use the
    # same folded *full-envelope* center as the assembly mesh transform.
    last_u, _last_depth = folded_profile_segment_center_from_full_envelope(
        part.fold_profile, len(part.fold_profile) - 1
    )
    physical_skin = last_u + t / 2.0
    if side == "top":
        # Head EndCap inside skin: physical upper Box Body bound H/2-T.
        # The top frame's U points +Y, not -Y.
        head_inner_y = h / 2.0 - t
        position = (cx, head_inner_y - physical_skin, cz)
        target = "head"
    else:
        vertical = cabinet_family_policy.inner_door_vertical_frame_contract(
            snapshot, inner_door_id
        )
        frame_center_y = float(vertical["center_y"])
        # Box Body side physical midplanes at ±(W-2T)/2; their inside
        # skins are another T/2 toward the opening.
        side_inner = w / 2.0 - 1.5 * t
        if side == "left":
            # Last flange local +U maps to cabinet -X.
            position = (-side_inner + physical_skin, frame_center_y, cz)
            target = "box_body:left_side"
        else:
            position = (side_inner - physical_skin, frame_center_y, cz)
            target = "box_body:right_side"
    stable_id = f"inner_door:{str(inner_door_id).strip()}:{side}_frame"
    world = tuple(float(v) for v in position)
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body:door_layout:inner_door",
        anchor=f"{target}:inside_skin:last_22_mm_flange",
        world_offset=world,
        rotation=(0.0, 0.0, 0.0),
        mate_target=target,
        relationship="INNER_DOOR_FRAME",
        placement_kind=f"inner_door_frame_{side}",
        semantic_position=world,
    )


def _divider_fw_face_flush_contract(
    snapshot: Mapping[str, object], stable_id: str
) -> tuple[float, float]:
    """Return (world_depth_offset, local_axis_to_world_z_sign) for Divider FW mating.

    Receiving's actual Divider Fold Profile decides where the FW band and core
    lie.  The family inward vector decides which direction the core must extend
    after the FW band is mated to the Box Body front FW face.  This derives both
    translation and orientation from geometry instead of a world-Z constant.
    Families without an explicit Divider FW segment contract keep the legacy
    +local-axis placement with zero depth offset.
    """
    from .assembly_geometry import folded_profile_segment_center_from_envelope
    from .cabinet_types import policy as cabinet_family_policy
    from .door_dividers import derive_box_body_dividers

    depth = float(snapshot.get("d", 0.0))
    thickness = float(snapshot.get("t", 0.0))
    frame_width = snapshot.get("fw")

    # Probe family capability before deriving a physical Divider.  Generic
    # snapshots intentionally omit D/T and must retain their historical path.
    capability = cabinet_family_policy.divider_fold_contract(
        snapshot, depth=depth, thickness=thickness, handle_side=False,
        frame_width=(None if frame_width is None else float(frame_width)),
    )
    if capability is None or capability.get("frame_width_segment_index") is None:
        return 0.0, 1.0

    columns, _cells = _topology(snapshot)
    dividers = derive_box_body_dividers(
        columns,
        depth=depth,
        thickness=thickness,
        frame_width=(None if frame_width is None else float(frame_width)),
        layout_scope=str(snapshot.get("door_layout_scope") or "main").strip() or "main",
        handle_edges=dict(snapshot.get("door_handle_edges") or {}),
        model_name=str(snapshot.get("model") or snapshot.get("cabinet_type") or "").strip() or None,
    )
    divider = next((item for item in dividers if str(item.stable_id) == str(stable_id)), None)
    if divider is None:
        raise ValueError(f"divider stable id outside authoritative topology: {stable_id!r}")

    fold_contract = cabinet_family_policy.divider_fold_contract(
        snapshot, depth=depth, thickness=thickness,
        handle_side=bool(divider.handle_side),
        frame_width=(None if frame_width is None else float(frame_width)),
    )
    if fold_contract is None or fold_contract.get("frame_width_segment_index") is None:
        raise ValueError("Divider lost its family FW segment contract")

    fw_index = int(fold_contract["frame_width_segment_index"])
    core_index = int(fold_contract["core_segment_index"])
    fw_axis, _ = folded_profile_segment_center_from_envelope(divider.fold_profile, fw_index)
    core_axis, _ = folded_profile_segment_center_from_envelope(divider.fold_profile, core_index)
    local_core_delta = float(core_axis - fw_axis)
    if abs(local_core_delta) <= 1e-9:
        raise ValueError("Divider FW/core folded axes do not define an inward direction")

    coordinate = cabinet_family_policy.assembly_coordinate_contract(
        snapshot, depth=depth, thickness=thickness
    )
    if coordinate is None:
        raise ValueError("Divider FW face-flush contract requires a family assembly coordinate contract")
    if str(coordinate.get("front_axis") or "").upper() != "Z":
        raise ValueError("Divider FW face-flush currently requires a Z front axis")
    inward = tuple(float(v) for v in coordinate.get("inward_vector", (0.0, 0.0, 0.0)))
    if len(inward) != 3 or abs(inward[2]) != 1.0:
        raise ValueError("Divider FW face-flush requires a unit Z inward vector")

    # Choose the local-axis mapping so moving from FW toward the core follows
    # the family's physical inward direction.
    local_delta_sign = 1.0 if local_core_delta > 0.0 else -1.0
    axis_to_world_z_sign = float(inward[2] / local_delta_sign)

    outward_sign = float(coordinate.get("outward_sign", 0.0))
    if abs(outward_sign) != 1.0:
        raise ValueError("family outward_sign must be +1 or -1")
    body_front_skin = float(coordinate["body_front_skin"])
    body_fw_midplane = body_front_skin - outward_sign * thickness / 2.0
    world_fw_relative = axis_to_world_z_sign * float(fw_axis)
    return float(body_fw_midplane - world_fw_relative), axis_to_world_z_sign

def _divider_position(snapshot: Mapping[str, object], stable_id: str, axis: str, boundary: str, depth_offset: float):
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
        z = float(depth_offset)
        return (x, 0.0, z)

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
    z = float(depth_offset)
    return (x, y, z)


def resolve_divider_placement(snapshot: Mapping[str, object], stable_id: str) -> AssemblyPlacement:
    """Resolve one divider's placement from authoritative Door topology."""
    stable_id = str(stable_id or "").strip()
    match = _DIVIDER_RE.fullmatch(stable_id)
    if match is None:
        raise ValueError(f"not an authoritative Box Body divider stable id: {stable_id!r}")
    axis = match.group("axis")
    boundary = match.group("boundary")
    depth_offset, depth_axis_sign = _divider_fw_face_flush_contract(snapshot, stable_id)
    position = _divider_position(snapshot, stable_id, axis, boundary, depth_offset)
    if axis == "VERTICAL":
        placement_kind = "divider_vertical_inward" if depth_axis_sign < 0.0 else "divider_vertical"
    else:
        placement_kind = "divider_horizontal_inward" if depth_axis_sign < 0.0 else "divider_horizontal"
    return AssemblyPlacement(
        stable_id=stable_id,
        parent_assembly_node="box_body",
        anchor=f"door_layout_boundary:{boundary}",
        world_offset=position,
        rotation=(0.0, 0.0, 0.0),
        mate_target="box_body:door_layout",
        relationship="SHARED_STRUCTURAL_DIVIDER",
        placement_kind=placement_kind,
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
    if key == "base_plate" or _BASE_PLATE_RE.fullmatch(key):
        return resolve_base_plate_placement(snapshot, key)
    if _DIVIDER_RE.fullmatch(key):
        return resolve_divider_placement(snapshot, key)
    panel = _PANEL_RE.fullmatch(key)
    if panel:
        return resolve_inner_door_panel_placement(snapshot, panel.group("door"))
    frame = _FRAME_RE.fullmatch(key)
    if frame:
        return resolve_inner_door_frame_placement(snapshot, frame.group("door"), frame.group("side"))
    raise ValueError(f"no authoritative placement contract for stable id: {key!r}")
