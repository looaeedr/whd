# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Headless manufacturing boundary for the existing AE engine.

This module is the stable public boundary inside the ``ae_engine`` package.
External callers use finished-face Features; compatibility with legacy
unfolded exporter coordinates is contained here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Literal, Mapping

from . import ae
from .dxf_serialization import save_scene_dxf
from .cabinet_types.policy import resolve_box_body_back_panel_contract
from .cabinet_types.receiving import resolve_box_body_structure_state as resolve_receiving_box_body_structure_state
from .box_body_structure_state import (
    BoxBodyStructureType, BackPanelMode, DEFAULT_STRUCTURE_TYPE,
    _default_join_settings, default_box_body_structure_state, _structure_type,
    legacy_box_body_structure_locked, _structure_locked_bool, normalize_box_body_structure_state,
    set_active_structure, activate_structure_with_defaults, set_structure_locked,
    _back_panel_mode, back_panel_mode, set_side_back_back_panel_mode,
    update_structure_config, _finite_dimension, _manual_integer,
    resolve_two_piece_widths, set_two_piece_width, reconcile_box_body_structure_for_total_w_change,
    set_join_seam_bend, resolve_three_piece_widths, set_three_piece_width,
    set_side_back_piece_profile, side_rear_bend_dimension_space, side_rear_bend_material_length,
    side_rear_bend_outside_length, set_side_back_geometry,
)

# Public compatibility aliases: old Phase6 helper names keep identical Engine
# callables without importing any private Engine module or private API member.
box_body_structure_default_join_settings = _default_join_settings
box_body_structure_type_from_value = _structure_type
box_body_structure_locked_bool = _structure_locked_bool
box_body_structure_back_panel_mode_from_value = _back_panel_mode
box_body_structure_finite_dimension = _finite_dimension
box_body_structure_manual_integer = _manual_integer

from .linked_endcap_fold import (
    is_canonical_box_body_mating_profile, box_body_front_mating_fold_chain,
    build_linked_endcap_xy_fold_profiles,
)
from .endcap_factory_fold import (
    selection_from_raw as endcap_corner_selection_from_raw, normalize_endcap_fw_state,
    resolve_endcap_fw, resolve_endcap_assembly_type, build_endcap_xy_fold_profiles,
    endcap_editor_fold_tabs, normalize_endcap_profile_order,
)
from .endcap_bottom_wrap_state import (
    WRAP_LINKED, WRAP_FOLLOW_HEAD, WRAP_FOLLOW_TAIL, WRAP_INDEPENDENT,
    ENDCAP_BOTTOM_WRAP_MODES, normalize_endcap_bottom_wrap_state,
    resolve_endcap_bottom_wrap, commit_endcap_bottom_wrap_joint,
    commit_endcap_bottom_wrap,
)
from .endcap_xy_readback import (
    fold_material_segment_outside_length, resolve_endcap_xy_outside_dimensions,
)
from .endcap_editor_fold import (
    build_endcap_editor_simple_profile, read_endcap_editor_simple_profile,
)
from .box_body_editor_readback import (
    formed_box_body_fw_widths,
    box_body_ui_segment_length_to_material,
    read_box_body_outside_dimensions,
    can_remove_box_body_fold_segment,
)
from .box_body_fold_profile import (
    BOX_BODY_TURNS,
    apply_outside_dimension_compensation,
    outside_profile_to_material,
    build_box_body_profile as build_box_body_fold_profile,
    merge_box_body_fold_profile,
    profile_to_fold_segments as box_body_profile_to_fold_segments,
)
from .receiving_quantity_versions import (
    SCHEMA, SCHEMA_V2, SCHEMA_V3, QUANTITY_MODE, SET_BAY_MODE,
    QuantityModel, positive_piece_count, quantity_inherited_nfb_brand_conflicts,
    normalize_quantity_snapshot, quantity_only_change,
)
from .indicator_editor_geometry import resolve_indicator_editor_components
from .manufacturing_legacy_export_guard import (
    has_submitted_nfb_in_current_snapshot,
    assert_legacy_nfb_export_scope_safe,
)
from .manufacturing_selected_export import (
    save_selected_resolved_manufacturing_dxf,
    selected_export_manufacturing_policy,
)
from .manufacturing_export_selection import (
    resolved_export_intention_key,
    select_resolved_export_geometry,
    resolve_receiving_bay_local_export_geometry,
)
from . import manufacturing_verification as _manufacturing_verification
from . import manufacturing_export as _manufacturing_export
from . import manufacturing_requests as _manufacturing_requests
from . import manufacturing_render as _manufacturing_render
from .contracts import (
    FinalMaterialCollisionPart,
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    FeatureLike,
    FoldProfileSegment,
    IndicatorBoxPartSpec,
    ManufacturingContext,
    ManufacturingPolicy,
    PartExportResult,
    PartSpec,
)
from .sheetmetal_features import (
    BoxBodyFaceContext,
    CircleFeature,
    DoorIndicatorContext,
    FeatureAnchor,
    ProfileFeature,
    RectFeature,
    box_body_face_contexts_from_strip,
    feature_finished_point,
    feature_to_legacy_hole,
    legacy_hole_to_feature,
    resolve_door_indicator_layout,
)
from .sheetmetal_geometry import (
    EndCapAssemblySemantics,
    FourCornerTypePolicy,
    Vec2,
    resolve_endcap_policy_assembly_semantics,
)
from .sheetmetal_part_adapters import (
    build_box_body_result_from_fold_profile,
    build_door_result,
    build_unknown_door_result,
    build_finished_reference_guide,
)
from .cabinet_types import policy as cabinet_family_policy



