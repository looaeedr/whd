# -*- coding: utf-8 -*-
"""Headless Engine-owned finished physical part dimensions and multi-Door projection.

Move-only ownership of existing approved dimension semantics. The Phase6
Settings view must not calculate Family material FW, formed Door dimensions,
Receiving base-plate physical sizes, or derived cell identities itself.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .cabinet_types import policy as cabinet_family_policy
from .box_body_fold_profile import _num
from .sheetmetal_part_adapters import (
    DoorFrameEdges,
    calculate_door_finished_size,
    derive_door_layout_cells,
    door_layout_part_key,
)

@dataclass(frozen=True)
class DoorPartProjection:
    part_key: str
    column_index: int
    row_index: int
    start_width: float
    start_height: float
    frame_edges: DoorFrameEdges
    formed_width: float
    formed_height: float


def door_part_projections(
    snapshot: Mapping[str, object],
) -> tuple[DoorPartProjection, ...]:
    """Project authoritative multi-door cells without duplicating layout formulas."""
    if not bool(snapshot.get("multi_door_enabled", False)):
        return ()
    columns = tuple(snapshot.get("door_layout_columns") or ())
    if not columns:
        return ()
    normalized = tuple(
        (float(row[0]), tuple(float(value) for value in row[1]))
        for row in columns
    )
    t = _num(snapshot.get("t", 2.0), 2.0)
    fw = _num(snapshot.get("fw", 25.0), 25.0)
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        snapshot,
        frame_width=fw,
        thickness=t,
    )
    gap_w = _num(snapshot.get("door_gap_w", 3.5), 3.5)
    gap_h = _num(snapshot.get("door_gap_h", 3.5), 3.5)
    rows = []
    for cell in derive_door_layout_cells(normalized):
        formed_w, formed_h = calculate_door_finished_size(
            w=cell.start_width,
            h=cell.start_height,
            t=t,
            fw=door_material_fw,
            gap_w=gap_w,
            gap_h=gap_h,
            frame_edges=cell.edges,
        )
        rows.append(
            DoorPartProjection(
                part_key=door_layout_part_key(cell),
                column_index=cell.column_index,
                row_index=cell.row_index,
                start_width=float(cell.start_width),
                start_height=float(cell.start_height),
                frame_edges=cell.edges,
                formed_width=float(formed_w),
                formed_height=float(formed_h),
            )
        )
    return tuple(rows)


def project_part_dimensions(snapshot: Mapping[str, object]) -> dict[str, dict[str, float]]:
    """Pure projection of Settings/input state into per-part finished dimensions."""
    snapshot = dict(snapshot or {})
    w = _num(snapshot.get("w", 500), 500)
    h = _num(snapshot.get("h", 600), 600)
    d = _num(snapshot.get("d", 200), 200)
    t = _num(snapshot.get("t", 2), 2)
    fw = _num(snapshot.get("fw", 25), 25)
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        snapshot,
        frame_width=fw,
        thickness=t,
    )
    dims = {
        key: dict(value)
        for key, value in (snapshot.get("part_dimensions") or {}).items()
    }
    dims["box_body"] = {"width": w, "height": h}
    dims["head"] = {"width": w, "height": d}
    dims["tail"] = {"width": w, "height": d}

    for key in tuple(dims):
        if re.fullmatch(r"door_c\d+_r\d+", str(key)) or re.fullmatch(
            r"base_plate_c\d+_r\d+", str(key)
        ):
            dims.pop(key, None)

    door_rows = door_part_projections(snapshot)
    if door_rows:
        dims.pop("door", None)
        for row in door_rows:
            dims[row.part_key] = {
                "width": row.formed_width,
                "height": row.formed_height,
            }
    else:
        door_w, door_h = calculate_door_finished_size(
            w=w,
            h=h,
            t=t,
            fw=door_material_fw,
            gap_w=_num(snapshot.get("door_gap_w", 3.5), 3.5),
            gap_h=_num(snapshot.get("door_gap_h", 3.5), 3.5),
            frame_edges=DoorFrameEdges(),
        )
        dims["door"] = {
            "width": max(1.0, float(door_w)),
            "height": max(1.0, float(door_h)),
        }

    shrink_left = _num(snapshot.get("base_plate_shrink_left", 55), 55)
    shrink_right = _num(snapshot.get("base_plate_shrink_right", 55), 55)
    shrink_top = _num(snapshot.get("base_plate_shrink_top", 55), 55)
    shrink_bottom = _num(snapshot.get("base_plate_shrink_bottom", 55), 55)
    base_w = max(1.0, w - shrink_left - shrink_right)
    base_h = max(1.0, h - shrink_top - shrink_bottom)
    if str(snapshot.get("model") or "").strip() in {"受電箱", "RECEIVING"}:
        from .receiving_base_plate_config import receiving_base_plate_blank_dimensions
        physical_size = receiving_base_plate_blank_dimensions(snapshot)
        if physical_size is not None:
            base_w, base_h = physical_size
    dims["base_plate"] = {"width": base_w, "height": base_h}

    if door_rows and str(snapshot.get("model") or "").strip() not in {"受電箱", "RECEIVING"}:
        columns = tuple(
            (float(row[0]), tuple(float(v) for v in row[1]))
            for row in tuple(snapshot.get("door_layout_columns") or ())
        )
        for cell in derive_door_layout_cells(columns):
            base_key = door_layout_part_key(cell).replace(
                "door_", "base_plate_", 1
            )
            dims[base_key] = {
                "width": max(
                    1.0,
                    float(cell.start_width) - shrink_left - shrink_right,
                ),
                "height": max(
                    1.0,
                    float(cell.start_height) - shrink_top - shrink_bottom,
                ),
            }
    return dims

