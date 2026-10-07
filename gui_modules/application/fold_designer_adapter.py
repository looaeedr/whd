"""Fold Designer application adapter boundary for #295/T7.

This module adapts existing application state to authoritative engine/manufacturing
APIs. It does not own project schema, workspace identity, committed settings, or
manufacturing geometry.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
import tkinter as tk

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.receiving_layout import (
    ensure_receiving_layout as ensure_receiving_preview_layout,
    resize_receiving_bays as resize_receiving_preview_bays,
)
from ae_engine.receiving_joint_locks import resolve_receiving_joint_lock_pattern
from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
from ae_engine.corner_type_ui import (
    is_unknown_model,
    normalize_custom_model_name,
    known_model_corner_state,
    policy_from_corner_state,
)
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    EDITABLE_CORNER_TYPE_IDS,
    CORNER_TYPE_LABELS,
    normalize_corner_selection,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    derive_door_layout_cells,
    door_layout_part_key,
    door_layout_export_filename,
    door_layout_feature_map_to_part_features,
)
from phase6_fold_profiles import formed_box_body_fw_widths
from ae_engine.assembly_joint import AssemblyJointSource, migrate_legacy_snapshot_joints
from phase6_endcap_semantics import (
    normalize_endcap_fw_state,
    ASSEMBLY_TYPE_LABELS,
    assembly_intent_value,
    normalize_endcap_bottom_wrap_state,
)
from phase6_settings_center import UI_TEXT_SIZE_LABELS, load_factory_defaults_from_ae
from phase6_settings_service import Phase6SettingsTransactionService
from phase6_sync_envelope import (
    materialize_sync_value,
    plan_live_sync_envelope,
)
from phase6_settings_contracts import SettingsStateSnapshot
from phase6_settings_transaction_controller import Phase6SettingsTransactionController
from phase6_project_controller import Phase6ProjectController
from phase6_workspace_navigation_controller import Phase6WorkspaceNavigationController
from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController
from phase6_registry_diagnostics_panel import (
    Phase6RegistryDiagnosticsPanel,
    registry_present_token,
    registry_formula_display,
    registry_formula_raw,
    registry_preconditions_display,
    registry_preconditions_raw,
    registry_source_display,
    registry_source_raw,
)
from phase6_settings_panel import Phase6SettingsPanel
from phase6_workspace_shell import (
    WorkspaceShellActions,
    WorkspaceShellOwner,
    WorkspaceShellState,
    toggle_fullscreen as workspace_shell_toggle_fullscreen,
)
from phase6_box_body_structure import BoxBodyStructureType
from whd_theme import WHD_THEME
from phase6_final_scene_contracts import (
    AssemblyScenePart,
    AssemblySceneRenderData,
    FinalSceneDependencies,
    FinalSceneViewRequest,
)
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_corner_data_view_adapter import Phase6CornerDataViewAdapter
from phase6_assembly_panel import Phase6AssemblyPanel
from phase6_manufacturing_adapter import operator_finished_dimensions_for_app
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from gui_modules.application.state_sync import Phase6DerivedCacheOwner
from phase6_derived_part_projection import (
    DerivedPartRequestAssemblyInput,
    build_derived_part_projection_request,
    build_derived_part_sync_plan,
)
from gui_modules.runtime_error_log import write_runtime_exception
from gui_modules.application.fold_designer_settings_coordinator import (
    Phase6FoldDesignerSettingsCoordinator,
    Phase6SettingsApplicationPorts,
)
from gui_modules.parts.panels.divider import collect_divider_input
from gui_modules.parts.panels.door import collect_door_input
from gui_modules.parts.panels.indicator_box import collect_indicator_box_input
from gui_modules.parts.panels.multipart import collect_multipart_input


from gui_modules.application.fold_designer_manufacturing_projection import (
    _fold_designer_secondary_scene_rows,
    _query_fold_designer_baseline_data,
    _apply_cabinet_family_endcap_policy,
    _fold_designer_corner_policy_from_payload,
    _authoritative_render_data,
    _require_verified_baseline_sources_for_manufacturing,
    _export_authoritative_part,
    _query_fold_designer_render_data,
    _payload_topology_context,
    _payload_policy,
    _fold_designer_part_spec_from_payload,
)
from gui_modules.application.fold_designer_snapshot_projection import (
    _snapshot_base_state,
    _snapshot_workspace_state,
    _snapshot_part_dimensions,
    _make_original_fold_designer_snapshot,
)




def install_fold_designer_bridge_facade(app_cls, bindings):
    """Install compatibility/composition aliases without owning their behavior."""
    for name, value in dict(bindings or {}).items():
        setattr(app_cls, str(name), value)
    return app_cls


@dataclass(frozen=True)
class FinalScenePortInventoryEntry:
    port_name: str
    source_owner: str
    access: str
    callback_direction: str
    bootstrap_need: bool
    mutation_capability: str


FINAL_SCENE_PORT_INVENTORY = (
    FinalScenePortInventoryEntry("number_text", "phase6_settings_panel", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("is_physical_piece_key", "fold_designer_bridge.compat", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("physical_piece_render_data", "fold_designer_bridge.compat", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("user_joint_parts", "ae_engine.assembly_joint", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("resolve_geometry", "phase6_manufacturing_adapter", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("scene_payload_for_part", "phase6_manufacturing_adapter", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("publish_live_state", "canonical live-sync application seam", "READ_WRITE", "FINAL_SCENE_TO_APP", True, "CANONICAL_APPLICATION_STATE"),
    FinalScenePortInventoryEntry("corner_dimension_text", "phase6_corner_dimension_display", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("formed_size_text", "fold_designer_bridge.compat", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("blank_text", "phase6_corner_data_view_adapter", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("refresh_box_body_piece_info", "phase6_assembly_panel", "WRITE", "FINAL_SCENE_TO_APP", True, "DISPLAY_EFFECT"),
    FinalScenePortInventoryEntry("operator_dimensions", "phase6_manufacturing_adapter", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("cabinet_family", "phase6_manufacturing_geometry", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("assembly_blank_text", "fold_designer_bridge.compat", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("active_mesh_profiles", "fold_designer_bridge.compat", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("assembly_render_data_cls", "phase6_final_scene_contracts", "TYPE", "BOOTSTRAP", True, "NONE"),
    FinalScenePortInventoryEntry("assembly_part_cls", "phase6_final_scene_contracts", "TYPE", "BOOTSTRAP", True, "NONE"),
    FinalScenePortInventoryEntry("final_render_provider", "Phase6FinalSceneViewAdapter compatibility seam", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("assembly_render_provider", "Phase6FinalSceneViewAdapter compatibility seam", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("request_provider", "Phase6FinalSceneViewAdapter compatibility seam", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("after_render", "Fold Designer presentation effects", "WRITE", "FINAL_SCENE_TO_APP", True, "DISPLAY_EFFECT"),
    FinalScenePortInventoryEntry("active_part", "Phase6DesignerWorkspace", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("scene_query", "Fold Designer scene query callback", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("input_snapshot", "Fold Designer canonical input snapshot", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("settings_values", "Phase6 settings application state", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("alpha_bend", "Fold Designer state", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("display_mode", "Fold Designer presentation state", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("assembly_corner_text_sink", "phase6_assembly_panel", "WRITE", "FINAL_SCENE_TO_APP", True, "DISPLAY_EFFECT"),
    FinalScenePortInventoryEntry("assembly_part_text_sink", "phase6_assembly_panel", "WRITE", "FINAL_SCENE_TO_APP", True, "DISPLAY_EFFECT"),
    FinalScenePortInventoryEntry("assembly_visibility", "phase6_assembly_panel", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("interference_probe_parts", "Fold Designer presentation state", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("show_interference", "Fold Designer presentation variable", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
    FinalScenePortInventoryEntry("render_committed", "Phase6FinalSceneRenderer display effect", "WRITE", "FINAL_SCENE_TO_APP", True, "DISPLAY_EFFECT"),
    FinalScenePortInventoryEntry("set_preview_enabled", "Phase6FinalSceneRenderer display effect", "WRITE", "FINAL_SCENE_TO_APP", True, "DISPLAY_EFFECT"),
    FinalScenePortInventoryEntry("refresh_preview", "Phase6FinalSceneRenderer display effect", "WRITE", "FINAL_SCENE_TO_APP", True, "DISPLAY_EFFECT"),
)


@dataclass(frozen=True)
class FinalSceneCompositionPorts:
    number_text: object
    is_physical_piece_key: object
    physical_piece_render_data: object
    user_joint_parts: object
    resolve_geometry: object
    scene_payload_for_part: object
    publish_live_state: object
    corner_dimension_text: object
    formed_size_text: object
    blank_text: object
    refresh_box_body_piece_info: object
    operator_dimensions: object
    cabinet_family: object
    assembly_blank_text: object
    active_mesh_profiles: object
    assembly_render_data_cls: type
    assembly_part_cls: type
    final_render_provider: object
    assembly_render_provider: object
    request_provider: object
    after_render: object
    active_part: object
    scene_query: object
    input_snapshot: object
    settings_values: object
    alpha_bend: object
    display_mode: object
    assembly_corner_text_sink: object
    assembly_part_text_sink: object
    assembly_visibility: object
    interference_probe_parts: object
    show_interference: object
    render_committed: object
    set_preview_enabled: object
    refresh_preview: object

    def dependencies(self):
        return FinalSceneDependencies(
            number_text=self.number_text,
            is_physical_piece_key=self.is_physical_piece_key,
            physical_piece_render_data=self.physical_piece_render_data,
            user_joint_parts=self.user_joint_parts,
            resolve_geometry=self.resolve_geometry,
            scene_payload_for_part=self.scene_payload_for_part,
            publish_live_state=self.publish_live_state,
            corner_dimension_text=self.corner_dimension_text,
            formed_size_text=self.formed_size_text,
            blank_text=self.blank_text,
            refresh_box_body_piece_info=self.refresh_box_body_piece_info,
            operator_dimensions=self.operator_dimensions,
            cabinet_family=self.cabinet_family,
            assembly_blank_text=self.assembly_blank_text,
            active_mesh_profiles=self.active_mesh_profiles,
            assembly_render_data_cls=self.assembly_render_data_cls,
            assembly_part_cls=self.assembly_part_cls,
            final_render_provider=self.final_render_provider,
            assembly_render_provider=self.assembly_render_provider,
            request_provider=self.request_provider,
            after_render=self.after_render,
            active_part=self.active_part,
            scene_query=self.scene_query,
            input_snapshot=self.input_snapshot,
            settings_values=self.settings_values,
            alpha_bend=self.alpha_bend,
            display_mode=self.display_mode,
            assembly_corner_text_sink=self.assembly_corner_text_sink,
            assembly_part_text_sink=self.assembly_part_text_sink,
            assembly_visibility=self.assembly_visibility,
            interference_probe_parts=self.interference_probe_parts,
            show_interference=self.show_interference,
            render_committed=self.render_committed,
            set_preview_enabled=self.set_preview_enabled,
            refresh_preview=self.refresh_preview,
        )


from gui_modules.application import fold_designer_composition_state as _composition_state
from gui_modules.application import fold_designer_composition_settings as _composition_settings
from gui_modules.application import fold_designer_composition_receiving as _composition_receiving
from gui_modules.application import fold_designer_composition_registry_edges as _composition_registry_edges
from gui_modules.application import fold_designer_composition_assembly_corner as _composition_assembly_corner
from gui_modules.application import fold_designer_composition_shell_settings as _composition_shell_settings

class Phase6FoldDesignerComposition:

    def __init__(self, app):
        self.app = app
        self._settings_service = None
        self._settings_transactions = None
        self._settings_coordinator = None
        self._workspace_navigation_controller = None
        self._registry_diagnostics_controller = None
        self._settings_panel = None
        self._registry_panel = None
        self._corner_data_view = None
        self._workspace_shell_owner = None
        self._final_scene_renderer = None
        self._final_scene_adapter = None

    def corner_transaction_payload(self, namespace):
        return _composition_state.corner_transaction_payload(self, namespace)

    def publish_live_state(self, namespace, *, force=False):
        return _composition_state.publish_live_state(self, namespace, force=force)

    def final_scene_set_preview_enabled(self, enabled):
        return _composition_state.final_scene_set_preview_enabled(self, enabled)

    def status_projection(self, namespace):
        return _composition_state.status_projection(self, namespace)

    def refresh_status_bar(self, namespace):
        return _composition_state.refresh_status_bar(self, namespace)

    def reset_initial_values(self, namespace):
        return _composition_state.reset_initial_values(self, namespace)

    def save_settings_context_as_defaults(self, namespace, context):
        return _composition_state.save_settings_context_as_defaults(self, namespace, context)

    def commit_output_draw_stock(self, namespace):
        return _composition_state.commit_output_draw_stock(self, namespace)

    def export_selected_dxf_from_3d(self):
        return _composition_state.export_selected_dxf_from_3d(self)

    def collect_workspace_state(self, namespace):
        return _composition_state.collect_workspace_state(self, namespace)

    def current_relief_source_signature(self, namespace, required_parts):
        return _composition_state.current_relief_source_signature(self, namespace, required_parts)

    def serialize_assembly_relief_state(self, namespace):
        return _composition_state.serialize_assembly_relief_state(self, namespace)

    def build_project_snapshot(self, namespace):
        return _composition_state.build_project_snapshot(self, namespace)

    def load_project_file(self, namespace):
        return _composition_state.load_project_file(self, namespace)

    def save_project_file(self, namespace, *, save_as=False):
        return _composition_state.save_project_file(self, namespace, save_as=save_as)

    def toggle_parameter_panel(self, namespace):
        return _composition_state.toggle_parameter_panel(self, namespace)

    @staticmethod
    def _required(namespace, name):
        return _composition_state._required(namespace, name)

    def flush_pending_settings(self, namespace):
        return _composition_state.flush_pending_settings(self, namespace)

    def stage_setting_update(self, namespace, key, value):
        return _composition_state.stage_setting_update(self, namespace, key, value)

    def settings_context_extension_projection(self, namespace, context):
        return _composition_settings.settings_context_extension_projection(self, namespace, context)

    def sync_settings_panel_extension(self, namespace, state, context):
        return _composition_settings.sync_settings_panel_extension(self, namespace, state, context)

    def sync_settings_panel_compat(self):
        return _composition_settings.sync_settings_panel_compat(self)

    def settings_panel_toggle_baseline(self):
        return _composition_settings.settings_panel_toggle_baseline(self)

    def invalidate_settings_page(self, context):
        return _composition_settings.invalidate_settings_page(self, context)

    def render_settings_context(self, namespace, context):
        return _composition_settings.render_settings_context(self, namespace, context)

    def save_current_settings_as_defaults(self):
        return _composition_settings.save_current_settings_as_defaults(self)

    def on_baseline_model_changed(self, namespace, *_args):
        return _composition_settings.on_baseline_model_changed(self, namespace, *_args)

    def apply_external_settings(self, namespace, updates):
        return _composition_settings.apply_external_settings(self, namespace, updates)

    def apply_external_model(self, namespace, model):
        return _composition_settings.apply_external_model(self, namespace, model)

    def apply_external_sync(self, namespace, envelope):
        return _composition_settings.apply_external_sync(self, namespace, envelope)

    def update_left_workspace_width(self, namespace, key=None):
        return _composition_settings.update_left_workspace_width(self, namespace, key)

    def apply_ui_text_size(self, namespace, key):
        return _composition_settings.apply_ui_text_size(self, namespace, key)

    def on_ui_text_size_changed(self, namespace, *_args):
        return _composition_settings.on_ui_text_size_changed(self, namespace, *_args)

    def receiving_layout_applicable(self):
        return _composition_receiving.receiving_layout_applicable(self)

    def confirm_receiving_destructive(self, stable_ids):
        return _composition_receiving.confirm_receiving_destructive(self, stable_ids)

    def receiving_adapter(self, namespace, *, reset=False):
        return _composition_receiving.receiving_adapter(self, namespace, reset=reset)

    def sync_receiving_current_bay(self, namespace, *, validate_common=True, refresh_controls=True):
        return _composition_receiving.sync_receiving_current_bay(self, namespace, validate_common=validate_common, refresh_controls=refresh_controls)

    def commit_receiving_current_bay_controls(self, namespace):
        return _composition_receiving.commit_receiving_current_bay_controls(self, namespace)

    def back_panel_mode_control_is_applicable(self, namespace):
        return _composition_receiving.back_panel_mode_control_is_applicable(self, namespace)

    def refresh_back_panel_mode_control(self, namespace):
        return _composition_receiving.refresh_back_panel_mode_control(self, namespace)

    def select_back_panel_mode(self, namespace, var):
        return _composition_receiving.select_back_panel_mode(self, namespace, var)

    def receiving_switch_adapter(self, namespace, *, reset=False):
        return _composition_receiving.receiving_switch_adapter(self, namespace, reset=reset)

    def mark_receiving_switch_layout_dirty(self, namespace, adapter):
        return _composition_receiving.mark_receiving_switch_layout_dirty(self, namespace, adapter)

    def refresh_receiving_set_bay_control(self, namespace):
        return _composition_receiving.refresh_receiving_set_bay_control(self, namespace)

    def on_receiving_switch_brand_selected(self, namespace, brand):
        return _composition_receiving.on_receiving_switch_brand_selected(self, namespace, brand)

    def add_receiving_layer(self, namespace):
        return _composition_receiving.add_receiving_layer(self, namespace)

    def remove_receiving_layer(self, namespace):
        return _composition_receiving.remove_receiving_layer(self, namespace)

    def resize_receiving_bays(self, namespace, layer_index, delta):
        return _composition_receiving.resize_receiving_bays(self, namespace, layer_index, delta)

    def confirm_receiving_opening(self, namespace, layer_index, connection_index, brand):
        return _composition_receiving.confirm_receiving_opening(self, namespace, layer_index, connection_index, brand)

    def receiving_bay_preview_request(self, namespace, set_index, bay_index):
        return _composition_receiving.receiving_bay_preview_request(self, namespace, set_index, bay_index)

    def receiving_layer_preview_payload(self, namespace, layer_index):
        return _composition_receiving.receiving_layer_preview_payload(self, namespace, layer_index)

    def receiving_settings_ports(self, namespace, set_index):
        return _composition_receiving.receiving_settings_ports(self, namespace, set_index)

    def open_receiving_layer_preview(self, namespace, layer_index):
        return _composition_receiving.open_receiving_layer_preview(self, namespace, layer_index)

    def settings_panel(self, namespace):
        return _composition_receiving.settings_panel(self, namespace)

    def registry_collect_rule_form(self):
        return _composition_registry_edges.registry_collect_rule_form(self)

    def registry_sample_variables(self):
        return _composition_registry_edges.registry_sample_variables(self)

    def registry_validate_formula_form(self):
        return _composition_registry_edges.registry_validate_formula_form(self)

    def registry_preview_payload(self):
        return _composition_registry_edges.registry_preview_payload(self)

    def registry_save_candidate_form(self, namespace):
        return _composition_registry_edges.registry_save_candidate_form(self, namespace)

    def registry_run_formula_matrix(self, namespace):
        return _composition_registry_edges.registry_run_formula_matrix(self, namespace)

    def registry_preview_assembly_3d(self, namespace):
        return _composition_registry_edges.registry_preview_assembly_3d(self, namespace)

    def registry_promote_form(self):
        return _composition_registry_edges.registry_promote_form(self)

    def corner_pair_var_changed(self, namespace, part_key, pair_key, var):
        return _composition_registry_edges.corner_pair_var_changed(self, namespace, part_key, pair_key, var)

    def corner_type_selected(self, namespace, part_key, target_key):
        return _composition_registry_edges.corner_type_selected(self, namespace, part_key, target_key)

    def corner_mode_selected(self, namespace, part_key, target_key):
        return _composition_registry_edges.corner_mode_selected(self, namespace, part_key, target_key)

    def corner_target_var_changed(self, namespace, part_key, target_key):
        return _composition_registry_edges.corner_target_var_changed(self, namespace, part_key, target_key)

    def refresh_active_endcap_from_linked(self, namespace, linked):
        return _composition_registry_edges.refresh_active_endcap_from_linked(self, namespace, linked)

    def commit_endcap_fw_state(self, namespace):
        return _composition_registry_edges.commit_endcap_fw_state(self, namespace)

    def set_endcap_fw_override(self, namespace, part_key, value):
        return _composition_registry_edges.set_endcap_fw_override(self, namespace, part_key, value)

    def on_endcap_fw_value_selected(self, namespace, part_key, value_var):
        return _composition_registry_edges.on_endcap_fw_value_selected(self, namespace, part_key, value_var)

    def on_box_symmetry_changed(self, namespace):
        return _composition_registry_edges.on_box_symmetry_changed(self, namespace)

    def on_endcap_edge_relation_selected(self, namespace, part_key, edge):
        return _composition_registry_edges.on_endcap_edge_relation_selected(self, namespace, part_key, edge)

    def ensure_drawing_edge_hosts(self, namespace):
        return _composition_registry_edges.ensure_drawing_edge_hosts(self, namespace)

    def clear_drawing_edge_controls(self):
        return _composition_registry_edges.clear_drawing_edge_controls(self)

    def render_endcap_edge_controls(self, namespace, *, part_key):
        return _composition_registry_edges.render_endcap_edge_controls(self, namespace, part_key=part_key)

    def commit_base_plate_edge_shrink(self, namespace, edge, raw_value):
        return _composition_registry_edges.commit_base_plate_edge_shrink(self, namespace, edge, raw_value)

    def render_base_plate_edge_controls(self, namespace):
        return _composition_registry_edges.render_base_plate_edge_controls(self, namespace)

    def render_active_drawing_edge_controls(self, namespace):
        return _composition_registry_edges.render_active_drawing_edge_controls(self, namespace)

    def on_assembly_type_selected(self, namespace, *_args):
        return _composition_assembly_corner.on_assembly_type_selected(self, namespace, *_args)

    def on_assembly_diagnostic_changed(self):
        return _composition_assembly_corner.on_assembly_diagnostic_changed(self)

    def create_relief_promotion_candidates(self, namespace):
        return _composition_assembly_corner.create_relief_promotion_candidates(self, namespace)

    def update_assembly_diagnostic_status(self, namespace):
        return _composition_assembly_corner.update_assembly_diagnostic_status(self, namespace)

    def on_assembly_part_visibility_changed(self):
        return _composition_assembly_corner.on_assembly_part_visibility_changed(self)

    def install_assembly_panel_aliases(self, owner):
        return _composition_assembly_corner.install_assembly_panel_aliases(self, owner)

    def current_assembly_panel_part_keys(self):
        return _composition_assembly_corner.current_assembly_panel_part_keys(self)

    def refresh_assembly_parts_panel_if_topology_changed(self, namespace):
        return _composition_assembly_corner.refresh_assembly_parts_panel_if_topology_changed(self, namespace)

    def refresh_assembly_parts_panel(self, namespace):
        return _composition_assembly_corner.refresh_assembly_parts_panel(self, namespace)

    def registry_panel(self, namespace):
        return _composition_assembly_corner.registry_panel(self, namespace)

    def corner_data_view(self):
        return _composition_assembly_corner.corner_data_view(self)

    def corner_data_part_keys(self):
        return _composition_assembly_corner.corner_data_part_keys(self)

    def corner_data_navigation_rows(self, namespace):
        return _composition_assembly_corner.corner_data_navigation_rows(self, namespace)

    def select_corner_data_part(self, namespace, key, *, refresh_view=True):
        return _composition_assembly_corner.select_corner_data_part(self, namespace, key, refresh_view=refresh_view)

    def corner_data_info_request_for_key(self, namespace, part_key, render_data):
        return _composition_assembly_corner.corner_data_info_request_for_key(self, namespace, part_key, render_data)

    def corner_data_info_text_for_key(self, namespace, part_key, render_data):
        return _composition_assembly_corner.corner_data_info_text_for_key(self, namespace, part_key, render_data)

    def corner_data_unfold_projection_for_key(self, namespace, part_key):
        return _composition_assembly_corner.corner_data_unfold_projection_for_key(self, namespace, part_key)

    def corner_data_unfold_projections(self, namespace, part_keys):
        return _composition_assembly_corner.corner_data_unfold_projections(self, namespace, part_keys)

    def corner_data_unfold_projection(self, namespace):
        return _composition_assembly_corner.corner_data_unfold_projection(self, namespace)

    def refresh_corner_data_unfold_view(self, namespace):
        return _composition_assembly_corner.refresh_corner_data_unfold_view(self, namespace)

    def corner_data_back_panel_mode_is_applicable(self, namespace):
        return _composition_assembly_corner.corner_data_back_panel_mode_is_applicable(self, namespace)

    def refresh_corner_data_back_panel_mode_control(self, namespace):
        return _composition_assembly_corner.refresh_corner_data_back_panel_mode_control(self, namespace)

    def refresh_corner_data_parts_panel(self, namespace):
        return _composition_assembly_corner.refresh_corner_data_parts_panel(self, namespace)

    def on_corner_data_mousewheel(self, namespace, event):
        return _composition_assembly_corner.on_corner_data_mousewheel(self, namespace, event)

    def prepare_corner_data_canvas(self, namespace):
        return _composition_assembly_corner.prepare_corner_data_canvas(self, namespace)

    def toggle_fullscreen(self):
        return _composition_shell_settings.toggle_fullscreen(self)

    def build_settings_center(self, namespace):
        return _composition_shell_settings.build_settings_center(self, namespace)

    def install_renderer_view(self, namespace):
        return _composition_shell_settings.install_renderer_view(self, namespace)

    def workspace_shell_owner(self, namespace):
        return _composition_shell_settings.workspace_shell_owner(self, namespace)

    def sync_authoritative_derived_parts(self, namespace, *, projected_snapshot=None, projected_workspace=None, projected_box_render_data=None):
        return _composition_shell_settings.sync_authoritative_derived_parts(self, namespace, projected_snapshot=projected_snapshot, projected_workspace=projected_workspace, projected_box_render_data=projected_box_render_data)

    def workspace_navigation(self):
        return _composition_shell_settings.workspace_navigation(self)

    def registry_diagnostics(self):
        return _composition_shell_settings.registry_diagnostics(self)

    def settings_service(self):
        return _composition_shell_settings.settings_service(self)

    def settings_transactions(self):
        return _composition_shell_settings.settings_transactions(self)

    def apply_settings_profile_projection(self, namespace, plan, *, render=True):
        return _composition_shell_settings.apply_settings_profile_projection(self, namespace, plan, render=render)

    def refresh_profiles_from_settings(self, namespace, *, reset_box_profile=False, reset_all_profiles=False, render=True):
        return _composition_shell_settings.refresh_profiles_from_settings(self, namespace, reset_box_profile=reset_box_profile, reset_all_profiles=reset_all_profiles, render=render)

    def settings_application_apply_profile_plan(self, namespace, committed, *, reset_box_profile=False, reset_all_profiles=False, render=True, editor_commit=False, editor_changed_keys=()):
        return _composition_shell_settings.settings_application_apply_profile_plan(self, namespace, committed, reset_box_profile=reset_box_profile, reset_all_profiles=reset_all_profiles, render=render, editor_commit=editor_commit, editor_changed_keys=editor_changed_keys)

    def settings_application_project_ui_values(self, namespace, values, *, rejected_key=None, error=None, baseline_transition=None, baseline_stage=None, new_model='', old_model='', new_editable=False, old_editable=False, factory_reset=False, editor_commit=False, editor_snapshot=None):
        return _composition_shell_settings.settings_application_project_ui_values(self, namespace, values, rejected_key=rejected_key, error=error, baseline_transition=baseline_transition, baseline_stage=baseline_stage, new_model=new_model, old_model=old_model, new_editable=new_editable, old_editable=old_editable, factory_reset=factory_reset, editor_commit=editor_commit, editor_snapshot=editor_snapshot)

    def settings_application_submit_update_intent(self, namespace, committed):
        return _composition_shell_settings.settings_application_submit_update_intent(self, namespace, committed)

    def settings_application_publish_live_state(self, committed, *, partial=False):
        return _composition_shell_settings.settings_application_publish_live_state(self, committed, partial=partial)

    def settings_application_ports(self, namespace):
        return _composition_shell_settings.settings_application_ports(self, namespace)

    def settings_coordinator(self, ports: Phase6SettingsApplicationPorts):
        return _composition_shell_settings.settings_coordinator(self, ports)

    def final_scene_renderer(self, *, number_text):
        if self._final_scene_renderer is None:
            app = self.app
            current = getattr(app, "final_scene_view", None)
            if isinstance(current, Phase6FinalSceneRenderer):
                self._final_scene_renderer = current
            else:
                raw_renderer = getattr(app, "renderer", None)
                if raw_renderer is None:
                    return None
                def report_render_error(exc):
                    snapshot = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
                    return write_runtime_exception(
                        "3d_final_scene_render",
                        exc,
                        metadata={
                            "display_mode": str(
                                getattr(app, "_phase6_3d_display_mode", "single") or "single"
                            ),
                            "active_part": str(
                                getattr(
                                    getattr(app, "designer_workspace", None),
                                    "active_part",
                                    "",
                                )
                                or ""
                            ),
                            "model": str(snapshot.get("model") or ""),
                        },
                    )

                self._final_scene_renderer = Phase6FinalSceneRenderer(
                    raw_renderer,
                    number_text=number_text,
                    error_reporter=report_render_error,
                )
                app.final_scene_view = self._final_scene_renderer
        return self._final_scene_renderer

    def final_scene_ports(self, namespace):
        """Compose the fixed 35-port FinalScene application boundary.

        The bridge namespace remains only for compatibility callbacks that still
        belong to the bridge boundary. FinalScene owner classes and callbacks
        removed from the bridge are wired directly here so composition cannot
        accidentally depend on deleted bridge re-exports.
        """
        app = self.app

        def required(name):
            try:
                return namespace[name]
            except KeyError as exc:
                raise RuntimeError(
                    f"Fold Designer FinalScene composition port is unavailable: {name}"
                ) from exc

        number_text = required("_setting_number_text")
        part_label = required("_phase6_part_label")
        corner_text = required("_phase6_render_data_corner_dimension_text")

        def blank_text(render_data, *, part_key=""):
            return Phase6CornerDataViewAdapter.unfolded_blank_text(
                render_data,
                part_key=part_key,
                measurer=manufacturing_api.measure_unfolded_blanks,
                number_text=number_text,
            )

        def formed_size_text(render_data, **kwargs):
            dimensions = tuple(kwargs.get("finished_dimensions") or ())
            if not dimensions:
                dimensions = tuple(
                    getattr(render_data, "formed_outer_dimensions", ()) or ()
                )
            return Phase6CornerDataViewAdapter.formed_size_text(
                dimensions,
                number_text=number_text,
            )

        def refresh_box_body_piece_info(render_data):
            owner = getattr(app, "_phase6_assembly_panel_owner", None)
            if owner is None:
                return ()
            snapshot = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
            return owner.refresh_box_body_piece_info(
                render_data,
                label_for=lambda key: part_label(key, snapshot=snapshot),
                number_text=number_text,
                corner_text_for_render_data=corner_text,
            )

        def assembly_blank_text(render_data):
            snapshot = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
            rows = []
            for part in tuple(getattr(render_data, "assembly_parts", ()) or ()):
                text = blank_text(part.render_data, part_key=part.part_key)
                if text.startswith("展開料："):
                    text = text[len("展開料："):]
                rows.append(
                    f"{part_label(part.part_key, snapshot=snapshot)}：{text}"
                )
            return "展開尺寸：\n" + "\n".join(rows) if rows else "展開尺寸：-"

        def update_unfolded_size_label():
            var = getattr(app, "unfolded_size_var", None)
            if var is None:
                return None
            key = str(
                getattr(
                    getattr(app, "designer_workspace", None),
                    "active_part",
                    "",
                )
                or ""
            )
            try:
                if getattr(app, "_phase6_initializing", False):
                    resolved = getattr(
                        app,
                        "_phase6_last_resolved_manufacturing_geometry",
                        None,
                    )
                    render_data = (
                        resolved.part(key).render_data
                        if resolved is not None and key
                        else None
                    )
                else:
                    render_data = required("_phase6_render_data_for_blank")(
                        app, key
                    ) if key else None
            except Exception:
                render_data = None
            return var.set(blank_text(render_data, part_key=key))

        def scene_query(key, payload):
            callback = getattr(app, "_scene_query_callback", None)
            if callback is None:
                raise RuntimeError("3D final-scene provider is not connected")
            return callback(key, payload)

        def corner_text_sink(values):
            values = {
                str(key): str(value)
                for key, value in dict(values or {}).items()
            }
            app._phase6_last_assembly_corner_dimension_texts = dict(values)
            owner = getattr(app, "_phase6_assembly_panel_owner", None)
            if owner is not None:
                owner.set_corner_texts(values)

        def part_text_sink(kind, part_key, value):
            owner = getattr(app, "_phase6_assembly_panel_owner", None)
            if owner is not None:
                owner.set_part_text(kind, part_key, value)

        def assembly_visibility(parts):
            owner = getattr(app, "_phase6_assembly_panel_owner", None)
            if owner is not None:
                return owner.resolve_visibility(parts)
            return Phase6AssemblyPanel._resolve_visibility_with_vars(
                parts, {}, {}
            )

        def render_committed():
            if not getattr(app, "preview_3d_enabled", True):
                return None
            canvas = app.renderer.canvas
            draw = getattr(canvas, "draw", None)
            draw_idle = getattr(canvas, "draw_idle", None)
            if (
                callable(draw)
                and callable(draw_idle)
                and not getattr(app, "_phase6_force_sync_preview", False)
            ):
                canvas.draw = draw_idle
                try:
                    return app.renderer.render()
                finally:
                    canvas.draw = draw
            return app.renderer.render()

        def refresh_preview():
            if not getattr(app, "preview_3d_enabled", True):
                return self.final_scene_set_preview_enabled(True)
            app._phase6_force_sync_preview = True
            try:
                return app.submit_update_intent("display", commit=True)
            finally:
                app._phase6_force_sync_preview = False

        return FinalSceneCompositionPorts(
            number_text=number_text,
            is_physical_piece_key=required("_phase6_is_box_body_physical_piece_key"),
            physical_piece_render_data=lambda key: required(
                "_phase6_box_body_piece_render_data"
            )(app, key),
            user_joint_parts=lambda: {
                str(raw.get(field) or "")
                for raw in tuple(
                    migrate_legacy_snapshot_joints(
                        dict(getattr(app, "_phase6_input_snapshot", {}) or {})
                    ).get("assembly_joints", ()) or ()
                )
                if str(raw.get("source") or "")
                == AssemblyJointSource.USER_ADDED.value
                for field in ("subject_part", "target_part")
            },
            resolve_geometry=lambda: required(
                "_phase6_resolve_manufacturing_geometry"
            )(app),
            scene_payload_for_part=lambda key: required(
                "_phase6_scene_query_payload_for_part"
            )(app, key),
            publish_live_state=lambda **kwargs: self.publish_live_state(
                namespace, **kwargs
            ),
            corner_dimension_text=corner_text,
            formed_size_text=formed_size_text,
            blank_text=blank_text,
            refresh_box_body_piece_info=refresh_box_body_piece_info,
            operator_dimensions=lambda part_key=None: operator_finished_dimensions_for_app(
                app, part_key
            ),
            cabinet_family=lambda: required("_phase6_current_cabinet_family")(app),
            assembly_blank_text=assembly_blank_text,
            active_mesh_profiles=lambda material: required(
                "_phase6_mesh_profiles_for_part"
            )(app, app.designer_workspace.active_part, material),
            assembly_render_data_cls=AssemblySceneRenderData,
            assembly_part_cls=AssemblyScenePart,
            final_render_provider=lambda: required(
                "_phase6_query_final_render_data"
            )(app),
            assembly_render_provider=lambda: (
                self._final_scene_adapter.query_assembly_render_data()
                if self._final_scene_adapter is not None
                else (_ for _ in ()).throw(
                    RuntimeError("FinalScene adapter is not initialized")
                )
            ),
            request_provider=lambda: required("_phase6_final_scene_view_request")(app),
            after_render=lambda: (
                update_unfolded_size_label(),
                required("_phase6_update_assembly_diagnostic_status")(app),
            ),
            active_part=lambda: str(
                getattr(
                    getattr(app, "designer_workspace", None),
                    "active_part",
                    "",
                )
                or ""
            ),
            scene_query=scene_query,
            input_snapshot=lambda: dict(
                getattr(app, "_phase6_input_snapshot", {}) or {}
            ),
            settings_values=lambda: dict(
                getattr(app, "_settings_values", {}) or {}
            ),
            alpha_bend=lambda: float(
                getattr(getattr(app, "state", None), "alpha_bend", 0.85)
            ),
            display_mode=lambda: str(
                getattr(app, "_phase6_3d_display_mode", "single") or "single"
            ),
            assembly_corner_text_sink=corner_text_sink,
            assembly_part_text_sink=part_text_sink,
            assembly_visibility=assembly_visibility,
            interference_probe_parts=lambda: tuple(
                getattr(app, "_phase6_last_interference_probe_parts", ()) or ()
            ),
            show_interference=lambda: bool(
                getattr(
                    getattr(app, "assembly_show_interference_var", None),
                    "get",
                    lambda: True,
                )()
            ),
            render_committed=render_committed,
            set_preview_enabled=self.final_scene_set_preview_enabled,
            refresh_preview=refresh_preview,
        )

    def final_scene_adapter(self, ports: FinalSceneCompositionPorts):
        if self._final_scene_adapter is None:
            self._final_scene_adapter = Phase6FinalSceneViewAdapter(
                dependencies=ports.dependencies(),
                renderer=self.final_scene_renderer(
                    number_text=ports.number_text
                ),
            )
        return self._final_scene_adapter

    @property
    def assembly_type(self):
        transactions = self._settings_transactions
        if transactions is not None:
            return transactions.assembly_type
        snapshot = dict(
            getattr(self.app, "_phase6_input_snapshot", {}) or {}
        )
        return snapshot.get("assembly_type", CornerTypeId.INSERT_OVERLAY)

    @property
    def last_external_revision(self):
        service = self._settings_service
        return service.last_external_revision if service is not None else 0

    @property
    def last_external_transaction_id(self):
        service = self._settings_service
        return service.last_external_transaction_id if service is not None else ""

    @property
    def active_transaction_id(self):
        service = self._settings_service
        return service.active_transaction_id if service is not None else ""
