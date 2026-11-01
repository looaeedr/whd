# -*- coding: utf-8 -*-
"""Read-only Door/BasePlate Hole Editor geometry owned by headless Engine."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from . import ae
from .sheetmetal_features import DoorIndicatorContext, feature_surface_from_structural_result
from .sheetmetal_part_adapters import (
    DoorFrameEdges, build_base_plate_result, build_door_result,
    build_finished_reference_guide, build_unknown_base_plate_result,
    build_unknown_door_result,
)


@dataclass(frozen=True)
class OperatorHoleEditorGeometry:
    surface: object
    width: float
    height: float
    reference_guide: object
    baseline_scene: object | None
    baseline_status: str
    door_indicator_context: DoorIndicatorContext | None = None
    door_frame_edges: DoorFrameEdges | None = None


def project_operator_hole_editor_door(
    values: Mapping[str, object], *, material_frame_width: float,
    is_custom: bool = False, corner_policy=None, baseline_model=None,
) -> OperatorHoleEditorGeometry:
    """Existing single Door editor display; canonical export remains separate."""
    v = values
    args = dict(
        w=v["w"], h=v["h"], t=v["t"], fw=material_frame_width,
        gap_w=v["door_gap_w"], gap_h=v["door_gap_h"],
        fold_left=v["door_fold_l"], fold_right=v["door_fold_r"],
        fold_top=v["door_fold_t"], fold_bottom=v["door_fold_b"],
    )
    result = (build_unknown_door_result(**args, corner_policy=corner_policy)
              if is_custom else build_door_result(**args))
    surface = feature_surface_from_structural_result("door", result)
    finished_w, finished_h = ae.calculate_door_finished_size(
        v["w"], v["h"], material_frame_width,
        v["door_gap_w"], v["door_gap_h"], v["t"],
    )
    guide = build_finished_reference_guide(
        "door", result, finished_width=finished_w, finished_height=finished_h,
    )
    scene = None
    status = "未使用基準檔（程式計算生成）"
    if baseline_model and ae.has_baseline_part(baseline_model, "門.dxf"):
        try:
            data = ae.get_stretched_door_data(
                baseline_model, v["w"], v["h"], v["t"], material_frame_width,
                v["door_gap_w"], v["door_gap_h"],
                v["door_fold_l"], v["door_fold_r"],
                v["door_fold_t"], v["door_fold_b"],
                frame_edges=DoorFrameEdges(),
            )
            scene = data.scene
            status = ae.baseline_source_label(baseline_model, "門.dxf")
        except Exception:
            # Previous preview-only fallback; cannot certify manufacture.
            pass
    return OperatorHoleEditorGeometry(
        surface=surface, width=result.width, height=result.height,
        reference_guide=guide, baseline_scene=scene, baseline_status=status,
        door_indicator_context=DoorIndicatorContext(
            finished_width=finished_w, finished_height=finished_h,
            left_fold=v["door_fold_l"], bottom_fold=v["door_fold_b"],
        ),
        door_frame_edges=DoorFrameEdges(),
    )


def project_operator_hole_editor_base_plate(
    values: Mapping[str, object], *, is_custom: bool = False,
    corner_policy=None,
) -> OperatorHoleEditorGeometry:
    """Existing BasePlate editor display; no new DXF permission."""
    v = values
    args = dict(
        w=v["w"], h=v["h"], t=v["t"],
        shrink_top=v["base_plate_shrink_top"],
        shrink_bottom=v["base_plate_shrink_bottom"],
        shrink_left=v["base_plate_shrink_left"],
        shrink_right=v["base_plate_shrink_right"],
        bend=v["base_plate_bend"],
    )
    result = (build_unknown_base_plate_result(**args, corner_policy=corner_policy)
              if is_custom else build_base_plate_result(**args))
    finished_w = v["w"] - v["base_plate_shrink_left"] - v["base_plate_shrink_right"]
    finished_h = v["h"] - v["base_plate_shrink_top"] - v["base_plate_shrink_bottom"]
    return OperatorHoleEditorGeometry(
        surface=feature_surface_from_structural_result("base_plate", result),
        width=result.width, height=result.height,
        reference_guide=build_finished_reference_guide(
            "base_plate", result,
            finished_width=finished_w, finished_height=finished_h,
        ),
        baseline_scene=None,
        baseline_status=("自訂 / 手動截角" if is_custom else "未使用基準檔（程式計算生成）"),
    )
