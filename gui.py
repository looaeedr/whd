# -*- coding: utf-8 -*-
"""
箱體展開圖計算器 - GUI 介面
"""

import tkinter as tk
from gui_modules.parts.panels.indicator_box import collect_indicator_box_input
from gui_modules.parts.panels.multipart import collect_multipart_input
from gui_modules.parts.panels.door import (
    collect_door_input,
    normalize_door_indicator_state as _normalize_door_indicator_state_impl,
    destroy_door_layout_entry_widgets as _destroy_door_layout_entry_widgets_impl,
    door_layout_entry_menu as _door_layout_entry_menu_impl,
    rebuild_door_layers_config_ui as _rebuild_door_layers_config_ui_impl,
)
import time
import sys
from pathlib import Path
from copy import deepcopy
from phase6_sync_envelope import stable_fingerprint
from dataclasses import replace
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS, apply_ttk_dark_theme
import ae_engine.ae as ae  # AE manufacturing engine package
from ae_engine import manufacturing_api
from ae_engine.engineering_drawing import build_engineering_drawing_projection
from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from ae_engine.cabinet_types import (
    policy as cabinet_family_policy,
    registered_cabinet_types,
    resolve_cabinet_type,
)

PHASE6_BUILD_ID = "RECEIVING_MODEL_SINGLE_SOURCE_20260824_0701"
from ae_engine.contracts import (
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    IndicatorBoxPartSpec,
    ManufacturingContext,
)
from ae_engine.sheetmetal_geometry import (
    Vec2,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    CornerDirection,
    EDITABLE_CORNER_TYPE_IDS,
    CORNER_TYPE_LABELS,
    normalize_corner_selection,
    box_body_vertical_offsets,
)
from ae_engine.sheetmetal_features import (
    box_body_face_dimensions,
    box_body_face_contexts_from_strip,
    resolve_box_body_face_features,
    CanvasTransform,
    CircleFeature,
    DoorIndicatorContext,
    RectFeature,
    ProfileFeature,
    legacy_hole_to_feature,
    resolve_door_indicator_features,
    resolve_door_indicator_layout,
    measure_door_indicator_position,
    door_indicator_offset_for_position,
    door_enclosure_reference_offsets,
    door_enclosure_reference_guide,
    resolve_features_in_finished_face,
    resolve_base_plate_mounting_holes,
    resolved_circles_from_baseline,
    resolve_vault_endcap_fixed_features,
    resolve_endcap_finished_face_guide,
    resolve_door_indicator_dimension_guides,
    FeatureAnchor,
    placement_from_finished_point,
    feature_finished_point,
    move_feature_to_finished_point,
    reanchor_feature,
    build_feature_placement_guides,
    feature_to_legacy_hole,
    feature_with_offset,
    expand_linear_pattern,
    expand_grid_pattern,
    ResolvedCircle,
    ResolvedRect,
    ResolvedProfile,
    resolve_endcap_features,
    endcap_feature_context_from_geometry,
    feature_surface_from_rect,
    feature_is_within_surface,
    move_feature_within_surface,
    feature_surface_from_structural_result,
    feature_surface_from_outline,
    resolve_surface_features,
    ReferenceAnchor,
    REFERENCE_ANCHOR_LABELS,
    REFERENCE_ANCHOR_BY_LABEL,
    feature_reference_anchor,
    feature_with_reference_anchor,
    feature_reference_point,
    reference_distances,
    move_feature_by_reference_distance,
    feature_with_process,
    circle_center_distance_from_gap,
    circle_gap_from_center_distance,
    align_circle_to_neighbor,
    generate_round_fill,
    generate_round_refill,
    RectGuide,
)


from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    derive_door_layout_cells,
    validate_door_layout_dimensions,
    complete_partition,
    door_layout_export_filename,
    door_layout_feature_map_to_part_features,
    door_part_features_to_layout_feature_map,
    build_box_body_result,
    build_box_body_result_from_fold_profile,
    build_door_result,
    build_base_plate_result,
    build_indicator_box_result,
    build_endcap_result,
    build_unknown_door_result,
    build_unknown_base_plate_result,
    build_unknown_indicator_box_result,
    build_unknown_endcap_result,
    build_finished_reference_guide,
)


from ae_engine.corner_type_ui import (
    UNKNOWN_MODEL_NAME,
    CUSTOM_MODEL_NAME,
    CORNER_KEYS,
    CORNER_LABELS,
    CORNER_PAIR_CORNERS,
    apply_manual_corner_selection,
    with_unknown_model,
    is_unknown_model,
    normalize_custom_model_name,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
    known_model_corner_state,
    policy_from_corner_state,
    set_manual_corner_pair_same,
    build_corner_type_preview_geometry,
    apply_box_assembly_type, assembly_type_from_corner_state,
)


from gui_modules.editors.dialogs import ask_xy_dialog as _ask_xy_dialog_impl
from gui_modules.editors.hole_editor import (
    HoleEditorContextSwitcher as _HoleEditorContextSwitcher,
    HoleEditorLiveContext as _HoleEditorLiveContext,
    HoleEditorSessionFactory as _HoleEditorSessionFactory,
    HoleEditorCanvasPointerActions as _HoleEditorCanvasPointerActions,
    HoleEditorCreatedListActions as _HoleEditorCreatedListActions,
    HoleEditorFeatureFactory as _HoleEditorFeatureFactory,
    HoleEditorIndicatorFitValidation as _HoleEditorIndicatorFitValidation,
    HoleEditorModalLifecycle as _HoleEditorModalLifecycle,
    HoleEditorReferenceActions as _HoleEditorReferenceActions,
    HoleEditorSelectedFeatureActions as _HoleEditorSelectedFeatureActions,
    HoleEditorTransientActions as _HoleEditorTransientActions,
    open_hole_editor as _open_hole_editor_impl,
    open_part_hole_editor as _open_part_hole_editor_impl,
)
from gui_modules.editors.hole_editor_composition import HoleEditorCompositionDependencies as _HoleEditorCompositionDependencies, open_unified_hole_editor as _open_unified_hole_editor_impl
from gui_modules.editors.hole_editor_render import HoleEditorCanvasRenderer as _HoleEditorCanvasRenderer
from gui_modules.editors.hole_editor_view import (
    HoleEditorCanvasViewFactory as _HoleEditorCanvasViewFactory,
    HoleEditorWindowShellBuilder as _HoleEditorWindowShellBuilder,
    HoleEditorCatalogControls as _HoleEditorCatalogControls,
    HoleEditorCatalogSidebarBuilder as _HoleEditorCatalogSidebarBuilder,
    HoleEditorCenterWorkspaceBuilder as _HoleEditorCenterWorkspaceBuilder,
    HoleEditorCreatedListPresentation as _HoleEditorCreatedListPresentation,
    HoleEditorFormRowBuilders as _HoleEditorFormRowBuilders,
    HoleEditorFullscreenActions as _HoleEditorFullscreenActions,
    HoleEditorIndicatorContextRefresh as _HoleEditorIndicatorContextRefresh,
    HoleEditorIndicatorGroupControls as _HoleEditorIndicatorGroupControls,
    HoleEditorIndicatorPanelBuilder as _HoleEditorIndicatorPanelBuilder,
    HoleEditorIndicatorStateCollector as _HoleEditorIndicatorStateCollector,
    HoleEditorIndicatorUiActions as _HoleEditorIndicatorUiActions,
    HoleEditorPageNavigation as _HoleEditorPageNavigation,
    HoleEditorReferencePresentation as _HoleEditorReferencePresentation,
    HoleEditorRoundSettingsLauncher as _HoleEditorRoundSettingsLauncher,
    HoleEditorSyncCoordinator as _HoleEditorSyncCoordinator,
    draw_hole_editor_hint as _draw_hole_editor_hint_impl,
    open_round_hole_settings as _open_round_hole_settings_impl,
)

from gui_modules.drawing import (
    _corner_preview_canvas_point,
    _corner_preview_flip_y_for_target,
    render_drawing_scene,
)

from gui_modules.application.render_snapshots import (
    indicator_box_render_snapshot as _indicator_box_render_snapshot_impl,
    indicator_door_render_snapshot as _indicator_door_render_snapshot_impl,
    door_layout_overview_snapshot as _door_layout_overview_snapshot_impl,
    door_layout_divider_frame_snapshot as _door_layout_divider_frame_snapshot_impl,
    single_door_render_snapshot as _single_door_render_snapshot_impl,
    base_plate_render_snapshot as _base_plate_render_snapshot_impl,
    box_body_render_snapshot as _box_body_render_snapshot_impl,
    end_cap_render_snapshot as _end_cap_render_snapshot_impl,
)

from gui_modules.rendering import (
    _rects_overlap,
    layout_reference_overlay_rects as _layout_reference_overlay_rects_impl,
    render_structural_result as _render_structural_result_impl,
    render_secondary_scene as _render_secondary_scene_impl,
    render_resolved_features as _render_resolved_features_impl,
    render_surface_user_features as _render_surface_user_features_impl,
    feature_surface_from_drawing_scene as _feature_surface_from_drawing_scene_impl,
    draw_phase6_annotation_projection as _draw_phase6_annotation_projection_impl,
    draw_phase6_corner_dimension_overlay as _draw_phase6_corner_dimension_overlay_impl,
    YMirroredPreviewTransform as _YMirroredPreviewTransform,
    phase6_2d_material_viewport as _phase6_2d_material_viewport_impl,
    draw_preview_error as _draw_preview_error_impl,
    draw_indicator_box_preview as _draw_indicator_box_preview_impl,
    draw_indicator_door_preview as _draw_indicator_door_preview_impl,
    draw_single_door_preview as _draw_single_door_preview_impl,
    draw_base_plate_preview as _draw_base_plate_preview_impl,
    draw_door_layout_error as _draw_door_layout_error_impl,
    draw_door_layout_overview_preview as _draw_door_layout_overview_preview_impl,
    draw_door_layout_dividers_and_frames_preview as _draw_door_layout_dividers_and_frames_preview_impl,
    door_layout_cell_at_canvas_point as _door_layout_cell_at_canvas_point_impl,
    on_door_canvas_press as _on_door_canvas_press_impl,
    on_door_canvas_drag as _on_door_canvas_drag_impl,
    on_door_canvas_release as _on_door_canvas_release_impl,
    on_door_canvas_double_click as _on_door_canvas_double_click_impl,
    box_body_face_at_canvas_point as _box_body_face_at_canvas_point_impl,
    select_box_body_face as _select_box_body_face_impl,
    on_box_body_canvas_press as _on_box_body_canvas_press_impl,
    draw_preview as _draw_preview_route_impl,
    open_box_body_face_editor as _open_box_body_face_editor_impl,
    draw_box_body_piece_preview as _draw_box_body_piece_preview_impl,
    draw_box_body_aggregate_preview as _draw_box_body_aggregate_preview_impl,
    draw_end_cap_preview as _draw_end_cap_preview_impl,
    draw_end_cap_error as _draw_end_cap_error_impl,
    box_body_baseline_faces as _box_body_baseline_faces_impl,
)


def layout_reference_overlay_rects(*args, **kwargs):
    kwargs.setdefault("overlap_fn", _rects_overlap)
    return _layout_reference_overlay_rects_impl(*args, **kwargs)


def render_structural_result(canvas, result, transform, tags=None):
    return _render_structural_result_impl(canvas, result, transform, tags=tags)


def render_secondary_scene(canvas, scene, transform):
    return _render_secondary_scene_impl(
        canvas, scene, transform, scene_renderer=render_drawing_scene
    )


def render_resolved_features(canvas, features, transform, *, color="#ff9f0a"):
    return _render_resolved_features_impl(
        canvas, features, transform, color=color
    )


def render_surface_user_features(canvas, surface, features, width, height, transform):
    return _render_surface_user_features_impl(
        canvas, surface, features, width, height, transform,
        resolver=resolve_surface_features,
        feature_renderer=render_resolved_features,
    )


def feature_surface_from_drawing_scene(surface_id, scene):
    return _feature_surface_from_drawing_scene_impl(
        surface_id, scene, ae_module=ae
    )


def _draw_phase6_annotation_projection(
    canvas, render_data, transform, *, part_key="", strict=False,
):
    return _draw_phase6_annotation_projection_impl(
        canvas, render_data, transform,
        part_key=part_key, strict=strict,
        projection_builder=build_engineering_drawing_projection,
    )


