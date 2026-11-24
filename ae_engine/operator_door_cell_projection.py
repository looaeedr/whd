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
from .fold_designer_snapshot_dimensions import (
    project_operator_door_cell_indicator_manufacturing_source,
)
from .sheetmetal_features import (
    DoorIndicatorContext, ResolvedRect, feature_surface_from_structural_result,
    resolve_door_indicator_layout, resolve_surface_features,
)
from .sheetmetal_geometry import Vec2
from .sheetmetal_part_adapters import build_door_result


def project_operator_door_cell_result(
    values: Mapping[str, object], *, cell_width, cell_height, frame_edges,
    material_frame_width=None, family_model=None,
):
    """Project a physical Door cell using the same Family FW owner as PartSpec.

    Modern GUI callers supply the original authored FW/T and actual Family.
    An older headless caller may still supply pre-resolved material FW, but
    the two mutually exclusive sources can never silently override each other.
    """
    if family_model is not None and material_frame_width is not None:
        raise ValueError("DOOR_CELL_PREVIEW_COMPETING_FRAME_WIDTH_SOURCES")
    if family_model is not None:
        material_frame_width = cabinet_family_policy.door_material_frame_width(
            family_model, frame_width=values["fw"], thickness=values["t"],
        )
    elif material_frame_width is None:
        raise ValueError("DOOR_CELL_PREVIEW_FRAME_WIDTH_SOURCE_REQUIRED")
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
    # Preview tolerates malformed inputs by omitting only their optional
    # lamp/box opening, never by converting them to valid-looking CUTTING.
    # Physical indicator counts and offsets share the manufacturing gate.
    try:
        state = project_operator_door_cell_indicator_manufacturing_source(indicator_state)
    except (TypeError, ValueError):
        state = {"mode": "none"}
    mode = state["mode"]
    if mode in {"indicator", "indicator_box"}:
        try:
            # Qualify each original physical source before any float coercion.
            # Otherwise bool(True) becomes 1 mm and a preview can invent a
            # plausible lamp/box CUTTING feature that PartSpec would reject.
            from .operator_settings_transactions import (
                normalize_operator_source_dimension,
            )
            from .door_operator_part_spec import _finite_operator_number

            w = normalize_operator_source_dimension(cell_width, field="w")
            h = normalize_operator_source_dimension(cell_height, field="h")
            t = normalize_operator_source_dimension(thickness, field="t")
            material_fw = cabinet_family_policy.door_material_frame_width(
                family_model, frame_width=frame_width, thickness=t,
            )
            resolved_gap_w = _finite_operator_number(gap_w, "door_gap_w")
            resolved_gap_h = _finite_operator_number(gap_h, "door_gap_h")
            resolved_fold_left = _finite_operator_number(fold_left, "door_fold_l")
            resolved_fold_bottom = _finite_operator_number(fold_bottom, "door_fold_b")
            finished_w, finished_h = ae.calculate_door_finished_size(
                w, h, material_fw,
                resolved_gap_w, resolved_gap_h, t, frame_edges=frame_edges,
            )
            context = DoorIndicatorContext(
                finished_width=float(finished_w),
                finished_height=float(finished_h),
                left_fold=resolved_fold_left, bottom_fold=resolved_fold_bottom,
            )
            groups = tuple(state["groups"][:state["layers"]])
            offset_x = state["offset_x"]
            offset_y = state["offset_y"]
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
    try:
        # Source validation precedes the fingerprint/cache lookup.  A cached
        # visible DXF preview must not reauthorize bool(True) as a 1-mm plate
        # or allow NaN/Inf to leak into the baseline stretcher.
        from .operator_settings_transactions import (
            normalize_operator_source_dimension,
        )
        from .door_operator_part_spec import _finite_operator_number

        w = normalize_operator_source_dimension(cell_width, field="w")
        h = normalize_operator_source_dimension(cell_height, field="h")
        t = normalize_operator_source_dimension(values["t"], field="t")
        fw = normalize_operator_source_dimension(values["fw"], field="fw")
        gap_w = _finite_operator_number(values["door_gap_w"], "door_gap_w")
        gap_h = _finite_operator_number(values["door_gap_h"], "door_gap_h")
        fold_l = _finite_operator_number(values["door_fold_l"], "door_fold_l")
        fold_r = _finite_operator_number(values["door_fold_r"], "door_fold_r")
        fold_t = _finite_operator_number(values["door_fold_t"], "door_fold_t")
        fold_b = _finite_operator_number(values["door_fold_b"], "door_fold_b")
        material_fw = cabinet_family_policy.door_material_frame_width(
            family_model, frame_width=fw, thickness=t,
        )
        source_fp = ae.baseline_source_fingerprint(
            ae.baseline_expected_path(baseline_model, "門.dxf")
        )
        key = (
            source_fp, family_model, baseline_model, w, h, t, fw,
            gap_w, gap_h, fold_l, fold_r, fold_t, fold_b,
            bool(frame_edges.left), bool(frame_edges.right),
            bool(frame_edges.top), bool(frame_edges.bottom),
        )
        if cache is not None and key in cache:
            return cache[key], ae.baseline_source_label(baseline_model, "門.dxf")

        data = ae.get_stretched_door_data(
            baseline_model,
            w, h, t, material_fw,
            gap_w, gap_h, fold_l, fold_r, fold_t, fold_b,
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