from .fold_designer_baseline_api import (
    fold_designer_secondary_scene_rows, query_fold_designer_baseline_rows,
)

from .manufacturing_baseline_policy import (
    resolve_policy,
    _resource_root,
    _expected_baseline_path,
    _indicator_shared_expected_path,
    expected_shared_indicator_baselines,
    _indicator_shared_existing_path,
    expected_baseline_path_for,
    expected_endcap_feature_baseline,
    receiving_baseline_source_stamp,
    _baseline_path,
    _extract_endcap_shared_6p4_mother_rule,
    _divider_post_relief_center_frame,
    apply_divider_endcap_shared_6p4_datum,
    _door_baseline_model_name,
    _endcap_baseline_feature_model_name,
    _door_nameplate_datum_top,
    _scoped_ae_resource_root,
    _supported_kwargs,
    _call,
    _has_named_parameter,
)

from .manufacturing_door_indicator import (
    _resolved_door_params,
    _resolved_door_corner_policy,
    door_finished_face_size,
    door_indicator_offset_for_finished_center,
    indicator_box_unfolded_size,
    indicator_box_finished_face_size,
    indicator_box_opening_size,
    indicator_small_door_finished_size,
    indicator_box_opening_feature,
    validate_door_indicator_fit,
    _validate_door_part_indicator_fit,
    indicator_small_door_spec,
    indicator_small_door_unfolded_size,
)

from .manufacturing_endcap_compat import (
    _as_feature,
    _door_features_for_legacy_engine,
    _endcap_feature_kwargs,
    _legacy_endcap_holes,
    _endcap_scalar,
    resolve_endcap_request,
    _baseline_endcap_holes_for_request,
    _merge_baseline_endcap_holes,
    _scene_with_authoritative_fold_profiles,
)

def apply_cabinet_family_endcap_policy(
    policy, part_key, *, family_source=None, thickness=None, structure_state=None,
):
    """Engine-only EndCap family geometry; preserve operator Corner selections.

    Receiving computes its effective lower material FW from the authoritative
    family/topology state.  Non-EndCap and other cabinet families are unchanged.
    """
    if policy is None or str(part_key) not in {"head", "tail"}:
        return policy
    if not cabinet_family_policy.supports_bottom_wrap_controls(family_source):
        return policy
    t = float(ae.T if thickness is None else thickness)
    default_fw = float(policy.bottom_fw if policy.bottom_fw is not None else policy.fw)
    return replace(
        policy,
        bottom_fw=cabinet_family_policy.effective_endcap_bottom_fw(
            family_source, structure_state,
            thickness=t, default_fw=default_fw,
        ),
    )


