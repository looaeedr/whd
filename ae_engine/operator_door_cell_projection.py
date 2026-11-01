# -*- coding: utf-8 -*-
"""Door-layout operator projection APIs; not a manufacturing release.

The GUI selects cells and presents already-projected Engine data. Canonical
manufacturing still uses DoorPartSpec / FinalScene and certified policies.
"""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from . import ae
from .cabinet_types import policy as cabinet_family_policy
from .manufacturing_door_indicator import indicator_box_opening_size
from .sheetmetal_features import (
    DoorIndicatorContext, ResolvedRect, feature_surface_from_structural_result,
    resolve_door_indicator_layout, resolve_surface_features,
)
from .sheetmetal_geometry import Vec2
from .sheetmetal_part_adapters import build_door_result


def project_operator_door_cell_result(
    values: Mapping[str, object], *, cell_width, cell_height, frame_edges,
    material_frame_width,
):
    """Preserve the legacy selected-cell structural preview through Engine."""
    return build_door_result(
        w=cell_width, h=cell_height, t=values["t"],
        fw=material_frame_width,
        gap_w=values["door_gap_w"], gap_h=values["door_gap_h"],
        fold_left=values["door_fold_l"], fold_right=values["door_fold_r"],
        fold_top=values["door_fold_t"], fold_bottom=values["door_fold_b"],
        frame_edges=frame_edges,
    )


def project_operator_door_cell_features(
    result, features, indicator_state: Mapping[str, object], *,
    cell_width, cell_height, frame_edges, family_model,
    frame_width, thickness, gap_w, gap_h, fold_left, fold_bottom,
):
    """Project saved holes and optional Indicator/Box opening in material space.

    Historical preview-only compatibility: malformed user features or
    incomplete indicator settings do not erase the other visible features.
    This is NOT a CUTTING validation or export-fallback authorization.
    """
    resolved = []
    if features:
        surface = feature_surface_from_structural_result("door", result)
        try:
            resolved.extend(resolve_surface_features(
                surface, features, result.width, result.height,
            ))
        except ValueError:
            pass
    state = indicator_state
    mode = state.get("mode", "indicator" if state.get("enabled") else "none")
    if mode in {"indicator", "indicator_box"}:
        try:
            t = float(thickness)
            material_fw = cabinet_family_policy.door_material_frame_width(
                family_model, frame_width=float(frame_width), thickness=t,
            )
            finished_w, finished_h = ae.calculate_door_finished_size(
                cell_width, cell_height, material_fw,
                gap_w, gap_h, t, frame_edges=frame_edges,
            )
            context = DoorIndicatorContext(
                finished_width=float(finished_w),
                finished_height=float(finished_h),
                left_fold=float(fold_left), bottom_fold=float(fold_bottom),
            )
            groups = tuple(
                int(v) for v in state.get("groups", [2])[:int(state.get("layers", 1))]
            )
            offset_x = float(state.get("offset_x", 0.0))
            offset_y = float(state.get("offset_y", 0.0))
            if mode == "indicator":
                layout = resolve_door_indicator_layout(
                    context, groups, Vec2(offset_x, offset_y),
                )
                resolved.extend(layout.features)
            else:
                opening_w, opening_h = indicator_box_opening_size(
                    groups, thickness=t,
                )
                resolved.append(ResolvedRect(
                    center=Vec2(
                        context.left_fold + context.finished_width / 2.0 + offset_x,
                        context.bottom_fold + context.finished_height / 2.0 + offset_y,
                    ),
                    width=opening_w, height=opening_h, layer="CUTTING",
                    source_type="indicator_box_opening",
                ))
        except Exception:
            # Legacy GUI preview did not display incomplete indicator geometry.
            pass
    return resolved


def project_operator_door_cell_baseline(
    values: Mapping[str, object], *, family_model, cell_width, cell_height,
    frame_edges, cache: MutableMapping | None = None,
):
    """Return the shared-family Door DXF preview scene with source-keyed cache.

    The cache is display-only. The Engine decides family source, fingerprint,
    datum and canonical AE stretching; absent or invalid sources never certify
    manufacturing geometry.
    """
    baseline_model = (
        cabinet_family_policy.baseline_feature_model_name(family_model)
        if family_model else None
    )
    if not baseline_model or not ae.has_baseline_part(baseline_model, "門.dxf"):
        return None, ae.baseline_source_label("", "門.dxf")
    source_fp = ae.baseline_source_fingerprint(
        ae.baseline_expected_path(baseline_model, "門.dxf")
    )
    key = (
        source_fp, family_model, baseline_model,
        float(cell_width), float(cell_height),
        float(values["t"]), float(values["fw"]),
        float(values["door_gap_w"]), float(values["door_gap_h"]),
        float(values["door_fold_l"]), float(values["door_fold_r"]),
        float(values["door_fold_t"]), float(values["door_fold_b"]),
        bool(frame_edges.left), bool(frame_edges.right),
        bool(frame_edges.top), bool(frame_edges.bottom),
    )
    if cache is not None and key in cache:
        return cache[key], ae.baseline_source_label(baseline_model, "門.dxf")
    try:
        material_fw = cabinet_family_policy.door_material_frame_width(
            family_model,
            frame_width=float(values["fw"]), thickness=float(values["t"]),
        )
        data = ae.get_stretched_door_data(
            baseline_model,
            cell_width, cell_height, values["t"], material_fw,
            values["door_gap_w"], values["door_gap_h"],
            values["door_fold_l"], values["door_fold_r"],
            values["door_fold_t"], values["door_fold_b"],
            frame_edges=frame_edges,
            nameplate_center_datum_top=(
                cabinet_family_policy.door_nameplate_center_datum_top(family_model)
            ),
        )
        if cache is not None:
            cache[key] = data.scene
        return data.scene, ae.baseline_source_label(baseline_model, "門.dxf")
    except Exception:
        return None, "未使用基準檔（程式計算生成）"
