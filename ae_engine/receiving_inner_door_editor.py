# -*- coding: utf-8 -*-
"""Engine-owned, headless Receiving inner-door Hole Editor context.

The large cell guide is only a measurement/display frame; the real physical
panel, feature surface, certified CUTTING and BEND stay separate.
"""
from __future__ import annotations
from dataclasses import dataclass

from .cabinet_types import policy as cabinet_family_policy
from .cabinet_types.receiving import DOOR_DEFAULTS, inner_door_panel_vertical_contract
from .inner_door_panels import is_inner_door_panel_part_key
from .sheetmetal_features import RectGuide, Vec2, feature_surface_from_structural_result
from .sheetmetal_part_adapters import (
    DoorFrameEdges, build_door_result, build_finished_reference_guide,
    derive_door_layout_cells,
)


@dataclass(frozen=True)
class InnerDoorHoleEditorContext:
    """Resolved physical sheet and read-only reference frames for a GUI client."""

    panel: object
    structural: object
    feature_surface: object
    local_reference_guide: RectGuide
    work_area_guide: RectGuide
    render: object
    frame_edges: DoorFrameEdges


def resolve_inner_door_hole_editor_context(input_snapshot, part_key: str) -> InnerDoorHoleEditorContext:
    """Reuse Family/Topology/Certified Door authority; never compute in GUI."""
    if not is_inner_door_panel_part_key(part_key):
        raise ValueError("不是可開孔編輯的內門門板")
    snapshot = dict(input_snapshot or {})
    panel = next((
        row for row in cabinet_family_policy.derive_inner_door_panels(snapshot)
        if row.stable_id == part_key
    ), None)
    if panel is None:
        raise ValueError("目前專案沒有這片內門門板")
    cells = derive_door_layout_cells(tuple(snapshot.get("door_layout_columns") or ()))
    cell = next((
        item for item in cells
        if f"{item.column_index}:{item.row_index}" == panel.cell_key
    ), None)
    if cell is None:
        raise ValueError(f"內門 {panel.inner_door_id} 找不到所屬作業區 {panel.cell_key}")

    # Same physical Vault Door engine, with no OUTER Door feature inheritance.
    frame_edges = DoorFrameEdges(left=False, right=False, top=False, bottom=False)
    structural = build_door_result(
        w=panel.width, h=panel.height, t=panel.thickness,
        fw=25.0, gap_w=0.0, gap_h=0.0,
        fold_left=panel.fold_left, fold_right=panel.fold_right,
        fold_top=panel.fold_top, fold_bottom=panel.fold_bottom,
        frame_edges=frame_edges,
    )
    surface = feature_surface_from_structural_result("door", structural)
    local_guide = build_finished_reference_guide(
        "door", structural, finished_width=panel.width,
        finished_height=panel.height,
    )
    vertical = inner_door_panel_vertical_contract(
        cell_height=cell.start_height, thickness=panel.thickness,
        gap_h=float(snapshot.get("door_gap_h", DOOR_DEFAULTS["door_gap_h"])),
    )
    # The top-frame occupation offsets the CELL center from the panel center.
    # This guide is NEVER used for CUTTING or FeatureSurface containment.
    cx = float(structural.width) / 2.0
    cy = float(structural.height) / 2.0 - vertical["center_offset_y"]
    half_w, half_h = float(cell.start_width) / 2.0, float(cell.start_height) / 2.0
    work_guide = RectGuide(
        Vec2(cx - half_w, cy - half_h), Vec2(cx + half_w, cy + half_h),
        "receiving_inner_door_work_area",
    )
    from .manufacturing_scene_orchestration import build_inner_door_panel_render_data
    render = build_inner_door_panel_render_data(panel)
    return InnerDoorHoleEditorContext(
        panel=panel, structural=structural, feature_surface=surface,
        local_reference_guide=local_guide, work_area_guide=work_guide,
        render=render, frame_edges=frame_edges,
    )
