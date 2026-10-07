"""Phase6 Fold Designer composition assembly corner implementation.

Extracted mechanically from fold_designer_adapter; public composition methods remain thin routes.
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

def on_assembly_type_selected(self, namespace, *_args):
    """Commit Assembly intent through the existing Settings transaction owner."""
    app = self.app
    if getattr(app, "_phase6_settings_rendering", False):
        return None
    required = lambda name: self._required(namespace, name)
    var = getattr(app, "assembly_type_var", None)
    type_id = (
        required("ASSEMBLY_LABEL_TO_TYPE").get(
            str(var.get()).strip()
        )
        if var is not None
        else None
    )
    if type_id is None:
        return None

    self.settings_transactions().commit_assembly_intent(
        type_id,
        available_parts=tuple(
            getattr(app.designer_workspace, "available_parts", ())
            or ()
        ),
        project_legacy_corner=False,
        mark_dirty=True,
    )

    # Do not rebuild the live box-body page while Tk is dispatching the
    # Combobox event; only dependent EndCap pages are invalidated here.
    for context in ("head", "tail"):
        self.invalidate_settings_page(context)
    required("_phase6_rebuild_linked_endcaps")(app)
    self.render_active_drawing_edge_controls(namespace)
    try:
        app.do_update()
    except Exception:
        pass
    return type_id

def on_assembly_diagnostic_changed(self):
    app = self.app
    if (
        str(getattr(app, "_phase6_3d_display_mode", "single") or "single")
        == "assembly"
    ):
        submit = getattr(app, "submit_update_intent", None)
        if callable(submit):
            submit("display", commit=True)
    return True

def create_relief_promotion_candidates(self, namespace):
    """Build non-mutating promotion manifests through the existing controller."""
    from ae_engine.certified_relief_registry import (
        build_relief_promotion_candidate,
    )

    app = self.app
    required = lambda name: self._required(namespace, name)
    controller = self.registry_diagnostics()
    candidates = controller.build_promotion_candidates(
        solutions=dict(
            getattr(app, "_phase6_last_relief_solutions", {}) or {}
        ),
        snapshot=dict(
            getattr(app, "_phase6_input_snapshot", {}) or {}
        ),
        assembly_intent=getattr(
            app,
            "_phase6_assembly_type",
            CornerTypeId.INSERT_OVERLAY,
        ),
        cabinet_family=required(
            "_phase6_current_cabinet_family"
        )(app),
        builder=build_relief_promotion_candidate,
    )
    required(
        "_phase6_sync_registry_diagnostics_compatibility_mirrors"
    )(app, controller)
    status_var = getattr(app, "assembly_collision_status_var", None)
    if status_var is not None and callable(
        getattr(status_var, "set", None)
    ):
        if candidates:
            status_var.set(
                "認證候選："
                + " / ".join(
                    "封頭" if key == "head" else "封尾"
                    for key in candidates
                )
                + "（僅建立候選，不修改正式資料庫）"
            )
        else:
            status_var.set(
                "認證候選：目前沒有已驗證的立體暫定結果"
            )
    return candidates

def update_assembly_diagnostic_status(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    status_var = getattr(app, "assembly_collision_status_var", None)
    size_var = getattr(app, "assembly_relief_size_var", None)
    if status_var is None:
        return None

    enabled_var = getattr(
        app, "assembly_ignore_fixed_corner_var", None
    )
    fallback_enabled = (
        bool(enabled_var.get())
        if enabled_var is not None
        else True
    )
    size_text, status_text = self.registry_diagnostics().diagnostic_status(
        fallback_enabled=fallback_enabled,
        solutions=dict(
            getattr(app, "_phase6_last_relief_solutions", {}) or {}
        ),
        errors=dict(
            getattr(app, "_phase6_last_relief_errors", {}) or {}
        ),
        measurement_text=required(
            "_phase6_relief_measurement_text"
        ),
    )
    if size_var is not None:
        size_var.set(size_text)
    status_var.set(status_text)
    return status_text

def on_assembly_part_visibility_changed(self):
    app = self.app
    if (
        str(getattr(app, "_phase6_3d_display_mode", "single") or "single")
        == "assembly"
    ):
        submit = getattr(app, "submit_update_intent", None)
        if callable(submit):
            submit("display", commit=True)

def install_assembly_panel_aliases(self, owner):
    return owner.install_legacy_aliases(self.app)

def current_assembly_panel_part_keys(self):
    owner = getattr(self.app, "_phase6_assembly_panel_owner", None)
    return owner.represented_part_keys() if owner is not None else ()

def refresh_assembly_parts_panel_if_topology_changed(
    self,
    namespace,
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    owner = getattr(app, "_phase6_assembly_panel_owner", None)
    if owner is None:
        return False
    snapshot = dict(
        getattr(app, "_phase6_input_snapshot", {}) or {}
    )
    return owner.refresh_if_topology_changed(
        app,
        getattr(app.designer_workspace, "available_parts", ()) or (),
        selector_keys=required(
            "_phase6_operator_part_selector_keys"
        ),
        label_for=lambda key: required("_phase6_part_label")(
            key, snapshot=snapshot
        ),
    )

def refresh_assembly_parts_panel(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    owner = getattr(app, "_phase6_assembly_panel_owner", None)
    if owner is None:
        return None
    snapshot = dict(
        getattr(app, "_phase6_input_snapshot", {}) or {}
    )
    return owner.render_available_parts(
        app,
        getattr(app.designer_workspace, "available_parts", ()) or (),
        label_for=lambda key: required("_phase6_part_label")(
            key, snapshot=snapshot
        ),
    )

def registry_panel(self, namespace):
    """Construct Registry diagnostics presentation through composition."""
    app = self.app
    current = getattr(app, "registry_diagnostics_panel", None)
    if current is not None:
        self._registry_panel = current
        return current
    if self._registry_panel is not None:
        return self._registry_panel

    required = lambda name: self._required(namespace, name)
    part_label = required("_phase6_part_label")
    part_labels = required("PART_LABELS")
    present_token = lambda value, **kwargs: registry_present_token(
        value, part_label=part_label, **kwargs
    )
    preconditions_display = lambda value: registry_preconditions_display(
        value, present_token=present_token
    )
    source_display = lambda value, **kwargs: registry_source_display(
        value, part_labels=part_labels, **kwargs
    )
    source_raw = lambda value: registry_source_raw(
        value, part_labels=part_labels
    )

    panel = Phase6RegistryDiagnosticsPanel(
        owner=app,
        present_token=present_token,
        formula_display=registry_formula_display,
        formula_raw=registry_formula_raw,
        preconditions_display=preconditions_display,
        preconditions_raw=registry_preconditions_raw,
        source_display=source_display,
        source_raw=source_raw,
        validate_formula=lambda: self.registry_validate_formula_form(),
        preview_payload=lambda: self.registry_preview_payload(),
        preview_assembly_3d=lambda: self.registry_preview_assembly_3d(
            namespace
        ),
        save_candidate=lambda: self.registry_save_candidate_form(namespace),
        run_formula_matrix=lambda: self.registry_run_formula_matrix(
            namespace
        ),
        promote_candidate=lambda: self.registry_promote_form(),
        load_rule_rows=lambda: required("_phase6_registry_load_rule_rows")(app),
        rule_record=lambda key: self.registry_diagnostics().rule_record(key),
        joint_rows=lambda: required("_phase6_joint_rows")(app),
        add_joint=lambda: required("_phase6_joint_form_add")(app),
        delete_joint=lambda: required("_phase6_joint_form_delete")(app),
        on_diagnostic_changed=lambda: required(
            "_phase6_on_assembly_diagnostic_changed"
        )(app),
        create_promotion_candidates=lambda: required(
            "_phase6_create_relief_promotion_candidates"
        )(app),
        diagnostic_ids=lambda resolved=None: self.registry_diagnostics().diagnostic_ids(
            resolved
            or getattr(app, "_phase6_last_resolved_manufacturing_geometry", None)
        ),
    )
    self._registry_panel = panel
    app.registry_diagnostics_panel = panel
    return panel

def corner_data_view(self):
    """Construct the Corner Data presentation adapter through composition."""
    app = self.app
    current = getattr(app, "_phase6_corner_data_view_adapter", None)
    if current is not None:
        self._corner_data_view = current
        return current
    if self._corner_data_view is None:
        self._corner_data_view = Phase6CornerDataViewAdapter(
            selected_part_key=getattr(
                app, "_phase6_corner_data_selected_part_key", None
            )
        )
        app._phase6_corner_data_view_adapter = self._corner_data_view
    return self._corner_data_view

def corner_data_part_keys(self):
    """Project authoritative workspace identities into Corner Data."""
    app = self.app
    return self.corner_data_view().part_keys(app.designer_workspace)

def corner_data_navigation_rows(self, namespace):
    required = lambda name: self._required(namespace, name)
    return self.corner_data_view().navigation_rows(
        self.corner_data_part_keys(),
        hierarchy_projector=required("_dm7_project_hierarchy"),
    )

def select_corner_data_part(
    self,
    namespace,
    key,
    *,
    refresh_view=True,
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    view = self.corner_data_view()
    previous = view.selected_part_key
    resolved = view.resolve_selection(
        self.corner_data_part_keys(),
        key,
        resolver=lambda requested: required(
            "_phase6_resolve_operator_part_key"
        )(app, requested),
    )
    required(
        "_phase6_sync_corner_data_view_compatibility_mirrors"
    )(app, view)
    self.refresh_corner_data_back_panel_mode_control(namespace)
    if previous != resolved:
        canvas = getattr(app, "corner_data_canvas", None)
        if canvas is not None:
            try:
                canvas._phase6_unfold_zoom = 1.0
            except Exception:
                pass
    if (
        refresh_view
        and str(getattr(app, "_phase6_3d_display_mode", "") or "")
        == "corner_data"
        and getattr(app, "corner_data_canvas", None) is not None
    ):
        self.refresh_corner_data_unfold_view(namespace)
    self.refresh_status_bar(namespace)
    return resolved

def corner_data_info_request_for_key(
    self,
    namespace,
    part_key,
    render_data,
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
    settings = getattr(app, "_settings_values", {}) or {}
    return self.corner_data_view().info_request(
        part_key=part_key,
        render_data=render_data,
        request_factory=required("FinalSceneViewRequest"),
        profile_provider=lambda key, material: required(
            "_phase6_mesh_profiles_for_part"
        )(app, key, material),
        dimensions_provider=lambda key: required(
            "_phase6_operator_finished_dimensions"
        )(app, key),
        corner_text_provider=required(
            "_phase6_render_data_corner_dimension_text"
        ),
        blank_text_provider=self.final_scene_ports(namespace).blank_text,
        alpha_bend=float(
            getattr(getattr(app, "state", None), "alpha_bend", 0.85)
        ),
        thickness=required("_num")(
            settings.get("t", snapshot.get("t", 2.0)),
            2.0,
        ),
    )

def corner_data_info_text_for_key(
    self,
    namespace,
    part_key,
    render_data,
):
    required = lambda name: self._required(namespace, name)
    request = self.corner_data_info_request_for_key(
        namespace, part_key, render_data
    )
    return required("format_operator_info_text")(
        request,
        dimensions=request.finished_dimensions,
        number_text=required("_setting_number_text"),
    )

def corner_data_unfold_projection_for_key(
    self,
    namespace,
    part_key,
):
    app = self.app
    required = lambda name: self._required(namespace, name)

    def render_provider(selected):
        if required("_phase6_is_box_body_physical_piece_key")(selected):
            return required("_phase6_box_body_piece_render_data")(
                app, selected
            )
        return required("_phase6_render_data_for_blank")(app, selected)

    return self.corner_data_view().unfold_projection(
        part_key,
        available_parts=self.corner_data_part_keys(),
        render_provider=render_provider,
        projection_factory=required(
            "Phase6CornerDataUnfoldProjection"
        ),
    )

def corner_data_unfold_projections(
    self,
    namespace,
    part_keys,
):
    return self.corner_data_view().unfold_projections(
        part_keys,
        projection_provider=lambda key: self.corner_data_unfold_projection_for_key(
            namespace, key
        ),
    )

def corner_data_unfold_projection(self, namespace):
    return self.corner_data_view().selected_projection(
        projection_provider=lambda key: self.corner_data_unfold_projection_for_key(
            namespace, key
        )
    )

def refresh_corner_data_unfold_view(self, namespace):
    app = self.app
    canvas = getattr(app, "corner_data_canvas", None)
    projection = self.corner_data_unfold_projection(namespace)
    payload = self.corner_data_view().view_payload(
        projection,
        info_provider=lambda part_key, render_data: self.corner_data_info_text_for_key(
            namespace, part_key, render_data
        ),
    )
    if payload is None:
        if canvas is not None and hasattr(canvas, "delete"):
            canvas.delete("all")
        return None

    info_text = payload["info_text"]
    info_var = getattr(app, "corner_data_info_var", None)
    if info_var is not None and hasattr(info_var, "set"):
        info_var.set(info_text)
    app.corner_data_info_text = info_text
    callback = getattr(app, "_corner_data_view_render_callback", None)
    projection = payload["projection"]
    if callback is not None and canvas is not None:
        callback(canvas, projection.part_key, projection.render_data)
    return projection

def corner_data_back_panel_mode_is_applicable(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    state = required("_phase6_box_structure_state")(app)
    return self.corner_data_view().back_panel_mode_is_applicable(
        getattr(self.corner_data_view(), "selected_part_key", None),
        family_name=cabinet_family_policy.canonical_family_name(
            getattr(app, "_phase6_input_snapshot", {}) or {}
        ),
        active_type=state.get("active_type"),
        three_piece_type=BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value,
    )

def refresh_corner_data_back_panel_mode_control(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    state = required("_phase6_box_structure_state")(app)
    current = required("back_panel_mode")(state)
    labels = required("_BACK_PANEL_MODE_LABELS")
    modes = required("BackPanelMode")
    return self.corner_data_view().refresh_back_panel_mode_control(
        app,
        applicable=self.corner_data_back_panel_mode_is_applicable(
            namespace
        ),
        current_label=labels[current],
        values=tuple(labels[item] for item in modes),
        on_selected=lambda var: self.select_back_panel_mode(
            namespace, var
        ),
    )

def refresh_corner_data_parts_panel(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    keys = self.corner_data_part_keys()
    return self.corner_data_view().refresh_parts_panel(
        app,
        keys=keys,
        selected=getattr(
            app, "_phase6_corner_data_selected_part_key", None
        ),
        navigation_rows=self.corner_data_navigation_rows(namespace),
        label_for=required("_phase6_part_label"),
        on_select=lambda key: self.select_corner_data_part(
            namespace, key
        ),
        on_refresh_back_panel_mode=lambda: self.refresh_corner_data_back_panel_mode_control(
            namespace
        ),
    )

def on_corner_data_mousewheel(self, namespace, event):
    app = self.app
    canvas = getattr(app, "corner_data_canvas", None)
    if canvas is None:
        return None
    updated = self.corner_data_view().zoom_from_event(
        getattr(canvas, "_phase6_unfold_zoom", 1.0),
        delta=getattr(event, "delta", 0),
        button=getattr(event, "num", 0),
    )
    if updated is None:
        return None
    canvas._phase6_unfold_zoom = updated
    if (
        str(getattr(app, "_phase6_3d_display_mode", "") or "")
        == "corner_data"
    ):
        self.refresh_corner_data_unfold_view(namespace)
    return "break"

def prepare_corner_data_canvas(self, namespace):
    app = self.app
    view = self.corner_data_view()
    return view.prepare_canvas(
        app,
        canvas_bg=WHD_THEME["corner_data_canvas"],
        on_configure=lambda _event: (
            self.refresh_corner_data_unfold_view(namespace)
            if str(
                getattr(app, "_phase6_3d_display_mode", "") or ""
            )
            == "corner_data"
            else None
        ),
        on_mousewheel=lambda event: self.on_corner_data_mousewheel(
            namespace, event
        ),
        visibility_plan=view.canvas_visibility_plan(True),
    )