def map_door_features_to_unfolded_material(
    spec: DoorPartSpec, context: ManufacturingContext | None = None,
):
    """Canonical Engine-owned finished-face → unfolded-material feature map.

    The FinalScene builder consumes this exact manufacturing geometry.  A
    trusted export verifier may compare source-attested features with it,
    but must not independently derive feature offsets or bend compensation.
    """
    return tuple(_door_features_for_legacy_engine(spec, context))


from .manufacturing_render_data import (
    FoldGuide,
    fold_guides_from_final_scene,
    MaterialSegment,
    UnfoldedBlankTopology,
    _profile_material_segments,
    PartRenderData,
    collision_part_from_render_data,
    UnfoldedBlankInfo,
    _measure_one_unfolded_blank,
    measure_unfolded_blanks,
    BoxBodyPieceRenderData,
    BoxBodyStructureRenderData,
    material_polygon_from_final_scene,
    _translated_scene,
    _exploded_box_body_preview,
)

from .manufacturing_scene_orchestration import (
    build_part_scene,
    build_inner_door_panel_render_data,
    build_inner_door_frame_render_data,
    build_box_body_divider_render_data,
    build_box_body_structure_render_data,
    generate_box_body_structure_parts,
    _resolved_endcap_bottom_joint_relation,
    _replace_receiving_bottom_relief_from_registry,
    _unfolded_topology_for_spec,
    build_part_render_data,
)

