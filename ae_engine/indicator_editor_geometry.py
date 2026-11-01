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


def _normalize_editor_groups(groups):
    groups = tuple(int(value) for value in groups)
    if not groups or any(value <= 0 for value in groups):
        raise ValueError("indicator groups must be positive")
    return groups


def resolve_indicator_box_editor_geometry(
    groups, *, thickness: float,
) -> IndicatorEditorComponentGeometry:
    """Read the Box alone; do not force the Small Door baseline to load."""
    groups = _normalize_editor_groups(groups)
    t = float(thickness)
    data = ae.get_stretched_indicator_box_data(None, groups, t, corner_policy=None)
    width, height = float(data.params["w"]), float(data.params["h"])
    fold = float(getattr(ae, "indicator_box_fold_def", 49.0))
    result = build_indicator_box_result(
        total_width=width, total_height=height, t=t, fold=fold,
    )
    return IndicatorEditorComponentGeometry(
        surface=ae.feature_surface_from_drawing_scene("indicator_box", data.scene),
        width=width, height=height,
        reference_guide=build_finished_reference_guide(
            "indicator_box", result,
            finished_width=width - 2.0 * fold + t,
            finished_height=height - 2.0 * fold + t,
        ),
        baseline_scene=data.scene,
        baseline_status=ae.indicator_shared_baseline_source_label("盒子.dxf"),
    )


def resolve_indicator_door_editor_geometry(
    groups, *, thickness: float, door_spec: DoorPartSpec,
) -> IndicatorEditorComponentGeometry:
    """Read the Small Door alone, retaining its existing optional custom policy."""
    groups = _normalize_editor_groups(groups)
    finished_w, finished_h = door_finished_face_size(door_spec)
    if door_spec.corner_policy is not None:
        result = build_unknown_door_result(
            w=door_spec.width, h=door_spec.height,
            t=door_spec.thickness, fw=door_spec.frame_width,
            gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
            fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
            fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
            corner_policy=door_spec.corner_policy,
        )
        surface = feature_surface_from_structural_result("indicator_door", result)
        width, height = result.width, result.height
        scene, status = None, "自訂 / 手動截角"
    else:
        data = ae.get_stretched_door_data(
            None, door_spec.width, door_spec.height, door_spec.thickness,
            door_spec.frame_width, door_spec.gap_w, door_spec.gap_h,
            door_spec.fold_left, door_spec.fold_right,
            door_spec.fold_top, door_spec.fold_bottom,
            indicator_window_groups=groups,
        )
        surface = ae.feature_surface_from_drawing_scene("indicator_door", data.scene)
        width = float(data.params["total_width"])
        height = float(data.params["total_depth"])
        result = build_door_result(
            w=door_spec.width, h=door_spec.height,
            t=door_spec.thickness, fw=door_spec.frame_width,
            gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
            fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
            fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
        )
        scene = data.scene
        status = ae.indicator_shared_baseline_source_label("小門.dxf")
    return IndicatorEditorComponentGeometry(
        surface=surface, width=width, height=height,
        reference_guide=build_finished_reference_guide(
            "indicator_door", result,
            finished_width=float(finished_w), finished_height=float(finished_h),
        ),
        baseline_scene=scene, baseline_status=status,
    )


def resolve_indicator_editor_components(
    groups, *, thickness: float, door_spec: DoorPartSpec,
) -> dict[str, IndicatorEditorComponentGeometry]:
    """Keep the established paired public API unchanged for existing callers."""
    groups = _normalize_editor_groups(groups)
    return {
        "indicator_box": resolve_indicator_box_editor_geometry(
            groups, thickness=thickness,
        ),
        "indicator_door": resolve_indicator_door_editor_geometry(
            groups, thickness=thickness, door_spec=door_spec,
        ),
    }
