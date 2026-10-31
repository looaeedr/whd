"""Shared indicator-box and small-door editor geometry from the headless engine.

No UI imports: GUI supplies groups/PartSpec and formats the returned geometry.
"""
from dataclasses import dataclass

from . import ae
from .contracts import DoorPartSpec
from .manufacturing_door_indicator import door_finished_face_size
from .sheetmetal_features import feature_surface_from_structural_result
from .sheetmetal_part_adapters import (
    build_door_result,
    build_finished_reference_guide,
    build_indicator_box_result,
    build_unknown_door_result,
)


@dataclass(frozen=True)
class IndicatorEditorComponentGeometry:
    surface: object
    width: float
    height: float
    reference_guide: object
    baseline_scene: object | None
    baseline_status: str


def resolve_indicator_editor_components(
    groups, *, thickness: float, door_spec: DoorPartSpec,
) -> dict[str, IndicatorEditorComponentGeometry]:
    """Resolve two physical editor surfaces from engine-owned source geometry."""
    groups = tuple(int(value) for value in groups)
    if not groups or any(value <= 0 for value in groups):
        raise ValueError("indicator groups must be positive")
    t = float(thickness)

    box_data = ae.get_stretched_indicator_box_data(
        None, groups, t, corner_policy=None,
    )
    box_baseline_scene = box_data.scene
    box_status = ae.indicator_shared_baseline_source_label("盒子.dxf")
    box_w = float(box_data.params["w"])
    box_h = float(box_data.params["h"])
    box_fold = float(getattr(ae, "indicator_box_fold_def", 49.0))
    box_result = build_indicator_box_result(
        total_width=box_w, total_height=box_h, t=t, fold=box_fold,
    )
    box_guide = build_finished_reference_guide(
        "indicator_box", box_result,
        finished_width=box_w - 2.0 * box_fold + t,
        finished_height=box_h - 2.0 * box_fold + t,
    )

    finished_w, finished_h = door_finished_face_size(door_spec)
    if door_spec.corner_policy is not None:
        door_result = build_unknown_door_result(
            w=door_spec.width, h=door_spec.height,
            t=door_spec.thickness, fw=door_spec.frame_width,
            gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
            fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
            fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
            corner_policy=door_spec.corner_policy,
        )
        door_surface = feature_surface_from_structural_result(
            "indicator_door", door_result,
        )
        door_width, door_height = door_result.width, door_result.height
        door_baseline_scene = None
        door_status = "自訂 / 手動截角"
    else:
        door_data = ae.get_stretched_door_data(
            None, door_spec.width, door_spec.height, door_spec.thickness,
            door_spec.frame_width, door_spec.gap_w, door_spec.gap_h,
            door_spec.fold_left, door_spec.fold_right,
            door_spec.fold_top, door_spec.fold_bottom,
            indicator_window_groups=groups,
        )
        door_surface = ae.feature_surface_from_drawing_scene(
            "indicator_door", door_data.scene,
        )
        door_width = float(door_data.params["total_width"])
        door_height = float(door_data.params["total_depth"])
        door_result = build_door_result(
            w=door_spec.width, h=door_spec.height,
            t=door_spec.thickness, fw=door_spec.frame_width,
            gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
            fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
            fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
        )
        door_baseline_scene = door_data.scene
        door_status = ae.indicator_shared_baseline_source_label("小門.dxf")
    door_guide = build_finished_reference_guide(
        "indicator_door", door_result,
        finished_width=float(finished_w),
        finished_height=float(finished_h),
    )
    return {
        "indicator_box": IndicatorEditorComponentGeometry(
            surface=ae.feature_surface_from_drawing_scene(
                "indicator_box", box_data.scene,
            ),
            width=box_w, height=box_h,
            reference_guide=box_guide, baseline_scene=box_baseline_scene,
            baseline_status=box_status,
        ),
        "indicator_door": IndicatorEditorComponentGeometry(
            surface=door_surface, width=door_width, height=door_height,
            reference_guide=door_guide, baseline_scene=door_baseline_scene,
            baseline_status=door_status,
        ),
    }
