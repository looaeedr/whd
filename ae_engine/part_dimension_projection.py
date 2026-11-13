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
from .door_layout_feature_projection import project_operator_saved_door_layout_columns
from .operator_settings_transactions import (
    normalize_operator_settings_boolean, normalize_operator_source_dimension,
)
from .sheetmetal_part_adapters import (
    DoorFrameEdges,
    calculate_door_finished_size,
    derive_door_layout_cells,
    door_layout_part_key,
)

def _source_door_gap(source: Mapping[str, object], field: str) -> float:
    """Use the same finite signed Gap contract as a real Door PartSpec."""
    from .door_operator_part_spec import _finite_operator_number
    return _finite_operator_number(
        source[field] if field in source else 3.5, field,
    )


def _source_base_plate_shrink(source: Mapping[str, object], edge: str) -> float:
    """Reuse the original BasePlate PartSpec/Settings signed numeric gate."""
    from .operator_auxiliary_part_specs import _finite_auxiliary_setting
    key = f"base_plate_shrink_{edge}"
    return _finite_auxiliary_setting(
        {key: source[key] if key in source else 55.0}, key,
    )


def _source_physical_dimension(source: Mapping[str, object], field: str, legacy_default: float) -> float:
    """Trust the original Engine W/H/D/T/FW contract, not float(True).

    The old Settings preview can omit a field and use its historical visual
    default. An explicitly authored invalid physical value is never absence
    and may not be rewritten to a plausible manufacturing dimension.
    """
    return normalize_operator_source_dimension(
        source[field] if field in source else legacy_default,
        field=field,
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
    # This same Engine API feeds GUI part dimensions AND confirmed Receiving
    # Door manufacturing. An authored saved "false" is not a physical enable,
    # and raw True must never be coerced into a 1 mm Door cell via float().
    if not normalize_operator_settings_boolean(
        snapshot.get("multi_door_enabled", False),
    ):
        return ()
    normalized = project_operator_saved_door_layout_columns(
        snapshot.get("door_layout_columns"),
    )
    if not normalized:
        return ()
    t = _source_physical_dimension(snapshot, "t", 2.0)
    fw = _source_physical_dimension(snapshot, "fw", 25.0)
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        snapshot,
        frame_width=fw,
        thickness=t,
    )
    gap_w = _source_door_gap(snapshot, "door_gap_w")
    gap_h = _source_door_gap(snapshot, "door_gap_h")
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
    w = _source_physical_dimension(snapshot, "w", 500.0)
    h = _source_physical_dimension(snapshot, "h", 600.0)
    d = _source_physical_dimension(snapshot, "d", 200.0)
    t = _source_physical_dimension(snapshot, "t", 2.0)
    fw = _source_physical_dimension(snapshot, "fw", 25.0)
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
            gap_w=_source_door_gap(snapshot, "door_gap_w"),
            gap_h=_source_door_gap(snapshot, "door_gap_h"),
            frame_edges=DoorFrameEdges(),
        )
        dims["door"] = {
            "width": max(1.0, float(door_w)),
            "height": max(1.0, float(door_h)),
        }

    shrink_left = _source_base_plate_shrink(snapshot, "left")
    shrink_right = _source_base_plate_shrink(snapshot, "right")
    shrink_top = _source_base_plate_shrink(snapshot, "top")
    shrink_bottom = _source_base_plate_shrink(snapshot, "bottom")
    base_w = max(1.0, w - shrink_left - shrink_right)
    base_h = max(1.0, h - shrink_top - shrink_bottom)
    # The main GUI's part-dimension recalculation is a second caller of the
    # same Engine physical BasePlate policy as Fold Designer Snapshot/PartSpec.
    # The Registry, not a hard-coded family spelling, owns whether Receiving
    # has one source-configured BasePlate rather than Vault per-Door grid plates.
    is_receiving = cabinet_family_policy.canonical_family_name(snapshot) == "受電箱"
    if is_receiving:
        from .receiving_base_plate_config import receiving_base_plate_blank_dimensions
        physical_size = receiving_base_plate_blank_dimensions(snapshot)
        if physical_size is not None:
            base_w, base_h = physical_size
    dims["base_plate"] = {"width": base_w, "height": base_h}

    if door_rows and not is_receiving:
        # BasePlate grid identity is the very same validated Engine Door
        # cell projection; never reinterpret the saved raw W/H a second time.
        for row in door_rows:
            base_key = row.part_key.replace("door_", "base_plate_", 1)
            dims[base_key] = {
                "width": max(1.0, row.start_width - shrink_left - shrink_right),
                "height": max(1.0, row.start_height - shrink_top - shrink_bottom),
            }
    return dims

