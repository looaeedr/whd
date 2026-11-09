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
from collections.abc import Mapping
from phase6_sync_envelope import stable_fingerprint
from dataclasses import replace
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS, apply_ttk_dark_theme
from gui_modules.runtime_error_log import install_tk_exception_logging, write_runtime_exception
from ae_engine import manufacturing_api
# Legacy GUI import compatibility; all decisions remain in public Engine.
is_unknown_model = manufacturing_api.is_unknown_operator_model
assembly_type_from_corner_state = manufacturing_api.operator_assembly_type_from_corner_state
from ae_engine.cabinet_types import (
    policy as cabinet_family_policy,
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
)
from ae_engine.sheetmetal_features import (
    box_body_face_contexts_from_strip,
    resolve_box_body_face_features,
    CircleFeature,
    DoorIndicatorContext,
    RectFeature,
    ProfileFeature,
    legacy_hole_to_feature,
    resolve_door_indicator_features,
    resolve_door_indicator_layout,
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
    feature_surface_from_structural_result,
    feature_surface_from_outline,
    ReferenceAnchor,
    REFERENCE_ANCHOR_LABELS,
    REFERENCE_ANCHOR_BY_LABEL,
    feature_reference_anchor,
    feature_reference_point,
    reference_distances,
    circle_center_distance_from_gap,
    circle_gap_from_center_distance,
    align_circle_to_neighbor,
    generate_round_fill,
    generate_round_refill,
    RectGuide,  # Existing unified HoleEditor composition dependency.
)


from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    derive_door_layout_cells,
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


# Stable compatibility names consumed by HoleEditorCompositionDependencies.
# Always pass public Engine geometry ownership into UI/session controllers.
# Read-only CornerType compatibility remains a public Engine callable.
normalize_corner_selection = manufacturing_api.operator_normalize_corner_selection

measure_door_indicator_position = manufacturing_api.project_operator_door_indicator_position
feature_with_reference_anchor = manufacturing_api.operator_hole_feature_with_reference_anchor
feature_with_process = manufacturing_api.operator_hole_feature_with_process
move_feature_by_reference_distance = manufacturing_api.operator_hole_move_feature_by_reference_distance
feature_is_within_surface = manufacturing_api.operator_hole_feature_is_within_surface
move_feature_within_surface = manufacturing_api.operator_hole_move_feature_within_surface

from ae_engine.corner_type_ui import (
    UNKNOWN_MODEL_NAME,
    CUSTOM_MODEL_NAME,
    CORNER_KEYS,
    CORNER_LABELS,
    with_unknown_model,
    normalize_custom_model_name,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
    policy_from_corner_state,
    build_corner_type_preview_geometry,
    apply_box_assembly_type,
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

from gui_modules.application.door_layout_controller import (
    DoorLayoutColumnState as _DoorLayoutColumnState,
    door_layout_cells as _door_layout_cells_impl,
    recompute_door_layout as _recompute_door_layout_impl,
    remap_owned_data as _remap_door_layout_owned_data_impl,
    validate_height_commit as _validate_door_layout_height_commit_impl,
    validate_width_commit as _validate_door_layout_width_commit_impl,
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
        resolver=manufacturing_api.resolve_hole_editor_canvas_features,
        feature_renderer=render_resolved_features,
    )


def feature_surface_from_drawing_scene(surface_id, scene):
    return _feature_surface_from_drawing_scene_impl(surface_id, scene)


def _draw_phase6_annotation_projection(
    canvas, render_data, transform, *, part_key="", strict=False,
):
    return _draw_phase6_annotation_projection_impl(
        canvas, render_data, transform,
        part_key=part_key, strict=strict,
        projection_builder=manufacturing_api.project_operator_engineering_drawing_annotations,
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
                  transform_type=manufacturing_api.CanvasTransform)
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


# The GUI composition injects exactly the public Engine catalog functions.
# Keep the legacy dependency names only for the existing UI composition port.
load_hole_catalog = manufacturing_api.operator_load_hole_catalog
load_pipe_catalog = manufacturing_api.operator_load_pipe_catalog
feature_from_definition = manufacturing_api.operator_hole_feature_from_definition
custom_circle_definition = manufacturing_api.operator_custom_circle_definition
custom_rectangle_definition = manufacturing_api.operator_custom_rectangle_definition


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
    mirror_point_y,
)