def _draw_phase6_corner_dimension_overlay(canvas, render_data, canvas_width):
    return _draw_phase6_corner_dimension_overlay_impl(
        canvas, render_data, canvas_width,
        text_builder=render_data_corner_dimension_text,
    )


def _phase6_2d_material_viewport(bounds, canvas_width, canvas_height, *, top_gutter=175.0,
                             right_gutter=82.0, bottom_gutter=48.0, left_gutter=48.0):
    kwargs = dict(top_gutter=top_gutter, right_gutter=right_gutter,
                  bottom_gutter=bottom_gutter, left_gutter=left_gutter,
                  transform_type=CanvasTransform)
    return _phase6_2d_material_viewport_impl(bounds, canvas_width, canvas_height, **kwargs)


from gui_modules.layout import (
    _project_toolbar_presentation,
    configure_styles as _configure_layout_styles,
    build_main_layout as _build_main_layout,
)


from gui_modules.part_panels import (
    _phase6_logical_part_present as _phase6_logical_part_present_impl,
)

from gui_modules.parts.panels.assembly_corner import (
    sync_endcap_fw_controls as _sync_endcap_fw_controls_impl,
    sync_fold_designer_manual_corner_context as _sync_fold_designer_manual_corner_context_impl,
    fixed_corner_summary as _fixed_corner_summary_impl,
    normalize_manual_corner_target as _normalize_manual_corner_target_impl,
    corner_parameter_summary as _corner_parameter_summary_impl,
    refresh_corner_type_panel as _refresh_corner_type_panel_impl,
    select_manual_corner as _select_manual_corner_impl,
    draw_corner_type_icon as _draw_corner_type_icon_impl,
    selection_from_manual_corner_controls as _selection_from_manual_corner_controls_impl,
    refresh_manual_corner_parameter_rows as _refresh_manual_corner_parameter_rows_impl,
    toggle_manual_corner_parameter_lock as _toggle_manual_corner_parameter_lock_impl,
    create_corner_type_panel as _create_corner_type_panel_impl,
)

from gui_modules.parts.panels.common import (
    create_input_row as _create_input_row_impl,
    create_result_row as _create_result_row_impl,
    create_separator as _create_separator_impl,
    create_advanced_inputs as _create_advanced_inputs_impl,
    create_sub_input as _create_sub_input_impl,
    toggle_advanced_panel as _toggle_advanced_panel_impl,
)

from gui_modules.parts.panels.common import _attach_part_hole_entrypoint as _attach_part_hole_entrypoint_impl
from gui_modules.parts.panels.door import (
    _parse_layout_value as _parse_layout_value_impl,
    _reject_door_layout_dimension as _reject_door_layout_dimension_impl,
    rebuild_door_layout_ui as _rebuild_door_layout_ui_impl,
    refresh_door_layout_status as _refresh_door_layout_status_impl,
    setup_tab_door_ui as _setup_tab_door_ui_impl,
)
from gui_modules.parts.panels.indicator_box import (
    setup_tab_indicator_box_ui as _setup_tab_indicator_box_ui_impl,
    _indicator_small_door_size_chain_label as _indicator_small_door_size_chain_label_impl,
    setup_tab_indicator_door_ui as _setup_tab_indicator_door_ui_impl,
    rebuild_layers_config_ui as _rebuild_layers_config_ui_impl,
)
from gui_modules.parts.panels.base_plate import sync_base_plate_shrink as _sync_base_plate_shrink_impl

from gui_modules.parts.panels.box_body import setup_tab_z_ui as _setup_tab_z_ui_impl

from gui_modules.parts.panels.endcap import setup_tab_endcap_ui as _setup_tab_endcap_ui_impl

from gui_modules.parts.panels.base_plate import setup_tab_base_plate_ui as _setup_tab_base_plate_ui_impl

from gui_modules.parts.panels.divider import collect_divider_input

from gui_modules.parts.selector import (
    refresh_presence_ui as _refresh_presence_ui_impl,
)
from gui_modules.parts.subtabs import (
    build_box_body_piece_selector,
    box_body_piece_label as _box_body_piece_label_impl,
    box_body_piece_face_key as _box_body_piece_face_key_impl,
    refresh_box_body_piece_tabs_2d as _refresh_box_body_piece_tabs_2d_impl,
    on_box_body_piece_2d_tab_changed as _on_box_body_piece_2d_tab_changed_impl,
    on_box_body_piece_double_click as _on_box_body_piece_double_click_impl,
)

from gui_modules.render_2d import (
    _draw_layout_resolved_features as _draw_layout_resolved_features_impl,
    _draw_layout_baseline_secondary as _draw_layout_baseline_secondary_impl,
    draw_grid as _draw_grid_impl,
)

from gui_modules.project_actions import (
    save_phase6_project_as as _save_phase6_project_as_impl,
    save_phase6_project as _save_phase6_project_impl,
    open_phase6_project as _open_phase6_project_impl,
    load_phase6_project as _load_phase6_project_impl,
)


from ae_engine.hole_catalog import (
    load_hole_catalog,
    load_pipe_catalog,
    feature_from_definition,
    custom_circle_definition,
    custom_rectangle_definition,
)


from fold_designer_bridge import Phase6FoldDesignerApp
from phase6_corner_dimension_display import render_data_corner_dimension_text
from phase6_fold_profiles import (
    profile_to_fold_segments, build_box_body_profile, build_endcap_xy_profiles, build_linked_endcap_xy_profiles,
    engine_segment_length_to_ui, formed_box_body_fw_widths,
)
from phase6_endcap_semantics import (
    resolve_box_assembly_type, ASSEMBLY_TYPE_LABELS, ASSEMBLY_LABEL_TO_TYPE,
    assembly_intent_value, assembly_intent_label, legacy_corner_projection_for_intent,
    normalize_endcap_fw_state, resolve_endcap_fw, set_endcap_fw_follow, set_endcap_fw_override,
    commit_box_fw, commit_endcap_fw,
    normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap,
)
from ae_engine.assembly_joint import (
    migrate_legacy_snapshot_joints, sync_snapshot_intent_joints, ASSEMBLY_JOINT_SCHEMA_VERSION,
)

from phase6_settings_center import (
    GLOBAL_CONTEXT,
    UI_TEXT_SIZE_LABELS,
    normalize_ui_text_size,
    ui_text_size_label,
    ui_text_size_factor,
    SettingsService,
    load_factory_defaults_from_ae,
    load_corner_defaults_from_ini,
    save_corner_defaults_to_ini,
)
from ui_text_scale import TextScaleController
from phase6_project_file import (
    PROJECT_SCHEMA as PHASE6_PROJECT_SCHEMA,
    PROJECT_EXTENSION as PHASE6_PROJECT_EXTENSION,
    read_project as read_phase6_project,
    write_project as write_phase6_project,
    project_path_from_argv,
    register_windows_file_association,
)
from phase6_project_controller import Phase6ProjectController
from phase6_workspace_controller import Phase6WorkspaceController
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from phase6_hole_editor_canvas_view import HoleEditorCanvasFrame

from ae_engine.sheetmetal_drawing import (
    PolylinePrimitive,
    LinePrimitive,
    CirclePrimitive,
    TextPrimitive,
    DrawingScene,
    resolved_features_to_primitives,
    mirror_point_y,
)

from gui_modules.application import lifecycle as _phase6_lifecycle
from gui_modules.application import command_router as _phase6_command_router
from gui_modules.application import state_sync as _phase6_state_sync
from gui_modules.application import cabinet_controller as _phase6_cabinet_controller
from gui_modules.application import calculation_controller as _phase6_calculation_controller
from gui_modules.application import fold_designer_adapter as _phase6_fold_adapter
from gui_modules.application import manufacturing_adapter as _phase6_manufacturing_adapter
from gui_modules.project import export_actions as _phase6_project_export
from gui_modules.visibility import controller as _phase6_visibility
_Phase6UpdateScheduler = _phase6_command_router._Phase6UpdateScheduler
_Phase6DerivedCacheOwner = _phase6_state_sync.Phase6DerivedCacheOwner

























def draw_hole_editor_hint(canvas, canvas_width, *, endcap=False):
    return _draw_hole_editor_hint_impl(canvas, canvas_width, endcap=endcap)






