# -*- coding: utf-8 -*-
"""Canonical box-body divider physical parts derived from Door layout topology.

Door layout remains the authoritative source of *where* internal boundaries
exist.  This module turns those boundaries into stable physical parts without
inventing a second partition algorithm.  Divider identity is topological, so
ratio-only geometry changes do not rename parts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .contracts import FoldProfileSegment
from .sheetmetal_part_adapters import derive_door_layout_cells


_AXES = ("VERTICAL", "HORIZONTAL")
_HANDLE_EDGES = {"LEFT", "RIGHT", "TOP", "BOTTOM"}


def _scope_token(value: object) -> str:
    token = str(value or "").strip().replace(":", "-")
    if not token:
        raise ValueError("layout_scope must be a stable non-empty identifier")
    return token


def _handle_edge(value: object) -> str | None:
    if value is None:
        return None
    token = str(value).strip().upper()
    aliases = {"左": "LEFT", "右": "RIGHT", "上": "TOP", "下": "BOTTOM"}
    token = aliases.get(token, token)
    if token not in _HANDLE_EDGES:
        raise ValueError(f"unsupported door handle edge: {value!r}")
    return token


def divider_stable_id(layout_scope: object, axis: str, boundary_key: str) -> str:
    axis = str(axis or "").upper()
    if axis not in _AXES:
        raise ValueError(f"unsupported divider axis: {axis!r}")
    boundary = str(boundary_key or "").strip().replace(":", "_")
    if not boundary:
        raise ValueError("divider boundary_key must be non-empty")
    return f"box_body:divider:{_scope_token(layout_scope)}:{axis}:{boundary}"


@dataclass(frozen=True)
class BoxBodyDividerPart:
    stable_id: str
    owner: str
    axis: str
    boundary_key: str
    span: float
    thickness: float
    formed_core_depth: float
    handle_side: bool
    signed_fold_chain: tuple[float, ...]
    material_lengths: tuple[float, ...]
    fold_profile: tuple[FoldProfileSegment, ...]
    adjacent_cells: tuple[str, ...]
    model_name: str | None = None
    core_segment_index: int = 3
    frame_width_segment_index: int | None = None

    @property
    def blank_width(self) -> float:
        return float(sum(self.material_lengths))

    @property
    def blank_height(self) -> float:
        return float(self.span)


@dataclass(frozen=True)
class InnerDoorSharedFrameRole:
    inner_door_id: str
    role: str
    divider_stable_id: str


def _material_core_from_formed(*, formed_core: float, thickness: float) -> float:
    """Convert the formed D-core through its actual two-adjacent-bend topology.

    The divider chain has a real bend on both sides of the D-core.  Phase6's
    outside-dimension contract contributes 1T per adjacent real bend, so the
    material segment is formed_core - 2T.  Keeping this conversion isolated
    prevents callers from treating the user's formed `D-2T` as flat material.
    """
    material = float(formed_core) - 2.0 * float(thickness)
    if material <= 0:
        raise ValueError("divider formed D core is too small for two bend compensations")
    return material


def _fold_profile(
    signed_chain: Sequence[float],
    material_lengths: Sequence[float],
    *,
    core_segment_index: int,
) -> tuple[FoldProfileSegment, ...]:
    rows = []
    signed_chain = tuple(float(v) for v in signed_chain)
    material_lengths = tuple(float(v) for v in material_lengths)
    if len(signed_chain) != len(material_lengths):
        raise ValueError("divider signed/material fold chains must have equal length")
    core_segment_index = int(core_segment_index)
    if core_segment_index < 0 or core_segment_index >= len(material_lengths):
        raise ValueError("divider core segment index is outside the fold chain")
    for index, (signed, length) in enumerate(zip(signed_chain, material_lengths)):
        if length <= 0:
            raise ValueError("divider material length must be positive")
        angle = None if index == len(material_lengths) - 1 else (90.0 if signed >= 0 else -90.0)
        rows.append(FoldProfileSegment(
            length=length,
            angle=angle,
            core=("D_DIVIDER" if index == core_segment_index else None),
            phase6_key=f"divider_fold_{index + 1}",
        ))
    return tuple(rows)


def _part(
    *,
    layout_scope,
    axis,
    boundary_key,
    span,
    depth,
    thickness,
    handle_side,
    adjacent_cells,
    model_name=None,
    frame_width=None,
):
    t = float(thickness)
    d = float(depth)
    span = float(span)
    if t <= 0 or d <= 0 or span <= 0:
        raise ValueError("divider depth/thickness/span must be > 0")

    from .cabinet_types import policy as cabinet_family_policy

    family_contract = cabinet_family_policy.divider_fold_contract(
        model_name,
        depth=d,
        thickness=t,
        handle_side=bool(handle_side),
        frame_width=(None if frame_width is None else float(frame_width)),
    )
    if family_contract is not None:
        material = tuple(float(v) for v in family_contract["material_lengths"])
        signed = tuple(float(v) for v in family_contract["signed_fold_chain"])
        formed_core = float(family_contract["formed_core_depth"])
        core_segment_index = int(family_contract["core_segment_index"])
        frame_width_segment_index = (
            None if family_contract.get("frame_width_segment_index") is None
            else int(family_contract["frame_width_segment_index"])
        )
    else:
        formed_core = d - 2.0 * t
        if formed_core <= 0:
            raise ValueError("divider formed D-2T must be > 0")
        first = -15.0 if handle_side else 18.0
        signed = (first, 20.0, 25.0, formed_core, 15.0)
        material = (
            abs(first),
            20.0,
            25.0,
            _material_core_from_formed(formed_core=formed_core, thickness=t),
            15.0,
        )
        core_segment_index = 3
        frame_width_segment_index = None

    return BoxBodyDividerPart(
        stable_id=divider_stable_id(layout_scope, axis, boundary_key),
        owner="box_body",
        axis=axis,
        boundary_key=boundary_key,
        span=span,
        thickness=t,
        formed_core_depth=formed_core,
        handle_side=bool(handle_side),
        signed_fold_chain=signed,
        material_lengths=material,
        fold_profile=_fold_profile(
            signed,
            material,
            core_segment_index=core_segment_index,
        ),
        adjacent_cells=tuple(adjacent_cells),
        model_name=(str(model_name).strip() if model_name else None),
        core_segment_index=int(core_segment_index),
        frame_width_segment_index=frame_width_segment_index,
    )

def derive_box_body_dividers(
    columns,
    *,
    depth: float,
    thickness: float,
    layout_scope: object,
    handle_edges: Mapping[str, object] | None = None,
    model_name: str | None = None,
    frame_width: float | None = None,
) -> tuple[BoxBodyDividerPart, ...]:
    """Derive one physical divider for each canonical internal Door boundary.

    Internal-boundary existence is read from ``derive_door_layout_cells``:
    ``right=False`` marks vertical internal boundaries and ``bottom=False``
    marks per-column horizontal internal boundaries.  No parallel N-1 layout
    algorithm is maintained here.
    """
    normalized_columns = tuple((float(w), tuple(float(h) for h in heights)) for w, heights in columns)
    cells = derive_door_layout_cells(normalized_columns)
    handles = {str(k): _handle_edge(v) for k, v in dict(handle_edges or {}).items()}
    by_col: dict[int, list[object]] = {}
    for cell in cells:
        by_col.setdefault(cell.column_index, []).append(cell)

    result: list[BoxBodyDividerPart] = []

    # Existing cell topology can repeat the same vertical internal edge for
    # each row; collapse those identical topology identities into one full-H
    # structural divider.
    vertical_columns = []
    for cell in cells:
        if not cell.edges.right and cell.column_index not in vertical_columns:
            vertical_columns.append(cell.column_index)
    for col in vertical_columns:
        left_cells = tuple(by_col.get(col, ()))
        right_cells = tuple(by_col.get(col + 1, ()))
        adjacent = tuple(
            [f"{c.column_index}:{c.row_index}" for c in left_cells]
            + [f"{c.column_index}:{c.row_index}" for c in right_cells]
        )
        handle_side = any(handles.get(f"{c.column_index}:{c.row_index}") == "RIGHT" for c in left_cells)
        handle_side = handle_side or any(handles.get(f"{c.column_index}:{c.row_index}") == "LEFT" for c in right_cells)
        span = sum(float(c.start_height) for c in left_cells)
        result.append(_part(
            layout_scope=layout_scope,
            axis="VERTICAL",
            boundary_key=f"C{col}|C{col + 1}",
            span=span,
            depth=depth,
            thickness=thickness,
            handle_side=handle_side,
            adjacent_cells=adjacent,
            model_name=model_name,
            frame_width=frame_width,
        ))

    for cell in cells:
        if cell.edges.bottom:
            continue
        col, row = cell.column_index, cell.row_index
        upper_key = f"{col}:{row}"
        lower_key = f"{col}:{row + 1}"
        handle_side = handles.get(upper_key) == "BOTTOM" or handles.get(lower_key) == "TOP"
        span = float(cell.start_width)
        if getattr(cell.edges, "left", False):
            span -= float(thickness)
        if getattr(cell.edges, "right", False):
            span -= float(thickness)
        result.append(_part(
            layout_scope=layout_scope,
            axis="HORIZONTAL",
            boundary_key=f"C{col}:R{row}|R{row + 1}",
            span=span,
            depth=depth,
            thickness=thickness,
            handle_side=handle_side,
            adjacent_cells=(upper_key, lower_key),
            model_name=model_name,
            frame_width=frame_width,
        ))
    return tuple(result)


def resolve_inner_door_lower_frame_role(
    inner_door_id: object,
    dividers: Sequence[BoxBodyDividerPart],
    *,
    previous_divider_stable_id: str | None = None,
) -> InnerDoorSharedFrameRole | None:
    """Resolve the shared lower-frame role without leaving dangling references.

    A previous stable ID is retained when its topology boundary still exists.
    If it disappeared, automatic rebinding is safe only when exactly one
    horizontal divider remains; otherwise the role is removed instead of
    silently pointing at an adjacent wrong divider.
    """
    door_id = str(inner_door_id or "").strip()
    if not door_id:
        raise ValueError("inner_door_id must be non-empty")
    horizontal = tuple(p for p in tuple(dividers or ()) if p.axis == "HORIZONTAL")
    if previous_divider_stable_id:
        match = next((p for p in horizontal if p.stable_id == str(previous_divider_stable_id)), None)
        if match is not None:
            return InnerDoorSharedFrameRole(door_id, "lower_frame", match.stable_id)
    if len(horizontal) == 1:
        return InnerDoorSharedFrameRole(door_id, "lower_frame", horizontal[0].stable_id)
    return None


def divider_part_profiles(dividers: Sequence[BoxBodyDividerPart]) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Workspace adapter: deterministic fold profiles keyed by stable part ID."""
    result = {}
    for part in tuple(dividers or ()):
        result[part.stable_id] = {
            "X": [
                {
                    "len": row.length,
                    **({"angle": row.angle} if row.angle is not None else {}),
                    **({"core": row.core} if row.core else {}),
                    "phase6_key": row.phase6_key,
                }
                for row in part.fold_profile
            ],
            "Y": [{"len": part.span, "phase6_key": "divider_span"}],
        }
    return result
