# -*- coding: utf-8 -*-
"""Pure derived-part identity and topology projection for Fold Designer.

This module owns bridge-independent projection only.  It must not import Tk,
GUI/application owners, or fold_designer_bridge.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    calculate_door_finished_size,
    derive_door_layout_cells,
    door_layout_part_key,
)
from phase6_fold_profiles import _num, clone_profile
from phase6_part_navigation import (
    box_body_piece_keys as _dm7_box_body_piece_keys,
    is_box_body_physical_piece_key as _dm7_is_box_body_physical_piece_key,
    operator_part_selector_keys as _dm7_operator_part_selector_keys,
    project_hierarchy as _dm7_project_hierarchy,
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


def _phase6_door_part_projections(
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
        snapshot, frame_width=fw, thickness=t,
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
        rows.append(DoorPartProjection(
            part_key=door_layout_part_key(cell),
            column_index=cell.column_index,
            row_index=cell.row_index,
            start_width=float(cell.start_width),
            start_height=float(cell.start_height),
            frame_edges=cell.edges,
            formed_width=float(formed_w),
            formed_height=float(formed_h),
        ))
    return tuple(rows)


def _phase6_is_box_body_physical_piece_key(value) -> bool:
    """Compatibility adapter to the single DM7 navigation identity owner."""
    return _dm7_is_box_body_physical_piece_key(value)


def _phase6_is_side_back_editable_piece_key(value) -> bool:
    """Only side/back-split physical children own editable piece Fold profiles."""
    return str(value or "") in {
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
    }


def _phase6_operator_part_selector_keys(values) -> tuple[str, ...]:
    """Compatibility adapter to the common DM7 hierarchy projection."""
    return _dm7_operator_part_selector_keys(values)


def _phase6_box_body_piece_keys(values) -> tuple[str, ...]:
    """Compatibility adapter to authoritative child identity classification."""
    return _dm7_box_body_piece_keys(values)


def _phase6_structure_tree_rows(values) -> tuple[tuple[str, str | None], ...]:
    """Compatibility adapter to the common DM7 hierarchy projection."""
    return tuple((row.part_key, row.parent_key) for row in _dm7_project_hierarchy(values))


def _phase6_reverse_fold_traversal(rows):
    """Reverse a fold chain while moving bend ownership to the same boundary."""
    source = clone_profile(tuple(rows or ()))
    result = []
    total = len(source)
    for index, source_row in enumerate(reversed(source)):
        row = {k: v for k, v in source_row.items() if k != "angle"}
        owner_index = total - 2 - index
        if owner_index >= 0 and "angle" in source[owner_index]:
            row["angle"] = float(source[owner_index]["angle"])
        result.append(row)
    if result:
        result[-1].pop("angle", None)
    return result


def _phase6_box_body_piece_part_profiles(
    render_data, snapshot=None
) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Project manufacturing pieces into operator-facing physical-child profiles."""
    source_snapshot = dict(snapshot or {})
    result = {}
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "").strip()
        if not role:
            continue
        key = f"box_body:{role}"
        rows = [
            {
                "len": float(row.length),
                **({"angle": float(row.angle)} if row.angle is not None else {}),
                **({"core": row.core} if getattr(row, "core", None) else {}),
                "phase6_key": str(getattr(row, "phase6_key", "") or ""),
            }
            for row in tuple(getattr(piece, "fold_profile", ()) or ())
        ]
        if role == "right_side":
            rows = _phase6_reverse_fold_traversal(rows)
        if role == "left_side" and float(source_snapshot.get("zl1", 0.0) or 0.0) < 0.0:
            for row in rows:
                if str(row.get("phase6_key") or "") == "zl1":
                    row["phase6_ui_sign"] = -1.0
                    break
        result[key] = {
            "X": rows,
            "Y": [{
                "len": float(piece.material_dimensions[1]),
                "phase6_key": "box_body_piece_height",
            }],
        }
    return result


def _phase6_is_door_part_key(value) -> bool:
    key = str(value or "")
    return key == "door" or re.fullmatch(r"door_c\d+_r\d+", key) is not None


def _phase6_is_base_plate_part_key(value) -> bool:
    key = str(value or "")
    return key == "base_plate" or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
