# -*- coding: utf-8 -*-
"""Read-only Door/BasePlate Hole Editor geometry owned by headless Engine."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from . import ae
from .contracts import DoorPartSpec
from .sheetmetal_features import (
    DoorIndicatorContext, RectGuide, box_body_face_dimensions,
    feature_surface_from_rect, feature_surface_from_structural_result,
)
from .sheetmetal_geometry import Vec2, box_body_vertical_offsets
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




def project_operator_hole_editor_endcap(
    role: str, *, width: object, depth: object, thickness: object,
) -> OperatorHoleEditorGeometry:
    """Existing Head/Tail finished-face Hole Editor geometry; fail closed on raw source.

    The same projection is used by the main GUI, Receiving Bay and candidate
    editors. It never authorizes manufacturing export or constructs a PartSpec.
    """
    from .operator_settings_transactions import normalize_operator_source_dimension
    from .sheetmetal_features import resolve_endcap_finished_face_guide

    if role not in {"head", "tail"}:
        raise ValueError("ENDCAP_HOLE_EDITOR_ROLE_INVALID")
    w = normalize_operator_source_dimension(width, field="w")
    d = normalize_operator_source_dimension(depth, field="d")
    t = normalize_operator_source_dimension(thickness, field="t")
    guide = resolve_endcap_finished_face_guide(w, d, t)
    return OperatorHoleEditorGeometry(
        surface=feature_surface_from_rect(
            f"{role}_finished_face", guide.min_point, guide.max_point,
        ),
        width=w, height=d,
        reference_guide=RectGuide(
            Vec2(0.0, 0.0), Vec2(w, d), "finished_boundary",
        ),
        baseline_scene=None, baseline_status="未使用基準檔（程式計算生成）",
    )


def project_operator_quantity_endcap_hole_editor_geometry(
    snapshot: Mapping[str, object], *, role: str,
) -> OperatorHoleEditorGeometry:
    """One Engine source for Quantity Head/Tail editor finished-face geometry.

    Receiving Quantity uses only its explicitly saved common physical box or
    the canonical fresh Receiving Family default. Neither a stale Set/Bay
    layout nor GUI W/H/D aliases may replace the quantity owner. Other
    Families preserve their own operator W/D. Material T must be validated by
    the shared EndCap projector and never cast bool to 1 mm.
    """
    from .cabinet_types.policy import canonical_family_name
    from .receiving_quantity_box import BOX_KEY, normalize_common_box

    if role not in {"head", "tail"}:
        raise ValueError("ENDCAP_HOLE_EDITOR_ROLE_INVALID")
    if not isinstance(snapshot, Mapping):
        raise ValueError("Quantity EndCap source must be a mapping")
    source = dict(snapshot)
    values = (normalize_common_box(source.get(BOX_KEY))
              if canonical_family_name(source) == "受電箱"
              else source)
    return project_operator_hole_editor_endcap(
        role, width=values["w"], depth=values["d"],
        thickness=source.get("t", 2),
    )


def project_operator_hole_editor_box_body_face(
    face_key: str, values: Mapping[str, object], *,
    head_corner_policy=None, tail_corner_policy=None,
    baseline_scene=None, baseline_status="未使用基準檔（程式計算生成）",
) -> OperatorHoleEditorGeometry:
    """Read-only WHD left/back/right face Hole Editor physical projection.

    Preserve the existing BoxBody face and vertical-corner authority instead
    of computing its surface rectangle and thickness offsets inside the GUI.
    This is editor display geometry; manufacturing stays with FinalScene/DXF.
    """
    if face_key not in {"left", "back", "right"}:
        raise ValueError(f"未知箱身面: {face_key}")
    v = values
    dimensions = box_body_face_dimensions(w=v["w"], h=v["h"], d=v["d"])
    width, height = dimensions[face_key]
    bottom_outer, top_outer = box_body_vertical_offsets(
        v["t"],
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    )
    surface = feature_surface_from_rect(
        f"box_body_{face_key}",
        Vec2(v["t"], bottom_outer),
        Vec2(width - v["t"], height - top_outer),
    )
    guide = RectGuide(
        Vec2(0.0, 0.0), Vec2(width, height), "enclosure_boundary",
    )
    return OperatorHoleEditorGeometry(
        surface=surface, width=width, height=height,
        reference_guide=guide, baseline_scene=baseline_scene,
        baseline_status=baseline_status,
    )


def project_operator_hole_editor_door_cell(
    result, spec: DoorPartSpec, *, baseline_scene=None,
    baseline_status="未使用基準檔（程式計算生成）",
) -> OperatorHoleEditorGeometry:
    """Project a selected Door cell from its already-resolved physical sources.

    The GUI passes the actual Engine structural result and the same DoorPartSpec
    used for DXF. Never reconstruct a default whole Door (which would lose the
    selected cell's frame edges) or recompute a finished-face formula in GUI.
    This is read-only editor geometry, not a manufacturing release.
    """
    from .manufacturing_door_indicator import door_finished_face_size

    if spec.fold_left is None or spec.fold_bottom is None:
        raise ValueError("門格 Hole Editor 缺少已確認的門板折邊")
    finished_w, finished_h = door_finished_face_size(spec)
    return OperatorHoleEditorGeometry(
        surface=feature_surface_from_structural_result("door", result),
        width=result.width, height=result.height,
        reference_guide=build_finished_reference_guide(
            "door", result, finished_width=finished_w, finished_height=finished_h,
        ),
        baseline_scene=baseline_scene,
        baseline_status=baseline_status,
        door_indicator_context=DoorIndicatorContext(
            finished_width=finished_w, finished_height=finished_h,
            left_fold=spec.fold_left, bottom_fold=spec.fold_bottom,
        ),
        door_frame_edges=spec.frame_edges,
    )


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