def save_part_render_data_dxf(
    render_data: PartRenderData,
    output_path: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> str:
    """Serialize an already-built authoritative FinalScene to DXF."""
    metadata = getattr(render_data, "metadata", None) or {}
    blocked = metadata.get("baseline_fit_error")
    if blocked:
        raise ValueError(str(blocked))
    # Numeric V5 CUTTING is a real 2D/3D trial, not an export authorization.
    # Only a separately certified manufacturing adapter can lift this gate.
    if (metadata.get("nfb_v5_trial_status")
            and metadata.get("nfb_trial_export_approved") is not True):
        raise ValueError("NFB V5 未驗證試作禁止使用正式製造 DXF 輸出")
    # Specific V5 trial guard takes priority, then the more general tier
    # physical-base gate handles unsourced/forged non-V5 scenes.
    _manufacturing_export.reject_unverified_receiving_nfb_tier_base(render_data)
    return _manufacturing_export.save_part_render_data_dxf(
        render_data.scene,
        output_path,
        serializer=save_scene_dxf,
        overwrite=overwrite,
    )

def _door_export(spec: DoorPartSpec, filepath: str, context: ManufacturingContext):
    _validate_door_part_indicator_fit(spec, context)
    is_indicator_small_door = spec.indicator_window_groups is not None
    if is_indicator_small_door:
        expected = _indicator_shared_expected_path("小門.dxf", context)
        baseline = _indicator_shared_existing_path("小門.dxf", context)
    else:
        expected = _expected_baseline_path(spec.model_name, "門.dxf", context)
        baseline = expected if expected is not None and expected.is_file() else None
    p = _resolved_door_params(spec, context)
    corner_policy = _resolved_door_corner_policy(spec, p["fw"])
    common = dict(
        W_val=p["w"],
        H_val=p["h"],
        T_val=p["t"],
        FW_val=p["fw"],
        draw_stock=context.draw_stock,
        indicator_hole=spec.indicator_hole,
        door_indicator=spec.door_indicator,
        door_indicator_offset=spec.door_indicator_offset,
        is_box_dist=spec.use_box_distance,
        user_features=_door_features_for_legacy_engine(spec, context),
        frame_edges=spec.frame_edges,
    )
    if baseline is not None:
        _call(
            ae.export_stretched_door_dxf,
            filepath,
            None if is_indicator_small_door else str(spec.model_name),
            gap_w_val=p["gap_w"],
            gap_h_val=p["gap_h"],
            fl_val=p["fold_left"],
            fr_val=p["fold_right"],
            ft_val=p["fold_top"],
            fb_val=p["fold_bottom"],
            indicator_window_groups=spec.indicator_window_groups,
            corner_policy=corner_policy,
            **common,
        )
        return "export_stretched_door_dxf", baseline, expected
    if corner_policy is not None:
        _call(
            ae.export_unknown_door_dxf,
            filepath,
            corner_policy=corner_policy,
            gap_w=p["gap_w"], gap_h=p["gap_h"],
            fold_left=p["fold_left"], fold_right=p["fold_right"],
            fold_top=p["fold_top"], fold_bottom=p["fold_bottom"],
            **common,
        )
        return "export_unknown_door_dxf", None, None

    _call(
        ae.export_door_dxf,
        filepath,
        gap_w=p["gap_w"],
        gap_h=p["gap_h"],
        fold_left=p["fold_left"],
        fold_right=p["fold_right"],
        fold_top=p["fold_top"],
        fold_bottom=p["fold_bottom"],
        **common,
    )
    return "export_door_dxf", None, expected


def _box_body_export(spec: BoxBodyPartSpec, filepath: str, context: ManufacturingContext):
    expected = _expected_baseline_path(spec.model_name, "箱身.dxf", context)
    baseline = expected if expected is not None and expected.is_file() else None
    _call(
        ae.export_box_body_dxf,
        filepath,
        W_val=spec.width,
        H_val=spec.height,
        D_val=spec.depth,
        T_val=spec.thickness,
        FW_val=spec.frame_width,
        zl1=spec.zl1,
        zl2=spec.zl2,
        zr1=spec.zr1,
        zr2=spec.zr2,
        z_comp=spec.z_comp,
        draw_stock=context.draw_stock,
        model_name=spec.model_name,
        user_features=list(spec.features),
        face_features={key: list(value) for key, value in spec.face_features.items()},
        head_corner_policy=spec.head_corner_policy,
        tail_corner_policy=spec.tail_corner_policy,
        fold_profile=spec.fold_profile or None,
    )
    return "export_box_body_dxf", baseline, expected


def _end_cap_export(spec: EndCapPartSpec, filepath: str, context: ManufacturingContext):
    """Export EndCap through the legacy AE API unless caller supplied resolved geometry.

    The headless adapter contract requires all GUI dimensions and normalized holes to
    cross the public ``export_end_cap_dxf`` seam.  Fully resolved Phase6 geometry still
    serializes the shared Final Scene so 2D/3D/export stay identical.
    """
    # Export must share the same EndCap resolver validation as 2D/3D.
    # Legacy formula export may still consume scalar requests for compatibility,
    # but invalid CornerType assembly semantics must fail before any DXF is written.
    resolve_endcap_request(spec)
    expected = _expected_baseline_path(spec.model_name, "封頭尾.dxf", context)
    baseline = expected if expected is not None and expected.is_file() else None
    has_resolved_geometry = bool(
        spec.corner_policy is not None
        or spec.fold_profile_x or spec.fold_profile_y
        or spec.resolved_assembly_relief_cuts
        or spec.assembly_relief is not None
    )
    if has_resolved_geometry:
        render_data = build_part_render_data(spec, context)
        save_part_render_data_dxf(render_data, filepath, overwrite=True)
        return "final_scene_end_cap_export", baseline, expected
    if baseline is not None:
        _call(
            ae.export_stretched_end_cap_dxf,
            filepath, spec.model_name,
            W_val=spec.width, H_val=spec.height, D_val=spec.depth,
            T_val=spec.thickness, FW_val=spec.frame_width,
            draw_stock=context.draw_stock, is_tail=spec.is_tail,
            holes=_legacy_endcap_holes(spec), corner_policy=spec.corner_policy,
        )
        return "export_stretched_end_cap_dxf", baseline, expected
    _call(
        ae.export_end_cap_dxf,
        filepath,
        W_val=spec.width, H_val=spec.height, D_val=spec.depth,
        T_val=spec.thickness, FW_val=spec.frame_width,
        yl1=spec.fold_left, yr1=spec.fold_right,
        ytop1=spec.fold_top, ybottom1=spec.fold_bottom,
        zl1=spec.box_fold_left, zr1=spec.box_fold_right,
        draw_stock=context.draw_stock, is_tail=spec.is_tail,
        holes=_legacy_endcap_holes(spec),
    )
    return "export_end_cap_dxf", baseline, expected


def _base_plate_export(spec: BasePlatePartSpec, filepath: str, context: ManufacturingContext):
    is_receiving = str(spec.model_name or "").strip() in {"受電箱", "RECEIVING"}
    if is_receiving and spec.receiving_bend_pattern is None:
        raise ValueError("RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING")
    # Receiving base plate uses final_scene path to preserve nominal blank
    # geometry and apply local seam reliefs consistently with 2D/render.
    if (spec.box_body_fold_profile and spec.box_body_structure_state) or spec.seam_positions or is_receiving:
        render_data = build_part_render_data(spec, context)
        # The legacy generic BasePlate exporter bypassed the shared FinalScene
        # manufacturing guard. Use exactly the same guarded serializer as
        # resolved/batch DXF; generate_part already provides a temp file.
        save_part_render_data_dxf(render_data, filepath, overwrite=True)
        return "final_scene_base_plate_structure_export", None, None
    exporter = ae.export_unknown_base_plate_dxf if spec.corner_policy is not None else ae.export_base_plate_dxf
    kwargs = {"corner_policy": spec.corner_policy} if spec.corner_policy is not None else {}
    _call(
        exporter,
        filepath,
        **kwargs,
        W_val=spec.width,
        H_val=spec.height,
        T_val=spec.thickness,
        shrink_top=spec.shrink_top,
        shrink_bottom=spec.shrink_bottom,
        shrink_left=spec.shrink_left,
        shrink_right=spec.shrink_right,
        bend=spec.bend,
        draw_stock=context.draw_stock,
        user_features=list(spec.features),
    )
    return ("export_unknown_base_plate_dxf" if spec.corner_policy is not None else "export_base_plate_dxf"), None, None


def _indicator_box_export(spec: IndicatorBoxPartSpec, filepath: str, context: ManufacturingContext):
    # Indicator boxes are globally shared parts.  Manufacturing owns only the part role;
    # AE owns discovery of the actual shared baseline folder under the scoped resource root.
    expected = _indicator_shared_expected_path("盒子.dxf", context)
    baseline = _indicator_shared_existing_path("盒子.dxf", context)
    if baseline is None:
        raise FileNotFoundError(f"AE_BASELINE_MISSING: {expected}")
    _call(
        ae.export_stretched_indicator_box_dxf,
        filepath, None, list(spec.layer_groups),
        T_val=spec.thickness,
        draw_stock=context.draw_stock,
        user_features=list(spec.features),
        corner_policy=spec.corner_policy,
    )
    return "export_stretched_indicator_box_dxf", baseline, expected


def _part_kind(spec: PartSpec) -> str:
    from .contracts import CustomFoldPartSpec
    if isinstance(spec, CustomFoldPartSpec):
        return spec.physical_id
    if isinstance(spec, DoorPartSpec):
        return "door"
    if isinstance(spec, BoxBodyPartSpec):
        return "box_body"
    if isinstance(spec, EndCapPartSpec):
        return "end_cap_tail" if spec.is_tail else "end_cap_head"
    if isinstance(spec, BasePlatePartSpec):
        return "base_plate"
    if isinstance(spec, IndicatorBoxPartSpec):
        return "indicator_box"
    raise TypeError(f"Unsupported PartSpec: {type(spec)!r}")


def _export_to_temp(spec: PartSpec, temp_path: str, context: ManufacturingContext):
    from .contracts import CustomFoldPartSpec
    if isinstance(spec, CustomFoldPartSpec):
        data=build_part_render_data(spec,context)
        save_part_render_data_dxf(data,temp_path,overwrite=True)
        return "save_custom_fold_scene", None, None
    if isinstance(spec, DoorPartSpec):
        return _door_export(spec, temp_path, context)
    if isinstance(spec, BoxBodyPartSpec):
        return _box_body_export(spec, temp_path, context)
    if isinstance(spec, EndCapPartSpec):
        return _end_cap_export(spec, temp_path, context)
    if isinstance(spec, BasePlatePartSpec):
        return _base_plate_export(spec, temp_path, context)
    if isinstance(spec, IndicatorBoxPartSpec):
        return _indicator_box_export(spec, temp_path, context)
    raise TypeError(f"Unsupported PartSpec: {type(spec)!r}")


def generate_part(
    spec: PartSpec,
    output_path: str | os.PathLike[str],
    context: ManufacturingContext | None = None,
) -> PartExportResult:
    """Export one part without GUI dependency, replacing destination atomically."""
    ctx = context or ManufacturingContext()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not ctx.overwrite:
        raise FileExistsError(str(destination))

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.tmp-",
        suffix=destination.suffix or ".dxf",
        dir=str(destination.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with _scoped_ae_resource_root(ctx):
            exporter_name, baseline, expected = _export_to_temp(spec, str(temp_path), ctx)
        os.replace(temp_path, destination)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise

    return PartExportResult(
        part_kind=_part_kind(spec),
        output_path=str(destination),
        exporter_name=exporter_name,
        used_baseline=baseline is not None,
        baseline_path=str(baseline) if baseline is not None else None,
        expected_baseline_path=str(expected) if expected is not None else None,
    )


_BOX_BODY_PHYSICAL_PIECE_ROLES = frozenset({
    "left", "middle", "right",
    "left_side", "back", "right_side",
    "integral",
})


def _safe_dxf_part_stem(part_id: str) -> str:
    return _manufacturing_export.safe_dxf_part_stem(part_id)


def _resolved_physical_dxf_stem(part_id: str) -> str:
    return _manufacturing_export.resolved_physical_dxf_stem(
        part_id, box_body_physical_piece_roles=_BOX_BODY_PHYSICAL_PIECE_ROLES
    )


def _resolved_physical_render_parts(resolved_geometry):
    return _manufacturing_export.resolved_physical_render_parts(resolved_geometry)


def _resolved_physical_dxf_filename(part_id: str, *, instance_namespace: str | None = None) -> str:
    return _manufacturing_export.resolved_physical_dxf_filename(
        part_id,
        box_body_physical_piece_roles=_BOX_BODY_PHYSICAL_PIECE_ROLES,
        instance_namespace=instance_namespace,
    )


def receiving_manufacturing_instance_namespace(*, set_id: str, bay_id: str) -> str:
    return _manufacturing_export.receiving_instance_namespace(set_id=set_id, bay_id=bay_id)


def save_resolved_manufacturing_geometry_dxf(
    resolved_geometry,
    output_dir: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    part_only: bool = False,
    instance_namespace: str | None = None,
) -> dict[str, str]:
    """Export physical DXF; part_only permits independently verified NFB base CUTTING, not full assembly."""
    return _manufacturing_export.save_resolved_manufacturing_geometry_dxf(
        resolved_geometry,
        output_dir,
        save_part_render_data_dxf=save_part_render_data_dxf,
        box_body_physical_piece_roles=_BOX_BODY_PHYSICAL_PIECE_ROLES,
        overwrite=overwrite,
        part_only=part_only,
        instance_namespace=instance_namespace,
    )


def save_resolved_manufacturing_geometry_batch_dxf(
    instances,
    output_dir: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    part_only: bool = False,
) -> dict[str, str]:
    """Export multi-Bay DXF; part_only never certifies incomplete EAR/box assembly."""
    return _manufacturing_export.save_resolved_manufacturing_geometry_batch_dxf(
        instances,
        output_dir,
        save_part_render_data_dxf=save_part_render_data_dxf,
        box_body_physical_piece_roles=_BOX_BODY_PHYSICAL_PIECE_ROLES,
        overwrite=overwrite,
        part_only=part_only,
    )


def save_verified_final_scene_batch_dxf(
    parts,
    output_dir: str | os.PathLike[str],
    *,
    pre_commit_guard,
    overwrite: bool = False,
    durable_stage_commit=None,
) -> dict[str, str]:
    """Stage and independently Save→Reload every WHD-owned FinalScene part."""
    return _manufacturing_export.save_verified_final_scene_batch_dxf(
        parts, output_dir,
        save_part_render_data_dxf=save_part_render_data_dxf,
        pre_commit_guard=pre_commit_guard, overwrite=overwrite,
        durable_stage_commit=durable_stage_commit,
    )


def resolved_manufacturing_nc_capability() -> dict[str, object]:
    return _manufacturing_export.resolved_manufacturing_nc_capability()


def verify_saved_part_render_data_dxf(
    render_data: PartRenderData,
    output_path: str | os.PathLike[str],
    *,
    coordinate_tolerance: float = 1e-6,
    area_tolerance: float = 1e-6,
):
    """Public manufacturing boundary for independent saved-DXF acceptance."""
    return _manufacturing_verification.verify_saved_part_render_data_dxf(
        render_data,
        output_path,
        coordinate_tolerance=coordinate_tolerance,
        area_tolerance=area_tolerance,
    )


def verify_saved_resolved_manufacturing_geometry_dxf(
    resolved_geometry,
    output_dir: str | os.PathLike[str],
    *,
    coordinate_tolerance: float = 1e-6,
    area_tolerance: float = 1e-6,
    instance_namespace: str | None = None,
):
    """Reopen and verify every canonical physical-part DXF as one acceptance set."""
    return _manufacturing_verification.verify_saved_resolved_manufacturing_geometry_dxf(
        resolved_geometry,
        output_dir,
        resolved_physical_render_parts=_resolved_physical_render_parts,
        resolved_physical_dxf_filename=_resolved_physical_dxf_filename,
        verify_part_dxf=verify_saved_part_render_data_dxf,
        coordinate_tolerance=coordinate_tolerance,
        area_tolerance=area_tolerance,
        instance_namespace=instance_namespace,
    )

def verify_saved_resolved_manufacturing_geometry_batch_dxf(
    instances,
    output_dir: str | os.PathLike[str],
    *,
    coordinate_tolerance: float = 1e-6,
    area_tolerance: float = 1e-6,
):
    """Reopen and verify an exact namespaced multi-instance DXF inventory."""
    return _manufacturing_verification.verify_saved_resolved_manufacturing_geometry_batch_dxf(
        instances,
        output_dir,
        resolved_physical_render_parts=_resolved_physical_render_parts,
        resolved_physical_dxf_filename=_resolved_physical_dxf_filename,
        verify_part_dxf=verify_saved_part_render_data_dxf,
        coordinate_tolerance=coordinate_tolerance,
        area_tolerance=area_tolerance,
    )


def resolved_quantity_physical_demands(versions, *, per_box_counts=None):
    """Project quantity demand using the canonical physical inventory."""
    from .manufacturing_quantity import resolved_quantity_physical_demands as project
    return project(versions, per_box_counts=per_box_counts)



def group_quantity_physical_demands(demands, parameters_by_source):
    from .manufacturing_equivalence import group_quantity_physical_demands as group
    return group(demands, parameters_by_source)


def save_quantity_manufacturing_groups_dxf(
    groups, output_dir, *, overwrite=False, render_data_transform=None,
    part_only: bool = False,
):
    return _manufacturing_export.save_quantity_manufacturing_groups_dxf(
        groups, output_dir, save_part_render_data_dxf=save_part_render_data_dxf,
        verify_part_dxf=verify_saved_part_render_data_dxf,
        overwrite=overwrite, render_data_transform=render_data_transform,
        part_only=part_only,
    )


# Import the NFB source verifier only after manufacturing scene/render APIs are
# fully initialized: the existing source-profile reader consumes those exports.
from .receiving_nfb_quantity_partial import (
    QuantityNfbPartialSelection, verify_quantity_nfb_inner_door,
    select_quantity_nfb_partial, quantity_partial_live_manifests,
)