class Phase6ApplicationHost:
    _fold_designer_factory = Phase6FoldDesignerApp
    # #289/T1 application lifecycle delegation; implementations live in focused modules.
    __init__ = _phase6_lifecycle.phase6_application_host_init
    _current_cabinet_type_name = _phase6_lifecycle._current_cabinet_type_name
    _apply_manual_corner_snapshot = _phase6_lifecycle._apply_manual_corner_snapshot
    _apply_fold_designer_live_settings = _phase6_lifecycle._apply_fold_designer_live_settings
    _save_fold_designer_defaults = _phase6_lifecycle._save_fold_designer_defaults
    _apply_fold_designer_live_corner_state = _phase6_lifecycle._apply_fold_designer_live_corner_state
    _notify_fold_designer_corner_state = _phase6_lifecycle._notify_fold_designer_corner_state
    _fold_designer_number_text = staticmethod(_phase6_lifecycle._fold_designer_number_text)
    _apply_existing_parts_from_fold_workspace = _phase6_lifecycle._apply_existing_parts_from_fold_workspace
    _apply_phase6_project_snapshot = _phase6_lifecycle._apply_phase6_project_snapshot
    _compose_phase6_project_snapshot_from_main_gui = _phase6_lifecycle._compose_phase6_project_snapshot_from_main_gui
    _capture_phase6_committed_snapshot = _phase6_lifecycle._capture_phase6_committed_snapshot
    _apply_original_fold_designer_snapshot = _phase6_lifecycle._apply_original_fold_designer_snapshot
    _store_fold_designer_workspace = _phase6_lifecycle._store_fold_designer_workspace
    _apply_fold_designer_live_snapshot = _phase6_lifecycle._apply_fold_designer_live_snapshot
    _apply_fold_designer_corner_transaction = _phase6_lifecycle._apply_fold_designer_corner_transaction
    _reload_current_baseline_features = _phase6_lifecycle._reload_current_baseline_features
    open_original_fold_designer = _phase6_lifecycle.open_original_fold_designer
    _request_phase6_update = _phase6_command_router._request_phase6_update
    _flush_phase6_authoritative_state = _phase6_command_router._flush_phase6_authoritative_state
    bind_live_updates = _phase6_command_router.bind_live_updates
    _fold_designer_secondary_scene_rows = staticmethod(_phase6_fold_adapter._fold_designer_secondary_scene_rows)
    _query_fold_designer_baseline_data = _phase6_fold_adapter._query_fold_designer_baseline_data
    _apply_cabinet_family_endcap_policy = _phase6_fold_adapter._apply_cabinet_family_endcap_policy
    _fold_designer_corner_policy_from_payload = staticmethod(_phase6_fold_adapter._fold_designer_corner_policy_from_payload)
    _authoritative_render_data = _phase6_fold_adapter._authoritative_render_data
    _require_verified_baseline_sources_for_manufacturing = _phase6_fold_adapter._require_verified_baseline_sources_for_manufacturing
    _export_authoritative_part = _phase6_fold_adapter._export_authoritative_part
    _query_fold_designer_render_data = _phase6_fold_adapter._query_fold_designer_render_data
    _fold_designer_part_spec_from_payload = _phase6_fold_adapter._fold_designer_part_spec_from_payload


    @property
    def fold_designer_box_body_profile(self):
        """舊介面相容：箱身 Fold Chain 直接由 Workspace Controller 提供。"""
        return self.workspace_controller.box_body_profile()

    @fold_designer_box_body_profile.setter
    def fold_designer_box_body_profile(self, profile):
        self.workspace_controller.set_box_body_profile(profile)

    @property
    def fold_designer_part_bundle(self):
        """舊介面相容：回傳 defensive-copy bundle，不保存 shadow dict。"""
        return self.workspace_controller.legacy_bundle()

    @fold_designer_part_bundle.setter
    def fold_designer_part_bundle(self, bundle):
        self.workspace_controller.load_legacy_bundle(bundle)

    @property
    def _phase6_existing_parts(self):
        """舊介面相容：實際 presence 由 Workspace Controller 擁有。"""
        return self.workspace_controller.raw_existing_parts()

    @_phase6_existing_parts.setter
    def _phase6_existing_parts(self, existing_parts):
        self.workspace_controller.replace_legacy_existing_parts(existing_parts)

    @property
    def _fold_designer_last_part_key(self):
        """舊介面相容：active part 不再有獨立 backing 欄位。"""
        return self.workspace_controller.active_part

    @_fold_designer_last_part_key.setter
    def _fold_designer_last_part_key(self, part_key):
        self.workspace_controller.set_active_part(part_key)

    @property
    def _phase6_loaded_project_path(self):
        """舊介面相容別名；直接委派 Project Controller，不保存第二份路徑。"""
        return self.project_controller.project_path

    @_phase6_loaded_project_path.setter
    def _phase6_loaded_project_path(self, path):
        self.project_controller.set_project_path(path)
        
    def setup_styles(self):
        _configure_layout_styles(self)
        
    def init_variables(self):
        return _phase6_state_sync.init_variables(self)
        
    def _setting_var_map(self):
        return _phase6_state_sync.setting_var_map(self)

    def _collect_main_setting_values(self):
        return _phase6_state_sync.collect_main_setting_values(self)

    @staticmethod
    def _serialize_corner_selection(raw_selection):
        return _phase6_state_sync.serialize_corner_selection(raw_selection)

    def _serialize_manual_corner_state(self):
        return _phase6_state_sync.serialize_manual_corner_state(self)


    @staticmethod
    def _baseline_model_choices():
        """One visible selector owns both cabinet type and baseline model.

        Registered implemented families are valid model choices even when they
        intentionally have no baseline DXF folder (受電箱 phase 1).  Physical
        baseline folders remain valid choices, and 自訂 stays last.
        """
        choices = []
        seen = set()
        physical_models = [normalize_custom_model_name(name) for name in ae.get_baseline_list()]
        for name in physical_models:
            name = normalize_custom_model_name(name)
            if name and name not in seen and not is_unknown_model(name):
                choices.append(name)
                seen.add(name)
        # Formula-only implemented families (currently 受電箱) must be visible
        # in the same selector even without a baseline DXF directory.  金庫型
        # remains resource-backed: do not invent it when its baseline is absent.
        for item in registered_cabinet_types():
            if not item.implemented:
                continue
            name = str(item.canonical_name or "").strip()
            if name == "金庫型" and name not in seen:
                continue
            if name and name not in seen:
                choices.append(name)
                seen.add(name)
        return with_unknown_model(choices)

    def _endcap_depth_comp_t_for_family(self, model_name=None):
        source = (
            Phase6ApplicationHost._current_cabinet_type_name(self)
            if model_name is None else model_name
        )
        return cabinet_family_policy.endcap_depth_comp_t(source)

    def _known_corner_state_for_current_family(self, parts):
        return known_model_corner_state(
            parts, cabinet_family=Phase6ApplicationHost._current_cabinet_type_name(self)
        )

    def _enforce_known_model_corner_types(self, *, reset_all=False):
        """Keep known-model CornerType fixed while allowing same-type parameter overrides."""
        model = str(self.baseline_var.get() if hasattr(self, "baseline_var") else "").strip()
        if not model or is_unknown_model(model):
            return
        fixed = self._known_corner_state_for_current_family(self.manual_corner_state.keys())
        for part_key, corners in fixed.items():
            if part_key not in self.manual_corner_state:
                continue
            for corner_key, fixed_selection in corners.items():
                current = normalize_corner_selection(self.manual_corner_state[part_key][corner_key])
                if reset_all or current.type_id is not fixed_selection.type_id:
                    self.manual_corner_state[part_key][corner_key] = fixed_selection
            if reset_all and part_key in self.manual_corner_pair_same:
                self.manual_corner_pair_same[part_key]["top"] = True
                self.manual_corner_pair_same[part_key]["bottom"] = True






    def _phase6_external_sync_envelope(self, delta):
        return _phase6_state_sync.phase6_external_sync_envelope(self, delta)

    def _on_main_setting_var_changed(self, key, var):
        return _phase6_state_sync.on_main_setting_var_changed(self, key, var)

    _make_original_fold_designer_snapshot = _phase6_fold_adapter._make_original_fold_designer_snapshot

    _phase6_logical_part_present = staticmethod(_phase6_logical_part_present_impl)





    save_phase6_project_as = _save_phase6_project_as_impl
    save_phase6_project = _save_phase6_project_impl
    open_phase6_project = _open_phase6_project_impl
    load_phase6_project = _load_phase6_project_impl








    def _apply_ui_text_size_preference(self, value, *, persist=True, notify_designer=True):
        key = normalize_ui_text_size(value)
        self.settings_service.update({"ui_text_size": key})
        self._ui_text_controller.apply(key)
        self.setup_styles()
        if hasattr(self, "ui_text_size_var"):
            label = ui_text_size_label(key)
            if self.ui_text_size_var.get() != label:
                self.ui_text_size_var.set(label)
        paned = getattr(self, "main_paned", None)
        left = getattr(self, "left_container", None)
        if paned is not None and left is not None:
            base_width = 320
            factor = ui_text_size_factor(key)
            scaled_width = int(round(base_width * factor))
            try:
                paned.paneconfig(left, width=scaled_width)
            except Exception:
                pass
        if persist:
            self.settings_service.persist_defaults(keys=("ui_text_size",))
        if notify_designer:
            designer = getattr(self, "fold_designer_app", None)
            if designer is not None and hasattr(designer, "apply_external_settings"):
                try:
                    designer.apply_external_settings({"ui_text_size": key})
                except tk.TclError:
                    pass
        try:
            self.draw_preview()
        except Exception:
            pass
        return key

    def on_ui_text_size_changed(self, event=None):
        return self._apply_ui_text_size_preference(self.ui_text_size_var.get())

    def _current_box_assembly_type(self):
        # Persisted UI mirror / Joint Graph owns the assembly intent.  Top
        # CornerType is only a legacy fallback for data that predates the graph.
        var = getattr(self, "box_assembly_type_var", None)
        if var is not None:
            try:
                label = str(var.get() or "").strip()
                if label in ASSEMBLY_LABEL_TO_TYPE:
                    return ASSEMBLY_LABEL_TO_TYPE[label]
            except Exception:
                pass
        state = getattr(self, "assembly_joint_state", None)
        if isinstance(state, dict):
            raw = state.get("assembly_type")
            if raw:
                try:
                    stable = assembly_intent_value(raw)
                    return CornerTypeId(stable) if stable != "WRAP_OVERLAY" else stable
                except Exception:
                    pass
        corner_state = getattr(self, "manual_corner_state", None)
        if corner_state:
            try:
                return assembly_type_from_corner_state(corner_state)
            except Exception:
                pass
        return CornerTypeId.INSERT_OVERLAY

    def _set_box_assembly_type(
        self, type_id, *, recalculate=True, notify_designer=True,
        reset_bottom_defaults=False,
    ):
        stable = assembly_intent_value(type_id)
        try:
            parts = tuple(self._phase6_current_existing_parts())
        except Exception:
            parts = ("box_body", "head", "tail")
        state = dict(getattr(self, "assembly_joint_state", {}) or {})
        state.setdefault("existing_parts", list(parts))
        state["existing_parts"] = list(parts)
        if not state.get("assembly_joint_schema_version"):
            state["assembly_type"] = stable
            state = migrate_legacy_snapshot_joints(state)
        state = sync_snapshot_intent_joints(state, stable)
        self.assembly_joint_state = state
        label = assembly_intent_label(stable)
        if self.box_assembly_type_var.get() != label:
            self.box_assembly_type_var.set(label)
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        self.refresh_corner_type_panel()
        if notify_designer:
            designer = getattr(self, "fold_designer_app", None)
            if designer is not None and getattr(designer, "_transaction_confirm_callback", None) is None:
                try:
                    designer.apply_external_assembly_type(stable)
                except Exception:
                    pass
        if recalculate:
            self._request_phase6_update("geometry")
        return CornerTypeId(stable) if stable != "WRAP_OVERLAY" else stable

    def on_box_assembly_changed(self, event=None):
        if not is_unknown_model(self.baseline_var.get()):
            return
        type_id = self._current_box_assembly_type()
        self._set_box_assembly_type(type_id, reset_bottom_defaults=False)

    def _effective_endcap_fw(self, part_key, box_fw=None):
        if box_fw is None:
            fw_var = getattr(self, "fw_z_var", None)
            if fw_var is not None:
                box_fw = float(fw_var.get())
            else:
                box_fw = float(self.settings_service.snapshot().get("fw", 25.0))
        state = getattr(self, "endcap_fw_state", None)
        if state is None:
            return float(box_fw)
        snapshot = {"fw": float(box_fw), "endcap_fw": state}
        return float(resolve_endcap_fw(snapshot, part_key, state=state))

    def _sync_endcap_fw_controls(self):
        return _sync_endcap_fw_controls_impl(self)

    def _apply_endcap_fw_snapshot(self, snapshot):
        state = normalize_endcap_fw_state(snapshot)
        self.endcap_fw_state = state
        self._sync_endcap_fw_controls()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        return state

    def on_endcap_fw_follow_changed(self, part_key):
        box_fw = float(self.fw_z_var.get())
        follow_var = self.fw_head_follow_var if part_key == "head" else self.fw_tail_follow_var
        set_endcap_fw_follow(self.endcap_fw_state, part_key, bool(follow_var.get()), box_fw=box_fw)
        self._sync_endcap_fw_controls()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        self._request_phase6_update("geometry")

    def on_fw_selected(self, source):
        if source == "z":
            # Explicit operator input on the box always retakes Head + Tail,
            # even when the numeric value is the same as before.
            commit_box_fw(self.endcap_fw_state, float(self.fw_z_var.get()))
            self._sync_endcap_fw_controls()
        elif source in {"head", "tail"}:
            var = self.fw_head_var if source == "head" else self.fw_tail_var
            try:
                value = float(var.get())
            except (TypeError, ValueError, tk.TclError):
                # The EndCap FW controls are intentionally free numeric inputs.
                # Invalid transient text must not corrupt control ownership.
                self._sync_endcap_fw_controls()
                return
            commit_endcap_fw(
                self.endcap_fw_state, source, value,
                box_fw=float(self.fw_z_var.get()),
            )
            self._sync_endcap_fw_controls()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        self._request_phase6_update("geometry")

    def _baseline_source_model(self):
        baseline_var = getattr(self, "baseline_var", None)
        if baseline_var is None or not hasattr(baseline_var, "get"):
            return None
        value = str(baseline_var.get() or "").strip()
        if not value or is_unknown_model(value):
            return None
        return value

    def _door_material_frame_width(self, frame_width, thickness, *, model_name=None):
        """Resolve operator Door FW into the material-space value consumed by AE."""
        source = self._baseline_source_model() if model_name is None else model_name
        return cabinet_family_policy.door_material_frame_width(
            source, frame_width=float(frame_width), thickness=float(thickness),
        )

    def _sync_fold_designer_manual_corner_context(self, active_part):
        return _sync_fold_designer_manual_corner_context_impl(self, active_part)

    def _current_manual_corner_part_key(self):
        override = getattr(self, '_manual_corner_part_override', None)
        state_map = getattr(self, 'manual_corner_state', {}) or {}
        if override in state_map:
            return override
        controller = getattr(self, 'workspace_controller', None)
        key = str(getattr(controller, 'active_part', '') or '')
        if key.startswith('box_body:') and not key.startswith('box_body:divider:'):
            key = 'box_body'
        elif key.startswith('door_c'):
            key = 'door'
        elif key.startswith('base_plate_c'):
            key = 'base_plate'
        return key if key in state_map else None

    def _manual_corner_policy(self, part_key, fw):
        state_map = getattr(self, "manual_corner_state", None)
        if isinstance(state_map, dict) and part_key in state_map:
            policy = policy_from_corner_state(state_map[part_key], fw=fw)
            family_adapter = getattr(self, "_apply_cabinet_family_endcap_policy", None)
            if callable(family_adapter):
                return family_adapter(policy, part_key)
            return policy

        # Geometry/spec helpers are also used by lightweight tests and legacy
        # callers that do not construct the full Tk state.  Preserve the same
        # model semantics instead of crashing or silently dropping CornerType.
        model_name = self._baseline_source_model() if hasattr(self, "_baseline_source_model") else None
        if model_name:
            fallback = known_model_corner_state((part_key,), cabinet_family=Phase6ApplicationHost._current_cabinet_type_name(self)).get(part_key)
        else:
            fallback = new_manual_corner_state((part_key,)).get(part_key)
        if fallback is None:
            return None
        return policy_from_corner_state(fallback, fw=fw)

    def _box_body_corner_policies(self, fw):
        """One shared CornerType state for custom and known models alike."""
        if hasattr(self, "fw_z_var") and hasattr(self, "endcap_fw_state"):
            head_fw = self._effective_endcap_fw("head", fw)
            tail_fw = self._effective_endcap_fw("tail", fw)
        else:
            # Keep this geometry helper independently usable by tests/legacy
            # callers that do not construct the full Tk FW-link state.
            head_fw = tail_fw = float(fw)
        return (
            self._manual_corner_policy("head", head_fw),
            self._manual_corner_policy("tail", tail_fw),
        )

    def _phase6_resolved_finished_dimensions(self, part_key):
        """Consume the same finished-dimension provider used by Phase6 3D."""
        key = str(part_key or "")
        snapshot = self._make_original_fold_designer_snapshot()
        settings = dict(snapshot.get("settings") or {})
        head_policy = tail_policy = None
        if key == "box_body":
            head_policy, tail_policy = self._box_body_corner_policies(
                float(snapshot.get("fw", ae.FW))
            )
        return resolve_operator_finished_dimensions(
            key,
            snapshot=snapshot,
            settings=settings,
            thickness=float(snapshot.get("t", ae.T)),
            head_corner_policy=head_policy,
            tail_corner_policy=tail_policy,
        )

    def _draw_phase6_finished_dimension_summary(self, canvas, *, part_key, y=132):
        """Draw operator finished dimensions from the shared 2D/3D provider."""
        dims = self._phase6_resolved_finished_dimensions(part_key)
        if not dims:
            return None
        text_values = [self._fold_designer_number_text(value) for value in dims]
        if str(part_key) == "box_body" and len(text_values) >= 3:
            text = f"折後包外：W {text_values[0]} × H {text_values[1]} × D {text_values[2]} mm"
        else:
            text = "成形尺寸：" + " × ".join(text_values[:2]) + " mm"
        canvas.create_text(
            25, float(y), anchor=tk.NW, text=text, fill=WHD_SEMANTIC_COLORS["success"],
            font=('Microsoft JhengHei', 9, 'bold'),
            tags=("phase6_finished_dimensions",),
        )
        return tuple(float(value) for value in dims)

    def _box_body_finished_height(self, val):
        """Return the single folded box-body outside height from shared assembly semantics."""
        h = float(val['h'])
        t = float(val['t'])
        head_policy, tail_policy = self._box_body_corner_policies(float(val['fw']))
        if head_policy is None or tail_policy is None:
            return h - 2.0 * t
        bottom_outer, top_outer = box_body_vertical_offsets(
            t, head_corner_policy=head_policy, tail_corner_policy=tail_policy
        )
        result = h - bottom_outer - top_outer
        if result <= 0:
            raise ValueError("箱身折後包外高度必須大於 0")
        return float(result)

    _CORNER_MODE_LABELS = {
        CrossCornerMode.STANDARD: "標準",
        CrossCornerMode.RETAIN: "單邊留肉",
        CrossCornerMode.EXTRA_CUT: "多切",
    }
    _CORNER_MODE_BY_LABEL = {value: key for key, value in _CORNER_MODE_LABELS.items()}
    _CORNER_DIRECTION_LABELS = {
        CornerDirection.WIDTH: "寬",
        CornerDirection.HEIGHT: "高",
        CornerDirection.BOTH: "寬＋高",
    }
    _CORNER_DIRECTION_BY_LABEL = {value: key for key, value in _CORNER_DIRECTION_LABELS.items()}
    _FIXED_CORNER_SUMMARIES = {
        "door": "十字截角｜單邊留肉 1T",
        "base_plate": "十字截角｜標準",
        "indicator_box": "十字截角｜單邊留肉 1T（固定）",
        "indicator_door": "十字截角｜單邊留肉 1T（固定）",
        "head": "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n下方：十字截角｜多切 0.5T（寬＋高）",
        "tail": "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n下方：十字截角｜多切 0.5T（寬＋高）",
    }

    def _fixed_corner_summary(self, part_key):
        return _fixed_corner_summary_impl(
            self, part_key, Phase6ApplicationHost._current_cabinet_type_name(self)
        )

    def _corner_part_type_editable(self, part_key):
        # CornerType 本身只在自訂盤型開放切換；已知盤型保留基準類型。
        return (
            is_unknown_model(self.baseline_var.get())
            and part_key in self.manual_corner_state
            and part_key not in {"indicator_box", "indicator_door"}
        )

    def _corner_part_editable(self, part_key):
        # Backwards-compatible meaning: type selection editable.
        return self._corner_part_type_editable(part_key)

    def _corner_part_parameters_unlockable(self, part_key):
        # 已知盤型也允許在明確解鎖後微調既有類型的細部參數；固定共享板件除外。
        return (
            part_key in self.manual_corner_state
            and part_key not in {"indicator_box", "indicator_door"}
        )

    def _manual_corner_parameters_unlocked(self, part_key):
        return bool(getattr(self, "_manual_corner_param_unlocked", {}).get(str(part_key), False))

    def _manual_corner_parameters_editable(self, part_key):
        return self._corner_part_parameters_unlockable(part_key) and self._manual_corner_parameters_unlocked(part_key)

    def _reset_manual_corner_parameter_locks(self):
        self._manual_corner_param_unlocked = {}

    def toggle_manual_corner_parameter_lock(self):
        return _toggle_manual_corner_parameter_lock_impl(self)

    @classmethod
    def _corner_parameter_summary(cls, selection):
        return _corner_parameter_summary_impl(cls, selection)

    def create_corner_type_panel(self, parent):
        return _create_corner_type_panel_impl(self, parent)

    def _draw_corner_type_icon(self, canvas, selection_or_type, *, large=False, flip_y=True):
        return _draw_corner_type_icon_impl(self, canvas, selection_or_type, large=large, flip_y=flip_y)

    def _pair_for_corner_target(self, target_key):
        if target_key in ('top', 'top_left', 'top_right'):
            return 'top'
        if target_key in ('bottom', 'bottom_left', 'bottom_right'):
            return 'bottom'
        return None

    def _normalize_manual_corner_target(self, part_key):
        return _normalize_manual_corner_target_impl(self, part_key)

    def _manual_selection_for_target(self, part_key, target_key):
        if target_key in CORNER_PAIR_CORNERS:
            target_key = CORNER_PAIR_CORNERS[target_key][0]
        return normalize_corner_selection(self.manual_corner_state[part_key][target_key])

    def select_manual_corner(self, corner_key):
        return _select_manual_corner_impl(self, corner_key)

    def on_manual_corner_pair_same_changed(self, pair_key):
        part_key = self._current_manual_corner_part_key()
        if part_key is None or part_key not in self.manual_corner_state:
            return
        if not self._manual_corner_parameters_editable(part_key):
            self.refresh_corner_type_panel()
            return
        enabled = self.manual_top_same_var.get() if pair_key == 'top' else self.manual_bottom_same_var.get()
        set_manual_corner_pair_same(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key], pair_key, enabled
        )
        if enabled:
            self.manual_active_corner_var.set(pair_key)
        elif self._pair_for_corner_target(self.manual_active_corner_var.get()) == pair_key:
            self.manual_active_corner_var.set(CORNER_PAIR_CORNERS[pair_key][0])
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    def set_manual_corner_type(self, type_id):
        part_key = self._current_manual_corner_part_key()
        if not self._corner_part_editable(part_key):
            return
        target_key = self._normalize_manual_corner_target(part_key)
        if part_key in {"head", "tail"} and target_key in {"top", "top_left", "top_right"}:
            # 上方類型由箱身組合方式擁有；此頁只調左右參數。
            self.refresh_corner_type_panel()
            return
        type_id = CornerTypeId(type_id)
        current = self._manual_selection_for_target(part_key, target_key)
        selection = current if current.type_id is type_id else CornerTypeSelection(type_id)
        apply_manual_corner_selection(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key],
            target_key, selection,
        )
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    @staticmethod
    def _corner_number_text(value):
        value = float(value)
        return str(int(value)) if value.is_integer() else f"{value:g}"

    def _selection_from_manual_corner_controls(self):
        return _selection_from_manual_corner_controls_impl(self)

    def on_manual_corner_mode_changed(self, event=None):
        if self._manual_corner_param_guard:
            return
        part_key = self._current_manual_corner_part_key()
        if not self._manual_corner_parameters_editable(part_key):
            return
        target_key = self._normalize_manual_corner_target(part_key)
        mode = self._CORNER_MODE_BY_LABEL.get(self.manual_corner_cross_mode_var.get())
        if mode is None:
            return
        selection = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=mode)
        apply_manual_corner_selection(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key],
            target_key, selection,
        )
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    def on_manual_corner_parameter_changed(self, event=None):
        if self._manual_corner_param_guard:
            return
        part_key = self._current_manual_corner_part_key()
        if not self._manual_corner_parameters_editable(part_key):
            return
        target_key = self._normalize_manual_corner_target(part_key)
        selection = self._selection_from_manual_corner_controls()
        if selection is None:
            return
        apply_manual_corner_selection(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key],
            target_key, selection,
        )
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    def _refresh_manual_corner_parameter_rows(self, selection):
        return _refresh_manual_corner_parameter_rows_impl(self, selection)

    def refresh_corner_type_panel(self):
        return _refresh_corner_type_panel_impl(self)

    def create_widgets(self):
        _build_main_layout(self)
        
    def on_base_plate_same_toggle(self, *args):
        # UI 已搬到 3D；此 helper 只保留舊資料同步語意。
        if self.base_plate_all_same_var.get():
            self.sync_base_plate_shrink()
        self._request_phase6_update("geometry")

    def sync_base_plate_shrink(self, *args):
        return _sync_base_plate_shrink_impl(self, *args)

    def create_input_row(self, parent, label_text, var):
        return _create_input_row_impl(self, parent, label_text, var)
        
    def create_result_row(self, parent, label_text, var):
        return _create_result_row_impl(self, parent, label_text, var)

    _phase6_current_existing_parts = _phase6_visibility.phase6_current_existing_parts
    _phase6_set_part_presence = _phase6_visibility.phase6_set_part_presence
    _phase6_refresh_presence_ui = _phase6_visibility.phase6_refresh_presence_ui

    def create_separator(self, parent):
        return _create_separator_impl(self, parent)
        
    def create_advanced_inputs(self, parent):
        return _create_advanced_inputs_impl(self, parent)

    def create_sub_input(self, parent, label_text, var):
        return _create_sub_input_impl(self, parent, label_text, var)
        
    def toggle_advanced_panel(self):
        return _toggle_advanced_panel_impl(self)

    def setup_tab_z_ui(self):
        # delegate to box_body panel preserving build_box_body_piece_selector contract
        return _setup_tab_z_ui_impl(self)

    def _render_fold_designer_corner_data_view(self, canvas, part_key, render_data):
        """Render supplied authoritative PartRenderData in Fold Designer 2D."""
        key = str(part_key or "")
        if canvas is None:
            return None

        multi_door_var = getattr(self, "multi_door_enabled_var", None)
        multi_door_enabled = bool(
            multi_door_var is not None
            and callable(getattr(multi_door_var, "get", None))
            and multi_door_var.get()
        )
        if key.startswith("door_c") and multi_door_enabled:
            designer = getattr(self, "fold_designer_app", None)
            if designer is not None:
                import fold_designer_bridge as phase6_bridge
                door_keys = tuple(
                    candidate
                    for candidate in phase6_bridge._phase6_corner_data_part_keys(designer)
                    if str(candidate).startswith("door_c")
                )
                projections = phase6_bridge._phase6_corner_data_unfold_projections(
                    designer, door_keys
                )
                render_data_by_part_key = {
                    projection.part_key: projection.render_data
                    for projection in projections
                }
                if key in render_data_by_part_key and len(render_data_by_part_key) == len(door_keys):
                    # The composite view returns before the ordinary single-part binding block.
                    # Bind only the established manual-click lifecycle on the visible canvas.
                    for sequence in (
                        "<Button-1>", "<B1-Motion>", "<ButtonRelease-1>",
                        "<Double-Button-1>", "<Button-3>",
                    ):
                        try:
                            canvas.unbind(sequence)
                        except Exception:
                            pass
                    canvas.bind("<Button-1>", self.on_door_canvas_press)
                    canvas.bind("<B1-Motion>", self.on_door_canvas_drag)
                    canvas.bind("<ButtonRelease-1>", self.on_door_canvas_release)
                    return self.draw_door_layout_overview(
                        canvas=canvas,
                        render_data_by_part_key=render_data_by_part_key,
                    )
        canvas.delete("all")
        material = getattr(render_data, "material", None) if render_data is not None else None
        scene = getattr(render_data, "scene", None) if render_data is not None else None
        if material is None or scene is None or bool(getattr(material, "is_empty", False)):
            return None

        cw = max(1, int(canvas.winfo_width()))
        ch = max(1, int(canvas.winfo_height()))
        bounds = tuple(float(v) for v in material.bounds)
        transform, _ox, _oy, _scale, _material_top = _phase6_2d_material_viewport(
            bounds, cw, ch,
            top_gutter=24.0, right_gutter=24.0,
            bottom_gutter=24.0, left_gutter=24.0,
        )
        try:
            zoom = float(getattr(canvas, "_phase6_unfold_zoom", 1.0) or 1.0)
        except Exception:
            zoom = 1.0
        zoom = max(0.50, min(3.00, zoom))
        if abs(zoom - 1.0) > 1e-12:
            minx, miny, maxx, maxy = bounds
            world_center = Vec2((minx + maxx) / 2.0, (miny + maxy) / 2.0)
            center_x, center_y = transform.world_to_canvas(world_center)
            scaled = transform.scale * zoom
            transform = CanvasTransform(
                scale=scaled,
                origin_x=center_x - world_center.x * scaled,
                origin_y=center_y + world_center.y * scaled,
            )
        render_drawing_scene(
            canvas, scene, transform, skip_layers=("CHECK", "STOCK")
        )
        _draw_phase6_annotation_projection(
            canvas, render_data, transform, part_key=key
        )
        draw_hole_editor_hint(canvas, cw, endcap=(key in {"head", "tail"}))

        warning_rows = tuple(
            str(v) for v in tuple(getattr(render_data, "warnings", ()) or ()) if str(v)
        )
        if warning_rows:
            canvas.create_text(
                12, 12, text="\n".join(warning_rows), anchor=tk.NW,
                fill=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9),
                width=max(180, int(cw * 0.48)), tags=("phase6_preview_hint",),
            )

        for sequence in (
            "<Button-1>", "<B1-Motion>", "<ButtonRelease-1>",
            "<Double-Button-1>", "<Button-3>",
        ):
            try:
                canvas.unbind(sequence)
            except Exception:
                pass
        canvas.bind(
            "<Double-Button-1>",
            lambda event, k=key: self.open_part_hole_editor(k),
        )
        if key == "door" or key.startswith("door_c"):
            canvas.bind("<Button-1>", self.on_door_canvas_press)
            canvas.bind("<B1-Motion>", self.on_door_canvas_drag)
            canvas.bind("<ButtonRelease-1>", self.on_door_canvas_release)
        return render_data

    def _attach_part_hole_entrypoint(self, canvas, part_key, *, allow_double=True):
        return _attach_part_hole_entrypoint_impl(self, canvas, part_key, allow_double=allow_double)

    def setup_tab_endcap_ui(self, tab_frame, key):
        return _setup_tab_endcap_ui_impl(self, tab_frame, key)

    def setup_tab_base_plate_ui(self):
        return _setup_tab_base_plate_ui_impl(self)

    @staticmethod
    def _door_layout_number_text(value):
        value = float(value)
        return str(int(value)) if value.is_integer() else str(value)

    def _new_door_layout_column(self, width, heights, *, width_auto=False, height_auto=None):
        height_values = list(heights)
        if height_auto is None:
            height_auto = [False] * len(height_values)
        return {
            "width_var": tk.StringVar(value=self._door_layout_number_text(width)),
            "width_auto": bool(width_auto),
            "width_committed": float(width),
            "height_vars": [tk.StringVar(value=self._door_layout_number_text(v)) for v in height_values],
            "height_auto": [bool(v) for v in height_auto],
            "height_committed": [float(v) for v in height_values],
            "height_completion": None,
        }

    def set_door_layout_columns(self, columns):
        """Replace Door layout with explicit user values, then append any W/H remainders."""
        model = []
        for width, heights in columns:
            height_values = list(heights)
            if not height_values:
                raise ValueError("每一欄至少需要一層高度")
            model.append(self._new_door_layout_column(width, height_values))
        if not model:
            raise ValueError("門配置至少需要一欄")
        self.door_layout_columns = model
        self.door_layout_selected_var.set("0:0")
        self._recompute_door_layout_remainders(rebuild=False)
        if hasattr(self, "door_layout_columns_frame"):
            self.rebuild_door_layout_ui()

    def _ensure_door_layout_default(self):
        if self.door_layout_columns:
            return
        try:
            width = float(self.w_var.get())
            height = float(self.h_var.get())
        except ValueError:
            width, height = ae.W, ae.H
        self.door_layout_columns = [self._new_door_layout_column(width, [height])]
        self._recompute_door_layout_remainders(rebuild=False)

    @staticmethod
    def _parse_layout_value(var, label):
        return _parse_layout_value_impl(var, label)

    def _recompute_column_height_remainder(self, column, column_index, total_height):
        fixed = []
        for row_index, (var, is_auto) in enumerate(zip(column["height_vars"], column["height_auto"]), start=1):
            if not is_auto:
                fixed.append(self._parse_layout_value(var, f"欄 {column_index+1} 第 {row_index} 層高度"))
        completion = complete_partition(fixed, total_height, tolerance=0.01)
        column["height_vars"] = [tk.StringVar(value=self._door_layout_number_text(v)) for v in completion.values]
        column["height_committed"] = [float(v) for v in completion.values]
        column["height_auto"] = [False] * len(completion.values)
        if completion.auto_index is not None:
            column["height_auto"][completion.auto_index] = True
        column["height_completion"] = completion

    def _recompute_door_layout_remainders(self, *, rebuild=True):
        """Regenerate the one automatic width/height remainder from user-owned cells."""
        if not self.door_layout_columns:
            return
        try:
            total_width = float(self.w_var.get())
            total_height = float(self.h_var.get())
        except ValueError as exc:
            raise ValueError("W / H 必須先填入有效數字") from exc
        if total_width <= 0 or total_height <= 0:
            raise ValueError("W / H 必須大於 0")

        fixed_columns = [column for column in self.door_layout_columns if not column.get("width_auto", False)]
        fixed_widths = [
            self._parse_layout_value(column["width_var"], f"欄 {index+1} 寬度")
            for index, column in enumerate(fixed_columns)
        ]
        width_completion = complete_partition(fixed_widths, total_width, tolerance=0.01)

        for index, column in enumerate(fixed_columns):
            self._recompute_column_height_remainder(column, index, total_height)

        model = fixed_columns
        if width_completion.auto_index is not None:
            auto_width = width_completion.values[width_completion.auto_index]
            auto_column = self._new_door_layout_column(
                auto_width, [total_height], width_auto=True, height_auto=[True]
            )
            auto_column["height_completion"] = complete_partition([], total_height, tolerance=0.01)
            model.append(auto_column)

        self.door_layout_columns = model
        for column in self.door_layout_columns:
            try:
                column["width_committed"] = self._parse_layout_value(column["width_var"], "欄寬")
            except ValueError:
                pass
        self._door_layout_width_completion = width_completion

        # Keep selection on a real cell after automatic cells are inserted/removed.
        if self.door_layout_columns:
            try:
                c_text, r_text = self.door_layout_selected_var.get().split(":", 1)
                c_idx, r_idx = int(c_text), int(r_text)
            except Exception:
                c_idx = r_idx = 0
            c_idx = min(max(c_idx, 0), len(self.door_layout_columns) - 1)
            r_idx = min(max(r_idx, 0), len(self.door_layout_columns[c_idx]["height_vars"]) - 1)
            self.door_layout_selected_var.set(f"{c_idx}:{r_idx}")

        if rebuild and hasattr(self, "door_layout_columns_frame"):
            self.rebuild_door_layout_ui()

    def get_door_layout_columns(self):
        """Read current fixed + generated remainder cells as numeric layout values."""
        if not self.door_layout_columns:
            self._ensure_door_layout_default()
        columns = []
        for column_index, column in enumerate(self.door_layout_columns, start=1):
            if isinstance(column, (list, tuple)):
                columns.append((float(column[0]), [float(h) for h in list(column[1])]))
                continue
            width = self._parse_layout_value(column["width_var"], f"欄 {column_index} 寬度")
            heights = [
                self._parse_layout_value(var, f"欄 {column_index} 第 {row_index} 層高度")
                for row_index, var in enumerate(column["height_vars"], start=1)
            ]
            columns.append((width, heights))
        return columns

    def get_door_layout_cells(self):
        columns = self.get_door_layout_columns()
        try:
            total_width = float(self.w_var.get())
            total_height = float(self.h_var.get())
        except ValueError as exc:
            raise ValueError("W / H 必須先填入有效數字") from exc
        return validate_door_layout_dimensions(
            columns, total_width=total_width, total_height=total_height, tolerance=0.01
        )

    @staticmethod
    def _door_layout_cell_key(cell):
        return f"{cell.column_index}:{cell.row_index}"

    def get_selected_door_layout_cell(self):
        cells = self.get_door_layout_cells()
        selected_key = self.door_layout_selected_var.get()
        for cell in cells:
            if self._door_layout_cell_key(cell) == selected_key:
                return cell
        first = cells[0]
        self.door_layout_selected_var.set(self._door_layout_cell_key(first))
        return first

    def select_door_layout_cell(self, column_index, row_index):
        """Select one multi-door cell without rebuilding geometry or Canvas widgets."""
        selected_key = f"{int(column_index)}:{int(row_index)}"
        self.door_layout_selected_var.set(selected_key)

        canvas = getattr(self, "canvas_door", None)
        designer = getattr(self, "fold_designer_app", None)
        if (
            designer is not None
            and str(getattr(designer, "_phase6_3d_display_mode", "") or "") == "corner_data"
        ):
            corner_canvas = getattr(designer, "corner_data_canvas", None)
            if corner_canvas is not None:
                canvas = corner_canvas
            import fold_designer_bridge as phase6_bridge
            stable_key = f"door_c{int(column_index) + 1}_r{int(row_index) + 1}"
            phase6_bridge._phase6_select_corner_data_part(
                designer, stable_key, refresh_view=False
            )
        if canvas is not None:
            for key, item_id in getattr(self, "door_layout_cell_items", {}).items():
                try:
                    canvas.itemconfigure(
                        item_id,
                        outline=self.COLOR_ACCENT if key == selected_key else "#30d158",
                        width=3 if key == selected_key else 2,
                    )
                except tk.TclError:
                    pass

        if hasattr(self, "last_door_layout_overview"):
            self.last_door_layout_overview["selected"] = selected_key

    def _sync_door_canvas_double_click_binding(self):
        """Multi-door counts two Button-1 presses itself; single Door keeps Tk double-click."""
        if not hasattr(self, "canvas_door"):
            return
        self.canvas_door.unbind("<Double-Button-1>")
        if not self.multi_door_enabled_var.get():
            self.canvas_door.bind("<Double-Button-1>", self.on_door_canvas_double_click)

    def toggle_multi_door_layout(self):
        self._door_layout_last_click = None
        if self.multi_door_enabled_var.get():
            self._ensure_door_layout_default()
            self._recompute_door_layout_remainders(rebuild=False)
        self._sync_door_canvas_double_click_binding()
        # 舊的欄/層表單永久不佔 Door 分頁空間；尺寸直接在 Canvas 上編輯。
        if hasattr(self, "door_layout_body"):
            self.door_layout_body.pack_forget()
        self._on_door_layout_value_changed()

    def _reject_door_layout_dimension(self, var, previous_value, message):
        return _reject_door_layout_dimension_impl(self, var, previous_value, message)

    def commit_door_layout_width(self, column_index):
        column = self.door_layout_columns[column_index]
        if "width_committed" in column:
            previous = float(column["width_committed"])
        else:
            previous = self._parse_layout_value(column["width_var"], "欄寬")
        try:
            current = self._parse_layout_value(column["width_var"], f"欄 {column_index+1} 寬度")
            total_width = self._parse_layout_value(self.w_var, "W")
            other_fixed = sum(
                self._parse_layout_value(c["width_var"], "欄寬")
                for i, c in enumerate(self.door_layout_columns)
                if i != column_index and not c.get("width_auto", False)
            )
            maximum = total_width - other_fixed
            if current > maximum + 0.01:
                return self._reject_door_layout_dimension(
                    column["width_var"], previous,
                    f"欄 {column_index+1} 寬度不可超過盤體 W。\n"
                    f"W = {total_width:g} mm，其餘固定欄合計 {other_fixed:g} mm，"
                    f"此欄最大只能輸入 {max(0.0, maximum):g} mm。"
                )
        except ValueError as exc:
            return self._reject_door_layout_dimension(column["width_var"], previous, str(exc))

        if column.get("width_auto", False):
            expected = total_width - other_fixed
            if abs(current - expected) > 0.01:
                column["width_auto"] = False
        column["width_committed"] = current
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)
        return True

    def commit_door_layout_height(self, column_index, row_index):
        column = self.door_layout_columns[column_index]
        committed = column.get("height_committed") or []
        previous = float(committed[row_index]) if row_index < len(committed) else self._parse_layout_value(
            column["height_vars"][row_index], "高度"
        )
        try:
            current = self._parse_layout_value(
                column["height_vars"][row_index], f"欄 {column_index+1} 第 {row_index+1} 層高度"
            )
            total_height = self._parse_layout_value(self.h_var, "H")
            other_fixed = sum(
                self._parse_layout_value(var, "高度")
                for i, (var, is_auto) in enumerate(zip(column["height_vars"], column["height_auto"]))
                if i != row_index and not is_auto
            )
            maximum = total_height - other_fixed
            if current > maximum + 0.01:
                return self._reject_door_layout_dimension(
                    column["height_vars"][row_index], previous,
                    f"欄 {column_index+1} 第 {row_index+1} 層高度不可超過盤體 H。\n"
                    f"H = {total_height:g} mm，同欄其他固定高度合計 {other_fixed:g} mm，"
                    f"此層最大只能輸入 {max(0.0, maximum):g} mm。"
                )
        except ValueError as exc:
            return self._reject_door_layout_dimension(column["height_vars"][row_index], previous, str(exc))

        if column["height_auto"][row_index]:
            expected = total_height - other_fixed
            if abs(current - expected) > 0.01:
                column["height_auto"][row_index] = False
        if row_index >= len(committed):
            column["height_committed"] = [
                self._parse_layout_value(var, "高度") for var in column["height_vars"]
            ]
        else:
            column["height_committed"][row_index] = current
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)
        return True

    def add_door_layout_column(self):
        """Compatibility action: promote current auto width; remainder creates the next column."""
        self._ensure_door_layout_default()
        auto_index = next((i for i, c in enumerate(self.door_layout_columns) if c.get("width_auto")), None)
        if auto_index is not None:
            self.commit_door_layout_width(auto_index)

    def _remap_door_layout_owned_data(self, mapper):
        for attr in (
            "door_layout_features", "door_layout_indicator_states",
            "door_layout_indicator_box_features", "door_layout_indicator_door_features",
        ):
            source = getattr(self, attr, {})
            remapped = {}
            for key, value in source.items():
                try:
                    c_text, r_text = key.split(":", 1)
                    mapped = mapper(int(c_text), int(r_text))
                except Exception:
                    mapped = None
                if mapped is None:
                    continue
                c_new, r_new = mapped
                remapped[f"{c_new}:{r_new}"] = value
            setattr(self, attr, remapped)

    def remove_door_layout_column(self, column_index):
        if not self.door_layout_columns:
            return
        if self.door_layout_columns[column_index].get("width_auto"):
            return
        self._remap_door_layout_owned_data(
            lambda c, r: None if c == column_index else ((c - 1, r) if c > column_index else (c, r))
        )
        del self.door_layout_columns[column_index]
        self.door_layout_selected_var.set("0:0")
        if not self.door_layout_columns:
            try:
                total_h = float(self.h_var.get())
            except ValueError:
                total_h = ae.H
            self.door_layout_columns = [self._new_door_layout_column(0.0, [total_h], width_auto=True, height_auto=[True])]
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)

    def add_door_layout_height(self, column_index):
        """Compatibility action: promote current auto height; remainder creates the next segment."""
        column = self.door_layout_columns[column_index]
        auto_index = next((i for i, value in enumerate(column["height_auto"]) if value), None)
        if auto_index is not None:
            self.commit_door_layout_height(column_index, auto_index)

    def remove_door_layout_height(self, column_index, row_index):
        column = self.door_layout_columns[column_index]
        if column["height_auto"][row_index]:
            return
        self._remap_door_layout_owned_data(
            lambda c, r: (
                None if c == column_index and r == row_index
                else ((c, r - 1) if c == column_index and r > row_index else (c, r))
            )
        )
        del column["height_vars"][row_index]
        del column["height_auto"][row_index]
        self.door_layout_selected_var.set(f"{column_index}:0")
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)

    def _on_door_layout_value_changed(self, *, recompute=True):
        if recompute and self.multi_door_enabled_var.get():
            try:
                self._recompute_door_layout_remainders(rebuild=False)
            except Exception:
                pass
        self.refresh_door_layout_status()
        self._request_phase6_update("geometry")

    def _on_total_door_dimension_changed(self):
        if self.multi_door_enabled_var.get() and self.door_layout_columns:
            try:
                self._recompute_door_layout_remainders(rebuild=True)
            except Exception:
                self.refresh_door_layout_status()



    def _on_main_geometry_var_changed(self, reason="geometry"):
        self._phase6_update_scheduler.mark_dirty(reason)

    @staticmethod
    def _receiving_inner_door_stable_id_for_cell(cell_key):
        key = str(cell_key or "").strip()
        if key == "0:0":
            return "upper"
        if key == "0:1":
            return "lower"
        try:
            column, row = (int(v) for v in key.split(":", 1))
        except (TypeError, ValueError):
            raise ValueError(f"invalid door cell key: {cell_key!r}")
        return f"c{column + 1}r{row + 1}"

    def _receiving_inner_door_enabled(self, cell_key):
        key = str(cell_key or "").strip()
        return any(
            isinstance(item, dict) and str(item.get("cell_key") or "").strip() == key
            for item in list(getattr(self, "receiving_inner_doors", []) or [])
        )

    def _receiving_inner_door_inward_offset(self, cell_key):
        key = str(cell_key or "").strip()
        item = next((
            item for item in list(getattr(self, "receiving_inner_doors", []) or [])
            if isinstance(item, dict) and str(item.get("cell_key") or "").strip() == key
        ), None)
        default = cabinet_family_policy.default_inner_door_inward_offset_mm(
            {"model": str(self.baseline_var.get() or "").strip()}, default=0.0
        )
        try:
            return float((item or {}).get("inward_offset_mm", default))
        except (TypeError, ValueError):
            return float(default)

    def _set_receiving_inner_door_inward_offset(self, cell_key, value):
        key = str(cell_key or "").strip()
        offset = float(value)
        if offset < 0:
            raise ValueError("內門內退尺寸不可小於 0")
        found = False
        items = []
        for raw in list(getattr(self, "receiving_inner_doors", []) or []):
            if not isinstance(raw, dict):
                continue
            item = deepcopy(raw)
            if str(item.get("cell_key") or "").strip() == key:
                item["inward_offset_mm"] = offset
                found = True
            items.append(item)
        if not found:
            raise ValueError(f"door cell has no enabled inner door: {key!r}")
        self.receiving_inner_doors = items
        return offset

    def _commit_receiving_inner_door_inward_offset(self, cell_key):
        key = str(cell_key or "").strip()
        var = dict(getattr(self, "door_layout_inner_door_offset_vars", {}) or {}).get(key)
        if var is None:
            return False
        try:
            value = self._set_receiving_inner_door_inward_offset(key, var.get())
        except (TypeError, ValueError):
            var.set(self._fold_designer_number_text(self._receiving_inner_door_inward_offset(key)))
            return False
        var.set(self._fold_designer_number_text(value))
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        scheduler = getattr(self, "_phase6_update_scheduler", None)
        if scheduler is not None:
            scheduler.mark_dirty("inner_door_inward_offset")
        if hasattr(self, "canvas_door"):
            try:
                self.draw_door_layout_overview()
            except Exception:
                pass
        return True

    def _set_receiving_inner_door_enabled(self, cell_key, enabled):
        key = str(cell_key or "").strip()
        items = [deepcopy(item) for item in list(getattr(self, "receiving_inner_doors", []) or []) if isinstance(item, dict)]
        existing = next((item for item in items if str(item.get("cell_key") or "").strip() == key), None)
        items = [item for item in items if str(item.get("cell_key") or "").strip() != key]
        if bool(enabled):
            stable_id = str((existing or {}).get("stable_id") or self._receiving_inner_door_stable_id_for_cell(key)).strip()
            item = deepcopy(existing or {})
            default_offset = cabinet_family_policy.default_inner_door_inward_offset_mm(
                {"model": str(self.baseline_var.get() or "").strip()}, default=0.0
            )
            item.update({
                "stable_id": stable_id,
                "cell_key": key,
                "included_frame_sides": list(item.get("included_frame_sides") or ("top", "left", "right")),
                "inward_offset_mm": float(item.get("inward_offset_mm", default_offset)),
            })
            items.append(item)
        def sort_key(item):
            raw = str(item.get("cell_key") or "")
            try:
                return tuple(int(v) for v in raw.split(":", 1))
            except Exception:
                return (10**9, 10**9)
        items.sort(key=sort_key)
        self.receiving_inner_doors = items
        return bool(enabled)

    def _commit_receiving_inner_door_checkbox(self, cell_key):
        key = str(cell_key or "").strip()
        var = dict(getattr(self, "door_layout_inner_door_vars", {}) or {}).get(key)
        enabled = bool(var.get()) if var is not None else False
        self._set_receiving_inner_door_enabled(key, enabled)
        entry = dict(getattr(self, "door_layout_inner_door_offset_entries", {}) or {}).get(key)
        if entry is not None:
            try:
                entry.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            except Exception:
                pass
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        scheduler = getattr(self, "_phase6_update_scheduler", None)
        if scheduler is not None:
            scheduler.mark_dirty("inner_door")
        if hasattr(self, "canvas_door"):
            try:
                self.draw_door_layout_overview()
            except Exception:
                pass
        return enabled

    def refresh_door_layout_status(self):
        return _refresh_door_layout_status_impl(self)

    def rebuild_door_layout_ui(self):
        return _rebuild_door_layout_ui_impl(self)

    def setup_tab_door_ui(self):
        return _setup_tab_door_ui_impl(self)

    def setup_tab_indicator_box_ui(self):
        return _setup_tab_indicator_box_ui_impl(self)

    def on_layers_count_changed(self):
        self.rebuild_layers_config_ui()
        self._request_phase6_update("geometry")

    def rebuild_layers_config_ui(self):
        return _rebuild_layers_config_ui_impl(self)



    def _indicator_box_render_snapshot(self, val):
        return _indicator_box_render_snapshot_impl(self, val)
    def draw_indicator_box(self, val):
        canvas = self.canvas_indicator_box; canvas.delete("all")
        cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._indicator_box_render_snapshot(val)
        except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "指示燈盒", exc)
        return _draw_indicator_box_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _normalize_door_indicator_state(self, state):
        return _normalize_door_indicator_state_impl(state)
    def _door_layout_indicator_state_for_key(self, key):
        state = self.door_layout_indicator_states.get(key)
        normalized = self._normalize_door_indicator_state(state)
        if state is None:
            state = normalized
            self.door_layout_indicator_states[key] = state
        else:
            state.clear()
            state.update(normalized)
        return state

    def _destroy_door_layout_entry_widgets(self):
        return _destroy_door_layout_entry_widgets_impl(self)
    def _door_layout_entry_menu(self, entry, *, column_index, row_index=None):
        return _door_layout_entry_menu_impl(self, entry, column_index=column_index, row_index=row_index)
    def _door_layout_cell_result(self, cell, val=None):
        val = val or self.get_float_values()
        return build_door_result(
            w=cell.start_width, h=cell.start_height, t=val['t'],
            fw=self._door_material_frame_width(val['fw'], val['t']),
            gap_w=val['door_gap_w'], gap_h=val['door_gap_h'],
            fold_left=val['door_fold_l'], fold_right=val['door_fold_r'],
            fold_top=val['door_fold_t'], fold_bottom=val['door_fold_b'],
            frame_edges=cell.edges,
        )

    def _door_layout_cell_resolved_features(self, cell, result, key):
        resolved = []
        features = self.door_layout_features.setdefault(key, [])
        if features:
            surface = feature_surface_from_structural_result("door", result)
            try:
                resolved.extend(resolve_surface_features(surface, features, result.width, result.height))
            except ValueError:
                pass
        state = self._door_layout_indicator_state_for_key(key)
        mode = state.get("mode", "indicator" if state.get("enabled") else "none")
        if mode in {"indicator", "indicator_box"}:
            try:
                material_fw = self._door_material_frame_width(
                    self.fw_z_var.get(), self.t_var.get()
                )
                finished_w, finished_h = ae.calculate_door_finished_size(
                    cell.start_width, cell.start_height, material_fw,
                    self.door_gap_w_var.get(), self.door_gap_h_var.get(), self.t_var.get(),
                    frame_edges=cell.edges,
                )
                context = DoorIndicatorContext(
                    finished_width=float(finished_w), finished_height=float(finished_h),
                    left_fold=float(self.door_fold_l_var.get()), bottom_fold=float(self.door_fold_b_var.get()),
                )
                groups = tuple(int(v) for v in state.get("groups", [2])[:int(state.get("layers", 1))])
                if mode == "indicator":
                    layout = resolve_door_indicator_layout(
                        context, groups,
                        Vec2(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
                    )
                    resolved.extend(layout.features)
                else:
                    hole_w, hole_h = manufacturing_api.indicator_box_opening_size(groups, thickness=float(self.t_var.get()))
                    resolved.append(ResolvedRect(
                        center=Vec2(
                            context.left_fold + context.finished_width / 2.0 + float(state.get("offset_x", 0.0)),
                            context.bottom_fold + context.finished_height / 2.0 + float(state.get("offset_y", 0.0)),
                        ),
                        width=hole_w, height=hole_h, layer="CUTTING", source_type="indicator_box_opening",
                    ))
            except Exception:
                pass
        return resolved

    def _door_layout_baseline_scene(self, cell, val):
        model = self._baseline_source_model()
        if not model or not ae.has_baseline_part(model, "門.dxf"):
            return None, ae.baseline_source_label("", "門.dxf")
        source_fp = ae.baseline_source_fingerprint(ae.baseline_expected_path(model, "門.dxf"))
        cache_key = (
            source_fp, model, float(cell.start_width), float(cell.start_height), float(val['t']), float(val['fw']),
            float(val['door_gap_w']), float(val['door_gap_h']),
            float(val['door_fold_l']), float(val['door_fold_r']), float(val['door_fold_t']), float(val['door_fold_b']),
            bool(cell.edges.left), bool(cell.edges.right), bool(cell.edges.top), bool(cell.edges.bottom),
        )
        if cache_key in self._door_layout_baseline_cache:
            return self._door_layout_baseline_cache[cache_key], ae.baseline_source_label(model, "門.dxf")
        try:
            material_fw = self._door_material_frame_width(
                val['fw'], val['t'], model_name=model
            )
            data = ae.get_stretched_door_data(
                model, cell.start_width, cell.start_height, val['t'], material_fw,
                val['door_gap_w'], val['door_gap_h'],
                val['door_fold_l'], val['door_fold_r'], val['door_fold_t'], val['door_fold_b'],
                frame_edges=cell.edges,
            )
            self._door_layout_baseline_cache[cache_key] = data.scene
            return data.scene, ae.baseline_source_label(model, "門.dxf")
        except Exception:
            return None, "未使用基準檔（程式計算生成）"

    def open_door_indicator_component_editor(self, key, component):
        state = self._door_layout_indicator_state_for_key(key)
        if state.get("mode") != "indicator_box":
            return
        try:
            val = self.get_float_values()
            layers = max(1, min(6, int(state.get("layers", 1))))
            groups = [int(v) for v in list(state.get("groups", [2] * 6))[:layers]]
        except Exception as exc:
            messagebox.showerror("開孔失敗", str(exc))
            return

        if component == "indicator_box":
            box_corner_policy = None
            data = ae.get_stretched_indicator_box_data(
                "指示燈", groups, val['t'], corner_policy=None
            )
            baseline_scene = data.scene
            status = ae.indicator_shared_baseline_source_label("盒子.dxf")
            surface = feature_surface_from_drawing_scene("indicator_box", data.scene)
            width, height = data.params['w'], data.params['h']
            fold = float(getattr(ae, 'indicator_box_fold_def', 49.0))
            result = (
                build_unknown_indicator_box_result(
                    total_width=width, total_height=height, t=val['t'], fold=fold,
                    corner_policy=box_corner_policy,
                ) if box_corner_policy is not None else
                build_indicator_box_result(total_width=width, total_height=height, t=val['t'], fold=fold)
            )
            guide = build_finished_reference_guide(
                "indicator_box", result, finished_width=width - 2.0 * fold + val['t'],
                finished_height=height - 2.0 * fold + val['t'],
            )
            feature_store = self.door_layout_indicator_box_features.setdefault(key, [])
            title = "指示燈盒子"
        elif component == "indicator_door":
            t = val['t']; fw = val['fw']; gw = val['door_gap_w']; gh = val['door_gap_h']
            policy = replace(
                manufacturing_api.resolve_policy(),
                frame_width=float(fw), door_gap_w=float(gw), door_gap_h=float(gh),
                indicator_small_door_fold=float(getattr(ae, 'indicator_small_door_fold_def', 19.0)),
            )
            indicator_ctx = ManufacturingContext(policy=policy)
            door_spec = manufacturing_api.indicator_small_door_spec(
                groups, thickness=t, context=indicator_ctx
            )
            finished_w, finished_h = manufacturing_api.door_finished_face_size(door_spec, indicator_ctx)
            source_w, source_h = door_spec.width, door_spec.height
            data = ae.get_stretched_door_data(
                None, source_w, source_h, t, fw, gw, gh,
                door_spec.fold_left, door_spec.fold_right, door_spec.fold_top, door_spec.fold_bottom,
                indicator_window_groups=groups,
            )
            surface = feature_surface_from_drawing_scene("indicator_door", data.scene)
            width, height = data.params['total_width'], data.params['total_depth']
            result = build_door_result(
                w=source_w, h=source_h, t=t, fw=fw, gap_w=gw, gap_h=gh,
                fold_left=19.0, fold_right=19.0, fold_top=19.0, fold_bottom=19.0,
            )
            guide = build_finished_reference_guide(
                "indicator_door", result, finished_width=finished_w, finished_height=finished_h,
            )
            feature_store = self.door_layout_indicator_door_features.setdefault(key, [])
            baseline_scene = data.scene
            status = ae.indicator_shared_baseline_source_label("小門.dxf")
            title = "指示燈小門"
        else:
            return

        self._open_unified_hole_editor(
            component, f"{title} [{key}]", surface, width, height,
            reference_guide=guide, feature_list_override=feature_store,
            baseline_scene=baseline_scene, baseline_status_text=status,
            on_close=self.draw_door_layout_overview,
        )

    def open_door_layout_cell_editor(self, column_index, row_index):
        """Open the unified Door hole editor for exactly one multi-door layout cell."""
        existing = getattr(self, "last_unified_hole_editor", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        self.door_layout_selected_var.set(f"{int(column_index)}:{int(row_index)}")
        cell = self.get_selected_door_layout_cell()
        key = self._door_layout_cell_key(cell)
        try:
            val = self.get_float_values()
            result = self._door_layout_cell_result(cell, val)
            surface = feature_surface_from_structural_result("door", result)
            material_fw = self._door_material_frame_width(val['fw'], val['t'])
            finished_w, finished_h = ae.calculate_door_finished_size(
                cell.start_width, cell.start_height, material_fw, val['door_gap_w'], val['door_gap_h'], val['t'],
                frame_edges=cell.edges,
            )
            reference_guide = build_finished_reference_guide(
                "door", result, finished_width=finished_w, finished_height=finished_h,
            )
        except Exception as exc:
            messagebox.showerror("開孔失敗", str(exc))
            return
        features = self.door_layout_features.setdefault(key, [])
        indicator_state = self._door_layout_indicator_state_for_key(key)
        indicator_context = DoorIndicatorContext(
            finished_width=finished_w, finished_height=finished_h,
            left_fold=val['door_fold_l'], bottom_fold=val['door_fold_b'],
        )
        baseline_scene, baseline_status = self._door_layout_baseline_scene(cell, val)
        self._open_unified_hole_editor(
            "door", f"門板 C{cell.column_index+1}-R{cell.row_index+1}",
            surface, result.width, result.height,
            reference_guide=reference_guide,
            feature_list_override=features,
            door_indicator_state=indicator_state,
            door_indicator_context=indicator_context,
            door_indicator_commit=lambda state, key=key: self._apply_multi_door_indicator_state(key, state),
            door_frame_edges=cell.edges, door_gap_w=val['door_gap_w'], door_gap_h=val['door_gap_h'],
            door_frame_width=val['fw'], door_thickness=val['t'],
            on_close=self.draw_door_layout_overview,
            baseline_scene=baseline_scene, baseline_status_text=baseline_status,
            indicator_component_context_provider=lambda state, key=key, val=val: self._indicator_component_editor_contexts(
                state, val,
                box_features=self.door_layout_indicator_box_features.setdefault(key, []),
                door_features=self.door_layout_indicator_door_features.setdefault(key, []),
            ),
        )

    def _door_layout_overview_snapshot(self, render_data_by_part_key=None):
        return _door_layout_overview_snapshot_impl(self, render_data_by_part_key)
    def draw_door_layout_overview(self, *, canvas=None, render_data_by_part_key=None):
        if canvas is None: self._sync_door_canvas_double_click_binding(); canvas = self.canvas_door
        self._destroy_door_layout_entry_widgets()
        snapshot = self._door_layout_overview_snapshot(render_data_by_part_key)
        if snapshot.get("error") is not None: return _draw_door_layout_error_impl(self, canvas, snapshot["error"])
        return _draw_door_layout_overview_preview_impl(self, snapshot, canvas)

    def _door_layout_divider_frame_snapshot(self, columns, val):
        return _door_layout_divider_frame_snapshot_impl(self, columns, val)
    def _draw_door_layout_dividers_and_frames(self, canvas, scale, x0, y0, columns, cells, val):
        snapshot = self._door_layout_divider_frame_snapshot(columns, val)
        return _draw_door_layout_dividers_and_frames_preview_impl(canvas, snapshot, scale, x0, y0)

    def _single_door_render_snapshot(self):
        return _single_door_render_snapshot_impl(self)
    def draw_door(self, val):
        if self.multi_door_enabled_var.get(): return self.draw_door_layout_overview()
        canvas = self.canvas_door; canvas.delete("all"); cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._single_door_render_snapshot()
        except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "門板", exc, width=cw-40, font_size=10)
        return _draw_single_door_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _base_plate_render_snapshot(self, val):
        return _base_plate_render_snapshot_impl(self, val)
    def draw_base_plate(self, val):
        canvas = self.canvas_base_plate; canvas.delete("all"); cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._base_plate_render_snapshot(val)
        except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "底板", exc, font_size=10)
        return _draw_base_plate_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _disable_all_door_indicators(self):
        """Disable only the legacy single-Door direct-indicator mode.

        Multi-Door cells own their own mutually-exclusive mode and must not be
        changed by the single-Door Indicator-Box checkbox.
        """
        self.is_door_indicator_var.set(False)

    def _disable_indicator_box_for_door_indicator(self):
        """Direct Door indicators remove the separate Indicator-Box assembly from physical presence."""
        self.is_indicator_box_var.set(False)
        existing = self.workspace_controller.set_part_presence("indicator_box", False)
        existing = self.workspace_controller.set_part_presence("indicator_door", False)
        self._phase6_refresh_presence_ui(existing)
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")

    def on_indicator_box_toggle(self):
        """Indicator Box toggle also owns physical box/small-door presence."""
        enabled = bool(self.is_indicator_box_var.get())
        if enabled:
            self._disable_all_door_indicators()
        self._phase6_set_part_presence("indicator_box", enabled)
        self._phase6_set_part_presence("indicator_door", enabled)
        self._request_phase6_update("geometry")

    def on_door_indicator_toggle(self):
        """Direct Door indicators exclude the Indicator-Box opening mode without hiding its tabs."""
        if self.is_door_indicator_var.get():
            self._disable_indicator_box_for_door_indicator()
        self._request_phase6_update("geometry")

    def on_door_layers_count_changed(self):
        self.rebuild_door_layers_config_ui()
        self._request_phase6_update("geometry")

    def rebuild_door_layers_config_ui(self):
        return _rebuild_door_layers_config_ui_impl(self)
    def reset_door_indicator_offset_x(self):
        self.door_indicator_offset_x = 0.0
        self.draw_preview()

    def reset_door_indicator_offset_y(self):
        self.door_indicator_offset_y = 0.0
        self.draw_preview()

        draw_hole_editor_hint(canvas, cw, endcap=False)

    def _door_layout_cell_at_canvas_point(self, x, y):
        return _door_layout_cell_at_canvas_point_impl(self.door_layout_cell_bounds, x, y)

    def on_door_canvas_press(self, event):
        return _on_door_canvas_press_impl(self, event)

    def on_door_canvas_drag(self, event):
        return _on_door_canvas_drag_impl(self, event)

    def on_door_canvas_release(self, event):
        return _on_door_canvas_release_impl(self, event)

    def on_door_canvas_double_click(self, event):
        return _on_door_canvas_double_click_impl(self, event)

    def ask_xy_dialog(self, current_x, current_y):
        return _ask_xy_dialog_impl(self.root, current_x, current_y, color_bg=self.COLOR_BG, color_text=self.COLOR_TEXT,
                                   color_panel=self.COLOR_PANEL, color_accent=self.COLOR_ACCENT)

    def on_double_click_indicator(self):
        params = self.last_door_draw_params
        context = params.get('indicator_context')
        groups = params.get('indicator_groups')
        layout = params.get('indicator_layout')
        if context is None or not groups or layout is None:
            return
        try:
            t_val = float(self.t_var.get())
        except Exception:
            t_val = 2.0
        try:
            fw_val = float(self.fw_z_var.get())
        except Exception:
            fw_val = 62.0

        position = measure_door_indicator_position(
            layout,
            context,
            frame_width=fw_val,
            thickness=t_val,
            use_box_distance=self.is_box_dist_var.get(),
            frame_edges=params.get('frame_edges') or DoorFrameEdges(),
            gap_w=float(self.door_gap_w_var.get()), gap_h=float(self.door_gap_h_var.get()),
        )
        new_x, new_y = self.ask_xy_dialog(position.distance_x, position.distance_y)
        if new_x is not None and new_y is not None:
            target = door_indicator_offset_for_position(
                context,
                groups,
                x_distance=new_x,
                y_distance=new_y,
                frame_width=fw_val,
                thickness=t_val,
                use_box_distance=self.is_box_dist_var.get(),
                frame_edges=params.get('frame_edges') or DoorFrameEdges(),
                gap_w=float(self.door_gap_w_var.get()), gap_h=float(self.door_gap_h_var.get()),
            )
            self.door_indicator_offset_x = target.x
            self.door_indicator_offset_y = target.y
            self.draw_preview()

    def _indicator_small_door_gap_text(self):
        gap = float(manufacturing_api.resolve_policy().indicator_small_door_gap)
        return f"{gap:g}"

    def _route_indicator_canvas_configure(self, event=None):
        return self.draw_preview()

    def _indicator_small_door_size_chain_label(self):
        return _indicator_small_door_size_chain_label_impl(self)

    def setup_tab_indicator_door_ui(self):
        return _setup_tab_indicator_door_ui_impl(self)

    def _indicator_door_render_snapshot(self, val):
        return _indicator_door_render_snapshot_impl(self, val)
    def draw_indicator_door(self, val):
        canvas = self.canvas_indicator_door; canvas.delete("all")
        cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._indicator_door_render_snapshot(val)
        except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "指示燈小門", exc)
        return _draw_indicator_door_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    _inherit_known_corner_state_into_custom = _phase6_cabinet_controller._inherit_known_corner_state_into_custom
    _capture_cabinet_family_runtime = _phase6_cabinet_controller._capture_cabinet_family_runtime
    _restore_cabinet_family_runtime = _phase6_cabinet_controller._restore_cabinet_family_runtime
    _apply_cabinet_family_for_current_model = _phase6_cabinet_controller._apply_cabinet_family_for_current_model
    on_baseline_changed = _phase6_cabinet_controller.on_baseline_changed
    get_float_values = _phase6_cabinet_controller.get_float_values
    _active_indicator_box_groups_for_results = _phase6_cabinet_controller._active_indicator_box_groups_for_results
    _has_any_indicator_box = _phase6_cabinet_controller._has_any_indicator_box
    _clear_indicator_box_result_values = _phase6_cabinet_controller._clear_indicator_box_result_values
    _refresh_indicator_box_result_values = _phase6_cabinet_controller._refresh_indicator_box_result_values

    update_calculations = _phase6_calculation_controller.update_calculations

    def draw_preview(self):
        return _draw_preview_route_impl(self)

    draw_grid = _draw_grid_impl


    def _box_body_face_at_canvas_point(self, x, y):
        return _box_body_face_at_canvas_point_impl(self.box_body_face_bounds, x, y)

    def select_box_body_face(self, face_key):
        return _select_box_body_face_impl(self, face_key)

    def on_box_body_canvas_press(self, event):
        return _on_box_body_canvas_press_impl(self, event)

    def _box_body_baseline_faces(self, val):
        return _box_body_baseline_faces_impl(self, val, ae_module=ae)

    def _box_body_face_baseline_scene(self, face_key, val):
        resolved = self._box_body_baseline_faces(val).get(face_key, [])
        if not resolved:
            return None
        scene = DrawingScene()
        scene.extend(resolved_features_to_primitives(resolved))
        return scene

    def open_box_body_face_editor(self, face_key):
        return _open_box_body_face_editor_impl(self, face_key, messagebox_module=messagebox, face_dimensions_fn=box_body_face_dimensions, vertical_offsets_fn=box_body_vertical_offsets, surface_builder=feature_surface_from_rect, guide_type=RectGuide, vec2_type=Vec2, baseline_label_fn=ae.box_body_baseline_source_label)

    @staticmethod
    def _box_body_piece_label(part_key):
        return _box_body_piece_label_impl(part_key)

    @staticmethod
    def _box_body_piece_face_key(part_key):
        return _box_body_piece_face_key_impl(part_key)

    def _refresh_box_body_piece_tabs_2d(self, render_data):
        return _refresh_box_body_piece_tabs_2d_impl(self, render_data)

    def _on_box_body_piece_2d_tab_changed(self, event=None):
        return _on_box_body_piece_2d_tab_changed_impl(self, event)

    def on_box_body_piece_double_click(self, event=None):
        return _on_box_body_piece_double_click_impl(self, event)

    def _draw_box_body_piece_preview(self, aggregate_render_data, piece, part_key):
        return _draw_box_body_piece_preview_impl(self, aggregate_render_data, piece, part_key, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection)

    def _box_body_render_snapshot(self, val):
        return _box_body_render_snapshot_impl(self, val, face_dimensions_fn=box_body_face_dimensions)
    def draw_box_body(self, val):
        canvas = self.canvas_z; canvas.delete("all"); self.box_body_face_bounds = {}
        cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        snapshot = self._box_body_render_snapshot(val)
        if snapshot["mode"] == "piece": return self._draw_box_body_piece_preview(snapshot["render_data"], snapshot["piece"], snapshot["piece_key"])
        return _draw_box_body_aggregate_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _end_cap_render_snapshot(self, val, *, part_label='封頭/尾', is_tail=False):
        return _end_cap_render_snapshot_impl(self, val, part_label=part_label, is_tail=is_tail)
    def draw_end_cap(self, val, canvas, part_label='封頭/尾', is_tail=False):
        canvas.delete("all"); cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._end_cap_render_snapshot(val, part_label=part_label, is_tail=is_tail)
        except Exception as exc: return _draw_end_cap_error_impl(self, canvas, cw, ch, exc, hint_drawer=draw_hole_editor_hint)
        return _draw_end_cap_preview_impl(self, snapshot, canvas, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    _manufacturing_context = _phase6_manufacturing_adapter._manufacturing_context
    _box_body_part_spec_from_values = _phase6_manufacturing_adapter._box_body_part_spec_from_values
    _box_body_part_spec = _phase6_manufacturing_adapter._box_body_part_spec
    _end_cap_part_spec_from_values = _phase6_manufacturing_adapter._end_cap_part_spec_from_values
    _phase6_relief_profile_signature = staticmethod(_phase6_manufacturing_adapter._phase6_relief_profile_signature)
    _resolved_committed_assembly_relief_cuts = _phase6_manufacturing_adapter._resolved_committed_assembly_relief_cuts
    _end_cap_part_spec = _phase6_manufacturing_adapter._end_cap_part_spec
    _door_part_spec_from_values = _phase6_manufacturing_adapter._door_part_spec_from_values
    _single_door_part_spec = _phase6_manufacturing_adapter._single_door_part_spec
    _door_layout_part_spec = _phase6_manufacturing_adapter._door_layout_part_spec
    _validate_indicator_state_fit = _phase6_manufacturing_adapter._validate_indicator_state_fit
    _validate_single_door_indicator_fit = _phase6_manufacturing_adapter._validate_single_door_indicator_fit
    _validate_door_layout_indicator_fit = _phase6_manufacturing_adapter._validate_door_layout_indicator_fit
    _base_plate_part_spec_from_values = _phase6_manufacturing_adapter._base_plate_part_spec_from_values
    _base_plate_part_spec = _phase6_manufacturing_adapter._base_plate_part_spec
    _indicator_box_part_spec_from_values = _phase6_manufacturing_adapter._indicator_box_part_spec_from_values
    _indicator_box_part_spec = _phase6_manufacturing_adapter._indicator_box_part_spec
    _indicator_door_part_spec_from_values = _phase6_manufacturing_adapter._indicator_door_part_spec_from_values
    _indicator_door_part_spec = _phase6_manufacturing_adapter._indicator_door_part_spec
    _indicator_component_editor_contexts = _phase6_manufacturing_adapter._indicator_component_editor_contexts

    export_multi_door_layout_dxfs = _phase6_project_export.export_multi_door_layout_dxfs
    export_multi_door_indicator_box_parts = _phase6_project_export.export_multi_door_indicator_box_parts
    export_selected_dxf = _phase6_project_export.export_selected_dxf
    _single_door_indicator_state_snapshot = _phase6_project_export._single_door_indicator_state_snapshot
    _apply_single_door_indicator_state = _phase6_project_export._apply_single_door_indicator_state
    _apply_multi_door_indicator_state = _phase6_project_export._apply_multi_door_indicator_state

    def open_part_hole_editor(self, part_key):
        return _open_part_hole_editor_impl(self, part_key)

    def _open_unified_hole_editor(self, *args, **kwargs):
        return _open_unified_hole_editor_impl(self, *args, dependencies=_HoleEditorCompositionDependencies.from_namespace(globals()), **kwargs)

    def open_hole_editor(self, key):
        return _open_hole_editor_impl(self, key)



class BoxCalculatorGUI(Phase6ApplicationHost):
    """Legacy 2D compatibility shell retained only for non-primary callers.

    Production startup uses Phase6PrimaryApplication. T5 owns final dead-code
    cleanup after the complete direct-3D regression matrix is terminal GREEN.
    """


class Phase6PrimaryApplication(Phase6ApplicationHost):
    """Primary 3D application owner on the shared non-legacy application host."""

    def __init__(self, root):
        self._phase6_primary_workspace = True
        super().__init__(root)
        self.open_original_fold_designer(target_window=root)

    def create_widgets(self):
        """Legacy 2D user-facing widgets are not part of the primary lifecycle."""
        self._legacy_2d_compat_host = None
        return None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        register_windows_file_association(
            executable=sys.executable, script_path=str(Path(__file__).resolve()),
            frozen=bool(getattr(sys, "frozen", False)),
        )
    except Exception:
        # File association is convenience only; it must never block CAD startup.
        pass

    root = tk.Tk()
    app = Phase6PrimaryApplication(root)
    project_path = project_path_from_argv(argv)
    if project_path is not None:
        def open_project_after_startup():
            try:
                app.load_phase6_project(project_path, open_designer=True)
            except Exception as exc:
                messagebox.showerror("專案開啟失敗", f"無法開啟 Phase6 專案：\n{exc}", parent=root)
        root.after_idle(open_project_after_startup)
    root.mainloop()
    return app


if __name__ == "__main__":
    main()