from gui_modules.application import lifecycle as _phase6_lifecycle
from gui_modules.application import command_router as _phase6_command_router
from gui_modules.application import state_sync as _phase6_state_sync
from gui_modules.application import cabinet_controller as _phase6_cabinet_controller
from gui_modules.application import calculation_controller as _phase6_calculation_controller
from gui_modules.application import fold_designer_adapter as _phase6_fold_adapter
from gui_modules.application import door_layout_host_adapter as _door_layout_host_adapter
from gui_modules.application import door_render_host_adapter as _door_render_host_adapter
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
        """One shared Engine catalog for Vault, Receiving and Custom choices."""
        return manufacturing_api.list_cabinet_model_choices()

    def _endcap_depth_comp_t_for_family(self, model_name=None):
        source = (
            Phase6ApplicationHost._current_cabinet_type_name(self)
            if model_name is None else model_name
        )
        return manufacturing_api.project_operator_endcap_depth_comp_t(source)

    def _known_corner_state_for_current_family(self, parts):
        return manufacturing_api.operator_known_model_corner_state(
            parts, cabinet_family=Phase6ApplicationHost._current_cabinet_type_name(self)
        )

    def _enforce_known_model_corner_types(self, *, reset_all=False):
        """Apply only the fully validated typed Engine/Registry corner draft."""
        model = str(self.baseline_var.get() if hasattr(self, "baseline_var") else "").strip()
        next_state, next_pairs = manufacturing_api.propose_operator_known_model_corner_draft(
            self.manual_corner_state, self.manual_corner_pair_same,
            baseline_model=model,
            cabinet_family=Phase6ApplicationHost._current_cabinet_type_name(self),
            reset_all=reset_all,
        )
        # Install only after Engine validates the entire candidate.
        # Preserve original nested dicts used by live GUI subscribers.
        for part_key, updated in next_state.items():
            existing = self.manual_corner_state[part_key]
            if existing != updated:
                existing.clear()
                existing.update(updated)
        for part_key, updated in next_pairs.items():
            existing = self.manual_corner_pair_same[part_key]
            if existing != updated:
                existing.clear()
                existing.update(updated)


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
                return manufacturing_api.operator_assembly_type_from_corner_state(corner_state)
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
        # Commit one detached, Engine-validated Joint workspace transaction.
        self.assembly_joint_state = manufacturing_api.commit_operator_box_assembly_joint_state(
            getattr(self, "assembly_joint_state", {}) or {},
            stable, available_parts=parts,
        )
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
        if not manufacturing_api.is_unknown_operator_model(self.baseline_var.get()):
            return
        type_id = self._current_box_assembly_type()
        self._set_box_assembly_type(type_id, reset_bottom_defaults=False)

    def _effective_endcap_fw(self, part_key, box_fw=None):
        # Only Engine validates physical FW before using it as Corner Policy input.
        if box_fw is None:
            fw_var = getattr(self, "fw_z_var", None)
            box_fw = (
                fw_var.get() if fw_var is not None
                else self.settings_service.snapshot().get("fw")
            )
        validated_fw = manufacturing_api.normalize_operator_source_dimension(
            box_fw, field="fw",
        )
        state = getattr(self, "endcap_fw_state", None)
        if state is None:
            return validated_fw
        # Validate both persisted physical rows before the original Engine
        # four-state resolver may consume their values in manufacturing policy.
        manufacturing_api.project_operator_endcap_fw_controls(
            state, validated_fw,
        )
        return manufacturing_api.resolve_endcap_fw(
            {"fw": validated_fw, "endcap_fw": state}, part_key, state=state,
        )

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
        # Engine alone validates raw follow flags, physical FW and saved rows.
        # Do not coerce serialized follow flags or partially commit state.
        follow_var = self.fw_head_follow_var if part_key == "head" else self.fw_tail_follow_var
        try:
            staged = manufacturing_api.operator_endcap_fw_follow(
                {"fw": self.fw_z_var.get()}, {}, self.endcap_fw_state,
                part_key, follow_var.get(),
            )
        except (TypeError, ValueError, tk.TclError):
            self._sync_endcap_fw_controls()
            return
        self.endcap_fw_state = staged
        self._sync_endcap_fw_controls()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        self._request_phase6_update("geometry")

    def on_fw_selected(self, source):
        # Only Engine may validate and commit the four-state physical FW source.
        # Transient invalid Tk values must not mutate even one EndCap row.
        try:
            if source == "z":
                # Explicit box takeover also applies for an unchanged number.
                manufacturing_api.commit_operator_box_fw_takeover(
                    self.endcap_fw_state, self.fw_z_var.get(),
                )
            elif source in {"head", "tail"}:
                var = self.fw_head_var if source == "head" else self.fw_tail_var
                manufacturing_api.commit_operator_endcap_fw_value(
                    self.endcap_fw_state, source, var.get(),
                    box_fw=self.fw_z_var.get(),
                )
            else:
                return
        except (TypeError, ValueError, tk.TclError):
            # Restore the authoritative saved values instead of propagating a
            # NaN/invalid operator value into PartSpec or 2D/3D/DXF caches.
            self._sync_endcap_fw_controls()
            return
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
        if not value or manufacturing_api.is_unknown_operator_model(value):
            return None
        return value

    def _door_material_frame_width(self, frame_width, thickness, *, model_name=None):
        """Resolve operator Door FW into the material-space value consumed by AE."""
        source = self._baseline_source_model() if model_name is None else model_name
        # Keep the operator's authored FW/T intact until the public Family
        # Engine validates the physical source and resolves material-space FW.
        return manufacturing_api.door_material_frame_width(
            source, frame_width=frame_width, thickness=thickness,
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
        """Collect live editor state; delegate manufacturing policy to Engine."""
        state_map = getattr(self, "manual_corner_state", None)
        model_name = self._baseline_source_model() if hasattr(self, "_baseline_source_model") else None
        has_explicit = isinstance(state_map, dict) and part_key in state_map
        family = (
            Phase6ApplicationHost._current_cabinet_type_name(self)
            if model_name and not has_explicit else None
        )
        policy = manufacturing_api.resolve_live_corner_policy(
            state_map, part_key, fw, model_name=model_name, cabinet_family=family,
        )
        if has_explicit:
            family_adapter = getattr(self, "_apply_cabinet_family_endcap_policy", None)
            if callable(family_adapter):
                return family_adapter(policy, part_key)
        return policy

    def _box_body_corner_policies(self, fw):
        """One shared CornerType state for custom and known models alike."""
        if hasattr(self, "fw_z_var") and hasattr(self, "endcap_fw_state"):
            head_fw = self._effective_endcap_fw("head", fw)
            tail_fw = self._effective_endcap_fw("tail", fw)
        else:
            # Keep this geometry helper independently usable by tests/legacy
            # callers that do not construct the full Tk FW-link state.
            head_fw = tail_fw = manufacturing_api.normalize_operator_source_dimension(
                fw, field="fw",
            )
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
                manufacturing_api.normalize_operator_source_dimension(
                    snapshot.get("fw"), field="fw",
                )
            )
        return manufacturing_api.resolve_operator_finished_dimensions(
            key,
            snapshot=snapshot,
            settings=settings,
            thickness=manufacturing_api.normalize_operator_source_dimension(
                snapshot.get("t"), field="t",
            ),
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
        """Only forward the operator source to Engine's canonical outside-height owner."""
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        return manufacturing_api.project_operator_box_body_finished_height(
            val['h'], val['t'],
            head_corner_policy=head_policy,
            tail_corner_policy=tail_policy,
        )

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
            manufacturing_api.is_unknown_operator_model(self.baseline_var.get())
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
        physical_key = manufacturing_api.project_operator_corner_selection_target(
            target_key,
        )
        return manufacturing_api.operator_normalize_corner_selection(
            self.manual_corner_state[part_key][physical_key],
        )

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
        manufacturing_api.operator_set_manual_corner_pair_same(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key], pair_key, enabled
        )
        if enabled:
            self.manual_active_corner_var.set(pair_key)
        elif self._pair_for_corner_target(self.manual_active_corner_var.get()) == pair_key:
            self.manual_active_corner_var.set(
                manufacturing_api.project_operator_corner_pair_members(pair_key)[0]
            )
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
        manufacturing_api.operator_apply_manual_corner_selection(
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
        manufacturing_api.operator_apply_manual_corner_selection(
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
        manufacturing_api.operator_apply_manual_corner_selection(
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
            transform = manufacturing_api.CanvasTransform(
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

    _door_layout_number_text = staticmethod(_door_layout_host_adapter._door_layout_number_text)
    _new_door_layout_column = _door_layout_host_adapter._new_door_layout_column
    set_door_layout_columns = _door_layout_host_adapter.set_door_layout_columns
    _ensure_door_layout_default = _door_layout_host_adapter._ensure_door_layout_default
    _parse_layout_value = staticmethod(_door_layout_host_adapter._parse_layout_value)
    _door_layout_controller_columns = _door_layout_host_adapter._door_layout_controller_columns
    _recompute_door_layout_remainders = _door_layout_host_adapter._recompute_door_layout_remainders
    get_door_layout_columns = _door_layout_host_adapter.get_door_layout_columns
    get_door_layout_cells = _door_layout_host_adapter.get_door_layout_cells
    _door_layout_cell_key = staticmethod(_door_layout_host_adapter._door_layout_cell_key)
    get_selected_door_layout_cell = _door_layout_host_adapter.get_selected_door_layout_cell
    select_door_layout_cell = _door_layout_host_adapter.select_door_layout_cell
    _sync_door_canvas_double_click_binding = _door_layout_host_adapter._sync_door_canvas_double_click_binding
    toggle_multi_door_layout = _door_layout_host_adapter.toggle_multi_door_layout
    _reject_door_layout_dimension = _door_layout_host_adapter._reject_door_layout_dimension
    commit_door_layout_width = _door_layout_host_adapter.commit_door_layout_width
    commit_door_layout_height = _door_layout_host_adapter.commit_door_layout_height
    add_door_layout_column = _door_layout_host_adapter.add_door_layout_column
    _remap_door_layout_owned_data = _door_layout_host_adapter._remap_door_layout_owned_data
    remove_door_layout_column = _door_layout_host_adapter.remove_door_layout_column
    add_door_layout_height = _door_layout_host_adapter.add_door_layout_height
    remove_door_layout_height = _door_layout_host_adapter.remove_door_layout_height
    _on_door_layout_value_changed = _door_layout_host_adapter._on_door_layout_value_changed
    _on_total_door_dimension_changed = _door_layout_host_adapter._on_total_door_dimension_changed

    def _on_main_geometry_var_changed(self, reason="geometry"):
        self._phase6_update_scheduler.mark_dirty(reason)

    @staticmethod
    def _receiving_inner_door_stable_id_for_cell(cell_key):
        """Operator-facing adapter; physical part identity belongs to Engine."""
        return manufacturing_api.receiving_inner_door_stable_id_for_cell(cell_key)

    def _receiving_inner_door_enabled(self, cell_key):
        # A duplicate/malformed saved physical source must never be hidden by
        # GUI's first-match selection or silent row filtering.
        return manufacturing_api.project_operator_receiving_inner_door_cell_source(
            getattr(self, "receiving_inner_doors", None),
            cell_key=cell_key,
        ) is not None

    def _receiving_inner_door_inward_offset(self, cell_key):
        item = manufacturing_api.project_operator_receiving_inner_door_cell_source(
            getattr(self, "receiving_inner_doors", None),
            cell_key=cell_key,
        )
        return manufacturing_api.resolve_operator_receiving_inner_door_inward_offset(
            {"model": str(self.baseline_var.get() or "").strip()}, item,
        )

    def _set_receiving_inner_door_inward_offset(self, cell_key, value):
        # GUI commits only the Engine's detached physical-source transaction.
        rows, offset = manufacturing_api.apply_operator_receiving_inner_door_inward_offset(
            getattr(self, "receiving_inner_doors", None),
            cell_key=cell_key, inward_offset_mm=value,
        )
        self.receiving_inner_doors = rows
        return offset

    def _commit_receiving_inner_door_inward_offset(self, cell_key):
        key = str(cell_key or "").strip()
        var = dict(getattr(self, "door_layout_inner_door_offset_vars", {}) or {}).get(key)
        if var is None:
            return False
        try:
            value = self._set_receiving_inner_door_inward_offset(key, var.get())
        except (TypeError, ValueError):
            # Invalid saved physical offsets are not silently corrected or
            # persisted by an unrelated failing edit.
            try:
                current = self._receiving_inner_door_inward_offset(key)
            except (TypeError, ValueError):
                return False
            var.set(self._fold_designer_number_text(current))
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
        # Do not filter/sort/commit physical Door identities inside Tk.
        rows = manufacturing_api.apply_operator_receiving_inner_door_presence(
            {"model": str(self.baseline_var.get() or "").strip()},
            getattr(self, "receiving_inner_doors", None),
            cell_key=cell_key, enabled=enabled,
        )
        self.receiving_inner_doors = rows
        return enabled

    def _commit_receiving_inner_door_checkbox(self, cell_key):
        key = str(cell_key or "").strip()
        var = dict(getattr(self, "door_layout_inner_door_vars", {}) or {}).get(key)
        if var is None:
            # A missing checkbox is not an authored "disable inner door".
            raise ValueError("內門選取控制不存在，拒絕變更實體板件")
        # The public Engine interprets raw operator/serialized booleans.
        # Preserve an authored "false" instead of Python truthiness.
        enabled = manufacturing_api.normalize_operator_settings_boolean(var.get())
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



    _indicator_box_render_snapshot = _door_render_host_adapter._indicator_box_render_snapshot
    draw_indicator_box = _door_render_host_adapter.draw_indicator_box
    _normalize_door_indicator_state = _door_render_host_adapter._normalize_door_indicator_state
    _door_layout_indicator_state_for_key = _door_render_host_adapter._door_layout_indicator_state_for_key
    _door_layout_cell_result = _door_render_host_adapter._door_layout_cell_result
    _door_layout_cell_resolved_features = _door_render_host_adapter._door_layout_cell_resolved_features
    _door_layout_baseline_scene = _door_render_host_adapter._door_layout_baseline_scene
    _door_layout_overview_snapshot = _door_render_host_adapter._door_layout_overview_snapshot
    draw_door_layout_overview = _door_render_host_adapter.draw_door_layout_overview
    _door_layout_divider_frame_snapshot = _door_render_host_adapter._door_layout_divider_frame_snapshot
    _draw_door_layout_dividers_and_frames = _door_render_host_adapter._draw_door_layout_dividers_and_frames
    _single_door_render_snapshot = _door_render_host_adapter._single_door_render_snapshot
    draw_door = _door_render_host_adapter.draw_door
    _base_plate_render_snapshot = _door_render_host_adapter._base_plate_render_snapshot
    draw_base_plate = _door_render_host_adapter.draw_base_plate
    _indicator_door_render_snapshot = _door_render_host_adapter._indicator_door_render_snapshot
    draw_indicator_door = _door_render_host_adapter.draw_indicator_door

    def _destroy_door_layout_entry_widgets(self):
        return _destroy_door_layout_entry_widgets_impl(self)
    def _door_layout_entry_menu(self, entry, *, column_index, row_index=None):
        return _door_layout_entry_menu_impl(self, entry, column_index=column_index, row_index=row_index)
    def open_door_indicator_component_editor(self, key, component):
        """Open the Engine-resolved Indicator Box/Small Door feature editor."""
        if component not in {"indicator_box", "indicator_door"}:
            return
        try:
            # Always validate the original committed source. Display-only
            # normalization must not authorize or rewrite physical holes.
            states = getattr(self, "door_layout_indicator_states", None)
            raw = (states.get(key) if isinstance(states, Mapping)
                   else self._door_layout_indicator_state_for_key(key))
            state = manufacturing_api.project_operator_door_cell_indicator_manufacturing_source(raw)
            if state["mode"] != "indicator_box":
                return
            val = self.get_float_values()
            groups = tuple(state["groups"][:state["layers"]])
            # The canonical shared Indicator geometry is already consumed by
            # Phase6's _indicator_component_editor_contexts. Never generate
            # another manufacturing surface or finished-face guide in GUI.
            door_features = self.door_layout_indicator_door_features.get(key, [])
            door_spec = self._indicator_door_part_spec(
                val, groups, features=door_features,
            )
            info = manufacturing_api.resolve_indicator_editor_components(
                groups, thickness=val["t"], door_spec=door_spec,
            )[component]
        except Exception as exc:
            messagebox.showerror("開孔失敗", str(exc))
            return
        surface, width, height = info.surface, info.width, info.height
        guide = info.reference_guide
        baseline_scene, status = info.baseline_scene, info.baseline_status
        if component == "indicator_box":
            feature_target = self.door_layout_indicator_box_features
            title = "指示燈盒子"
        else:
            feature_target = self.door_layout_indicator_door_features
            title = "指示燈小門"
        # The hole editor receives a private working list. Opening it must
        # not create a physical Feature row or mutate saved Features.
        feature_store = list(feature_target.get(key, []))

        def sync_indicator_component_features():
            feature_target[key] = list(feature_store)
            designer = getattr(self, "fold_designer_app", None)
            if designer is not None and isinstance(getattr(designer, "_phase6_input_snapshot", None), dict):
                designer._phase6_input_snapshot["door_layout_indicator_box_features"] = {
                    k: list(v) for k, v in self.door_layout_indicator_box_features.items()
                }
                designer._phase6_input_snapshot["door_layout_indicator_door_features"] = {
                    k: list(v) for k, v in self.door_layout_indicator_door_features.items()
                }
                designer.submit_update_intent("geometry", commit=True)
            else:
                # Per-cell indicator maps on the host are the authoritative
                # source even when the 3D Fold Designer has never been opened.
                if hasattr(self, "_derived_cache_owner"):
                    self._derived_cache_owner.invalidate("geometry")
                if hasattr(self, "_authoritative_part_render_cache"):
                    self._authoritative_part_render_cache.pop(component, None)
                if hasattr(self, "_request_phase6_update"):
                    self._request_phase6_update("geometry")

        self._open_unified_hole_editor(
            component, f"{title} [{key}]", surface, width, height,
            reference_guide=guide, feature_list_override=feature_store,
            sync_callback=sync_indicator_component_features,
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
        try:
            cell = self.get_selected_door_layout_cell()
            key = self._door_layout_cell_key(cell)
            val = self.get_float_values()
            # The host's main-Settings W/H/D may intentionally differ from
            # the active Receiving designer. Project current Bay/Quantity
            # geometry into this one editor request; never change host defaults.
            live = _door_layout_host_adapter._receiving_live_door_layout_source(self)
            if live is not None:
                snapshot, whd = live
                val.update({
                    key: snapshot[key]
                    for key in (
                        "t", "fw", "door_gap_w", "door_gap_h",
                        "door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b",
                    )
                    if key in snapshot
                })
                # Forward validated live source without GUI coercion (bool
                # must never become a valid-looking 1-mm manufactured value).
                val.update({axis: whd[axis] for axis in ("w", "h", "d")})
            result = self._door_layout_cell_result(cell, val)
            # The same DoorPartSpec drives both the editor and physical DXF.
            # Engine owns the selected cell surface, finished-face reference
            # guide, Fold datum and physical frame edges.
            door_spec = self._door_layout_part_spec(cell, val)
            baseline_scene, baseline_status = self._door_layout_baseline_scene(cell, val)
            editor_geometry = manufacturing_api.project_operator_hole_editor_door_cell(
                result, door_spec,
                baseline_scene=baseline_scene, baseline_status=baseline_status,
            )
        except Exception as exc:
            messagebox.showerror("開孔失敗", str(exc))
            return
        designer = getattr(self, 'fold_designer_app', None)
        physical_key = manufacturing_api.door_layout_part_key(cell)
        workspace = getattr(designer, 'designer_workspace', None)
        # Stage edits in a detached list; only sync_features commits them.
        features = list(
            workspace.features_for(physical_key) if workspace is not None
            and physical_key in workspace.available_parts
            else self.door_layout_features.get(key, [])
        )

        def sync_features():
            self.door_layout_features[key] = list(features)
            self.surface_features[physical_key] = list(features)
            workspace_features = self.workspace_controller.part_features_snapshot()
            workspace_features[physical_key] = list(features)
            self.workspace_controller.replace_part_features(workspace_features)
            if workspace is not None and physical_key in workspace.available_parts:
                workspace.stash_features(physical_key, features)
            if designer is not None and isinstance(getattr(designer, "_phase6_input_snapshot", None), dict):
                designer._phase6_input_snapshot["door_layout_features"] = {
                    k: list(v) for k, v in self.door_layout_features.items()
                }
                designer._phase6_input_snapshot["door_layout_indicator_states"] = {
                    k: dict(v) for k, v in self.door_layout_indicator_states.items()
                }
                designer._phase6_input_snapshot["door_layout_indicator_box_features"] = {
                    k: list(v) for k, v in self.door_layout_indicator_box_features.items()
                }
                designer._phase6_input_snapshot["door_layout_indicator_door_features"] = {
                    k: list(v) for k, v in self.door_layout_indicator_door_features.items()
                }
                designer.submit_update_intent('geometry', commit=True)
            else:
                if hasattr(self, "_derived_cache_owner"):
                    self._derived_cache_owner.invalidate("geometry")
                if hasattr(self, "_authoritative_part_render_cache"):
                    self._authoritative_part_render_cache.pop(physical_key, None)
                if hasattr(self, "_request_phase6_update"):
                    self._request_phase6_update("geometry")
        indicator_state = self._door_layout_indicator_state_for_key(key)
        self._open_unified_hole_editor(
            "door", f"門板 C{cell.column_index+1}-R{cell.row_index+1}",
            editor_geometry.surface, editor_geometry.width, editor_geometry.height,
            reference_guide=editor_geometry.reference_guide,
            feature_list_override=features,
            sync_callback=sync_features,
            door_indicator_state=indicator_state,
            door_indicator_context=editor_geometry.door_indicator_context,
            door_indicator_commit=lambda state, key=key: self._apply_multi_door_indicator_state(key, state),
            door_frame_edges=editor_geometry.door_frame_edges, door_gap_w=val['door_gap_w'], door_gap_h=val['door_gap_h'],
            door_frame_width=val['fw'], door_thickness=val['t'],
            on_close=self.draw_door_layout_overview,
            baseline_scene=editor_geometry.baseline_scene,
            baseline_status_text=editor_geometry.baseline_status,
            indicator_component_context_provider=lambda state, key=key, val=val: self._indicator_component_editor_contexts(
                state, val,
                box_features=self.door_layout_indicator_box_features.get(key, []),
                door_features=self.door_layout_indicator_door_features.get(key, []),
            ),
        )

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
        # Qualify the exact UI flag before changing either physical part.
        enabled = manufacturing_api.normalize_operator_settings_boolean(
            self.is_indicator_box_var.get()
        )
        if enabled:
            self._disable_all_door_indicators()
        self._phase6_set_part_presence("indicator_box", enabled)
        self._phase6_set_part_presence("indicator_door", enabled)
        self._request_phase6_update("geometry")

    def on_door_indicator_toggle(self):
        """Direct Door indicators exclude the Indicator-Box opening mode without hiding its tabs."""
        # The saved/textual "false" flag is not Python truthiness.
        enabled = manufacturing_api.normalize_operator_settings_boolean(
            self.is_door_indicator_var.get()
        )
        if enabled:
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
        # Use the actual operator source. The public Engine transaction
        # validates thickness/FW/gaps before any edit dialog or offset write;
        # never turn invalid live input into silent manufacturing defaults.
        t_val = self.t_var.get()
        fw_val = self.fw_z_var.get()

        position = manufacturing_api.project_operator_door_indicator_position(
            layout,
            context,
            frame_width=fw_val,
            thickness=t_val,
            use_box_distance=self.is_box_dist_var.get(),
            frame_edges=params.get('frame_edges'),
            gap_w=self.door_gap_w_var.get(), gap_h=self.door_gap_h_var.get(),
        )
        new_x, new_y = self.ask_xy_dialog(position.distance_x, position.distance_y)
        if new_x is not None and new_y is not None:
            target = manufacturing_api.propose_operator_door_indicator_offset_candidate(
                context,
                groups,
                x_distance=new_x,
                y_distance=new_y,
                frame_width=fw_val,
                thickness=t_val,
                use_box_distance=self.is_box_dist_var.get(),
                frame_edges=params.get('frame_edges'),
                gap_w=self.door_gap_w_var.get(), gap_h=self.door_gap_h_var.get(),
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
        return _box_body_baseline_faces_impl(self, val)

    def _box_body_face_baseline_scene(self, face_key, val):
        resolved = self._box_body_baseline_faces(val).get(face_key, [])
        if not resolved:
            return None
        scene = DrawingScene()
        scene.extend(manufacturing_api.project_operator_resolved_feature_drawing_primitives(resolved))
        return scene

    def open_box_body_face_editor(self, face_key):
        return _open_box_body_face_editor_impl(
            self, face_key,
            messagebox_module=messagebox,
            editor_projection=manufacturing_api.project_operator_hole_editor_box_body_face,
            baseline_label_fn=manufacturing_api.operator_box_body_baseline_source_label,
        )

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

    def _draw_box_body_piece_preview(self, aggregate_render_data, piece, part_key, *, ear_marking_preview_blocker=None):
        return _draw_box_body_piece_preview_impl(self, aggregate_render_data, piece, part_key, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, ear_marking_preview_blocker=ear_marking_preview_blocker)

    def _box_body_render_snapshot(self, val):
        return _box_body_render_snapshot_impl(self, val, face_dimensions_fn=manufacturing_api.project_operator_box_body_face_dimensions)
    def draw_box_body(self, val):
        canvas = self.canvas_z; canvas.delete("all"); self.box_body_face_bounds = {}
        cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        snapshot = self._box_body_render_snapshot(val)
        if snapshot["mode"] == "piece": return self._draw_box_body_piece_preview(snapshot["render_data"], snapshot["piece"], snapshot["piece_key"], ear_marking_preview_blocker=snapshot.get("ear_marking_preview_blocker"))
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
    export_receiving_pad_base_part_only_dxf = (
        _phase6_project_export.export_receiving_pad_base_part_only_dxf)
    export_receiving_ear_side_check_dxf = _phase6_project_export.export_receiving_ear_side_check_dxf
    export_receiving_ear_side_manufacturing_dxf = _phase6_project_export.export_receiving_ear_side_manufacturing_dxf
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
    runtime_metadata = {"build_id": PHASE6_BUILD_ID}
    runtime_log_path = install_tk_exception_logging(
        root, metadata=runtime_metadata
    )
    try:
        app = Phase6PrimaryApplication(root)
    except Exception as exc:
        logged_path = write_runtime_exception(
            "application_startup",
            exc,
            metadata=runtime_metadata,
        ) or runtime_log_path
        try:
            messagebox.showerror(
                "3D 啟動失敗",
                f"Phase6 3D 工作區載入失敗：\n{exc}\n\n錯誤紀錄：{logged_path}",
                parent=root,
            )
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
        raise

    project_path = project_path_from_argv(argv)
    if project_path is not None:
        def open_project_after_startup():
            try:
                app.load_phase6_project(project_path, open_designer=True)
            except Exception as exc:
                logged_path = write_runtime_exception(
                    "project_load",
                    exc,
                    metadata={
                        **runtime_metadata,
                        "project_path": str(project_path),
                    },
                ) or runtime_log_path
                messagebox.showerror(
                    "專案開啟失敗",
                    f"無法開啟 Phase6 專案：\n{exc}\n\n錯誤紀錄：{logged_path}",
                    parent=root,
                )
        root.after_idle(open_project_after_startup)
    root.mainloop()
    return app


if __name__ == "__main__":
    main()
