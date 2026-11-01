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
from .door_layout_numeric_transitions import (
    DoorLayoutColumnState, DoorLayoutResolvedColumn,
    DoorLayoutRecomputeResult, DoorLayoutCommitValidation,
)
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
    apply_box_body_structure_numeric,
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
    selection_from_raw as endcap_corner_selection_from_raw,
    selection_to_raw as endcap_corner_selection_to_raw,
    legacy_corner_projection_for_intent as legacy_endcap_corner_projection_for_intent,
    apply_box_assembly_type_to_raw_state as apply_endcap_box_assembly_type_to_raw_state,
    normalize_endcap_fw_state,
    resolve_endcap_fw, resolve_endcap_assembly_type, build_endcap_xy_fold_profiles,
    endcap_profiles_for_assembly,
    ENDCAP_FW_PARTS, FW_FOLLOW_BODY, FW_FOLLOW_HEAD, FW_FOLLOW_TAIL,
    FW_INDEPENDENT, ENDCAP_FW_MODES, commit_box_fw, commit_endcap_fw,
    set_endcap_fw_follow, set_endcap_fw_override,
    endcap_editor_fold_tabs, normalize_endcap_profile_order,
)
from .cabinet_family_model_transition import (
    FamilyModelTransition, FamilyModelPlan, plan_cabinet_family_model_transition,
)
from .assembly_intent_transactions import (
    AssemblyIntentTransition, normalize_assembly_type, commit_assembly_intent_state,
)
from .corner_type_ui import corner_policy_from_payload, resolve_live_corner_policy
from .corner_state_transactions import (
    CornerStateTransition, MANUAL_CORNER_KEYS, MANUAL_CORNER_PAIR_KEYS,
    ensure_corner_part, corner_selection, corner_targets, commit_corner_pair,
    commit_corner_type, commit_corner_mode, commit_corner_parameters, apply_corner_preset,
)
from .endcap_bottom_wrap_state import (
    WRAP_LINKED, WRAP_FOLLOW_HEAD, WRAP_FOLLOW_TAIL, WRAP_INDEPENDENT,
    ENDCAP_BOTTOM_WRAP_MODES, normalize_endcap_bottom_wrap_state,
    resolve_endcap_bottom_wrap, commit_endcap_bottom_wrap_joint,
    commit_endcap_bottom_wrap,
)
from .endcap_xy_readback import (
    fold_material_segment_outside_length, resolve_endcap_xy_outside_dimensions,
    endcap_derived_core_lengths, reconcile_endcap_live_outside_dimensions,
)
from .endcap_editor_fold import (
    build_endcap_editor_simple_profile, read_endcap_editor_simple_profile,
)
from .box_body_editor_readback import (
    reverse_box_body_fold_traversal, box_body_piece_editor_profiles,
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
from .corner_dimension_projection import (
    RenderCornerDimensionGroup, project_render_corner_relief_measurements,
)
from .physical_sheet_editor_context import (
    PhysicalSheetEditorContext, resolve_physical_sheet_editor_context,
)
from .indicator_editor_geometry import resolve_indicator_editor_components
from .receiving_endcap_feature_preview import receiving_endcap_feature_preview_shapes
from .receiving_ear_side_preview import project_receiving_ear_side_piece_2d_preview
from .receiving_single_bay_door_snapshot import (
    project_receiving_single_bay_door_controls,
)
from .receiving_nfb_verified_scope import (
    NfbCsvVerifiedPhysicalSite, NfbCsvVerifiedExportScope,
    NfbCsvVerifiedSelectorProof, resolve_verified_csv_v5_export_scope,
    capture_verified_csv_v5_pair_display_proof, verified_csv_v5_operator_label,
)
from .receiving_nfb_v5_source_preview import (
    ReceivingNfbV5SourcePreview, ReceivingNfbV5SourcePreviewCache,
)
from .receiving_inner_door_inventory import (
    ReceivingInnerDoorInventoryLayer, resolve_receiving_inner_door_preview_inventory,
)
from .receiving_inner_door_editor import (
    InnerDoorHoleEditorContext, resolve_inner_door_hole_editor_context,
)
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
from .cabinet_types.policy import door_material_frame_width



from .display_dimensions import resolve_live_operator_finished_dimensions
from .live_cabinet_family import resolve_live_cabinet_family
from .assembly_mesh_profiles import resolve_material_mesh_profiles
from .standard_part_fold_profiles import build_standard_part_fold_profiles
from .standard_part_fold_readback import read_standard_part_fold_profiles
from .custom_part_catalog import (
    PREFIX as CUSTOM_PART_PREFIX, PRESET as CUSTOM_PART_PRESET,
    CustomPartCatalog, is_custom_part, custom_part_only_change,
)
from .custom_fold_api import (
    descriptor_from_snapshot, build_custom_part_profiles, custom_part_spec,
)
from .keyed_fold_reconciliation import merge_keyed_fold_profiles
from .relief_commit_policy import (
    endcap_relief_solution_committable, endcap_relief_transaction_committable,
)
from .endcap_assembly_resolution import (
    solve_endcap_assembly_relief, endcap_relief_solution_diagnostic,
)
from .manufacturing_cache_signature import (
    canonical_manufacturing_signature_value, manufacturing_state_fingerprint,
)
from .physical_part_identity import is_box_body_physical_piece_key, is_derived_physical_part_key

from .part_dimension_projection import (
    DoorPartProjection, door_part_projections, project_part_dimensions,
)

from .fold_designer_baseline_api import (
    fold_designer_secondary_scene_rows, query_fold_designer_baseline_rows,
    project_finished_features_to_legacy_renderer_holes,
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
    indicator_small_door_operator_spec,
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


from .divider_manufacturing import resolve_family_divider_reliefs
from .assembly_collision import (
    apply_verified_joint_cut_to_part, apply_verified_joint_cut_to_owner,
)
from .assembly_collision import (
    serialize_joint_relief_polygons, restore_joint_relief_cut_geometry,
)
from .endcap_verified_replay import replay_resolved_endcap_render
from .assembly_geometry import build_joint_world_geometry
from .assembly_geometry_folded_mesh import (
    expand_box_body_fw_world_mid, shift_multistage_terminal_fold_world_mid,
    fit_receiving_left_zl1_world_mid,
)
from .assembly_joint import (
    side_wrap_target_corners, resolve_box_body_piece_solver_key,
    joint_relief_state_item_matches, resolve_manufacturing_joint_graph,
)
from .assembly_joint import joint_registry_diagnostic_info
from .manufacturing_relief_evidence import resolve_manufacturing_relief_evidence
from .resolved_manufacturing_parts import materialize_resolved_manufacturing_parts
from .explicit_joint_pipeline import (
    EXPLICIT_JOINT_PIPELINE_STAGES,
    ExplicitJointPipelineOps,
    ExplicitJointPipelineRequest,
    ExplicitJointCandidateInventory,
    ExplicitJointOwnerDecision,
    normalize_candidate_inventory,
    decide_owner_registry,
    query_world_geometry,
    solve_explicit_joint_candidate,
    apply_resolved_cut,
    assemble_diagnostics_evidence,
    assemble_mutation_result,
    resolve_explicit_joint_reliefs,
    resolve_manufacturing_explicit_joint_reliefs,
)
from .assembly_placement import (
    SCENE_ASSEMBLY_PLACEMENTS, resolve_legacy_door_cell_scene_placement,
    resolve_scene_assembly_placement,
)
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

def rebase_receiving_set_parent_nfb_brand(set_row, proposed_brand):
    """Public Engine NFB brand proof transition; lazy owner import avoids a cycle."""
    from .receiving_nfb_brand_transition import (
        rebase_receiving_set_parent_nfb_brand as _engine_rebase,
    )
    return _engine_rebase(set_row, proposed_brand)

def candidate_committed_csv_nfb_config(source):
    """Public Engine NFB candidate provenance query (deferred owner import)."""
    from .receiving_nfb_csv_committed_config import candidate_committed_csv_nfb_config as resolve
    return resolve(source)


def validate_candidate_nfb_replacement(
    layout, selected_bays, source, csv_config, *, rejection_message=None,
):
    """Public Engine guard for submitted NFB source replacement."""
    from .receiving_nfb_csv_committed_config import validate_candidate_nfb_replacement as validate
    if rejection_message is None:
        return validate(layout, selected_bays, source, csv_config)
    return validate(
        layout, selected_bays, source, csv_config, rejection_message=rejection_message,
    )


def replace_candidate_bay_nfb(layout, set_index, bay_index, csv_config):
    """Public Engine physical Bay identity and NFB state transaction."""
    from .receiving_nfb_csv_committed_config import replace_candidate_bay_nfb as replace
    return replace(layout, set_index, bay_index, csv_config)

def apply_receiving_inner_door_quantity_configuration(
    layout, library, quantities, assigned, *, expected_counts=None,
):
    """Headless public Engine API for atomic cross-Set/Bay candidate Apply."""
    from .receiving_inner_door_pairing import (
        apply_receiving_inner_door_quantity_configuration as _apply,
    )
    return _apply(
        layout, library, quantities, assigned, expected_counts=expected_counts,
    )

def apply_receiving_endcap_quantity_configuration(
    layout, role, library, quantities, assigned, *, expected_counts=None,
):
    """Public Engine Head/Tail cross-Set quantity allocation transaction."""
    from .receiving_quantity_allocation import (
        apply_receiving_endcap_quantity_configuration as _apply,
    )
    return _apply(
        layout, role, library, quantities, assigned,
        expected_counts=expected_counts,
    )

def apply_receiving_endcap_candidate_to_bays(
    layout, role, set_index, bay_indices, features, *, version_id=None,
):
    """Public Engine Head/Tail candidate Apply to highlighted physical Bays."""
    from .receiving_quantity_allocation import (
        apply_receiving_endcap_candidate_to_bays as _apply,
    )
    return _apply(
        layout, role, set_index, bay_indices, features, version_id=version_id,
    )

def mark_receiving_bays_live_version(layout, role, set_index, bay_indices):
    """Public headless Engine transition for highlighted Live version provenance."""
    from .receiving_version_transactions import mark_receiving_bays_live_version as _mark
    return _mark(layout, role, set_index, bay_indices)

def apply_receiving_inner_door_candidate_to_bays(layout, config, set_index, bay_indices, *, version_id=None):
    """Public Engine API: one source-backed inner-door candidate Apply."""
    from .receiving_inner_door_pairing import (
        apply_receiving_inner_door_candidate_to_bays as _apply,
    )
    return _apply(layout, config, set_index, bay_indices, version_id=version_id)

def apply_receiving_bay_dimensions(
    layout, set_index, bay_indices, *, width, height, depth, expected_count,
):
    """Public Engine atomic Receiving Bay W/H/D and NFB X proof transition."""
    from .receiving_layout import apply_receiving_bay_dimensions as _apply
    return _apply(
        layout, set_index, bay_indices, width=width, height=height,
        depth=depth, expected_count=expected_count,
    )

def resize_receiving_bays_with_family_defaults(layout, *, set_index, bay_count):
    """Public Engine Receiving Family default projection on new Bay creation."""
    from .receiving_layout import resize_receiving_bays_with_family_defaults as resize
    return resize(layout, set_index=set_index, bay_count=bay_count)

def receiving_inner_door_stable_id_for_cell(cell_key):
    """Public physical inner-door stable identity for an authored Door cell."""
    from .door_layout_physical_remap import receiving_inner_door_stable_id_for_cell as resolve
    return resolve(cell_key)


def remap_receiving_door_layout_after_delete(
    *, operation, column_index, row_index=None, inner_doors=None,
    cell_sources=None, physical_sources=None, cell_transitions=None,
):
    """Public Engine atomic Door-grid deletion/physical-source remap."""
    from .door_layout_physical_remap import remap_receiving_door_layout_after_delete as remap
    return remap(
        operation=operation, column_index=column_index, row_index=row_index,
        inner_doors=inner_doors, cell_sources=cell_sources,
        physical_sources=physical_sources, cell_transitions=cell_transitions,
    )

def recompute_door_layout(columns, *, total_width, total_height, selected_key):
    """Public Engine operator Door W/H partition/remainder transaction."""
    from .door_layout_numeric_transitions import recompute_door_layout as compute
    return compute(
        columns, total_width=total_width, total_height=total_height,
        selected_key=selected_key,
    )


def door_layout_cells(columns, *, total_width, total_height):
    """Public Engine projection of canonical Door W/H source cells."""
    from .door_layout_numeric_transitions import door_layout_cells as project
    return project(columns, total_width=total_width, total_height=total_height)


def validate_door_layout_width_commit(columns, column_index, total_width, current):
    """Public Engine guard for Door column W operator edits."""
    from .door_layout_numeric_transitions import validate_width_commit as validate
    return validate(columns, column_index, total_width, current)


def validate_door_layout_height_commit(
    columns, column_index, row_index, total_height, current,
):
    """Public Engine guard for Door row H operator edits."""
    from .door_layout_numeric_transitions import validate_height_commit as validate
    return validate(columns, column_index, row_index, total_height, current)

def validate_receiving_base_plate_settings(
    *, input_snapshot, settings_values, config,
):
    """Public Engine physical Receiving Base Plate and weld-EAR preflight."""
    from .receiving_base_plate_settings_validation import (
        validate_receiving_base_plate_settings as validate,
    )
    return validate(
        input_snapshot=input_snapshot, settings_values=settings_values,
        config=config,
    )

def normalize_receiving_switch_operator_layout(layout):
    """Public Engine port for Receiving Switch input topology state."""
    from .receiving_switch_layout import normalize_receiving_switch_layout
    return normalize_receiving_switch_layout(layout)


def apply_receiving_switch_operator_action(
    layout, *, operation, brand=None, layer_index=None, delta=None,
):
    """Public Engine transaction for physical Receiving Switch input edits."""
    from .receiving_switch_layout import apply_receiving_switch_operator_action as apply
    return apply(
        layout, operation=operation, brand=brand,
        layer_index=layer_index, delta=delta,
    )

def resolve_fold_designer_divider_part(part_key, divider_input):
    """Public Engine selection of one canonical Box Body Divider physical part."""
    from .fold_designer_physical_selection import resolve_fold_designer_divider_part as resolve
    return resolve(part_key, divider_input)


def resolve_fold_designer_frame_part(part_key, payload, *, default_thickness):
    """Public Engine Family/legacy inner-door frame physical-part selection."""
    from .fold_designer_physical_selection import resolve_fold_designer_frame_part as resolve
    return resolve(part_key, payload, default_thickness=default_thickness)


def resolve_fold_designer_panel_part(part_key, payload):
    """Public Engine inner-door panel identity from canonical Family topology."""
    from .fold_designer_physical_selection import resolve_fold_designer_panel_part as resolve
    return resolve(part_key, payload)



from .fold_designer_snapshot_dimensions import FoldDesignerSnapshotDimensions


def project_fold_designer_snapshot_dimensions(snapshot, indicator_layer_groups):
    """Public Engine ownership for original Fold Designer snapshot part sizes."""
    from .fold_designer_snapshot_dimensions import project_fold_designer_snapshot_dimensions as project
    return project(snapshot, indicator_layer_groups)



def project_fold_designer_snapshot_part_features(
    snapshot, surface_features, door_layout_features,
):
    """Public headless Door-grid Feature source-to-physical identity projection."""
    from .door_layout_feature_projection import project_fold_designer_snapshot_part_features as project
    return project(snapshot, surface_features, door_layout_features)


# #2517: canonical Fold material/formed coordinate mapping exposed to GUI clients.

def fold_profile_base_index(profile):
    """Public Engine Fold mapping; canonical assembly_geometry_folded_mesh owns math."""
    from .assembly_geometry_folded_mesh import _profile_base_index as resolve
    return resolve(profile)


def fold_profile_geometry(profile, *, enabled_folds=None):
    """Public Engine Fold mapping; canonical assembly_geometry_folded_mesh owns math."""
    from .assembly_geometry_folded_mesh import _profile_geometry as resolve
    return resolve(profile, enabled_folds=enabled_folds)


def fold_profile_bend_mask(profile, axis, cross_position, fold_guides, *, tol=1e-6):
    """Public Engine Fold mapping; canonical assembly_geometry_folded_mesh owns math."""
    from .assembly_geometry_folded_mesh import _fold_mask_for_cross_coordinate as resolve
    return resolve(profile, axis, cross_position, fold_guides, tol=tol)


def fold_profile_map_with_guides(position, cross_position, profile, *, axis, fold_guides):
    """Public Engine Fold mapping; canonical assembly_geometry_folded_mesh owns math."""
    from .assembly_geometry_folded_mesh import _profile_map_with_guides as resolve
    return resolve(position, cross_position, profile, axis=axis, fold_guides=fold_guides)


def fold_profile_map(position, boundaries, folded):
    """Public Engine Fold mapping; canonical assembly_geometry_folded_mesh owns math."""
    from .assembly_geometry_folded_mesh import _profile_map as resolve
    return resolve(position, boundaries, folded)


def fold_profile_flat_map(position, boundaries, *, profile=None):
    """Public Engine Fold mapping; canonical assembly_geometry_folded_mesh owns math."""
    from .assembly_geometry_folded_mesh import _profile_flat_map as resolve
    return resolve(position, boundaries, profile=profile)



def prepare_fold_profile_mapper(profile, *, axis, fold_guides=()):
    """Prepare one Engine-owned fold mapper per rendered source, not per vertex.

    Same bounded mask/chain memoization as actual canonical assembly mesh; the
    caller must replace it whenever any source profile or BEND guide changes.
    """
    from .assembly_geometry_folded_mesh import _profile_geometry, _prepare_profile_mapper
    rows = tuple(profile or ())
    guides = tuple(fold_guides or ())
    return _prepare_profile_mapper(
        rows, axis=axis, fold_guides=guides, geometry=_profile_geometry(rows),
    )

def physical_solid_mesh_feature_segments(triangles, *, tolerance=1e-6):
    """Public Engine physical solid mesh feature-boundary projection."""
    from .solid_mesh_feature_edges import physical_solid_mesh_feature_segments as resolve
    return resolve(triangles, tolerance=tolerance)



def build_door_operator_part_spec(
    values, *, model_name, features=(), indicator_hole=None,
    door_indicator=None, door_indicator_offset=(0.0, 0.0),
    use_box_distance=False, corner_policy=None, frame_edges=None,
    indicator_window_groups=None, nameplate_center_datum_top=None,
) -> DoorPartSpec:
    """Public Engine-owned Door operator → canonical manufacturing PartSpec."""
    from .door_operator_part_spec import build_door_operator_part_spec as build
    return build(
        values, model_name=model_name, features=features,
        indicator_hole=indicator_hole, door_indicator=door_indicator,
        door_indicator_offset=door_indicator_offset,
        use_box_distance=use_box_distance, corner_policy=corner_policy,
        frame_edges=frame_edges,
        indicator_window_groups=indicator_window_groups,
        nameplate_center_datum_top=nameplate_center_datum_top,
    )

# #2517: physical Receiving NFB highlighted partial DXF batch is Engine-owned.
# The GUI import path is a compatibility facade, never a second release gate.
from .receiving_nfb_partial_batch_dispatcher import (
    require_highlighted_nfb_inner_doors,
    export_highlighted_nfb_inner_doors,
)


# #2517: paired real NFB PART_ONLY CHECK/Q belongs exclusively to Engine.
from .receiving_nfb_pair_quantity_check import (
    NfbPairedPartOnlyDxf, NfbPairedQuantityInput, NfbPairedQuantityCheck,
    group_reopened_nfb_pair_check_q, save_checked_reopened_nfb_pair_q_dxf,
)


# #2517: Source-current Receiving NFB BasePlate physical PART_ONLY release.
from .receiving_nfb_base_partial_export import (
    nfb_verification_geometry_changed,
    prepare_verified_receiving_nfb_base_plate,
    export_verified_receiving_nfb_base_plate,
)


# #2517: Engine is the only Receiving NFB real partial inner-door exporter.
from .receiving_nfb_inner_door_partial_export import (
    export_verified_receiving_nfb_inner_door,
)


# #2517: Receiving original-source / CSV V5 pair PART_ONLY actual DXF ownership.
# Existing GUI entry re-exports these typed Engine operations without manufacture.
from .receiving_nfb_pair_export import (
    export_verified_receiving_nfb_door_base_pair,
    NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
    export_current_csv_nfb_door_base_pair,
)


# #2517: read-only Receiving NFB physical-manifest safety before GUI disclosure.
from .receiving_nfb_manifest_validation import (
    validate_receiving_nfb_manifest_view,
    validate_receiving_nfb_highlighted_manifest,
)

# Canonical Engine owner for Door/BasePlate/Divider/InnerDoor physical namespaces,
# retired GUI-owned immutable request/sync intent builder (#2517).
from .derived_part_projection import (
    FrozenMappingValue,
    FrozenSequenceValue,
    DerivedPartProfileProjection,
    DerivedPartFeatureProjection,
    DerivedPartNamespaceProjection,
    DerivedPartProjectionRequest,
    DerivedPartRequestAssemblyInput,
    DerivedPartSyncPlan,
    build_derived_part_projection_request,
    build_derived_part_sync_plan,
    profile_projection,
    feature_projection,
    namespace_projection,
    materialize_profiles,
    materialize_features,
    materialize_namespace,
)



def build_box_body_operator_part_spec(
    values, *, model_name, features=(), face_features=None,
    head_corner_policy=None, tail_corner_policy=None, fold_profile=(),
    structure_state=None, source_part_features=None,
    endcap_y_profiles=None, head_ybottom1=None, tail_ybottom1=None,
    snapshot=None,
) -> BoxBodyPartSpec:
    """Public Engine physical BoxBodyPartSpec operator/family projection."""
    from .box_body_operator_part_spec import build_box_body_operator_part_spec as build
    return build(
        values, model_name=model_name, features=features,
        face_features=face_features,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
        fold_profile=fold_profile, structure_state=structure_state,
        source_part_features=source_part_features,
        endcap_y_profiles=endcap_y_profiles,
        head_ybottom1=head_ybottom1, tail_ybottom1=tail_ybottom1,
        snapshot=snapshot,
    )


# #2517 Receiving CSV V5 physical BasePlate trial/source & display gate.
# Public, GUI-independent: never a manufacturing/DXF certification.
from .receiving_nfb_v5_operator_preview import (
    preview_receiving_nfb_v5_real_base_sources,
    require_receiving_nfb_v5_inner_door_trial_preview,
    require_receiving_nfb_v5_base_trial_preview,
)


# #2517: Receiving side EAR read-only 2D/3D source identity and cache stamp.
from .receiving_ear_side_display_context import (
    ReceivingEarSideDisplayContext,
    resolve_receiving_ear_side_display_context,
)

# #2517: read-only world XY physical-feature projection for Receiving settings.
from .receiving_settings_orthographic_projection import project_solid_mesh_xy_outline

def resolve_box_body_formed_width_datum(pieces):
    """Public Engine authority for physical multipart Box Body outside W datum."""
    from .box_body_world_datum import resolve_box_body_formed_width_datum as resolve
    return resolve(pieces)
