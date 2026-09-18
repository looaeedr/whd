# -*- coding: utf-8 -*-
"""
箱體展開圖計算器 - GUI 介面
"""

import tkinter as tk
from gui_modules.parts.panels.indicator_box import collect_indicator_box_input
from gui_modules.parts.panels.multipart import collect_multipart_input
from gui_modules.parts.panels.door import collect_door_input
import time
import sys
from pathlib import Path
from copy import deepcopy
from phase6_sync_envelope import stable_fingerprint
from dataclasses import replace
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from whd_theme import WHD_THEME, apply_ttk_dark_theme
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
    draw_box_body_piece_preview as _draw_box_body_piece_preview_impl,
    draw_box_body_aggregate_preview as _draw_box_body_aggregate_preview_impl,
    draw_end_cap_preview as _draw_end_cap_preview_impl,
    draw_end_cap_error as _draw_end_cap_error_impl,
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

from gui_modules.parts.panels.common import _attach_part_hole_entrypoint as __attach_part_hole_entrypoint_impl
from gui_modules.parts.panels.door import (
    _parse_layout_value as __parse_layout_value_impl,
    _reject_door_layout_dimension as __reject_door_layout_dimension_impl,
    rebuild_door_layout_ui as _rebuild_door_layout_ui_impl,
    refresh_door_layout_status as _refresh_door_layout_status_impl,
    setup_tab_door_ui as _setup_tab_door_ui_impl,
)
from gui_modules.parts.panels.indicator_box import (
    setup_tab_indicator_box_ui as _setup_tab_indicator_box_ui_impl,
    _indicator_small_door_size_chain_label as __indicator_small_door_size_chain_label_impl,
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


def _endcap_profiles_for_assembly(values, stored_profiles, assembly_type, part_key):
    """Return render profiles consistent with the current box assembly type.

    OVERLAY has no left/right X bends, even when the operator has never opened
    the 3D workspace (and therefore has no stored Phase6 profile yet).  Existing
    Y topology is preserved.  Switching back from OVERLAY restores the normal X
    topology from the shared scalar parameters without changing CornerType or
    the deferred bottom-corner rule.
    """
    intent_id = assembly_intent_value(assembly_type)
    source = dict(values or {})
    source["assembly_type"] = intent_id
    defaults = build_endcap_xy_profiles(source, part_key=part_key)
    profiles = deepcopy(dict(stored_profiles or {}))

    if not profiles:
        return defaults if intent_id == CornerTypeId.OVERLAY.value else None

    current_x = list(profiles.get("X", ()) or ())
    is_flat_x = len(current_x) == 1 and current_x[0].get("phase6_key") == "endcap_w_flat"
    if intent_id == CornerTypeId.OVERLAY.value or is_flat_x:
        profiles["X"] = deepcopy(defaults["X"])
    if not profiles.get("Y"):
        profiles["Y"] = deepcopy(defaults["Y"])
    return profiles

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
_Phase6UpdateScheduler = _phase6_command_router._Phase6UpdateScheduler

























def draw_hole_editor_hint(canvas, canvas_width, *, endcap=False):
    return _draw_hole_editor_hint_impl(canvas, canvas_width, endcap=endcap)






class _Phase6DerivedCacheOwner:
    """Own invalidation for GUI-derived geometry without touching immutable DXF source cache."""

    PRODUCTS = ("door_layout", "box_body_faces", "authoritative_render")
    _REASON_PRODUCTS = {
        "geometry": frozenset(PRODUCTS),
        "assembly": frozenset({"box_body_faces", "authoritative_render"}),
        "family-structure": frozenset(PRODUCTS),
        "baseline": frozenset(PRODUCTS),
        "display": frozenset(),
        "annotation": frozenset(),
        "camera": frozenset(),
    }

    def __init__(self):
        self._caches = {name: {} for name in self.PRODUCTS}
        self._invalidations = {name: 0 for name in self.PRODUCTS}

    def cache(self, product):
        return self._caches[str(product)]

    def invalidate(self, reason, changed_keys=()):
        reason = str(reason or "geometry")
        products = self._REASON_PRODUCTS.get(reason)
        if products is None:
            # Unknown state mutation fails closed at the derived layer only.
            products = frozenset(self.PRODUCTS)
        for product in products:
            cache = self._caches[product]
            if cache:
                cache.clear()
            self._invalidations[product] += 1
        return tuple(sorted(products))

    def metrics_snapshot(self):
        return dict(self._invalidations)


class Phase6ApplicationHost:
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
        # Tk variables 是 UI adapter；committed runtime 由 SettingsService 持有。
        settings = self.settings_service.snapshot()
        self.ui_text_size_var = tk.StringVar(value=ui_text_size_label(settings.get("ui_text_size", "small")))

        # 基礎設定（仍保留在主 GUI，並與 3D 設定中心雙向連動）
        self.w_var = tk.StringVar(value=self._fold_designer_number_text(settings["w"]))
        self.h_var = tk.StringVar(value=self._fold_designer_number_text(settings["h"]))
        self.d_var = tk.StringVar(value=self._fold_designer_number_text(settings["d"]))
        
        # 連動的 FW (邊框寬度)
        fw_value = float(settings["fw"])
        fw_init_val = str(int(fw_value) if fw_value.is_integer() else fw_value)
        self.fw_z_var = tk.StringVar(value=fw_init_val)
        self.fw_head_var = tk.StringVar(value=fw_init_val)
        self.fw_tail_var = tk.StringVar(value=fw_init_val)
        self.endcap_fw_state = normalize_endcap_fw_state({"fw": fw_value})
        self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({
            "model": self.baseline_var.get() if hasattr(self, "baseline_var") else "",
        })
        self.fw_head_follow_var = tk.BooleanVar(value=True)
        self.fw_tail_follow_var = tk.BooleanVar(value=True)
        self.cb_fw_head = None
        self.cb_fw_tail = None
        
        # 進階設定
        self.t_var = tk.StringVar(value=self._fold_designer_number_text(settings["t"]))
        
        # 箱身 z 參數
        self.zl1_var = tk.StringVar(value=self._fold_designer_number_text(settings["zl1"]))
        self.zl2_var = tk.StringVar(value=self._fold_designer_number_text(settings["zl2"]))
        self.zr1_var = tk.StringVar(value=self._fold_designer_number_text(settings["zr1"]))
        self.zr2_var = tk.StringVar(value=self._fold_designer_number_text(settings["zr2"]))
        self.z_comp_var = tk.StringVar(value=self._fold_designer_number_text(settings["z_comp"]))
        
        # 封頭尾 y 參數
        self.yl1_var = tk.StringVar(value=self._fold_designer_number_text(settings["yl1"]))
        self.yr1_var = tk.StringVar(value=self._fold_designer_number_text(settings["yr1"]))
        self.ytop1_var = tk.StringVar(value=self._fold_designer_number_text(settings["ytop1"]))
        self.ybottom1_var = tk.StringVar(value=self._fold_designer_number_text(settings["ybottom1"]))
        
        # 門參數
        self.door_gap_w_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_gap_w"]))
        self.door_gap_h_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_gap_h"]))
        self.door_fold_l_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_l"]))
        self.door_fold_r_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_r"]))
        self.door_fold_t_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_t"]))
        self.door_fold_b_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_b"]))

        # 多門配置：W/H 仍是整盤尺寸；這裡只描述各欄起始寬與由上到下的起始高度。
        self.multi_door_enabled_var = tk.BooleanVar(value=False)
        self.door_layout_selected_var = tk.StringVar(value="0:0")
        self.door_layout_columns = []
        # UI adapter only. Authoritative inner-door enable state remains
        # self.receiving_inner_doors; these vars are rebuilt from that state.
        self.door_layout_inner_door_vars = {}
        self.door_layout_inner_door_offset_vars = {}
        self.door_layout_inner_door_offset_entries = {}
        # Family-authoritative inner-door presence/config. Geometry spans are
        # deliberately not invented here; T04 frame parts consume explicit
        # spans once a family/caller owns them.
        self.receiving_inner_doors = []
        self.door_layout_scope = "main"
        self.door_layout_handle_edges = {}
        self.door_nameplate_center_datum_top = None
        # 多門每一格各自保存孔位與門指示燈設定；單門仍沿用 surface_features["door"]。
        self.door_layout_features = {}
        self.door_layout_indicator_states = {}
        # Indicator-Box assembly holes belong to the Door cell that owns the box.
        self.door_layout_indicator_box_features = {}
        self.door_layout_indicator_door_features = {}
        self._derived_cache_owner = getattr(self, "_derived_cache_owner", None) or _Phase6DerivedCacheOwner()
        self._door_layout_baseline_cache = self._derived_cache_owner.cache("door_layout")
        self.door_layout_width_entries = {}
        self.door_layout_height_entries = {}
        self.door_layout_entry_windows = []
        self.door_layout_cell_bounds = {}
        self._door_layout_last_click = None  # ((column_index, row_index), event_time_ms)

        # 箱身三面編輯：使用者座標直接使用 WHD，不暴露展開/板厚補償座標。
        self.box_body_face_selected_var = tk.StringVar(value="back")
        # Multi-piece BoxBody stays one top-level 2D tab; this nested selection
        # chooses the physical child whose authoritative unfold is displayed.
        self.box_body_piece_2d_selected_var = tk.StringVar(value="")
        self._box_body_piece_2d_tab_keys = ()
        self._box_body_piece_2d_tab_map = {}
        self._box_body_piece_2d_tab_guard = False
        self.box_body_face_features = {"left": [], "back": [], "right": []}
        self.box_body_face_bounds = {}
        self._box_body_face_last_click = None  # (face_key, event_time_ms)
        self.last_box_body_face_overview = {}
        self._box_body_baseline_face_cache = self._derived_cache_owner.cache("box_body_faces")
        
        # 底板參數
        self.base_plate_entries = []
        base_shrinks = [float(settings[k]) for k in (
            "base_plate_shrink_top", "base_plate_shrink_bottom",
            "base_plate_shrink_left", "base_plate_shrink_right",
        )]
        base_same = max(base_shrinks) - min(base_shrinks) < 1e-9
        self.base_plate_all_same_var = tk.BooleanVar(value=base_same)
        self.base_plate_shrink_same_var = tk.StringVar(value=self._fold_designer_number_text(base_shrinks[0]))
        self.base_plate_shrink_top_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_top"]))
        self.base_plate_shrink_bottom_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_bottom"]))
        self.base_plate_shrink_left_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_left"]))
        self.base_plate_shrink_right_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_right"]))
        self.base_plate_bend_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_bend"]))
        
        # 計算結果顯示用變數
        self.result_z_var = tk.StringVar(value="-")
        self.result_z_h_var = tk.StringVar(value="-")
        self.result_y_w_var = tk.StringVar(value="-")
        self.result_y_d_var = tk.StringVar(value="-")
        self.result_door_w_var = tk.StringVar(value="-")
        self.result_door_h_var = tk.StringVar(value="-")
        self.result_base_plate_w_var = tk.StringVar(value="-")
        self.result_base_plate_h_var = tk.StringVar(value="-")
        
        # 輸出選項：STOCK 開關
        self.draw_stock_var = tk.BooleanVar(value=bool(settings["draw_stock"]))
        # 輸出零件選擇
        self.export_z_var    = tk.BooleanVar(value=True)
        self.export_head_var = tk.BooleanVar(value=True)
        self.export_tail_var = tk.BooleanVar(value=True)
        self.export_door_var = tk.BooleanVar(value=True)
        self.export_base_plate_var = tk.BooleanVar(value=True)
        self.export_ib_var   = tk.BooleanVar(value=False)
        self.export_ib_door_var = tk.BooleanVar(value=False)
        self.baseline_var    = tk.StringVar(master=self.root, value="")
        self._active_cabinet_type = "金庫型"
        # Known-model switches always re-apply the target preset.  This map
        # stores immutable startup presets only; it must never become a
        # per-family "remember my last edits" session cache.
        self._cabinet_family_defaults = {}

        # 箱身組合方式是封頭/封尾上方截角的唯一類型來源。
        self.box_assembly_type_var = tk.StringVar(value=ASSEMBLY_TYPE_LABELS[CornerTypeId.INSERT_OVERLAY])
        self.cb_box_assembly = None
        self.assembly_joint_state = migrate_legacy_snapshot_joints({
            "assembly_type": "INSERT_OVERLAY",
            "existing_parts": ["box_body", "head", "tail"],
        })

        # 自訂：截角型式只在此模式可手動選；金庫型永遠使用固定 Factory mapping。
        manual_corner_parts = ["head", "tail", "door", "base_plate", "indicator_box", "indicator_door"]
        self.manual_corner_state = new_manual_corner_state(manual_corner_parts)
        # Normal shop-floor case: top pair is the same, bottom pair is the same.
        # Four physical-corner values are still retained underneath for exceptions.
        self.manual_corner_pair_same = new_manual_corner_pair_same_state(manual_corner_parts)
        self.manual_active_corner_var = tk.StringVar(value="top")
        self.manual_top_same_var = tk.BooleanVar(master=self.root, value=True)
        self.manual_bottom_same_var = tk.BooleanVar(master=self.root, value=True)
        self.manual_corner_type_var = tk.StringVar(value=CornerTypeId.CROSS.value)
        self.manual_corner_cross_mode_var = tk.StringVar(value="標準")
        self.manual_corner_direction_var = tk.StringVar(value="寬")
        self.manual_corner_amount_var = tk.StringVar(value="1")
        self.manual_corner_secondary_retain_var = tk.StringVar(value="0.5")
        self.manual_corner_secondary_depth_var = tk.StringVar(value="2")
        self._manual_corner_param_guard = False
        # UI-only safety state: fine corner parameters are collapsed/locked by default.
        # This state is intentionally NOT serialized into .p6fold.
        self._manual_corner_param_unlocked = {}
        self.corner_type_panel = None
        self.corner_type_preview_canvas = None
        self.corner_type_small_canvases = {}
        saved_corner_state, saved_corner_pairs = load_corner_defaults_from_ini(ae)
        self._apply_manual_corner_snapshot(saved_corner_state, saved_corner_pairs)
        # The box-level assembly semantic is authoritative.  Old/default INI
        # snapshots may contain only CROSS end-cap corners; normalize them once
        # here so the state shown in 2D and consumed by manufacturing is the
        # same state.  Valid legacy INSERT/OVERLAY/INSERT_OVERLAY values are
        # preserved by assembly_type_from_corner_state().
        initial_assembly = assembly_type_from_corner_state(self.manual_corner_state)
        apply_box_assembly_type(
            self.manual_corner_state, self.manual_corner_pair_same, initial_assembly,
            reset_bottom_defaults=True,
        )
        self.box_assembly_type_var.set(ASSEMBLY_TYPE_LABELS[initial_assembly])

        # 指示燈盒子相關變數
        self.is_indicator_box_var = tk.BooleanVar(value=False)
        self.is_indicator_door_var = tk.BooleanVar(value=False)
        self.indicator_g_var = tk.StringVar(value="2")
        self.indicator_l_var = tk.StringVar(value="1")
        self.indicator_layer_g_vars = [tk.StringVar(value="2") for _ in range(6)]
        self.ib_hole_start_x_var = tk.StringVar(value="172.5")
        self.ib_hole_pitch_var = tk.StringVar(value="150")
        self.ib_hole_count_var = tk.StringVar(value="2")
        self.ib_hole_y_var = tk.StringVar(value="178.5")
        
        # 外門指示燈相關變數
        self.is_door_indicator_var = tk.BooleanVar(value=False)
        self.door_indicator_l_var = tk.StringVar(value="1")
        self.door_indicator_layer_g_vars = [tk.StringVar(value="2") for _ in range(6)]
        self.door_indicator_offset_x = 0.0
        self.door_indicator_offset_y = 0.0
        self.drag_active = False
        self.is_box_dist_var = tk.BooleanVar(value=False)
        
        # 左側指示燈盒子結果變數
        self.result_ib_w_var = tk.StringVar(value="-")
        self.result_ib_h_var = tk.StringVar(value="-")
        self.result_ib_door_w_var = tk.StringVar(value="-")
        self.result_ib_door_h_var = tk.StringVar(value="-")
        
        # 封頭/封尾開孔清單
        self.head_holes = []
        self.tail_holes = []
        # Generic unfolded-surface features for every other panel/frame.
        self.surface_features = {
            "box_body": [],
            "door": [],
            "base_plate": [],
            "indicator_box": [],
            "indicator_door": [],
            "head": [],
            "tail": [],
        }

        # 使用者提供的原始折彎/3D 設計器：只做資料橋接，不取代 Phase6 renderer/geometry。
        self.fold_designer_window = None
        self.fold_designer_app = None
        # Workspace presence / active part / profile stash are owned by
        # Phase6WorkspaceController.  Legacy attribute names below are
        # compatibility properties only; no second backing state is created.
        # Hidden auxiliary parts (indicator box / small door) have no top-level
        # preview Notebook tab.  When one is returned from the 3D designer,
        # keep it as the manual CornerType context until the user selects a
        # visible preview tab.
        self._manual_corner_part_override = None
        
    def _setting_var_map(self):
        """Tk variables backed by the single Phase6 runtime settings state."""
        return {
            "w": self.w_var, "h": self.h_var, "d": self.d_var,
            "t": self.t_var, "fw": self.fw_z_var, "draw_stock": self.draw_stock_var,
            "zl1": self.zl1_var, "zl2": self.zl2_var, "zr1": self.zr1_var, "zr2": self.zr2_var,
            "z_comp": self.z_comp_var,
            "yl1": self.yl1_var, "yr1": self.yr1_var,
            "ytop1": self.ytop1_var, "ybottom1": self.ybottom1_var,
            "door_gap_w": self.door_gap_w_var, "door_gap_h": self.door_gap_h_var,
            "door_fold_l": self.door_fold_l_var, "door_fold_r": self.door_fold_r_var,
            "door_fold_t": self.door_fold_t_var, "door_fold_b": self.door_fold_b_var,
            "base_plate_shrink_top": self.base_plate_shrink_top_var,
            "base_plate_shrink_bottom": self.base_plate_shrink_bottom_var,
            "base_plate_shrink_left": self.base_plate_shrink_left_var,
            "base_plate_shrink_right": self.base_plate_shrink_right_var,
            "base_plate_bend": self.base_plate_bend_var,
        }

    def _collect_main_setting_values(self):
        values = self.settings_service.snapshot().as_dict()
        for key, var in self._setting_var_map().items():
            try:
                if isinstance(var, tk.BooleanVar):
                    values[key] = bool(var.get())
                else:
                    values[key] = float(var.get())
            except (TypeError, ValueError, tk.TclError):
                pass
        return self.settings_service.update(values).as_dict()

    @staticmethod
    def _serialize_corner_selection(raw_selection):
        selection = normalize_corner_selection(raw_selection)
        raw = {
            "type_id": selection.type_id.value,
            "rotation_quadrants": 0,
        }
        if selection.cross_mode is not None:
            raw["cross_mode"] = selection.cross_mode.value
        if selection.direction is not None:
            raw["direction"] = selection.direction.value
        if selection.amount_t is not None:
            raw["amount_t"] = float(selection.amount_t)
        if selection.secondary_retain_t is not None:
            raw["secondary_retain_t"] = float(selection.secondary_retain_t)
        if selection.secondary_depth_t is not None:
            raw["secondary_depth_t"] = float(selection.secondary_depth_t)
        return raw

    def _serialize_manual_corner_state(self):
        result = {}
        for part_key, corners in self.manual_corner_state.items():
            result[part_key] = {
                corner_key: self._serialize_corner_selection(raw_selection)
                for corner_key, raw_selection in corners.items()
            }
        return result


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
        state = {"settings": self.settings_service.snapshot().as_dict()}
        fingerprint = stable_fingerprint(state)
        if fingerprint == getattr(self, "_phase6_main_sync_fingerprint", None):
            return None
        revision = int(getattr(self, "_phase6_main_sync_revision", 0) or 0) + 1
        self._phase6_main_sync_revision = revision
        self._phase6_main_sync_fingerprint = fingerprint
        return {
            "origin": "main_gui",
            "revision": revision,
            "transaction_id": f"main_gui:{revision}",
            "delta": deepcopy(dict(delta or {})),
            "fingerprint": fingerprint,
        }

    def _on_main_setting_var_changed(self, key, var):
        if getattr(self, "_settings_sync_guard", False):
            return
        try:
            value = bool(var.get()) if isinstance(var, tk.BooleanVar) else float(var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        scheduler = self._phase6_update_scheduler
        scheduler.begin()
        try:
            self.settings_service.update({key: value})
            if key == "fw":
                self._settings_sync_guard = True
                try:
                    for part in ("head", "tail"):
                        state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": value})
                        if bool(state.get("follow_box", True)):
                            state["value"] = float(value)
                    self._sync_endcap_fw_controls()
                finally:
                    self._settings_sync_guard = False
            scheduler.mark_dirty(f"setting:{key}")
            designer = getattr(self, "fold_designer_app", None)
            if not getattr(self, "_fold_designer_live_sync_guard", False) and designer is not None:
                try:
                    if hasattr(designer, "apply_external_sync"):
                        envelope = self._phase6_external_sync_envelope({"settings": {key: value}})
                        if envelope is not None:
                            designer.apply_external_sync(envelope)
                    elif hasattr(designer, "apply_external_settings"):
                        designer.apply_external_settings({key: value})
                except tk.TclError:
                    pass
        finally:
            scheduler.end()

    @staticmethod
    def _fold_designer_secondary_scene_rows(scene):
        """Return numeric baseline hole rows, excluding the structural outline/BEND."""
        rows = []
        skipped_outline = False
        for primitive in getattr(scene, "primitives", ()): 
            layer = str(getattr(primitive, "layer", "") or "")
            if layer not in {"CUTTING", "BLIND_HOLE"}:
                continue
            if isinstance(primitive, PolylinePrimitive):
                if layer == "CUTTING" and not skipped_outline:
                    skipped_outline = True
                    continue
                points = tuple(getattr(primitive, "points", ()) or ())
                if not getattr(primitive, "closed", False) or len(points) < 3:
                    continue
                xs = [float(p.x) for p in points]; ys = [float(p.y) for p in points]
                rows.append({
                    "kind": "方孔", "layer": layer,
                    "x": (min(xs) + max(xs)) / 2.0,
                    "y": (min(ys) + max(ys)) / 2.0,
                    "d1": max(xs) - min(xs), "d2": max(ys) - min(ys),
                })
            elif isinstance(primitive, CirclePrimitive):
                center = primitive.center
                rows.append({
                    "kind": "圓孔", "layer": layer,
                    "x": float(center.x), "y": float(center.y),
                    "d1": float(primitive.radius) * 2.0, "d2": 0.0,
                })
        return rows

    def _query_fold_designer_baseline_data(self, part_key, model, values):
        """Read-only lazy baseline numeric data for the 3D settings panel."""
        model = str(model or "").strip()
        if not model or is_unknown_model(model):
            return []
        v = dict(values or {})
        try:
            w = float(v.get("w", self.w_var.get())); h = float(v.get("h", self.h_var.get()))
            d = float(v.get("d", self.d_var.get())); t = float(v.get("t", self.t_var.get()))
            fw = float(v.get("fw", self.fw_z_var.get()))
            if part_key == "door":
                if hasattr(ae, "has_baseline_part") and not ae.has_baseline_part(model, "門.dxf"):
                    return []
                door_fw = self._door_material_frame_width(fw, t, model_name=model)
                data = ae.get_stretched_door_data(
                    model, w, h, t, door_fw,
                    float(v.get("door_gap_w", ae.door_gap_w_def)),
                    float(v.get("door_gap_h", ae.door_gap_h_def)),
                    float(v.get("door_fold_l", ae.door_fold_left_def)),
                    float(v.get("door_fold_r", ae.door_fold_right_def)),
                    float(v.get("door_fold_t", ae.door_fold_top_def)),
                    float(v.get("door_fold_b", ae.door_fold_bottom_def)),
                    frame_edges=DoorFrameEdges(),
                )
                return self._fold_designer_secondary_scene_rows(data.scene)
            if part_key in {"head", "tail"}:
                data = ae.get_stretched_end_cap_data(
                    model, w, h, d, t, FW_val=fw, is_tail=(part_key == "tail")
                )
                return self._fold_designer_secondary_scene_rows(data.scene)
        except Exception:
            return []
        return []

    def _apply_cabinet_family_endcap_policy(
        self, policy, part_key, *, snapshot=None, thickness=None, structure_state=None
    ):
        """Apply cabinet-family geometry inputs without changing operator Corner selections.

        The Corner selections remain the operator/registry Source of Truth. Cabinet families
        may supply only family geometry such as the receiving-cabinet effective bottom FW.
        Both the main GUI and Fold Designer payload adapter call this helper so 2D/3D cannot
        drift by rebuilding the same family rule differently.
        """
        if policy is None or str(part_key) not in {"head", "tail"}:
            return policy

        family_source = (
            Phase6ApplicationHost._current_cabinet_type_name(self)
            if snapshot is None else snapshot
        )
        if not cabinet_family_policy.supports_bottom_wrap_controls(family_source):
            return policy

        if structure_state is None:
            try:
                structure_state = self.workspace_controller.box_body_structure_state()
            except Exception:
                structure_state = None
        if thickness is None:
            try:
                thickness = float(self.t_var.get())
            except Exception:
                thickness = float(ae.T)
        return replace(
            policy,
            bottom_fw=cabinet_family_policy.effective_endcap_bottom_fw(
                family_source,
                structure_state,
                thickness=float(thickness),
                default_fw=float(policy.bottom_fw if policy.bottom_fw is not None else policy.fw),
            ),
        )

    @staticmethod
    def _fold_designer_corner_policy_from_payload(corner_state, part_key, fw):
        corners = dict((corner_state or {}).get(part_key, {}) or {})
        required = ("top_left", "top_right", "bottom_left", "bottom_right")
        if not all(key in corners for key in required):
            return None
        selections = {}
        for key in required:
            raw = corners[key]
            if isinstance(raw, CornerTypeSelection):
                selections[key] = normalize_corner_selection(raw)
                continue
            raw = dict(raw or {})
            selections[key] = CornerTypeSelection(
                CornerTypeId(str(raw.get("type_id", "CROSS")).upper()),
                rotation_quadrants=int(raw.get("rotation_quadrants", 0) or 0),
                cross_mode=raw.get("cross_mode"),
                direction=raw.get("direction"),
                amount_t=raw.get("amount_t"),
                secondary_retain_t=raw.get("secondary_retain_t"),
                secondary_depth_t=raw.get("secondary_depth_t"),
            )
        return policy_from_corner_state(selections, fw=float(fw))

    def _authoritative_render_data(self, spec, context=None):
        """Return one immutable manufacturing render object for an exact PartSpec.

        2D and 3D callers share this cache.  Geometry is built only by
        manufacturing_api; GUI/renderer code may consume scene/material but may
        not reconstruct CUTTING, baseline or CornerType geometry.
        """
        ctx = context or ManufacturingContext(draw_stock=False)
        cache = getattr(self, "_authoritative_part_render_cache", None)
        if cache is None:
            owner = getattr(self, "_derived_cache_owner", None)
            if owner is None:
                owner = self._derived_cache_owner = _Phase6DerivedCacheOwner()
            cache = self._authoritative_part_render_cache = owner.cache("authoritative_render")
        cache_key = (repr(spec), repr(ctx))
        if cache_key in cache:
            return cache[cache_key]
        if isinstance(spec, BoxBodyPartSpec):
            from phase6_box_body_structure import BoxBodyStructureType, normalize_box_body_structure_state
            structure = normalize_box_body_structure_state(spec.structure_state)
            if structure.get("active_type") != BoxBodyStructureType.INTEGRAL.value:
                render_data = manufacturing_api.build_box_body_structure_render_data(spec, ctx)
            else:
                render_data = manufacturing_api.build_part_render_data(spec, ctx)
        else:
            render_data = manufacturing_api.build_part_render_data(spec, ctx)
        cache[cache_key] = render_data
        if len(cache) > 32:
            cache.pop(next(iter(cache)))
        return render_data

    def _require_verified_baseline_sources_for_manufacturing(self):
        """Fail closed when a baseline-backed manufacturing source is not freshly verified."""
        model = self._baseline_source_model() if hasattr(self, "_baseline_source_model") else ""
        if not model:
            return True
        for filename in ("箱身.dxf", "封頭尾.dxf", "門.dxf"):
            path = ae.baseline_part_path(model, filename)
            if not path:
                continue
            _doc, status = ae.load_baseline_dxf_source_with_status(
                path, allow_unverified_source=False
            )
            if status != ae.BASELINE_SOURCE_VERIFIED:
                raise RuntimeError(
                    f"基準來源尚未驗證：{model}/{filename}；正式製造輸出已停止。"
                )
        return True

    def _export_authoritative_part(self, spec, output_path, context=None):
        """Save the exact cached FinalScene used by 2D/3D without rebuilding it."""
        self._flush_phase6_authoritative_state()
        self._require_verified_baseline_sources_for_manufacturing()
        ctx = context or self._manufacturing_context(draw_stock=False)
        render_data = self._authoritative_render_data(spec, ctx)
        if getattr(render_data, "pieces", None):
            output = Path(output_path)
            return manufacturing_api.generate_box_body_structure_parts(spec, output.parent, ctx)
        return manufacturing_api.save_part_render_data_dxf(
            render_data, output_path, overwrite=bool(getattr(ctx, "overwrite", False))
        )


    def _fold_designer_part_spec_from_payload(self, part_key, payload):
        """Convert Fold Designer draft state to the canonical manufacturing request.

        This is the only draft-state adapter.  It returns ``(PartSpec, context)``;
        the bridge never builds manufacturing geometry itself.
        """
        data = dict(payload or {})
        key = str(part_key or "")
        w = float(data.get("w", ae.W)); h = float(data.get("h", ae.H))
        d = float(data.get("d", ae.D)); t = float(data.get("t", ae.T))
        fw = float(data.get("fw", ae.FW))
        model = normalize_custom_model_name(data.get("model"))
        unknown = is_unknown_model(model)
        corner_state = data.get("corner_state") or {}
        features = tuple(data.get("features") or ())
        face_features = data.get("face_features") or {}
        door_cell = None
        base_plate_cell = None
        if key.startswith("door_c"):
            columns = tuple(
                (float(row[0]), tuple(float(value) for value in row[1]))
                for row in tuple(data.get("door_layout_columns") or ())
            )
            if not columns:
                raise ValueError(f"門格缺少 authoritative multi-door topology: {key}")
            door_cell = next(
                (cell for cell in derive_door_layout_cells(columns)
                 if door_layout_export_filename(cell).removesuffix(".dxf") == key),
                None,
            )
            if door_cell is None:
                raise ValueError(f"門格 stable_id 不存在於 authoritative topology: {key}")
            w = float(door_cell.start_width)
            h = float(door_cell.start_height)
        elif key.startswith("base_plate_c"):
            columns = tuple(
                (float(row[0]), tuple(float(value) for value in row[1]))
                for row in tuple(data.get("door_layout_columns") or ())
            )
            if not columns:
                raise ValueError(f"底板缺少 authoritative multi-door topology: {key}")
            owner_door_key = key.replace("base_plate_", "door_", 1)
            base_plate_cell = next(
                (cell for cell in derive_door_layout_cells(columns)
                 if door_layout_export_filename(cell).removesuffix(".dxf") == owner_door_key),
                None,
            )
            if base_plate_cell is None:
                raise ValueError(f"底板 stable_id 不存在於 authoritative topology: {key}")
            w = float(base_plate_cell.start_width)
            h = float(base_plate_cell.start_height)

        def payload_policy(part):
            resolved = self._fold_designer_corner_policy_from_payload(corner_state, part, fw)
            if resolved is None and not unknown:
                fallback = known_model_corner_state(
                    (part,), cabinet_family=Phase6ApplicationHost._current_cabinet_type_name(self)
                ).get(part)
                resolved = policy_from_corner_state(fallback, fw=fw) if fallback is not None else None
            return self._apply_cabinet_family_endcap_policy(
                resolved, part, snapshot=data, thickness=t,
                structure_state=data.get("box_body_structure"),
            )

        policy_part = "door" if door_cell is not None else ("base_plate" if base_plate_cell is not None else key)
        policy = payload_policy(policy_part)

        context = ManufacturingContext(draw_stock=False)
        if key == "box_body":
            spec = self._box_body_part_spec_from_values(
                {
                    "w": w, "h": h, "d": d, "t": t, "fw": fw,
                    "zl1": float(data.get("zl1", ae.zl1_def)),
                    "zl2": float(data.get("zl2", ae.zl2_def)),
                    "zr1": float(data.get("zr1", ae.zr1_def)),
                    "zr2": float(data.get("zr2", ae.zr2_def)),
                    "z_comp": float(data.get("z_comp", getattr(ae, "z_comp_def", 0.0))),
                },
                model_name=(None if unknown else model),
                features=features, face_features=face_features,
                head_corner_policy=payload_policy("head"),
                tail_corner_policy=payload_policy("tail"),
                fold_profile=data.get("fold_profile"),
                structure_state=data.get("box_body_structure"),
                head_ybottom1=float(data.get("head_ybottom1", data.get("ybottom1", ae.ybottom1_def))),
                tail_ybottom1=float(data.get("tail_ybottom1", data.get("ybottom1", ae.ybottom1_def))),
            )
        elif key in {"head", "tail"}:
            endcap_values = {
                "w": w, "h": h, "d": d, "t": t, "fw": fw,
                "yl1": float(data.get("yl1", ae.yl1_def)),
                "yr1": float(data.get("yr1", ae.yr1_def)),
                "ytop1": float(data.get("ytop1", ae.ytop1_def)),
                "ybottom1": float(data.get("ybottom1", ae.ybottom1_def)),
                "zl1": float(data.get("zl1", ae.zl1_def)),
                "zr1": float(data.get("zr1", ae.zr1_def)),
            }
            resolved_cuts = data.get("resolved_assembly_relief_cuts", None)
            if resolved_cuts is None and bool(data.get("_use_committed_relief")):
                resolved_cuts = self._resolved_committed_assembly_relief_cuts(
                    key, endcap_values, data.get("fold_profiles") or {}
                )
            formed_fw_left, formed_fw_right = formed_box_body_fw_widths(
                data.get("box_body_profile") or self.workspace_controller.box_body_profile() or (), t
            )
            spec = self._end_cap_part_spec_from_values(
                endcap_values,
                model_name=(None if unknown else model), is_tail=(key == "tail"),
                holes=features, corner_policy=policy, fold_profiles=data.get("fold_profiles"),
                resolved_assembly_relief_cuts=resolved_cuts or (),
                box_body_formed_fw_left=formed_fw_left, box_body_formed_fw_right=formed_fw_right,
                box_body_structure_state=(data.get("box_body_structure") or self.workspace_controller.box_body_structure_state()),
                endcap_bottom_wrap_state=data.get("endcap_bottom_wrap"),
                assembly_joints=data.get("assembly_joints"),
            )
        elif key == "door" or door_cell is not None:
            groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or ()))
            direct = tuple(int(v) for v in (data.get("door_indicator_groups") or ()))
            indicator_hole = None
            if bool(data.get("door_indicator_box_enabled")) and groups:
                indicator_hole = manufacturing_api.indicator_box_opening_size(groups, thickness=t)
            spec = self._door_part_spec_from_values(
                {
                    "w": w, "h": h, "t": t, "fw": fw,
                    "door_gap_w": float(data.get("door_gap_w", ae.door_gap_w_def)),
                    "door_gap_h": float(data.get("door_gap_h", ae.door_gap_h_def)),
                    "door_fold_l": float(data.get("door_fold_l", ae.door_fold_left_def)),
                    "door_fold_r": float(data.get("door_fold_r", ae.door_fold_right_def)),
                    "door_fold_t": float(data.get("door_fold_t", ae.door_fold_top_def)),
                    "door_fold_b": float(data.get("door_fold_b", ae.door_fold_bottom_def)),
                },
                model_name=(None if unknown else model),
                features=features,
                indicator_hole=indicator_hole,
                door_indicator=(direct or None),
                door_indicator_offset=tuple(data.get("door_indicator_offset") or (0.0, 0.0)),
                use_box_distance=bool(data.get("use_box_distance", False)),
                corner_policy=policy,
                frame_edges=(door_cell.edges if door_cell is not None else None),
            )
        elif key == "base_plate" or key.startswith("base_plate_c"):
            spec = self._base_plate_part_spec_from_values(
                {
                    "w": w, "h": h, "t": t, "fw": fw,
                    "base_plate_shrink_top": float(data.get("base_plate_shrink_top", 0)),
                    "base_plate_shrink_bottom": float(data.get("base_plate_shrink_bottom", 0)),
                    "base_plate_shrink_left": float(data.get("base_plate_shrink_left", 0)),
                    "base_plate_shrink_right": float(data.get("base_plate_shrink_right", 0)),
                    "base_plate_bend": float(data.get("base_plate_bend", 20)),
                    "model": model,
                },
                features=features, corner_policy=policy,
            )
        elif key == "indicator_box":
            groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
            spec = self._indicator_box_part_spec_from_values(
                {"t": t}, groups, features=features
            )
        elif key == "indicator_door":
            groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
            spec, context = self._indicator_door_part_spec_from_values(
                {
                    "t": t, "fw": fw,
                    "door_gap_w": float(data.get("door_gap_w", ae.door_gap_w_def)),
                    "door_gap_h": float(data.get("door_gap_h", ae.door_gap_h_def)),
                    "indicator_door_fold": float(data.get("indicator_door_fold", getattr(ae, "indicator_small_door_fold_def", 19.0))),
                },
                groups, features=features,
            )
        else:
            raise ValueError(f"未知 3D 板件: {key}")
        return spec, context

    def _query_fold_designer_render_data(self, part_key, payload):
        if str(part_key or "").startswith("indicator"):
            payload = collect_indicator_box_input(payload)
        if str(part_key or "").startswith("box_body:part:"):
            payload = collect_multipart_input(payload)
        if str(part_key or "").startswith("door:"):
            payload = collect_door_input(payload)
        """Return the same authoritative final geometry used by 2D consumers."""
        key = str(part_key or "")
        if key.startswith("box_body:divider:"):
            from ae_engine.door_dividers import derive_box_body_dividers

            divider_input = collect_divider_input(
                key,
                payload,
                default_depth=ae.D,
                default_thickness=ae.T,
            )
            dividers = derive_box_body_dividers(
                divider_input["columns"],
                depth=divider_input["depth"],
                thickness=divider_input["thickness"],
                layout_scope=divider_input["layout_scope"],
                handle_edges=divider_input["handle_edges"],
                model_name=divider_input["model_name"],
            )
            divider = next((item for item in dividers if item.stable_id == key), None)
            if divider is None:
                raise ValueError(f"中隔 stable_id 不存在於 authoritative topology: {key}")
            return manufacturing_api.build_box_body_divider_render_data(divider)

        if key.startswith("inner_door:") and key.endswith(":panel"):
            data = dict(payload or {})
            panels = cabinet_family_policy.derive_inner_door_panels(data)
            panel = next((item for item in panels if item.stable_id == key), None)
            if panel is None:
                raise ValueError(f"內門板 stable_id 不存在於 authoritative topology: {key}")
            return manufacturing_api.build_inner_door_panel_render_data(panel)

        if key.startswith("inner_door:") and key.endswith("_frame"):
            from ae_engine.inner_door_frames import (
                InnerDoorFrameSet,
                derive_all_inner_door_frames,
            )
            data = dict(payload or {})
            if cabinet_family_policy.has_inner_door_frame_derivation(data):
                frame_sets = list(cabinet_family_policy.derive_inner_door_frame_sets(data))
            else:
                frame_sets = []
                thickness = float(data.get("t", ae.T))
                for item in tuple(data.get("inner_doors") or ()):
                    if not isinstance(item, dict):
                        continue
                    stable_id = str(item.get("stable_id") or "").strip()
                    spans = item.get("frame_spans")
                    if not stable_id or not isinstance(spans, dict) or not spans:
                        continue
                    included = tuple(
                        str(side).strip().lower()
                        for side in tuple(item.get("included_frame_sides") or ("top", "bottom", "left", "right"))
                    )
                    frame_sets.append(InnerDoorFrameSet(
                        inner_door_id=stable_id,
                        spans=dict(spans),
                        thickness=thickness,
                        included_sides=included,
                    ))
            frames = derive_all_inner_door_frames(tuple(frame_sets))
            frame = next((item for item in frames if item.stable_id == key), None)
            if frame is None:
                raise ValueError(f"內門框 stable_id 不存在於 authoritative topology: {key}")
            return manufacturing_api.build_inner_door_frame_render_data(frame)

        spec, context = self._fold_designer_part_spec_from_payload(part_key, payload)
        if isinstance(spec, BoxBodyPartSpec):
            from phase6_box_body_structure import BoxBodyStructureType, normalize_box_body_structure_state
            state = normalize_box_body_structure_state(spec.structure_state)
            if state.get("active_type") != BoxBodyStructureType.INTEGRAL.value:
                return manufacturing_api.build_box_body_structure_render_data(spec, context)
        return self._authoritative_render_data(spec, context)

    def _make_original_fold_designer_snapshot(self):
        def number(var, fallback=0.0):
            try:
                return float(var.get())
            except (TypeError, ValueError, tk.TclError):
                return float(fallback)

        workspace_active = str(self.workspace_controller.active_part or "").strip()
        box_body_active_piece = (
            workspace_active
            if workspace_active.startswith("box_body:")
            and not workspace_active.startswith("box_body:divider:")
            else None
        )

        snapshot = {
            "model": self.baseline_var.get().strip(),
            "_runtime_project_path": self.project_controller.project_path,
            "w": number(self.w_var, ae.W),
            "h": number(self.h_var, ae.H),
            "d": number(self.d_var, ae.D),
            "t": number(self.t_var, ae.T),
            "fw": number(self.fw_z_var, ae.FW),
            "zl1": number(self.zl1_var, ae.zl1_def),
            "zl2": number(self.zl2_var, ae.zl2_def),
            "zr2": number(self.zr2_var, ae.zr2_def),
            "zr1": number(self.zr1_var, ae.zr1_def),
            "yl1": number(self.yl1_var, ae.yl1_def),
            "yr1": number(self.yr1_var, ae.yr1_def),
            "ytop1": number(self.ytop1_var, ae.ytop1_def),
            "ybottom1": number(self.ybottom1_var, ae.ybottom1_def),
            "door_gap_w": number(self.door_gap_w_var, ae.door_gap_w_def),
            "door_gap_h": number(self.door_gap_h_var, ae.door_gap_h_def),
            "door_fold_l": number(self.door_fold_l_var, ae.door_fold_left_def),
            "door_fold_r": number(self.door_fold_r_var, ae.door_fold_right_def),
            "door_fold_t": number(self.door_fold_t_var, ae.door_fold_top_def),
            "door_fold_b": number(self.door_fold_b_var, ae.door_fold_bottom_def),
            "base_plate_shrink_top": number(self.base_plate_shrink_top_var, 0),
            "base_plate_shrink_bottom": number(self.base_plate_shrink_bottom_var, 0),
            "base_plate_shrink_left": number(self.base_plate_shrink_left_var, 0),
            "base_plate_shrink_right": number(self.base_plate_shrink_right_var, 0),
            "base_plate_bend": number(self.base_plate_bend_var, 20),
            "indicator_box_fold": float(getattr(ae, "indicator_box_fold_def", 49.0)),
            "indicator_door_fold": float(getattr(ae, "indicator_small_door_fold_def", 19.0)),
            "use_box_distance": bool(self.is_box_dist_var.get()),
            "assembly_type": assembly_intent_value(self._current_box_assembly_type()),
            "endcap_fw": deepcopy(self.endcap_fw_state),
            "endcap_bottom_wrap": deepcopy(getattr(
                self, "endcap_bottom_wrap_state", normalize_endcap_bottom_wrap_state({"model": self.baseline_var.get()})
            )),
            "assembly_relief": deepcopy(getattr(self, "assembly_relief_state", {}) or {}),
            "multi_door_enabled": bool(self.multi_door_enabled_var.get()) if hasattr(self, "multi_door_enabled_var") else False,
            "door_layout_scope": str(getattr(self, "door_layout_scope", "main") or "main"),
            "door_handle_edges": deepcopy(getattr(self, "door_layout_handle_edges", {}) or {}),
            "inner_doors": deepcopy(getattr(self, "receiving_inner_doors", []) or []),
            "door_nameplate_center_datum_top": getattr(self, "door_nameplate_center_datum_top", None),
            # Compatibility projection only: the retired 2D widget is not an
            # authority.  Seed Fold Designer child selection from workspace identity.
            "box_body_active_piece": box_body_active_piece,
        }
        if getattr(self, "door_layout_columns", None):
            snapshot["door_layout_columns"] = [
                [float(width), [float(v) for v in heights]]
                for width, heights in self.get_door_layout_columns()
            ]
        else:
            snapshot["door_layout_columns"] = []
        settings = self._collect_main_setting_values()
        snapshot.update({key: value for key, value in settings.items() if key in snapshot})
        snapshot["settings"] = dict(settings)
        # Project files always persist the actual current fine parameters.
        # Known models keep CornerType itself readonly in the UI, but an explicit
        # parameter unlock is a real project edit and must survive save/load.
        snapshot["corner_state"] = self._serialize_manual_corner_state()
        snapshot["corner_pair_same"] = deepcopy(self.manual_corner_pair_same)
        snapshot["corner_editable"] = is_unknown_model(self.baseline_var.get())
        snapshot["corner_type_labels"] = {type_id.value: CORNER_TYPE_LABELS[type_id] for type_id in EDITABLE_CORNER_TYPE_IDS}
        baseline_models = self._baseline_model_choices()
        snapshot["baseline_models"] = baseline_models
        snapshot["baseline_unknown_value"] = next(
            (model for model in baseline_models if is_unknown_model(model)), "自訂"
        )
        # Immutable reset source: ae.default_config, never config.ini/runtime.
        snapshot["factory_defaults"] = load_factory_defaults_from_ae(ae)

        box_body_profile = self.workspace_controller.box_body_profile()
        if box_body_profile:
            snapshot["box_body_profile"] = [dict(seg) for seg in box_body_profile]

        # Physical presence is one source of truth.  Output checkboxes only
        # decide which EXISTING parts to export; unchecking export must never
        # delete a part when the 3D designer is opened.
        committed_profiles = self.workspace_controller.part_profiles_snapshot()
        ordered = [
            key for key in ("box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door")
            if key in self._phase6_current_existing_parts()
        ]
        snapshot["existing_parts"] = ordered
        joint_state = dict(getattr(self, "assembly_joint_state", {}) or {})
        joint_state["existing_parts"] = list(ordered)
        joint_state["assembly_type"] = snapshot["assembly_type"]
        joint_state = migrate_legacy_snapshot_joints(joint_state)
        self.assembly_joint_state = joint_state
        snapshot["assembly_joint_schema_version"] = joint_state["assembly_joint_schema_version"]
        snapshot["assembly_joints"] = deepcopy(joint_state["assembly_joints"])

        active = self.workspace_controller.active_part
        snapshot["active_part"] = active if active in ordered else (ordered[0] if ordered else None)

        snapshot["part_features"] = {
            str(key): list(features or ())
            for key, features in dict(self.surface_features or {}).items()
        }
        if snapshot.get("multi_door_enabled") and snapshot.get("door_layout_columns"):
            formal_door_features = door_layout_feature_map_to_part_features(
                tuple((float(row[0]), tuple(float(v) for v in row[1])) for row in snapshot["door_layout_columns"]),
                getattr(self, "door_layout_features", {}) or {},
            )
            for key, features in formal_door_features.items():
                # Live Fold Designer formal features take precedence when present;
                # otherwise project the canonical main 2D layout store.
                snapshot["part_features"].setdefault(key, list(features))
        snapshot["part_face_features"] = {
            "box_body": {face: list(features) for face, features in self.box_body_face_features.items()}
        }

        w, h, d, t, fw = snapshot["w"], snapshot["h"], snapshot["d"], snapshot["t"], snapshot["fw"]
        door_material_fw = self._door_material_frame_width(
            fw, t, model_name=snapshot.get("model")
        )
        door_w, door_h = ae.calculate_door_finished_size(
            w, h, door_material_fw,
            snapshot["door_gap_w"], snapshot["door_gap_h"], t,
            frame_edges=DoorFrameEdges(),
        )
        door_w = max(1.0, float(door_w))
        door_h = max(1.0, float(door_h))
        base_w = max(1.0, w - snapshot["base_plate_shrink_left"] - snapshot["base_plate_shrink_right"])
        base_h = max(1.0, h - snapshot["base_plate_shrink_top"] - snapshot["base_plate_shrink_bottom"])
        try:
            layers = max(1, int(self.indicator_l_var.get()))
            groups = [int(self.indicator_layer_g_vars[i].get()) for i in range(layers)]
            policy = replace(
                manufacturing_api.resolve_policy(),
                frame_width=float(fw),
                door_gap_w=float(snapshot["door_gap_w"]), door_gap_h=float(snapshot["door_gap_h"]),
                indicator_box_fold=float(snapshot["indicator_box_fold"]),
                indicator_small_door_fold=float(snapshot["indicator_door_fold"]),
            )
            indicator_ctx = ManufacturingContext(policy=policy)
            ib_w, ib_h = manufacturing_api.indicator_box_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
            id_w, id_h = manufacturing_api.indicator_small_door_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
        except Exception:
            groups = [1]
            indicator_ctx = ManufacturingContext()
            ib_w, ib_h = manufacturing_api.indicator_box_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
            id_w, id_h = manufacturing_api.indicator_small_door_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
        snapshot["indicator_layer_groups"] = list(groups)
        try:
            if self.is_door_indicator_var.get():
                _n = max(1, int(self.door_indicator_l_var.get()))
                snapshot["door_indicator_groups"] = [int(self.door_indicator_layer_g_vars[i].get()) for i in range(_n)]
            else:
                snapshot["door_indicator_groups"] = []
        except Exception:
            snapshot["door_indicator_groups"] = []
        snapshot["door_indicator_offset"] = (float(self.door_indicator_offset_x), float(self.door_indicator_offset_y))
        snapshot["door_indicator_box_enabled"] = bool(self.is_indicator_box_var.get())
        snapshot["part_dimensions"] = {
            "box_body": {"width": w, "height": h},
            "head": {"width": w, "height": d},
            "tail": {"width": w, "height": d},
            "door": {"width": door_w, "height": door_h},
            "base_plate": {"width": base_w, "height": base_h},
            "indicator_box": {"width": ib_w, "height": ib_h},
            "indicator_door": {"width": id_w, "height": id_h},
        }
        if committed_profiles:
            snapshot["part_profiles"] = committed_profiles
        return snapshot


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
            25, float(y), anchor=tk.NW, text=text, fill="#30d158",
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

    def _phase6_current_existing_parts(self):
        """Return physical presence from the single Workspace Controller."""
        indicator_var = getattr(self, "is_indicator_box_var", None)
        indicator_enabled = bool(indicator_var.get()) if indicator_var is not None else False
        return self.workspace_controller.current_existing_parts(
            indicator_box_enabled=indicator_enabled
        )

    def _phase6_set_part_presence(self, key, present):
        """Mutate physical presence through the single Workspace Controller."""
        existing = self.workspace_controller.set_part_presence(str(key), bool(present))
        self._phase6_refresh_presence_ui(existing)
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        return existing

    def _phase6_refresh_presence_ui(self, existing_parts=None):
        return _refresh_presence_ui_impl(self, existing_parts)
        
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
        return __attach_part_hole_entrypoint_impl(self, canvas, part_key, allow_double=allow_double)

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
        return __parse_layout_value_impl(var, label)

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
        return __reject_door_layout_dimension_impl(self, var, previous_value, message)

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
        count = max(1, int(self.indicator_l_var.get()))
        layer_groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(count))
        spec = self._indicator_box_part_spec(
            val, layer_groups, features=self.surface_features["indicator_box"]
        )
        context = self._manufacturing_context(draw_stock=False)
        render_data = self._authoritative_render_data(spec, context)
        bounds = tuple(float(v) for v in render_data.material.bounds)
        return {
            "render_data": render_data,
            "bounds": bounds,
            "layer_groups": layer_groups,
            "baseline_label": ae.indicator_shared_baseline_source_label("盒子.dxf"),
        }

    def draw_indicator_box(self, val):
        canvas = self.canvas_indicator_box; canvas.delete("all")
        cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._indicator_box_render_snapshot(val)
        except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "指示燈盒", exc)
        return _draw_indicator_box_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _normalize_door_indicator_state(self, state):
        raw = dict(state or {})
        mode = raw.get("mode")
        if mode not in {"none", "indicator", "indicator_box"}:
            if raw.get("box_enabled"):
                mode = "indicator_box"
            elif raw.get("enabled"):
                mode = "indicator"
            else:
                mode = "none"
        try:
            layers = max(1, min(6, int(raw.get("layers", 1))))
        except (TypeError, ValueError):
            layers = 1
        groups = list(raw.get("groups", [2] * 6))
        while len(groups) < 6:
            groups.append(2)
        normalized_groups = []
        for value in groups[:6]:
            try:
                normalized_groups.append(max(1, int(value)))
            except (TypeError, ValueError):
                normalized_groups.append(2)
        return {
            "mode": mode,
            "enabled": mode == "indicator",
            "box_enabled": mode == "indicator_box",
            "layers": layers,
            "groups": normalized_groups,
            "offset_x": float(raw.get("offset_x", 0.0) or 0.0),
            "offset_y": float(raw.get("offset_y", 0.0) or 0.0),
            "is_box_dist": bool(raw.get("is_box_dist", False)),
        }

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
        for widget in list(self.door_layout_width_entries.values()) + list(self.door_layout_height_entries.values()):
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self.door_layout_width_entries = {}
        self.door_layout_height_entries = {}
        self.door_layout_entry_windows = []

    def _door_layout_entry_menu(self, entry, *, column_index, row_index=None):
        menu = tk.Menu(entry, tearoff=False)
        if row_index is None:
            column = self.door_layout_columns[column_index]
            if not column.get("width_auto", False):
                menu.add_command(label="刪除此欄", command=lambda: self.remove_door_layout_column(column_index))
        else:
            column = self.door_layout_columns[column_index]
            if not column["height_auto"][row_index]:
                menu.add_command(label="刪除此層", command=lambda: self.remove_door_layout_height(column_index, row_index))
        if menu.index("end") is not None:
            entry.bind("<Button-3>", lambda e, m=menu: (m.tk_popup(e.x_root, e.y_root), "break")[1])

    _draw_layout_resolved_features = staticmethod(_draw_layout_resolved_features_impl)


    _draw_layout_baseline_secondary = staticmethod(_draw_layout_baseline_secondary_impl)


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
        try:
            total_w = float(self.w_var.get())
            total_h = float(self.h_var.get())
            columns = self.get_door_layout_columns()
            cells = self.get_door_layout_cells()
            val = self.get_float_values()
        except Exception as exc:
            return {"error": exc}

        cell_payloads = {}
        for cell in cells:
            column_index = int(cell.column_index)
            row_index = int(cell.row_index)
            key = f"{column_index}:{row_index}"
            if render_data_by_part_key is None:
                result = self._door_layout_cell_result(cell, val)
                baseline_scene, _baseline_status = self._door_layout_baseline_scene(cell, val)
                resolved = self._door_layout_cell_resolved_features(cell, result, key)
                cell_payloads[(column_index, row_index)] = {
                    "mode": "local",
                    "scene": baseline_scene,
                    "resolved": resolved,
                    "width": float(result.width),
                    "height": float(result.height),
                }
            else:
                stable_key = f"door_c{column_index + 1}_r{row_index + 1}"
                peer_render_data = render_data_by_part_key.get(stable_key)
                material = getattr(peer_render_data, "material", None)
                scene = getattr(peer_render_data, "scene", None)
                if (
                    material is not None
                    and scene is not None
                    and not bool(getattr(material, "is_empty", False))
                ):
                    minx, miny, maxx, maxy = (float(v) for v in material.bounds)
                    cell_payloads[(column_index, row_index)] = {
                        "mode": "peer",
                        "scene": scene,
                        "width": max(maxx - minx, 1e-9),
                        "height": max(maxy - miny, 1e-9),
                    }
                else:
                    cell_payloads[(column_index, row_index)] = {"mode": "none"}

        baseline_model = self._baseline_source_model() or ""
        return {
            "error": None,
            "total_w": total_w,
            "total_h": total_h,
            "columns": columns,
            "cells": cells,
            "val": val,
            "selected_key": self.door_layout_selected_var.get(),
            "cell_payloads": cell_payloads,
            "baseline_status": ae.baseline_source_label(baseline_model, "門.dxf"),
        }

    def draw_door_layout_overview(self, *, canvas=None, render_data_by_part_key=None):
        if canvas is None: self._sync_door_canvas_double_click_binding(); canvas = self.canvas_door
        self._destroy_door_layout_entry_widgets()
        snapshot = self._door_layout_overview_snapshot(render_data_by_part_key)
        if snapshot.get("error") is not None: return _draw_door_layout_error_impl(self, canvas, snapshot["error"])
        return _draw_door_layout_overview_preview_impl(self, snapshot, canvas)

    def _door_layout_divider_frame_snapshot(self, columns, val):
        t_val = float(val.get('t', 2.0))
        project_snapshot = self._compose_phase6_project_snapshot_from_main_gui()
        total_w = float(project_snapshot.get("w", val.get("w", 0.0)))
        total_h = float(project_snapshot.get("h", val.get("h", 0.0)))
        divider_payloads = []
        frame_payloads = []

        try:
            from ae_engine.assembly_placement import resolve_assembly_placement
            from ae_engine.door_dividers import derive_box_body_dividers
            normalized = tuple(
                (float(c[0]), tuple(float(h) for h in c[1])) for c in columns
            )
            dividers = derive_box_body_dividers(
                normalized,
                depth=float(val.get('d', 350.0)),
                thickness=t_val,
                layout_scope=getattr(self, "door_layout_scope", "main"),
                handle_edges=getattr(self, "door_layout_handle_edges", {}),
            )
            for div in dividers:
                placement = resolve_assembly_placement(project_snapshot, div.stable_id)
                divider_payloads.append({
                    "axis": str(div.axis),
                    "span": float(div.span),
                    "formed_core_depth": float(div.formed_core_depth),
                    "world_offset": tuple(float(v) for v in placement.world_offset),
                })
        except Exception:
            pass

        try:
            from ae_engine.assembly_placement import resolve_assembly_placement
            from ae_engine.inner_door_frames import inner_door_frame_stable_id
            if cabinet_family_policy.has_inner_door_frame_derivation(project_snapshot):
                frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(project_snapshot)
                for fset in frame_sets:
                    for side in tuple(fset.included_sides):
                        if side not in {"top", "left", "right"}:
                            continue
                        stable_id = inner_door_frame_stable_id(fset.inner_door_id, side)
                        placement = resolve_assembly_placement(project_snapshot, stable_id)
                        frame_payloads.append({
                            "side": str(side),
                            "span": float(fset.spans[side]),
                            "world_offset": tuple(float(v) for v in placement.world_offset),
                        })
        except Exception:
            pass

        return {
            "total_w": total_w,
            "total_h": total_h,
            "dividers": tuple(divider_payloads),
            "frames": tuple(frame_payloads),
        }

    def _draw_door_layout_dividers_and_frames(self, canvas, scale, x0, y0, columns, cells, val):
        snapshot = self._door_layout_divider_frame_snapshot(columns, val)
        return _draw_door_layout_dividers_and_frames_preview_impl(canvas, snapshot, scale, x0, y0)

    def _single_door_render_snapshot(self):
        door_val = {
            'w': float(self.w_var.get()),
            'h': float(self.h_var.get()),
            't': float(self.t_var.get()),
            'fw': float(self.fw_z_var.get()),
            'door_gap_w': float(self.door_gap_w_var.get()),
            'door_gap_h': float(self.door_gap_h_var.get()),
            'door_fold_l': float(self.door_fold_l_var.get()),
            'door_fold_r': float(self.door_fold_r_var.get()),
            'door_fold_t': float(self.door_fold_t_var.get()),
            'door_fold_b': float(self.door_fold_b_var.get()),
        }

        indicator_hole = None
        if self.is_indicator_box_var.get():
            try:
                count = max(1, int(self.indicator_l_var.get()))
                indicator_box_groups = tuple(
                    int(self.indicator_layer_g_vars[i].get()) for i in range(count)
                )
                indicator_hole = manufacturing_api.indicator_box_opening_size(
                    indicator_box_groups, thickness=door_val['t']
                )
            except Exception:
                indicator_hole = None

        door_indicator = None
        if self.is_door_indicator_var.get():
            try:
                count = max(1, int(self.door_indicator_l_var.get()))
                door_indicator = tuple(
                    int(self.door_indicator_layer_g_vars[i].get()) for i in range(count)
                )
            except Exception:
                door_indicator = None

        spec = self._single_door_part_spec(
            door_val, indicator_hole=indicator_hole, door_indicator=door_indicator
        )
        render_context = self._manufacturing_context(draw_stock=False)
        render_data = self._authoritative_render_data(spec, render_context)
        bounds = tuple(float(v) for v in render_data.material.bounds)
        minx, miny, maxx, maxy = bounds
        if maxx - minx <= 0 or maxy - miny <= 0:
            raise ValueError("門板 Final Part Geometry 尺寸無效")

        finished_context = self._manufacturing_context(draw_stock=False)
        finished_size = tuple(
            float(v) for v in manufacturing_api.door_finished_face_size(spec, finished_context)
        )

        indicator_context = None
        indicator_layout = None
        x_guide = None
        y_guide = None
        indicator_groups = tuple(door_indicator or ())
        if indicator_groups:
            try:
                finished_w, finished_h = finished_size
                indicator_context = DoorIndicatorContext(
                    finished_width=finished_w,
                    finished_height=finished_h,
                    left_fold=door_val['door_fold_l'],
                    bottom_fold=door_val['door_fold_b'],
                )
                indicator_layout = resolve_door_indicator_layout(
                    indicator_context,
                    indicator_groups,
                    Vec2(self.door_indicator_offset_x, self.door_indicator_offset_y),
                )
                position = measure_door_indicator_position(
                    indicator_layout,
                    indicator_context,
                    frame_width=door_val['fw'],
                    thickness=door_val['t'],
                    use_box_distance=spec.use_box_distance,
                    frame_edges=spec.frame_edges,
                    gap_w=door_val['door_gap_w'],
                    gap_h=door_val['door_gap_h'],
                )
                x_guide, y_guide = resolve_door_indicator_dimension_guides(position)
            except Exception:
                indicator_context = None
                indicator_layout = None
                x_guide = None
                y_guide = None

        return {
            "render_data": render_data,
            "bounds": bounds,
            "finished_size": finished_size,
            "door_val": door_val,
            "model_name": spec.model_name,
            "frame_edges": spec.frame_edges,
            "indicator_context": indicator_context,
            "indicator_groups": indicator_groups,
            "indicator_layout": indicator_layout,
            "x_guide": x_guide,
            "y_guide": y_guide,
        }

    def draw_door(self, val):
        if self.multi_door_enabled_var.get(): return self.draw_door_layout_overview()
        canvas = self.canvas_door; canvas.delete("all"); cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._single_door_render_snapshot()
        except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "門板", exc, width=cw-40, font_size=10)
        return _draw_single_door_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _base_plate_render_snapshot(self, val):
        shrink_top = float(self.base_plate_shrink_top_var.get())
        shrink_bottom = float(self.base_plate_shrink_bottom_var.get())
        shrink_left = float(self.base_plate_shrink_left_var.get())
        shrink_right = float(self.base_plate_shrink_right_var.get())
        bend = float(self.base_plate_bend_var.get())
        spec_val = dict(val)
        spec_val.update({
            'base_plate_shrink_top': shrink_top,
            'base_plate_shrink_bottom': shrink_bottom,
            'base_plate_shrink_left': shrink_left,
            'base_plate_shrink_right': shrink_right,
            'base_plate_bend': bend,
        })
        spec = self._base_plate_part_spec(spec_val)
        context = self._manufacturing_context(draw_stock=False)
        render_data = self._authoritative_render_data(spec, context)
        bounds = tuple(float(v) for v in render_data.material.bounds)
        minx, miny, maxx, maxy = bounds
        box_l = -(shrink_left - bend)
        box_b = -(shrink_bottom - bend)
        world_bounds = (
            min(minx, box_l),
            min(miny, box_b),
            max(maxx, box_l + val['w']),
            max(maxy, box_b + val['h']),
        )
        return {
            "render_data": render_data,
            "bounds": bounds,
            "world_bounds": tuple(float(v) for v in world_bounds),
            "box_rect": (float(box_l), float(box_b), float(val['w']), float(val['h'])),
            "bend": float(bend),
        }

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
        # 清空先前的元件
        for widget in self.door_layers_config_frame.winfo_children():
            widget.destroy()
            
        try:
            layers = int(self.door_indicator_l_var.get())
        except ValueError:
            layers = 1
            
        # 逐層建立橫向的組數選擇選單
        for ly in range(layers):
            ly_frame = tk.Frame(self.door_layers_config_frame, bg=self.COLOR_PANEL)
            ly_frame.pack(side=tk.LEFT, padx=15, pady=4)
            
            label_text = f"第 {ly+1} 層組數:"
            if ly == 0:
                label_text = "第 1 層 (底) 組數:"
            elif ly == layers - 1 and layers > 1:
                label_text = f"第 {ly+1} 層 (頂) 組數:"
                
            tk.Label(ly_frame, text=label_text, bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold')).pack(side=tk.LEFT, padx=2)
            
            cb = ttk.Combobox(ly_frame, textvariable=self.door_indicator_layer_g_vars[ly], values=["1", "2", "3", "4", "5", "6", "7", "8"], width=4, state="readonly", style='TCombobox')
            cb.pack(side=tk.LEFT, padx=2)
            cb.bind("<<ComboboxSelected>>", lambda e: self._request_phase6_update("geometry"))

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
        return __indicator_small_door_size_chain_label_impl(self)

    def setup_tab_indicator_door_ui(self):
        return _setup_tab_indicator_door_ui_impl(self)

    def _indicator_door_render_snapshot(self, val):
        count = max(1, int(self.indicator_l_var.get()))
        layer_groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(count))
        spec, context = self._indicator_door_part_spec_from_values(
            val, layer_groups, features=self.surface_features["indicator_door"]
        )
        render_data = self._authoritative_render_data(spec, context)
        bounds = tuple(float(v) for v in render_data.material.bounds)
        finished_size = manufacturing_api.door_finished_face_size(spec, context)
        return {
            "render_data": render_data,
            "bounds": bounds,
            "finished_size": tuple(float(v) for v in finished_size),
        }

    def draw_indicator_door(self, val):
        canvas = self.canvas_indicator_door; canvas.delete("all")
        cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._indicator_door_render_snapshot(val)
        except Exception as exc: return _draw_preview_error_impl(canvas, cw, ch, "指示燈小門", exc)
        return _draw_indicator_door_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _inherit_known_corner_state_into_custom(self):
        """把目前已知固定板件的實際截角狀態複製成自訂起點。"""
        copied = self._known_corner_state_for_current_family(self.manual_corner_state.keys())
        for part_key, corners in copied.items():
            if part_key not in self.manual_corner_state:
                continue
            self.manual_corner_state[part_key].update(corners)
            if part_key in self.manual_corner_pair_same:
                self.manual_corner_pair_same[part_key]["top"] = True
                self.manual_corner_pair_same[part_key]["bottom"] = True

    def _capture_cabinet_family_runtime(self):
        # The family preset itself must carry a real canonical Box Body profile.
        # Startup used to capture None here, which later restored a profile-less
        # family and reopened the legacy fixed-segment manufacturing fallback.
        box_profile = self.workspace_controller.box_body_profile()
        if box_profile is None:
            profile_source = {
                key: var.get() for key, var in self._setting_var_map().items()
            }
            profile_source["model"] = Phase6ApplicationHost._current_cabinet_type_name(self)
            box_profile = build_box_body_profile(profile_source)
            if not box_profile:
                raise ValueError("canonical Box Body Fold Profile materialization failed")
            self.workspace_controller.set_box_body_profile(box_profile)
        elif not box_profile:
            raise ValueError("canonical Box Body Fold Profile is empty")

        layout = []
        if getattr(self, "door_layout_columns", None):
            try:
                layout = [[float(width), [float(v) for v in heights]] for width, heights in self.get_door_layout_columns()]
            except Exception:
                layout = []
        return {
            "settings": {key: var.get() for key, var in self._setting_var_map().items()},
            "corner_state": self._serialize_manual_corner_state(),
            "corner_pair_same": deepcopy(self.manual_corner_pair_same),
            "endcap_bottom_wrap": deepcopy(getattr(self, "endcap_bottom_wrap_state", {})),
            "box_body_structure": self.workspace_controller.box_body_structure_state(),
            "box_body_profile": self.workspace_controller.box_body_profile(),
            "assembly_joint_state": deepcopy(getattr(self, "assembly_joint_state", {}) or {}),
            "multi_door_enabled": bool(self.multi_door_enabled_var.get()),
            "door_layout_columns": layout,
            "door_layout_scope": str(getattr(self, "door_layout_scope", "main") or "main"),
            "door_handle_edges": deepcopy(getattr(self, "door_layout_handle_edges", {}) or {}),
            "receiving_inner_doors": deepcopy(getattr(self, "receiving_inner_doors", []) or []),
            "door_nameplate_center_datum_top": getattr(self, "door_nameplate_center_datum_top", None),
        }

    def _restore_cabinet_family_runtime(self, state):
        state = dict(state or {})
        values = {}
        for key, raw in dict(state.get("settings") or {}).items():
            try:
                values[key] = bool(raw) if key == "draw_stock" else float(raw)
            except (TypeError, ValueError):
                continue
        self._apply_fold_designer_live_settings(values, recalculate=False)
        self._apply_manual_corner_snapshot(state.get("corner_state"), state.get("corner_pair_same"))
        if state.get("endcap_bottom_wrap") is not None:
            self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({
                "model": Phase6ApplicationHost._current_cabinet_type_name(self),
                "endcap_bottom_wrap": state.get("endcap_bottom_wrap"),
            })
        joint_state = state.get("assembly_joint_state")
        if isinstance(joint_state, dict) and joint_state:
            self.assembly_joint_state = migrate_legacy_snapshot_joints(deepcopy(joint_state))
            stable = assembly_intent_value(self.assembly_joint_state.get("assembly_type", "INSERT_OVERLAY"))
            self.box_assembly_type_var.set(assembly_intent_label(stable))
        self.multi_door_enabled_var.set(bool(state.get("multi_door_enabled", False)))
        layout = list(state.get("door_layout_columns") or [])
        if layout:
            self.set_door_layout_columns([(float(row[0]), [float(v) for v in row[1]]) for row in layout])
        else:
            self.door_layout_columns = []
        self.door_layout_scope = str(state.get("door_layout_scope") or "main")
        self.door_layout_handle_edges = deepcopy(dict(state.get("door_handle_edges") or {}))
        self.receiving_inner_doors = deepcopy(state.get("receiving_inner_doors") or [])
        datum = state.get("door_nameplate_center_datum_top")
        self.door_nameplate_center_datum_top = None if datum is None else float(datum)
        self.workspace_controller.set_box_body_structure_state(state.get("box_body_structure"))
        self.workspace_controller.set_box_body_profile(state.get("box_body_profile"))

    def _apply_cabinet_family_for_current_model(self):
        """Apply an explicit model switch without remembering known-family edits.

        Known models always load their own preset.  ``自訂`` is the sole
        exception: entering custom leaves the current operator values in place
        as the starting point.  Project/3D snapshot restoration uses the
        baseline commit guard and therefore does not run this fresh-preset path.
        """
        raw_model = normalize_custom_model_name(
            self.baseline_var.get() if getattr(self, "baseline_var", None) is not None else ""
        )
        new_type = Phase6ApplicationHost._current_cabinet_type_name(self)
        previous = str(getattr(self, "_active_cabinet_type", "金庫型") or "金庫型")

        # Project load / 3D live-state application owns the complete snapshot.
        # Do not wash saved values through a fresh family preset in that path.
        if getattr(self, "_fold_designer_baseline_commit_guard", False):
            self._active_cabinet_type = new_type
            return previous != new_type

        # Custom is intentionally not another family preset.  It inherits the
        # current values exactly; later edits become the custom starting state.
        if is_unknown_model(raw_model):
            self._active_cabinet_type = new_type
            owner = getattr(self, "_derived_cache_owner", None)
            if owner is not None:
                owner.invalidate("geometry")
            return previous != new_type

        if new_type == "金庫型":
            defaults = deepcopy(
                dict(getattr(self, "_cabinet_family_defaults", {}) or {}).get("金庫型")
                or {}
            )
            if defaults:
                self._restore_cabinet_family_runtime(defaults)
        elif new_type == "受電箱":
            # Start from immutable/startup settings, never from the last edited
            # Receiving runtime.  The family policy then overlays its canonical
            # receiving defaults (800/1600/350, FW 29, structure, etc.).
            vault_defaults = deepcopy(
                dict(getattr(self, "_cabinet_family_defaults", {}) or {}).get("金庫型")
                or {}
            )
            base_settings = dict(vault_defaults.get("settings") or self.settings_service.snapshot().as_dict())
            values = cabinet_family_policy.apply_fresh_family_defaults(base_settings, new_type)
            self._apply_fold_designer_live_settings(values, recalculate=False)
            self._set_box_assembly_type(values["assembly_type"], recalculate=False, notify_designer=False)
            self.multi_door_enabled_var.set(bool(values.get("multi_door_enabled", True)))
            self.set_door_layout_columns([
                (float(row[0]), [float(v) for v in row[1]])
                for row in values.get("door_layout_columns", ())
            ])
            self.door_layout_scope = str(values.get("door_layout_scope") or "receiving-main")
            self.door_layout_handle_edges = deepcopy(dict(values.get("door_handle_edges") or {}))
            self.receiving_inner_doors = deepcopy(values.get("inner_doors") or [])
            self.door_nameplate_center_datum_top = float(values["door_nameplate_center_datum_top"])
            structure = cabinet_family_policy.resolve_box_body_structure_state(
                new_type, self.workspace_controller.box_body_structure_state()
            )
            self.workspace_controller.set_box_body_structure_state(structure)
            self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({"model": new_type})
            bottom = cabinet_family_policy.endcap_bottom_selection(new_type)
            for part in ("head", "tail"):
                self.manual_corner_state[part]["bottom_left"] = bottom
                self.manual_corner_state[part]["bottom_right"] = bottom
                self.manual_corner_pair_same[part]["bottom"] = True
            snap = self._make_original_fold_designer_snapshot()
            box_profile = build_box_body_profile(snap)
            workspace = self.workspace_controller.workspace_snapshot()
            workspace["box_body_profile"] = box_profile
            workspace["box_body_structure"] = structure
            self._store_fold_designer_workspace(workspace)

        self._active_cabinet_type = new_type
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        return previous != new_type


    def on_baseline_changed(self):
        self._reset_manual_corner_parameter_locks()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("baseline")
        val = self.baseline_var.get()
        previous = str(getattr(self, "_baseline_last_value", "") or "").strip()
        self._apply_cabinet_family_for_current_model()
        if is_unknown_model(val) and previous and not is_unknown_model(previous):
            self._inherit_known_corner_state_into_custom()
        elif val and not is_unknown_model(val) and val != previous:
            self._enforce_known_model_corner_types(reset_all=True)
        current_intent = self._current_box_assembly_type()
        assembly_var = getattr(self, "box_assembly_type_var", None)
        if assembly_var is not None:
            label = assembly_intent_label(current_intent)
            if assembly_var.get() != label:
                assembly_var.set(label)
        cb_assembly = getattr(self, "cb_box_assembly", None)
        if cb_assembly is not None:
            cb_assembly.configure(state=("readonly" if is_unknown_model(val) else "disabled"))
        self._baseline_last_value = str(val or "").strip()
        self.refresh_corner_type_panel()
        designer = getattr(self, "fold_designer_app", None)
        if designer is not None and hasattr(designer, "apply_external_model"):
            try:
                designer.apply_external_model(val)
            except tk.TclError:
                pass
        if getattr(self, "_fold_designer_baseline_commit_guard", False):
            # 3D 確定 only changes the baseline/corner transaction. Do not let
            # the legacy baseline handler overwrite already-edited fold values.
            return
        if not val:
            return
        if is_unknown_model(val):
            # 自訂沒有 baseline DXF；保留使用者輸入的折彎尺寸。
            self._request_phase6_update("baseline")
            return
        if Phase6ApplicationHost._current_cabinet_type_name(self) == "受電箱":
            # 受電箱第一階段使用公式/Family policy，沒有自己的 baseline DXF。
            self._request_phase6_update("baseline")
            return
        try:
            t_val = float(self.t_var.get()) if self.t_var.get() else 2.0
            
            # 1. 載入封頭尾基準檔分析折彎參數
            geom = ae.get_stretched_end_cap_data(val, 500, 500, 150, t_val, FW_val=None, is_tail=False)
            p = geom.params
            
            self.yl1_var.set(f"{p['yl1']:.1f}".replace(".0", ""))
            self.yr1_var.set(f"{p['yr1']:.1f}".replace(".0", ""))
            self.ytop1_var.set(f"{p['ytop1']:.1f}".replace(".0", ""))
            self.ybottom1_var.set(f"{p['ybottom1']:.1f}".replace(".0", ""))
            # 基準檔更新箱身 FW；封頭尾只有仍在「跟隨箱身」時同步。
            fw_val = f"{p['fw']:.1f}".replace(".0", "")
            self.fw_z_var.set(fw_val)
            box_fw = float(p['fw'])
            for part in ("head", "tail"):
                state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": box_fw})
                if bool(state.get("follow_box", True)):
                    state["value"] = box_fw
            self._sync_endcap_fw_controls()
            
            # 2. 箱身主結構固定由 StripFoldChain 公式控制。
            # 箱身.dxf 只映射固定加工特徵，不反推/覆寫 zl1/zl2/zr1/zr2/z_comp。

            # 3. 檢查並加載目前型號的門基準；GUI 不自行組 baseline 路徑。
            if ae.has_baseline_part(val, "門.dxf"):
                try:
                    door_fw = self._door_material_frame_width(
                        self.fw_z_var.get(), t_val, model_name=val
                    )
                    geom_door = ae.get_stretched_door_data(
                        val, 500, 500, t_val, door_fw
                    )
                    pd = geom_door.params
                    self.door_fold_l_var.set(f"{pd['door_fold_l']:.1f}".replace(".0", ""))
                    self.door_fold_r_var.set(f"{pd['door_fold_r']:.1f}".replace(".0", ""))
                    self.door_fold_t_var.set(f"{pd['door_fold_t']:.1f}".replace(".0", ""))
                    self.door_fold_b_var.set(f"{pd['door_fold_b']:.1f}".replace(".0", ""))
                except Exception as door_err:
                    self.door_fold_l_var.set("19")
                    self.door_fold_r_var.set("15")
                    self.door_fold_t_var.set("15")
                    self.door_fold_b_var.set("15")
        except Exception as e:
            messagebox.showerror("基準檔載入出錯", f"無法讀取基準檔參數: {e}")

        # STOCK 開關變動時也觸發重繪 (Checkbutton 已用 command 綁定，此處不需重複)

    def get_float_values(self):
        """
        取得所有浮點數輸入值，若輸入有誤則拋出 Exception
        """
        try:
            return {
                'w': float(self.w_var.get()),
                'h': float(self.h_var.get()),
                'd': float(self.d_var.get()),
                'fw': float(self.fw_z_var.get()),
                't': float(self.t_var.get()),
                'zl1': float(self.zl1_var.get()),
                'zl2': float(self.zl2_var.get()),
                'zr1': float(self.zr1_var.get()),
                'zr2': float(self.zr2_var.get()),
                'z_comp': float(self.z_comp_var.get()),
                'yl1': float(self.yl1_var.get()),
                'yr1': float(self.yr1_var.get()),
                'ytop1': float(self.ytop1_var.get()),
                'ybottom1': float(self.ybottom1_var.get()),
                'door_gap_w': float(self.door_gap_w_var.get()),
                'door_gap_h': float(self.door_gap_h_var.get()),
                'door_fold_l': float(self.door_fold_l_var.get()),
                'door_fold_r': float(self.door_fold_r_var.get()),
                'door_fold_t': float(self.door_fold_t_var.get()),
                'door_fold_b': float(self.door_fold_b_var.get()),
                'base_plate_shrink_top': float(self.base_plate_shrink_top_var.get()),
                'base_plate_shrink_bottom': float(self.base_plate_shrink_bottom_var.get()),
                'base_plate_shrink_left': float(self.base_plate_shrink_left_var.get()),
                'base_plate_shrink_right': float(self.base_plate_shrink_right_var.get()),
                'base_plate_bend': float(self.base_plate_bend_var.get()),
            }
        except ValueError:
            raise ValueError("請輸入有效的數字格式")

    def _active_indicator_box_groups_for_results(self):
        """Return groups only when the currently relevant Door really uses an Indicator Box.

        Single-Door follows the explicit Indicator-Box toggle. Multi-Door follows
        only the currently selected cell, so an unrelated cell cannot leak box
        dimensions into the result panel.
        """
        if self.multi_door_enabled_var.get():
            key = str(self.door_layout_selected_var.get() or "")
            state = self.door_layout_indicator_states.get(key)
            if not state:
                return None
            state = self._normalize_door_indicator_state(state)
            if state.get("mode") != "indicator_box":
                return None
            layers = max(1, min(6, int(state.get("layers", 1))))
            groups = tuple(int(v) for v in list(state.get("groups", ()))[:layers])
        else:
            if not self.is_indicator_box_var.get():
                return None
            layers = max(1, min(6, int(self.indicator_l_var.get())))
            groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
        if not groups or any(value <= 0 for value in groups):
            return None
        return groups

    def _has_any_indicator_box(self):
        """True only when at least one real Door/cell is configured as Indicator Box."""
        if not self.multi_door_enabled_var.get():
            return bool(self.is_indicator_box_var.get())
        try:
            keys = [self._door_layout_cell_key(cell) for cell in self.get_door_layout_cells()]
        except Exception:
            keys = list(getattr(self, "door_layout_indicator_states", {}).keys())
        for key in keys:
            state = self._normalize_door_indicator_state(
                getattr(self, "door_layout_indicator_states", {}).get(key)
            )
            if state.get("mode") == "indicator_box":
                return True
        return False

    def _clear_indicator_box_result_values(self):
        self.result_ib_w_var.set("-")
        self.result_ib_h_var.set("-")
        self.result_ib_door_w_var.set("-")
        self.result_ib_door_h_var.set("-")

    def _refresh_indicator_box_result_values(self, val):
        """Refresh box/small-door dimensions from actual Indicator-Box state only."""
        self._clear_indicator_box_result_values()
        layer_groups = self._active_indicator_box_groups_for_results()
        if layer_groups is None:
            return

        g_max = max(layer_groups)
        indicator_ctx = ManufacturingContext()
        ib_w, ib_h = manufacturing_api.indicator_box_unfolded_size(
            layer_groups, thickness=val['t'], context=indicator_ctx
        )
        ib_door_w, ib_door_h = manufacturing_api.indicator_small_door_unfolded_size(
            layer_groups, thickness=val['t'], context=indicator_ctx
        )
        self.result_ib_w_var.set(f"{ib_w:.2f} mm")
        self.result_ib_h_var.set(f"{ib_h:.2f} mm")
        self.result_ib_door_w_var.set(f"{ib_door_w:.2f} mm")
        self.result_ib_door_h_var.set(f"{ib_door_h:.2f} mm")
        self.indicator_g_var.set(str(g_max))

        x_left_light = 171.0
        x_right_light = 171.0 + 90.0 * max(0, g_max - 1)
        if g_max <= 1:
            hc = 1
        elif g_max <= 3:
            hc = 2
        elif g_max <= 5:
            hc = 3
        else:
            hc = 4
        if hc > 1:
            max_pitch = (x_right_light - x_left_light) / (hc - 1)
            hp = max(50.0, float(int(max_pitch // 50) * 50))
            x_mid = (x_left_light + x_right_light) / 2.0
            hx = x_mid - (hc - 1) * hp / 2.0
        else:
            hp = 150.0
            hx = 191.0 if g_max == 1 else 172.5
        self.ib_hole_start_x_var.set(f"{hx:.1f}".replace(".0", ""))
        self.ib_hole_pitch_var.set(f"{int(hp)}")
        self.ib_hole_count_var.set(str(hc))
        self.ib_hole_y_var.set("178.5")

    def update_calculations(self):
        try:
            val = self.get_float_values()
            # 1. 箱身結果尺寸只量 authoritative canonical Z Fold Chain。
            # Multi-piece render_data.material 是 exploded preview envelope；
            # summary 必須改量同一 spec 的 canonical strip，不得退回固定段數公式。
            z_spec = self._box_body_part_spec(val)
            z_render = self._authoritative_render_data(
                z_spec, self._manufacturing_context(draw_stock=False)
            )
            z_dimension_render = getattr(z_render, "canonical_strip_render_data", z_render)
            z_minx, z_miny, z_maxx, z_maxy = (
                float(v) for v in z_dimension_render.material.bounds
            )
            z_len = z_maxx - z_minx
            z_h = z_maxy - z_miny
            
            # 2. 封頭／封尾結果尺寸。Phase6 一旦提交 linked Fold Profile，
            # 主 2D 必須直接量同一份 authoritative FinalScene；不得再回到
            # ytop1 + FW + D 的 legacy 公式，否則 3D 自動刪折後主畫面仍會
            # 顯示舊 300 mm。
            baseline = self._baseline_source_model()
            existing_parts = self._phase6_current_existing_parts()
            committed_profiles = self.workspace_controller.part_profiles_snapshot()
            summary_part = next((
                k for k in ("head", "tail")
                if k in existing_parts and committed_profiles.get(k)
            ), None)
            has_endcap = bool({"head", "tail"} & existing_parts)
            if not has_endcap:
                y_w = y_d = None
            elif summary_part is not None:
                y_spec = self._end_cap_part_spec(val, is_tail=(summary_part == "tail"))
                y_render = self._authoritative_render_data(
                    y_spec, self._manufacturing_context(draw_stock=False)
                )
                y_minx, y_miny, y_maxx, y_maxy = (float(v) for v in y_render.material.bounds)
                y_w = y_maxx - y_minx
                y_d = y_maxy - y_miny
            else:
                if baseline:
                    geom = ae.get_stretched_end_cap_data(
                        baseline, val['w'], val['h'], val['d'], val['t'],
                        FW_val=val['fw'], is_tail=False
                    )
                    y_w = geom.params['total_width']
                    y_d = geom.params['total_depth']
                else:
                    y_w = ae.calculate_y_width(val['yl1'], val['yr1'], val['w'], val['t'])
                    y_d = ae.calculate_y_depth(
                        val['ytop1'], val['ybottom1'], val['d'], val['t'], val['fw']
                    )
            
            # 3. 計算門 Door。不存在的板件不建立/計算預覽資料。
            door_material_fw = self._door_material_frame_width(val['fw'], val['t'])
            if not self._phase6_logical_part_present(existing_parts, "door"):
                door_w = door_h = None
            elif self.multi_door_enabled_var.get():
                cell = self.get_selected_door_layout_cell()
                door_w, door_h = ae.calculate_door_blank_size(
                    cell.start_width, cell.start_height, val['t'], door_material_fw,
                    val['door_gap_w'], val['door_gap_h'],
                    val['door_fold_l'], val['door_fold_r'],
                    val['door_fold_t'], val['door_fold_b'],
                    frame_edges=cell.edges,
                )
            elif baseline:
                try:
                    geom_door = ae.get_stretched_door_data(baseline, val['w'], val['h'], val['t'], door_material_fw,
                                                          val['door_gap_w'], val['door_gap_h'],
                                                          val['door_fold_l'], val['door_fold_r'],
                                                          val['door_fold_t'], val['door_fold_b'])
                    door_w = geom_door.params['total_width']
                    door_h = geom_door.params['total_depth']
                except Exception:
                    door_w, door_h = ae.calculate_door_blank_size(
                        val['w'], val['h'], val['t'], door_material_fw,
                        val['door_gap_w'], val['door_gap_h'],
                        val['door_fold_l'], val['door_fold_r'],
                        val['door_fold_t'], val['door_fold_b']
                    )
            else:
                door_w, door_h = ae.calculate_door_blank_size(
                    val['w'], val['h'], val['t'], door_material_fw,
                    val['door_gap_w'], val['door_gap_h'],
                    val['door_fold_l'], val['door_fold_r'],
                    val['door_fold_t'], val['door_fold_b']
                )
            
            # 3.5 計算底板
            if self._phase6_logical_part_present(existing_parts, "base_plate"):
                base_plate_w = val['w'] - val['base_plate_shrink_left'] - val['base_plate_shrink_right'] + 2.0 * val['base_plate_bend']
                base_plate_h = val['h'] - val['base_plate_shrink_top'] - val['base_plate_shrink_bottom'] + 2.0 * val['base_plate_bend']
            else:
                base_plate_w = base_plate_h = None
            
            self.result_z_var.set(f"{z_len:.2f} mm")
            self.result_z_h_var.set(f"{z_h:.2f} mm")
            self.result_y_w_var.set("-" if y_w is None else f"{y_w:.2f} mm")
            self.result_y_d_var.set("-" if y_d is None else f"{y_d:.2f} mm")
            self.result_door_w_var.set("-" if door_w is None else f"{door_w:.2f} mm")
            self.result_door_h_var.set("-" if door_h is None else f"{door_h:.2f} mm")
            self.result_base_plate_w_var.set("-" if base_plate_w is None else f"{base_plate_w:.2f} mm")
            self.result_base_plate_h_var.set("-" if base_plate_h is None else f"{base_plate_h:.2f} mm")
            
            # 只有存在的指示燈板件才計算；不存在就保持完全空白。
            if {"indicator_box", "indicator_door"} & existing_parts:
                try:
                    self._refresh_indicator_box_result_values(val)
                except Exception:
                    self._clear_indicator_box_result_values()
            else:
                self._clear_indicator_box_result_values()
            self._phase6_refresh_presence_ui(existing_parts)
            
            # 重新繪製預覽
            self.draw_preview()
            
        except Exception:
            # 數值尚未輸入完整時，不顯示錯誤，只把計算結果顯示為 "-"
            self.result_z_var.set("-")
            self.result_z_h_var.set("-")
            self.result_y_w_var.set("-")
            self.result_y_d_var.set("-")
            self.result_door_w_var.set("-")
            self.result_door_h_var.set("-")
            self.result_base_plate_w_var.set("-")
            self.result_base_plate_h_var.set("-")
            self.result_ib_w_var.set("-")
            self.result_ib_h_var.set("-")
            self.result_ib_door_w_var.set("-")
            self.result_ib_door_h_var.set("-")


    def draw_preview(self):
        """Refresh only the visible authoritative Fold Designer corner-data View."""
        designer = getattr(self, "fold_designer_app", None)
        if designer is None:
            return None
        if str(getattr(designer, "_phase6_3d_display_mode", "") or "") != "corner_data":
            return None
        if getattr(designer, "corner_data_canvas", None) is None:
            return None
        refresh = getattr(designer, "_phase6_refresh_corner_data_unfold_view", None)
        return refresh() if callable(refresh) else None

    draw_grid = _draw_grid_impl


    def _box_body_face_at_canvas_point(self, x, y):
        return _box_body_face_at_canvas_point_impl(self.box_body_face_bounds, x, y)

    def select_box_body_face(self, face_key):
        return _select_box_body_face_impl(self, face_key)

    def on_box_body_canvas_press(self, event):
        return _on_box_body_canvas_press_impl(self, event)

    def _box_body_baseline_faces(self, val):
        model = self._baseline_source_model()
        if not model or not ae.has_baseline_part(model, "箱身.dxf"):
            return {"left": [], "back": [], "right": []}
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        source_fp = ae.baseline_source_fingerprint(ae.baseline_expected_path(model, "箱身.dxf"))
        cache_key = (
            source_fp, model, val['w'], val['h'], val['d'], val['t'], val['fw'],
            val['zl1'], val['zl2'], val['zr1'], val['zr2'], val['z_comp'],
            head_policy, tail_policy,
        )
        if cache_key not in self._box_body_baseline_face_cache:
            self._box_body_baseline_face_cache[cache_key] = ae.get_box_body_baseline_face_features(
                model,
                w=val['w'], h=val['h'], d=val['d'], t=val['t'], fw=val['fw'],
                zl1=val['zl1'], zl2=val['zl2'], zr1=val['zr1'], zr2=val['zr2'],
                z_comp=val['z_comp'],
                head_corner_policy=head_policy, tail_corner_policy=tail_policy,
            )
        return self._box_body_baseline_face_cache[cache_key]

    def _box_body_face_baseline_scene(self, face_key, val):
        resolved = self._box_body_baseline_faces(val).get(face_key, [])
        if not resolved:
            return None
        scene = DrawingScene()
        scene.extend(resolved_features_to_primitives(resolved))
        return scene

    def open_box_body_face_editor(self, face_key):
        if face_key not in {"left", "back", "right"}:
            messagebox.showerror("開孔失敗", f"未知箱身面: {face_key}")
            return
        try:
            val = self.get_float_values()
        except ValueError as exc:
            messagebox.showerror("輸入錯誤", str(exc))
            return
        dims = box_body_face_dimensions(w=val['w'], h=val['h'], d=val['d'])
        width, height = dims[face_key]
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        bottom_outer, top_outer = box_body_vertical_offsets(
            val['t'], head_corner_policy=head_policy, tail_corner_policy=tail_policy
        )
        surface = feature_surface_from_rect(
            f"box_body_{face_key}",
            Vec2(val['t'], bottom_outer),
            Vec2(width - val['t'], height - top_outer),
        )
        reference_guide = RectGuide(
            Vec2(0.0, 0.0), Vec2(width, height), "enclosure_boundary"
        )
        title = {"left": "箱身左側", "back": "箱身背面", "right": "箱身右側"}[face_key]
        self.box_body_face_selected_var.set(face_key)
        self._open_unified_hole_editor(
            f"box_body_{face_key}", title, surface, width, height,
            reference_guide=reference_guide,
            feature_list_override=self.box_body_face_features[face_key],
            baseline_scene=self._box_body_face_baseline_scene(face_key, val),
            baseline_status_text=ae.box_body_baseline_source_label(self.baseline_var.get()),
            on_close=lambda: self.draw_box_body(self.get_float_values()),
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

    def _draw_box_body_piece_preview(self, aggregate_render_data, piece, part_key):
        return _draw_box_body_piece_preview_impl(self, aggregate_render_data, piece, part_key, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection)

    def _box_body_render_snapshot(self, val):
        spec = self._box_body_part_spec(val)
        render_data = self._authoritative_render_data(
            spec, self._manufacturing_context(draw_stock=False)
        )
        selected_piece_key = self._refresh_box_body_piece_tabs_2d(render_data)
        if selected_piece_key:
            selected_role = selected_piece_key.split(":", 1)[1]
            selected_piece = next(
                (
                    piece
                    for piece in tuple(getattr(render_data, "pieces", ()) or ())
                    if str(getattr(piece, "role", "") or "") == selected_role
                ),
                None,
            )
            if selected_piece is not None:
                return {
                    "mode": "piece",
                    "render_data": render_data,
                    "piece": selected_piece,
                    "piece_key": selected_piece_key,
                }

        bounds = tuple(float(v) for v in render_data.material.bounds)
        contexts = getattr(render_data, "box_body_face_contexts", None)
        if not contexts:
            raise ValueError("authoritative Box Body face contexts unavailable")
        baseline = self._baseline_source_model()
        return {
            "mode": "aggregate",
            "render_data": render_data,
            "bounds": bounds,
            "contexts": contexts,
            "selected_face": self.box_body_face_selected_var.get(),
            "baseline_status": ae.box_body_baseline_source_label(baseline),
            "dimensions": box_body_face_dimensions(
                w=val['w'], h=val['h'], d=val['d']
            ),
            "piece_keys": tuple(
                f"box_body:{str(piece.role)}"
                for piece in tuple(getattr(render_data, "pieces", ()) or ())
            ),
        }

    def draw_box_body(self, val):
        canvas = self.canvas_z; canvas.delete("all"); self.box_body_face_bounds = {}
        cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        snapshot = self._box_body_render_snapshot(val)
        if snapshot["mode"] == "piece": return self._draw_box_body_piece_preview(snapshot["render_data"], snapshot["piece"], snapshot["piece_key"])
        return _draw_box_body_aggregate_preview_impl(self, snapshot, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _end_cap_render_snapshot(self, val, *, part_label='封頭/尾', is_tail=False):
        baseline = self._baseline_source_model()
        spec = self._end_cap_part_spec(val, is_tail=is_tail)
        context = self._manufacturing_context(draw_stock=False)
        render_data = self._authoritative_render_data(spec, context)
        bounds = tuple(float(v) for v in render_data.material.bounds)
        if is_unknown_model(self.baseline_var.get()):
            baseline_hint = " (自訂 / Final Part Geometry)"
        elif baseline:
            baseline_hint = f" ({baseline} Final Part Geometry)"
        else:
            baseline_hint = " (Y-Cap Final Part Geometry)"
        return {
            "render_data": render_data,
            "bounds": bounds,
            "baseline_hint": baseline_hint,
            "part_label": part_label,
            "is_tail": bool(is_tail),
        }

    def draw_end_cap(self, val, canvas, part_label='封頭/尾', is_tail=False):
        canvas.delete("all"); cw = canvas.winfo_width(); ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1: return
        self.draw_grid(canvas, cw, ch)
        try: snapshot = self._end_cap_render_snapshot(val, part_label=part_label, is_tail=is_tail)
        except Exception as exc: return _draw_end_cap_error_impl(self, canvas, cw, ch, exc, hint_drawer=draw_hole_editor_hint)
        return _draw_end_cap_preview_impl(self, snapshot, canvas, cw, ch, viewport=_phase6_2d_material_viewport, scene_renderer=render_drawing_scene, annotation_drawer=_draw_phase6_annotation_projection, hint_drawer=draw_hole_editor_hint)

    def _manufacturing_context(self, *, draw_stock=False):
        """GUI-owned execution context for the headless manufacturing boundary."""
        return ManufacturingContext(draw_stock=bool(draw_stock), overwrite=True)

    def _box_body_part_spec_from_values(
        self, val, *, model_name, features, face_features,
        head_corner_policy=None, tail_corner_policy=None, fold_profile=None,
        structure_state=None, head_ybottom1=None, tail_ybottom1=None,
    ):
        def resolved_ybottom(part_key):
            profiles = self.workspace_controller.profile_for(part_key) or {}
            rows = list(dict(profiles).get("Y", ()) or ())
            for row in rows:
                if str(row.get("phase6_key") or "") == "ybottom1":
                    return float(engine_segment_length_to_ui(row))
            return float(val.get("ybottom1", ae.ybottom1_def))

        source_structure = (
            self.workspace_controller.box_body_structure_state()
            if structure_state is None else deepcopy(dict(structure_state or {}))
        )
        structure_state = cabinet_family_policy.resolve_box_body_structure_state(
            model_name, source_structure
        )

        return BoxBodyPartSpec(
            width=float(val['w']), height=float(val['h']), depth=float(val['d']),
            thickness=float(val['t']), frame_width=float(val['fw']),
            model_name=model_name,
            zl1=float(val['zl1']), zl2=float(val['zl2']),
            zr1=float(val['zr1']), zr2=float(val['zr2']),
            z_comp=float(val['z_comp']),
            fold_profile=profile_to_fold_segments(
                fold_profile if fold_profile is not None else (self.workspace_controller.box_body_profile() or ())
            ),
            features=tuple(features or ()),
            face_features={k: tuple(v) for k, v in dict(face_features or {}).items()},
            head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
            structure_state=(
                self.workspace_controller.box_body_structure_state()
                if structure_state is None else deepcopy(dict(structure_state or {}))
            ),
            head_ybottom1=(resolved_ybottom("head") if head_ybottom1 is None else float(head_ybottom1)),
            tail_ybottom1=(resolved_ybottom("tail") if tail_ybottom1 is None else float(tail_ybottom1)),
        )

    def _box_body_part_spec(self, val):
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        return self._box_body_part_spec_from_values(
            val, model_name=self._baseline_source_model(),
            features=self.surface_features["box_body"],
            face_features=self.box_body_face_features,
            head_corner_policy=head_policy, tail_corner_policy=tail_policy,
        )

    def _end_cap_part_spec_from_values(
        self, val, *, model_name, is_tail, holes, corner_policy=None, fold_profiles=None,
        depth_comp_t=None, resolved_assembly_relief_cuts=(),
        box_body_formed_fw_left=None, box_body_formed_fw_right=None,
        box_body_structure_state=None, endcap_bottom_wrap_state=None, assembly_joints=None,
    ):
        profiles = dict(fold_profiles or {})
        x_rows = [dict(row) for row in profiles.get("X", ())]
        y_rows = [dict(row) for row in profiles.get("Y", ())]

        if depth_comp_t is None:
            depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(model_name)

        # Scalar folds remain the canonical/legacy request values.  Fold Profile
        # precedence is resolved exactly once inside AE manufacturing_api.
        fold_left = float(val['yl1'])
        fold_right = float(val['yr1'])
        fold_top = float(val['ytop1'])
        fold_bottom = float(val['ybottom1'])

        if box_body_structure_state is None:
            controller = getattr(self, "workspace_controller", None)
            getter = getattr(controller, "box_body_structure_state", None)
            resolved_structure_state = deepcopy(dict(getter() if callable(getter) else {}))
        else:
            resolved_structure_state = deepcopy(dict(box_body_structure_state or {}))
        if assembly_joints is None:
            joint_state = dict(getattr(self, "assembly_joint_state", {}) or {})
            resolved_assembly_joints = tuple(deepcopy(joint_state.get("assembly_joints", ())) or ())
        else:
            resolved_assembly_joints = tuple(deepcopy(tuple(assembly_joints or ())))
            joint_state = {"assembly_joints": resolved_assembly_joints}
        if cabinet_family_policy.supports_bottom_wrap_controls(model_name):
            try:
                part_key = "tail" if is_tail else "head"
                wrap_state = endcap_bottom_wrap_state
                if wrap_state is None:
                    wrap_state = getattr(self, "endcap_bottom_wrap_state", None)
                if wrap_state is None:
                    wrap_state = normalize_endcap_bottom_wrap_state({"model": model_name})
                projection_snapshot = {"model": model_name, **joint_state}
                item = resolve_endcap_bottom_wrap(projection_snapshot, part_key, state=wrap_state)
                # enabled is graph-owned; Receiving state retains only geometric
                # reserve inputs for the certified BOTTOM WRAP formula.
                resolved_structure_state = cabinet_family_policy.set_bottom_relief_reserves(
                    model_name,
                    resolved_structure_state,
                    reserve_u=item["reserve_u"],
                    reserve_v=item["reserve_v"],
                )
            except Exception:
                pass

        return EndCapPartSpec(
            width=float(val['w']), height=float(val['h']), depth=float(val['d']),
            thickness=float(val['t']), frame_width=float(val['fw']),
            model_name=model_name, is_tail=bool(is_tail),
            fold_left=fold_left, fold_right=fold_right,
            fold_top=fold_top, fold_bottom=fold_bottom,
            box_fold_left=float(val['zl1']), box_fold_right=float(val['zr1']),
            box_body_formed_fw_left=(None if box_body_formed_fw_left is None else float(box_body_formed_fw_left)),
            box_body_formed_fw_right=(None if box_body_formed_fw_right is None else float(box_body_formed_fw_right)),
            box_body_structure_state=resolved_structure_state,
            assembly_joints=resolved_assembly_joints,
            fold_profile_x=profile_to_fold_segments(x_rows),
            fold_profile_y=profile_to_fold_segments(y_rows),
            holes=tuple(holes or ()), corner_policy=corner_policy,
            depth_comp_t=float(depth_comp_t),
            resolved_assembly_relief_cuts=tuple(
                tuple((float(x), float(y)) for x, y in polygon)
                for polygon in tuple(resolved_assembly_relief_cuts or ())
                if len(polygon) >= 3
            ),
        )

    @staticmethod
    def _phase6_relief_profile_signature(profile):
        rows = []
        for row in list(profile or ()):
            row = dict(row or {})
            rows.append((
                str(row.get("phase6_key") or ""),
                round(float(row.get("len", row.get("length", 0.0)) or 0.0), 6),
                None if row.get("angle") is None else round(float(row.get("angle") or 0.0), 6),
                str(row.get("core") or ""),
            ))
        return tuple(rows)

    def _resolved_committed_assembly_relief_cuts(self, key, val, stored_profiles):
        state = deepcopy(getattr(self, "assembly_relief_state", {}) or {})
        if not bool(state.get("enabled")):
            return ()
        part = dict((state.get("parts") or {}).get(str(key), {}) or {})
        if not bool(part.get("verified")) and not bool(part.get("canonical_accepted")):
            return ()
        trust_level = str(part.get("trust_level") or "")
        rule_id = part.get("rule_id")
        rule_revision = part.get("rule_revision")
        if trust_level in {"CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"} and rule_id:
            from ae_engine.certified_relief_registry import certified_rule_revision_exists
            try:
                active_revision = certified_rule_revision_exists(str(rule_id), int(rule_revision))
            except (TypeError, ValueError):
                active_revision = False
            if not active_revision:
                return ()
        source = dict(state.get("source") or {})
        from ae_engine.certified_relief_registry import RELIEF_CONTRACT_VERSION
        try:
            if int(source.get("relief_contract_version", 0) or 0) != RELIEF_CONTRACT_VERSION:
                return ()
        except (TypeError, ValueError):
            return ()

        # Replay identity is mechanical, not the high-level assembly mirror.
        # Graph/family/structure must all match the state that was shadow-verified.
        from ae_engine.assembly_joint import resolved_joint_graph_fingerprint
        import hashlib as _hashlib, json as _json
        try:
            current_graph_fp = resolved_joint_graph_fingerprint(dict(getattr(self, "assembly_joint_state", {}) or {}))
        except Exception:
            return ()
        if not str(source.get("joint_graph_fingerprint") or "") or str(source.get("joint_graph_fingerprint")) != current_graph_fp:
            return ()
        controller = getattr(self, "workspace_controller", None)
        structure_getter = getattr(controller, "box_body_structure_state", None)
        current_structure = structure_getter() if callable(structure_getter) else {}
        structure_payload = _json.dumps(current_structure or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        current_structure_fp = _hashlib.sha256(structure_payload.encode("utf-8")).hexdigest()
        if not str(source.get("family_structure_fingerprint") or "") or str(source.get("family_structure_fingerprint")) != current_structure_fp:
            return ()
        family_getter = getattr(self, "_baseline_source_model", None)
        current_family = str(family_getter() if callable(family_getter) else "")
        if str(source.get("cabinet_family") or "") != current_family:
            return ()

        saved_formed = dict(source.get("box_body_formed_fw") or {})
        if saved_formed:
            body_profile_getter = getattr(controller, "box_body_profile", None)
            current_formed_left, current_formed_right = formed_box_body_fw_widths(
                body_profile_getter() if callable(body_profile_getter) else (),
                float(val.get("t", 0.0) or 0.0),
            )
            for side, current in (("left", current_formed_left), ("right", current_formed_right)):
                try:
                    if current is None or abs(float(saved_formed[side]) - float(current)) > 1e-6:
                        return ()
                except (KeyError, TypeError, ValueError):
                    return ()

        source_rules = dict(source.get("registry_rules") or {})
        if trust_level in {"CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"} and rule_id:
            saved_rule = dict(source_rules.get(str(key)) or {})
            try:
                if str(saved_rule.get("rule_id") or "") != str(rule_id):
                    return ()
                if int(saved_rule.get("revision", 0) or 0) != int(rule_revision):
                    return ()
            except (TypeError, ValueError):
                return ()

        source_profiles = dict(source.get("part_profiles") or {})
        expected = dict(source_profiles.get(str(key), {}) or {})
        current_scalars = {
            "w": float(val.get("w", 0.0)),
            "h": float(val.get("h", 0.0)),
            "d": float(val.get("d", 0.0)),
            "t": float(val.get("t", 0.0)),
            "fw": float(val.get("fw", 0.0)),
            "zl1": float(val.get("zl1", ae.zl1_def)),
            "zr1": float(val.get("zr1", ae.zr1_def)),
            "yl1": float(val.get("yl1", ae.yl1_def)),
            "yr1": float(val.get("yr1", ae.yr1_def)),
            "ytop1": float(val.get("ytop1", ae.ytop1_def)),
            "ybottom1": float(val.get("ybottom1", ae.ybottom1_def)),
        }
        for name, current in current_scalars.items():
            if name not in source:
                continue
            # ytop1 is an optional legacy aggregate. Once a saved Y Fold
            # Profile exists, that profile is the authoritative topology/length
            # fingerprint; comparing the legacy scalar as well can reject a
            # valid committed 3D relief when the top fold was structurally
            # removed (the editor adapter correctly reports ytop1=0).
            if name == "ytop1" and "Y" in expected:
                continue
            try:
                if abs(float(source[name]) - current) > 1e-6:
                    return ()
            except (TypeError, ValueError):
                return ()
        for axis in ("X", "Y"):
            expected_rows = expected.get(axis)
            if expected_rows is None:
                continue
            current_rows = dict(stored_profiles or {}).get(axis, ())
            if self._phase6_relief_profile_signature(expected_rows) != self._phase6_relief_profile_signature(current_rows):
                return ()
        cuts = []
        for polygon in list(part.get("cuts") or ()):
            coords = tuple((float(point[0]), float(point[1])) for point in polygon if len(point) >= 2)
            if len(coords) >= 3:
                cuts.append(coords)
        return tuple(cuts)

    def _end_cap_part_spec(self, val, *, is_tail):
        key = "tail" if is_tail else "head"
        stored_profiles = self.workspace_controller.profile_for(key)
        local_val = dict(val)
        local_val["fw"] = self._effective_endcap_fw(key, val.get("fw", 25.0))
        stored_profiles = _endcap_profiles_for_assembly(
            local_val, stored_profiles, self._current_box_assembly_type(), key
        )
        resolved_cuts = self._resolved_committed_assembly_relief_cuts(key, local_val, stored_profiles)
        formed_fw_left, formed_fw_right = formed_box_body_fw_widths(
            self.workspace_controller.box_body_profile() or (), local_val.get("t", 0.0)
        )
        return self._end_cap_part_spec_from_values(
            local_val, model_name=self._baseline_source_model(), is_tail=is_tail,
            holes=(self.tail_holes if is_tail else self.head_holes),
            corner_policy=(
                self._manual_corner_policy(key, local_val['fw'])
            ),
            fold_profiles=stored_profiles,
            depth_comp_t=self._endcap_depth_comp_t_for_family(self._baseline_source_model()),
            resolved_assembly_relief_cuts=resolved_cuts,
            box_body_formed_fw_left=formed_fw_left,
            box_body_formed_fw_right=formed_fw_right,
            box_body_structure_state=self.workspace_controller.box_body_structure_state(),
        )

    def _door_part_spec_from_values(
        self, val, *, model_name, features, indicator_hole=None, door_indicator=None,
        door_indicator_offset=(0.0, 0.0), use_box_distance=False, corner_policy=None,
        frame_edges=None, indicator_window_groups=None,
    ):
        """Canonical Door state -> DoorPartSpec mapping used by 2D and 3D."""
        return DoorPartSpec(
            width=float(val['w']), height=float(val['h']),
            thickness=float(val['t']), frame_width=float(val['fw']),
            model_name=model_name,
            gap_w=float(val['door_gap_w']), gap_h=float(val['door_gap_h']),
            fold_left=float(val['door_fold_l']), fold_right=float(val['door_fold_r']),
            fold_top=float(val['door_fold_t']), fold_bottom=float(val['door_fold_b']),
            frame_edges=frame_edges or DoorFrameEdges(),
            features=tuple(features or ()), feature_space="legacy_unfolded",
            indicator_hole=indicator_hole,
            door_indicator=tuple(door_indicator) if door_indicator else None,
            door_indicator_offset=(float(door_indicator_offset[0]), float(door_indicator_offset[1])),
            use_box_distance=bool(use_box_distance),
            corner_policy=corner_policy,
            indicator_window_groups=(tuple(indicator_window_groups) if indicator_window_groups else None),
            nameplate_center_datum_top=(
                None if getattr(self, "door_nameplate_center_datum_top", None) is None
                else float(self.door_nameplate_center_datum_top)
            ),
        )

    def _single_door_part_spec(self, val, *, indicator_hole=None, door_indicator=None):
        return self._door_part_spec_from_values(
            val,
            model_name=self._baseline_source_model(),
            features=self.surface_features["door"],
            indicator_hole=indicator_hole,
            door_indicator=door_indicator,
            door_indicator_offset=(self.door_indicator_offset_x, self.door_indicator_offset_y),
            use_box_distance=bool(self.is_box_dist_var.get()),
            corner_policy=(
                self._manual_corner_policy(
                    'door', self._door_material_frame_width(val['fw'], val['t'])
                )
            ),
        )

    def _door_layout_part_spec(self, cell, val):
        key = self._door_layout_cell_key(cell)
        state = self._door_layout_indicator_state_for_key(key)
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        mode = state.get("mode", "indicator" if state.get("enabled") else "none")
        door_val = dict(val)
        door_val["w"] = cell.start_width
        door_val["h"] = cell.start_height
        return self._door_part_spec_from_values(
            door_val,
            model_name=self._baseline_source_model(),
            frame_edges=cell.edges,
            features=self.door_layout_features.get(key, []),
            indicator_hole=(manufacturing_api.indicator_box_opening_size(groups, thickness=val['t'])
                            if mode == "indicator_box" else None),
            door_indicator=(groups if mode == "indicator" else None),
            door_indicator_offset=(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
            use_box_distance=bool(state.get("is_box_dist", False)),
            corner_policy=(
                self._manual_corner_policy(
                    'door', self._door_material_frame_width(val['fw'], val['t'])
                )
            ),
        )

    def _validate_indicator_state_fit(self, state, *, finished_width, finished_height, thickness):
        state = self._normalize_door_indicator_state(state)
        mode = state.get("mode", "none")
        if mode == "none":
            return (0.0, 0.0)
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        return manufacturing_api.validate_door_indicator_fit(
            mode=mode, groups=groups,
            finished_width=float(finished_width), finished_height=float(finished_height),
            thickness=float(thickness),
            offset=(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
        )

    def _validate_single_door_indicator_fit(self, val, state=None):
        state = self._single_door_indicator_state_snapshot() if state is None else state
        spec = self._single_door_part_spec(val)
        finished_w, finished_h = manufacturing_api.door_finished_face_size(spec)
        return self._validate_indicator_state_fit(
            state, finished_width=finished_w, finished_height=finished_h, thickness=val['t']
        )

    def _validate_door_layout_indicator_fit(self, cell, state, val):
        spec = self._door_layout_part_spec(cell, val)
        finished_w, finished_h = manufacturing_api.door_finished_face_size(spec)
        return self._validate_indicator_state_fit(
            state, finished_width=finished_w, finished_height=finished_h, thickness=val['t']
        )

    def _base_plate_part_spec_from_values(self, val, *, features, corner_policy=None):
        return BasePlatePartSpec(
            width=float(val['w']), height=float(val['h']), thickness=float(val['t']),
            shrink_top=float(val['base_plate_shrink_top']),
            shrink_bottom=float(val['base_plate_shrink_bottom']),
            shrink_left=float(val['base_plate_shrink_left']),
            shrink_right=float(val['base_plate_shrink_right']),
            bend=float(val['base_plate_bend']),
            features=tuple(features or ()), corner_policy=corner_policy,
            box_body_structure_state=self.workspace_controller.box_body_structure_state(),
            box_body_fold_profile=profile_to_fold_segments(self.workspace_controller.box_body_profile() or ()),
            model_name=str(val.get('model', '')).strip() or None,
        )

    def _base_plate_part_spec(self, val):
        return self._base_plate_part_spec_from_values(
            val, features=self.surface_features["base_plate"],
            corner_policy=(
                self._manual_corner_policy('base_plate', val['fw'])
            ),
        )

    def _indicator_box_part_spec_from_values(self, val, layer_groups, *, features):
        return IndicatorBoxPartSpec(
            layer_groups=tuple(int(v) for v in layer_groups),
            thickness=float(val['t']), model_name=None,
            features=tuple(features or ()), corner_policy=None,
        )

    def _indicator_box_part_spec(self, val, layer_groups, *, features):
        return IndicatorBoxPartSpec(
            layer_groups=tuple(int(v) for v in layer_groups),
            thickness=float(val['t']), model_name=None,
            features=tuple(features or ()), corner_policy=None,
        )

    def _indicator_door_part_spec_from_values(self, val, layer_groups, *, features):
        groups = tuple(int(v) for v in layer_groups)
        policy = replace(
            manufacturing_api.resolve_policy(),
            frame_width=float(val['fw']),
            door_gap_w=float(val['door_gap_w']),
            door_gap_h=float(val['door_gap_h']),
            indicator_small_door_fold=float(
                val.get('indicator_door_fold', getattr(ae, 'indicator_small_door_fold_def', 19.0))
            ),
        )
        context = ManufacturingContext(policy=policy, draw_stock=False)
        base = manufacturing_api.indicator_small_door_spec(
            groups, thickness=float(val['t']), context=context
        )
        spec = replace(
            base, features=tuple(features or ()), feature_space="legacy_unfolded",
            corner_policy=None, model_name=None,
        )
        return spec, context

    def _indicator_door_part_spec(self, val, layer_groups, *, features):
        spec, _context = self._indicator_door_part_spec_from_values(
            val, layer_groups, features=features
        )
        return spec

    def _indicator_component_editor_contexts(self, state, val, *, box_features, door_features):
        """Build the two editable members of one Door-owned indicator-box assembly."""
        state = self._normalize_door_indicator_state(state)
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        if not groups:
            groups = (2,)

        # Box and small door are global shared parts, independent of the cabinet model.
        # GUI identifies the part role only; AE owns the physical shared-baseline namespace.
        box_corner_policy = None
        box_data = ae.get_stretched_indicator_box_data(
            None, groups, val['t'], corner_policy=None
        )
        box_baseline_scene = box_data.scene
        box_status = ae.indicator_shared_baseline_source_label("盒子.dxf")
        box_surface = feature_surface_from_drawing_scene("indicator_box", box_data.scene)
        box_w = float(box_data.params['w'])
        box_h = float(box_data.params['h'])
        box_fold = float(getattr(ae, 'indicator_box_fold_def', 49.0))
        box_result = (
            build_unknown_indicator_box_result(
                total_width=box_w, total_height=box_h, t=val['t'], fold=box_fold,
                corner_policy=box_corner_policy,
            ) if box_corner_policy is not None else
            build_indicator_box_result(total_width=box_w, total_height=box_h, t=val['t'], fold=box_fold)
        )
        box_guide = build_finished_reference_guide(
            "indicator_box", box_result,
            finished_width=box_w - 2.0 * box_fold + val['t'],
            finished_height=box_h - 2.0 * box_fold + val['t'],
        )

        door_spec = self._indicator_door_part_spec(val, groups, features=door_features)
        finished_w, finished_h = manufacturing_api.door_finished_face_size(door_spec)
        if door_spec.corner_policy is not None:
            door_result = build_unknown_door_result(
                w=door_spec.width, h=door_spec.height, t=door_spec.thickness, fw=door_spec.frame_width,
                gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
                fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
                fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
                corner_policy=door_spec.corner_policy,
            )
            door_surface = feature_surface_from_structural_result("indicator_door", door_result)
            door_width, door_height = door_result.width, door_result.height
            door_baseline_scene = None
            door_status = "自訂 / 手動截角"
        else:
            door_data = ae.get_stretched_door_data(
                None, door_spec.width, door_spec.height, door_spec.thickness, door_spec.frame_width,
                door_spec.gap_w, door_spec.gap_h,
                door_spec.fold_left, door_spec.fold_right, door_spec.fold_top, door_spec.fold_bottom,
                indicator_window_groups=groups,
            )
            door_surface = feature_surface_from_drawing_scene("indicator_door", door_data.scene)
            door_width = float(door_data.params['total_width'])
            door_height = float(door_data.params['total_depth'])
            door_result = build_door_result(
                w=door_spec.width, h=door_spec.height, t=door_spec.thickness, fw=door_spec.frame_width,
                gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
                fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
                fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
            )
            door_baseline_scene = door_data.scene
            door_status = ae.indicator_shared_baseline_source_label("小門.dxf")
        door_guide = build_finished_reference_guide(
            "indicator_door", door_result,
            finished_width=float(finished_w), finished_height=float(finished_h),
        )

        return {
            "indicator_box": {
                "part_key": "indicator_box", "title": "指示燈盒 — 盒體（基準檔＋指示燈）",
                "surface": box_surface, "width": box_w, "height": box_h,
                "reference_guide": box_guide, "feature_list": box_features,
                "baseline_scene": box_baseline_scene,
                "baseline_status_text": (
                    f"{box_status}｜排列 {list(groups)}｜{box_w:g} × {box_h:g} mm"
                ),
            },
            "indicator_door": {
                "part_key": "indicator_door", "title": "指示燈盒 — 小門（基準檔）",
                "surface": door_surface, "width": door_width, "height": door_height,
                "reference_guide": door_guide, "feature_list": door_features,
                "baseline_scene": door_baseline_scene, "baseline_status_text": door_status,
            },
        }

    def export_multi_door_layout_dxfs(self, folder, val, *, draw_stock=False):
        """Export one Door DXF per validated layout cell through the headless API."""
        import os

        exported = []
        context = self._manufacturing_context(draw_stock=draw_stock)
        for cell in self.get_door_layout_cells():
            filename = door_layout_export_filename(cell)
            filepath = os.path.join(folder, filename)
            self._export_authoritative_part(self._door_layout_part_spec(cell, val), filepath, context)
            exported.append(filename)
        return exported

    def export_multi_door_indicator_box_parts(self, folder, val, *, draw_stock=False, export_box=True, export_door=True):
        """Export each per-cell Indicator-Box assembly through the headless API."""
        import os

        exported = []
        context = self._manufacturing_context(draw_stock=draw_stock)
        for cell in self.get_door_layout_cells():
            key = self._door_layout_cell_key(cell)
            state = self._door_layout_indicator_state_for_key(key)
            if state.get("mode") != "indicator_box":
                continue
            self._validate_door_layout_indicator_fit(cell, state, val)
            layers = max(1, min(6, int(state.get("layers", 1))))
            groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
            stem = f"c{cell.column_index + 1}_r{cell.row_index + 1}"

            if export_box:
                filename = f"indicator_box_{stem}.dxf"
                spec = self._indicator_box_part_spec(
                    val, groups, features=self.door_layout_indicator_box_features.get(key, [])
                )
                self._export_authoritative_part(spec, os.path.join(folder, filename), context)
                exported.append(filename)

            if export_door:
                filename = f"indicator_door_{stem}.dxf"
                spec = self._indicator_door_part_spec(
                    val, groups, features=self.door_layout_indicator_door_features.get(key, [])
                )
                self._export_authoritative_part(spec, os.path.join(folder, filename), context)
                exported.append(filename)
        return exported

    def export_selected_dxf(self):
        """批次輸出勾選零件；GUI 只組 PartSpec，實際 DXF 一律交給 manufacturing_api。"""
        self._flush_phase6_authoritative_state()
        existing_parts = self._phase6_current_existing_parts()
        has_indicator_box = self._has_any_indicator_box()
        export_z = bool(self.export_z_var.get() and "box_body" in existing_parts)
        export_head = bool(self.export_head_var.get() and "head" in existing_parts)
        export_tail = bool(self.export_tail_var.get() and "tail" in existing_parts)
        export_door = bool(
            self.export_door_var.get()
            and self._phase6_logical_part_present(existing_parts, "door")
        )
        export_base_plate = bool(
            self.export_base_plate_var.get()
            and self._phase6_logical_part_present(existing_parts, "base_plate")
        )
        export_ib = bool(self.export_ib_var.get() and "indicator_box" in existing_parts and has_indicator_box)
        export_ib_door = bool(self.export_ib_door_var.get() and "indicator_door" in existing_parts and has_indicator_box)
        if not any([export_z, export_head, export_tail, export_door, export_base_plate, export_ib, export_ib_door]):
            messagebox.showwarning("未選擇零件", "請至少勾選一個要輸出的零件。")
            return

        try:
            val = self.get_float_values()
        except ValueError as ex:
            messagebox.showerror("輸入錯誤", str(ex))
            return

        try:
            indicator_related = bool(
                export_door or export_ib or export_ib_door
            )
            if indicator_related:
                if self.multi_door_enabled_var.get():
                    for cell in self.get_door_layout_cells():
                        key = self._door_layout_cell_key(cell)
                        state = self._door_layout_indicator_state_for_key(key)
                        if state.get("mode") != "none":
                            self._validate_door_layout_indicator_fit(cell, state, val)
                else:
                    self._validate_single_door_indicator_fit(val)
        except ValueError as ex:
            messagebox.showerror("指示燈配置無法套用", str(ex))
            return

        folder = filedialog.askdirectory(title="選擇 DXF 檔案儲存資料夾")
        if not folder:
            return

        import os
        draw_stock = self.draw_stock_var.get()
        context = self._manufacturing_context(draw_stock=draw_stock)
        exported = []
        errors = []

        def run_part(filename, spec):
            fp = os.path.join(folder, filename)
            result = self._export_authoritative_part(spec, fp, context)
            if isinstance(result, tuple):
                exported.extend(os.path.basename(item.output_path) for item in result)
            else:
                exported.append(filename)

        if export_z:
            try:
                run_part("box_body_z.dxf", self._box_body_part_spec(val))
            except Exception as ex:
                errors.append(f"box_body_z.dxf: {ex}")

        if export_head:
            try:
                run_part("end_cap_head.dxf", self._end_cap_part_spec(val, is_tail=False))
            except Exception as ex:
                errors.append(f"end_cap_head.dxf: {ex}")

        if export_tail:
            try:
                run_part("end_cap_tail.dxf", self._end_cap_part_spec(val, is_tail=True))
            except Exception as ex:
                errors.append(f"end_cap_tail.dxf: {ex}")

        indicator_hole = None
        if self.is_indicator_box_var.get():
            try:
                layers = int(self.indicator_l_var.get())
                groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
                indicator_hole = manufacturing_api.indicator_box_opening_size(groups, thickness=val['t'])
            except Exception:
                pass

        if export_door:
            try:
                if self.multi_door_enabled_var.get():
                    exported.extend(self.export_multi_door_layout_dxfs(folder, val, draw_stock=draw_stock))
                else:
                    door_indicator = None
                    if self.is_door_indicator_var.get():
                        try:
                            layers = int(self.door_indicator_l_var.get())
                            door_indicator = tuple(int(self.door_indicator_layer_g_vars[i].get()) for i in range(layers))
                        except Exception:
                            pass
                    run_part(
                        "door_unfold.dxf",
                        self._single_door_part_spec(
                            val, indicator_hole=indicator_hole, door_indicator=door_indicator,
                        ),
                    )
            except Exception as ex:
                target = "multi-door layout" if self.multi_door_enabled_var.get() else "door_unfold.dxf"
                errors.append(f"{target}: {ex}")

        if export_base_plate:
            try:
                run_part("base_plate.dxf", self._base_plate_part_spec(val))
            except Exception as ex:
                errors.append(f"base_plate.dxf: {ex}")

        if self.multi_door_enabled_var.get() and (export_ib or export_ib_door):
            try:
                exported.extend(self.export_multi_door_indicator_box_parts(
                    folder, val, draw_stock=draw_stock,
                    export_box=export_ib, export_door=export_ib_door,
                ))
            except Exception as ex:
                errors.append(f"multi-door indicator box parts: {ex}")

        if export_ib and not self.multi_door_enabled_var.get():
            try:
                layers = int(self.indicator_l_var.get())
                groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
                run_part(
                    "indicator_box.dxf",
                    self._indicator_box_part_spec(val, groups, features=self.surface_features["indicator_box"]),
                )
            except Exception as ex:
                errors.append(f"indicator_box.dxf: {ex}")

        if export_ib_door and not self.multi_door_enabled_var.get():
            try:
                layers = int(self.indicator_l_var.get())
                groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
                run_part(
                    "indicator_door.dxf",
                    self._indicator_door_part_spec(val, groups, features=self.surface_features["indicator_door"]),
                )
            except Exception as ex:
                errors.append(f"indicator_door.dxf: {ex}")

        if exported and not errors:
            messagebox.showinfo(
                "輸出成功",
                f"已成功輸出 {len(exported)} 個檔案至：\n{folder}\n\n" +
                "\n".join(f"  • {f}" for f in exported)
            )
        elif exported and errors:
            messagebox.showwarning(
                "部分成功",
                f"成功輸出：{', '.join(exported)}\n失敗：{', '.join(errors)}"
            )
        else:
            messagebox.showerror("輸出失敗", "\n".join(errors))


    def _single_door_indicator_state_snapshot(self):
        if self.is_indicator_box_var.get():
            mode = "indicator_box"
            layer_var = self.indicator_l_var
            group_vars = self.indicator_layer_g_vars
        else:
            mode = "indicator" if self.is_door_indicator_var.get() else "none"
            layer_var = self.door_indicator_l_var
            group_vars = self.door_indicator_layer_g_vars
        try:
            layers = max(1, min(6, int(layer_var.get())))
        except ValueError:
            layers = 1
        groups = []
        for i in range(6):
            try:
                groups.append(int(group_vars[i].get()))
            except ValueError:
                groups.append(2)
        return self._normalize_door_indicator_state({
            "mode": mode,
            "layers": layers,
            "groups": groups,
            "offset_x": float(self.door_indicator_offset_x),
            "offset_y": float(self.door_indicator_offset_y),
            "is_box_dist": bool(self.is_box_dist_var.get()),
        })

    def _apply_single_door_indicator_state(self, state):
        state = self._normalize_door_indicator_state(state)
        mode = state["mode"]
        self.is_door_indicator_var.set(mode == "indicator")
        self.is_indicator_box_var.set(mode == "indicator_box")
        layers = state["layers"]
        groups = state["groups"]
        # Keep both legacy parameter banks synchronized with the editor's one source of truth.
        self.door_indicator_l_var.set(str(layers))
        self.indicator_l_var.set(str(layers))
        for i in range(6):
            self.door_indicator_layer_g_vars[i].set(str(int(groups[i])))
            self.indicator_layer_g_vars[i].set(str(int(groups[i])))
        self.door_indicator_offset_x = float(state.get("offset_x", 0.0))
        self.door_indicator_offset_y = float(state.get("offset_y", 0.0))
        self.is_box_dist_var.set(bool(state.get("is_box_dist", False)))
        self._request_phase6_update("geometry")

    def _apply_multi_door_indicator_state(self, key, state):
        normalized = self._normalize_door_indicator_state(state)
        target = self.door_layout_indicator_states.get(key)
        if target is None:
            self.door_layout_indicator_states[key] = normalized
        else:
            target.clear()
            target.update(normalized)

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
