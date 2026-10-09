"""Phase6 Fold Designer composition shell settings implementation.

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

def toggle_fullscreen(self):
    """Apply fullscreen presentation effects while composition owns app state."""
    app = self.app
    enabled, geometry = workspace_shell_toggle_fullscreen(
        app.root,
        getattr(app, "fullscreen_button", None),
        enabled=bool(getattr(app, "_phase6_fullscreen", False)),
        restore_geometry=getattr(app, "_phase6_restore_geometry", None),
    )
    app._phase6_fullscreen = bool(enabled)
    app._phase6_restore_geometry = geometry
    return app._phase6_fullscreen

def build_settings_center(self, namespace):
    """Build Settings/diagnostics around the renderer without changing owners."""
    app = self.app
    renderer_widget = app.renderer.canvas.get_tk_widget()
    renderer_widget.pack_forget()
    panel = self.settings_panel(namespace)
    panel.build_settings_center(app.right)
    self.registry_panel(namespace).build_assembly_diagnostics(app.right)
    renderer_widget.pack(fill=tk.BOTH, expand=True)
    self.sync_settings_panel_compat()

def install_renderer_view(self, namespace):
    """Install the FinalScene view and keep its Tk canvas out of focus order."""
    app = self.app
    adapter = self.final_scene_adapter(self.final_scene_ports(namespace))
    result = adapter.install_renderer()
    try:
        app.renderer.canvas.get_tk_widget().configure(takefocus=False)
    except Exception:
        pass
    return result

def workspace_shell_owner(self, namespace):
    """Compose WorkspaceShell state/actions without moving presentation ownership."""
    app = self.app
    current = getattr(app, "__dict__", {}).get("_phase6_workspace_shell_owner")
    if isinstance(current, WorkspaceShellOwner):
        self._workspace_shell_owner = current
        return current
    if self._workspace_shell_owner is not None:
        return self._workspace_shell_owner

    required = lambda name: self._required(namespace, name)
    panel = self.settings_panel(namespace)
    structure_state = required("_phase6_box_structure_state")(app)
    active_structure = BoxBodyStructureType(structure_state["active_type"])
    structure_labels = required("_BOX_STRUCTURE_LABELS")

    shell_state = WorkspaceShellState(
        root=app.root,
        left=app.left,
        right=app.right,
        renderer_canvas_widget=app.renderer.canvas.get_tk_widget(),
        ui_text_size_values=tuple(UI_TEXT_SIZE_LABELS.values()),
        v_a_bend=app.v_a_bend,
        v_a_face=app.v_a_face,
        baseline_models=tuple(app._baseline_models),
        initial_model=app._phase6_baseline_initial_model,
        structure_label=structure_labels[active_structure],
        structure_choices=tuple(structure_labels.values()),
        assembly_label=ASSEMBLY_TYPE_LABELS[
            getattr(app, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)
        ],
        assembly_choices=tuple(ASSEMBLY_TYPE_LABELS.values()),
        settings_values=dict(app._settings_values),
        external_draw_stock_var=getattr(
            app, "_phase6_external_draw_stock_var", None
        ),
        external_export_vars=dict(
            getattr(app, "_phase6_external_export_vars", {}) or {}
        ),
        left_workspace_width=required("_phase6_left_workspace_width")(
            app._settings_values.get("ui_text_size", "small")
        ),
        theme_background=WHD_THEME["background"],
    )
    actions = WorkspaceShellActions(
        status_projection=lambda: required("_phase6_status_projection")(app),
        load_project_file=app.load_project_file,
        save_project_file=app.save_project_file,
        save_project_file_as=app.save_project_file_as,
        open_relief_registry=lambda: required(
            "_phase6_open_relief_registry_form"
        )(app),
        reset_initial_values=app.reset_initial_values,
        build_settings_global_controls=lambda host: panel.build_left_global_controls(
            host,
            baseline_models=tuple(app._baseline_models),
            initial_model=app._phase6_baseline_initial_model,
        ),
        sync_settings_panel_compat=lambda: self.sync_settings_panel_compat(),
        get_left_global_controls=lambda: app.left_global_controls,
        get_left_global_cells=lambda: app.left_global_cells,
        get_ui_text_size_var=lambda: app.ui_text_size_var,
        set_ui_text_size_combo=lambda combo: setattr(
            app.settings_panel, "ui_text_size_combo", combo
        ),
        toggle_parameter_panel=lambda: self.toggle_parameter_panel(namespace),
        select_structure_type=lambda var: required(
            "_phase6_select_box_structure_type"
        )(app, var),
        select_assembly_type=lambda: self.on_assembly_type_selected(
            namespace
        ),
        refresh_persistent_structure_controls=lambda: required(
            "_phase6_refresh_persistent_structure_controls"
        )(app),
        commit_output_draw_stock=lambda: self.commit_output_draw_stock(namespace),
        export_selected_dxf=lambda: self.export_selected_dxf_from_3d(),
        queue_update=app.queue_update,
        pack_right_panel=lambda widget: required(
            "_phase6_pack_right_panel_above_canvas"
        )(app, widget),
        refresh_sticky_structure_tree=lambda: required(
            "_phase6_refresh_sticky_structure_tree"
        )(app),
        install_keyboard_shortcuts=lambda: required(
            "_phase6_install_keyboard_shortcuts"
        )(app),
        toggle_fullscreen=lambda: self.toggle_fullscreen(),
    )
    owner = WorkspaceShellOwner(shell_state, actions)
    self._workspace_shell_owner = owner
    app._phase6_workspace_shell_owner = owner
    return owner

def sync_authoritative_derived_parts(
    self, namespace, *, projected_snapshot=None,
    projected_workspace=None, projected_box_render_data=None,
):
    """Compose cross-domain derived topology, then delegate the unique workspace mutation."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    snapshot = dict(projected_snapshot if projected_snapshot is not None else getattr(app, "_phase6_input_snapshot", {}) or {})
    workspace = projected_workspace if projected_workspace is not None else getattr(app, "designer_workspace", None)
    navigation = Phase6WorkspaceNavigationController(workspace) if projected_workspace is not None else self.capabilities.workspace.navigation()
    if workspace is None or not navigation.supports_derived_sync:
        return (), ()

    # Pure collection/derivation only. Domain formulas stay in their existing owners.
    door_rows = required("_phase6_door_part_projections")(snapshot)
    source_part_features = dict(snapshot.get("part_features") or {})
    known_feature_keys = set(workspace.part_features_snapshot())
    source_parts = tuple(snapshot.get("existing_parts") or ())
    available_parts = tuple(workspace.available_parts)

    build_profiles = required("build_standard_part_profiles")
    door_profiles = {}
    for row in door_rows:
        local = dict(snapshot)
        local_dims = {
            key: dict(value)
            for key, value in dict(snapshot.get("part_dimensions") or {}).items()
        }
        local_dims[row.part_key] = {
            "width": row.formed_width,
            "height": row.formed_height,
        }
        local["part_dimensions"] = local_dims
        door_profiles[row.part_key] = build_profiles(local, row.part_key)

    base_plate_profiles = {}
    if door_rows:
        columns = tuple(
            (float(row[0]), tuple(float(v) for v in row[1]))
            for row in tuple(snapshot.get("door_layout_columns") or ())
        )
        number = required("_num")
        shrink_left = number(snapshot.get("base_plate_shrink_left", 55), 55)
        shrink_right = number(snapshot.get("base_plate_shrink_right", 55), 55)
        shrink_top = number(snapshot.get("base_plate_shrink_top", 55), 55)
        shrink_bottom = number(snapshot.get("base_plate_shrink_bottom", 55), 55)
        for cell in derive_door_layout_cells(columns):
            base_key = door_layout_part_key(cell).replace("door_", "base_plate_", 1)
            local = dict(snapshot)
            local_dims = {
                key: dict(value)
                for key, value in dict(snapshot.get("part_dimensions") or {}).items()
            }
            local_dims[base_key] = {
                "width": max(1.0, float(cell.start_width) - shrink_left - shrink_right),
                "height": max(1.0, float(cell.start_height) - shrink_top - shrink_bottom),
            }
            local["part_dimensions"] = local_dims
            base_plate_profiles[base_key] = build_profiles(local, base_key)

    if projected_workspace is not None:
        box_render_data = projected_box_render_data
    else:
        try:
            box_render_data = required("_phase6_box_body_structure_render_data")(app)
        except Exception:
            box_render_data = None
    box_piece_profiles = (
        required("_phase6_box_body_piece_part_profiles")(box_render_data, snapshot)
        if box_render_data is not None
        else {}
    )
    desired_piece_keys = set(box_piece_profiles)
    is_piece_key = required("_phase6_is_box_body_physical_piece_key")
    current_piece_keys = {key for key in available_parts if is_piece_key(key)}

    divider_profiles = {}
    columns = list(snapshot.get("door_layout_columns") or ())
    if bool(snapshot.get("multi_door_enabled", False)) and columns:
        from ae_engine.door_dividers import derive_box_body_dividers, divider_part_profiles

        normalized_columns = tuple(
            (float(row[0]), tuple(float(value) for value in row[1]))
            for row in columns
        )
        dividers = derive_box_body_dividers(
            normalized_columns,
            depth=float(snapshot.get("d", 0.0)),
            thickness=float(snapshot.get("t", 0.0)),
            layout_scope=(str(snapshot.get("door_layout_scope") or "main").strip() or "main"),
            handle_edges=dict(snapshot.get("door_handle_edges") or {}),
            model_name=str(snapshot.get("model") or "").strip() or None,
            frame_width=float(snapshot.get("fw", 0.0)),
        )
        divider_profiles = divider_part_profiles(dividers)

    from ae_engine.inner_door_frames import (
        InnerDoorFrameSet,
        derive_all_inner_door_frames,
        inner_door_frame_part_profiles,
    )
    from ae_engine.inner_door_panels import inner_door_panel_part_profiles

    frame_sets = []
    thickness = float(snapshot.get("t", 0.0))
    if cabinet_family_policy.has_inner_door_frame_derivation(snapshot):
        frame_sets.extend(cabinet_family_policy.derive_inner_door_frame_sets(snapshot))
    else:
        for item in list(snapshot.get("inner_doors") or ()):
            if not isinstance(item, Mapping):
                continue
            spans = item.get("frame_spans")
            if not isinstance(spans, Mapping) or not spans:
                continue
            stable_id = str(item.get("stable_id") or "").strip()
            if not stable_id:
                continue
            included = tuple(
                str(side).strip().lower()
                for side in (item.get("included_frame_sides") or ("top", "bottom", "left", "right"))
            )
            frame_sets.append(
                InnerDoorFrameSet(
                    inner_door_id=stable_id,
                    spans=dict(spans),
                    thickness=thickness,
                    included_sides=included,
                )
            )
    frames = derive_all_inner_door_frames(tuple(frame_sets))
    panels = cabinet_family_policy.derive_inner_door_panels(snapshot)
    inner_profiles = inner_door_frame_part_profiles(frames)
    inner_profiles.update(inner_door_panel_part_profiles(panels))

    single_door_profiles = (
        build_profiles(snapshot, "door")
        if not door_rows and "door" in source_parts and "door" not in available_parts
        else None
    )
    single_base_plate_profiles = (
        build_profiles(snapshot, "base_plate")
        if not door_rows and "base_plate" in source_parts and "base_plate" not in available_parts
        else None
    )
    request = build_derived_part_projection_request(
        DerivedPartRequestAssemblyInput(
            door_part_keys=tuple(row.part_key for row in door_rows),
            door_profiles=door_profiles,
            base_plate_profiles=base_plate_profiles,
            divider_profiles=divider_profiles,
            inner_profiles=inner_profiles,
            box_piece_profiles=box_piece_profiles,
            current_piece_keys=tuple(current_piece_keys),
            source_parts=source_parts,
            available_parts=available_parts,
            source_part_features=source_part_features,
            known_feature_keys=tuple(known_feature_keys),
            single_door_profiles=single_door_profiles,
            single_base_plate_profiles=single_base_plate_profiles,
            active_part=workspace.active_part,
            selected_part=workspace.selected_part,
        )
    )
    plan = build_derived_part_sync_plan(request)
    navigation.apply_derived_sync_plan(plan)

    return (
        tuple(divider_profiles),
        tuple([*(frame.stable_id for frame in frames), *(panel.stable_id for panel in panels)]),
    )

def settings_service(self):
    """Construct the Settings service once from explicit committed-state ports."""
    service = self._capabilities.settings.service()
    self._settings_service = service
    return service

def settings_transactions(self):
    if self._settings_transactions is None:
        app = self.app
        input_snapshot = getattr(app, "_phase6_input_snapshot", {})
        self._settings_transactions = Phase6SettingsTransactionController(
            settings_values=getattr(app, "_settings_values", {}),
            input_snapshot=input_snapshot,
            box_whd=getattr(app, "_phase6_box_whd", {}),
            workspace=getattr(app, "designer_workspace", None),
            endcap_fw_state=getattr(app, "_phase6_endcap_fw_state", {}),
            endcap_bottom_wrap_state=getattr(
                app, "_phase6_endcap_bottom_wrap_state", {}
            ),
            corner_state=getattr(app, "_phase6_corner_state", {}),
            corner_pair_same=getattr(app, "_phase6_corner_pair_same", {}),
            assembly_type=input_snapshot.get(
                "assembly_type", CornerTypeId.INSERT_OVERLAY
            ),
            orchestration=self.settings_service(),
        )
    return self._settings_transactions

def apply_settings_profile_projection(
    self,
    namespace,
    plan,
    *,
    render=True,
):
    """Apply one pure Settings profile plan through existing app owners."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    materialize = required("materialize_settings_profile_value")
    clone = required("clone_profile")

    snapshot = materialize(plan.snapshot)
    app._phase6_input_snapshot.update(snapshot)

    box_profile = materialize(plan.box_body_profile)
    app.state.profiles_vault["箱身"] = box_profile

    if plan.derived_sync_required:
        self.sync_authoritative_derived_parts(namespace)
    self.refresh_assembly_parts_panel_if_topology_changed(namespace)

    navigation = self.capabilities.workspace.navigation()
    planned_profiles = materialize(plan.part_profiles)
    for key, profiles in planned_profiles.items():
        navigation.stash_profiles(key, profiles)

    active = str(
        plan.active_part
        or app.designer_workspace.active_part
        or "box_body"
    )
    if active == "box_body":
        app.state.phase6_fold_ui_profiles = {
            "X": app.state.profiles_vault["箱身"]
        }
    elif active in app.designer_workspace.available_parts:
        active_profiles = materialize(plan.active_profiles)
        profiles = active_profiles or (
            app.designer_workspace.profiles_for(active, {}) or {}
        )
        app.state.profiles["X"] = clone(profiles.get("X", []))
        app.state.profiles["Y"] = clone(profiles.get("Y", []))

    if render:
        try:
            app.bend_ui.render()
        except Exception:
            pass
    return plan

def refresh_profiles_from_settings(
    self,
    namespace,
    *,
    reset_box_profile=False,
    reset_all_profiles=False,
    render=True,
):
    """Build the pure Settings projection, then apply it at composition."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    workspace = app.designer_workspace
    request = required("SettingsProfileProjectionRequest")(
        settings_values=getattr(app, "_settings_values", {}),
        input_snapshot=getattr(app, "_phase6_input_snapshot", {}),
        available_parts=tuple(workspace.available_parts),
        existing_profiles=workspace.part_profiles_snapshot(),
        box_body_profile=app.state.profiles_vault.get("箱身", []),
        active_part=workspace.active_part or "box_body",
        reset_box_profile=bool(reset_box_profile),
        reset_all_profiles=bool(reset_all_profiles),
    )
    plan = required("build_settings_profile_projection")(request)
    return self.apply_settings_profile_projection(
        namespace,
        plan,
        render=bool(render),
    )

def settings_application_apply_profile_plan(
    self,
    namespace,
    committed,
    *,
    reset_box_profile=False,
    reset_all_profiles=False,
    render=True,
    editor_commit=False,
    editor_changed_keys=(),
):
    """Apply Settings profile effects at the existing application composition boundary."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    committed = dict(committed or {})
    if bool(editor_commit):
        required("_phase6_recalculate_part_dimensions")(app)
        changed_keys = set(editor_changed_keys or ())
        if {"w", "h", "d", "t", "fw"}.intersection(changed_keys):
            required("_phase6_refresh_linked_part_profiles")(app, changed_keys)
        return committed
    if "t" in committed:
        app.state.phase6_thickness = float(committed["t"])
    app._phase6_settings_guard = True
    try:
        return self.refresh_profiles_from_settings(
            namespace,
            reset_box_profile=bool(reset_box_profile),
            reset_all_profiles=bool(reset_all_profiles),
            render=bool(render),
        )
    finally:
        app._phase6_settings_guard = False

def settings_application_project_ui_values(
    self,
    namespace,
    values,
    *,
    rejected_key=None,
    error=None,
    baseline_transition=None,
    baseline_stage=None,
    new_model="",
    old_model="",
    new_editable=False,
    old_editable=False,
    factory_reset=False,
    editor_commit=False,
    editor_snapshot=None,
):
    """Project committed Settings state onto Fold Designer application widgets."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    values = dict(values or {})
    plan = baseline_transition
    number_text = required("_setting_number_text")
    original = required("original")

    if baseline_stage == "rollback":
        model_var = getattr(app, "baseline_model_var", None)
        app._phase6_baseline_guard = True
        try:
            if (
                model_var is not None
                and str(model_var.get() or "").strip()
                != str(new_model or "").strip()
            ):
                model_var.set(str(new_model or ""))
        finally:
            app._phase6_baseline_guard = False
        return

    if bool(editor_commit) and editor_snapshot is not None:
        app._phase6_input_snapshot.update(dict(editor_snapshot or {}))

    if rejected_key == "w":
        if error is not None:
            required("_phase6_box_structure_error")(app, ValueError(str(error)))
        app._phase6_settings_guard = True
        try:
            previous_w = values.get("w")
            if previous_w is not None and hasattr(app, "v_w"):
                app.v_w.set(number_text(previous_w))
            var = getattr(app, "left_global_vars", {}).get("w")
            if previous_w is not None and var is not None:
                var.set(number_text(previous_w))
        finally:
            app._phase6_settings_guard = False
        return

    if baseline_stage == "commit" and plan is not None:
        remembered = getattr(plan, "remember_non_receiving_structure", None)
        if remembered is not None:
            app._phase6_non_receiving_structure_state = deepcopy(remembered)

        if "fw" in values:
            state = getattr(app, "_phase6_endcap_fw_state", None)
            if isinstance(state, required("MutableMapping")):
                required("commit_box_fw")(state, float(values["fw"]))
                app._phase6_input_snapshot["endcap_fw"] = deepcopy(state)

        defaults = dict(getattr(plan, "defaults", {}) or {})
        if defaults:
            for key, attr in (("w", "w"), ("h", "h"), ("d", "d")):
                if key in defaults:
                    setattr(app.state, attr, original.get_int(defaults[key]))
            app.v_w.set(str(app.state.w))
            app.v_h.set(str(app.state.h))
            app.v_d.set(str(app.state.d))
            app._phase6_last_w = app.state.w
            app._phase6_last_d = app.state.d

        assembly_var = getattr(app, "assembly_type_var", None)
        if assembly_var is not None:
            assembly_var.set(ASSEMBLY_TYPE_LABELS[plan.assembly_type])

    if "ui_text_size" in values:
        key = values["ui_text_size"]
        if hasattr(app, "_ui_text_controller"):
            app._ui_text_controller.apply(key)
        app.state.ui_text_scale = (
            getattr(app, "_ui_text_controller", None).factor
            if hasattr(app, "_ui_text_controller")
            else 1.0
        )
        required("_phase6_update_left_workspace_width")(app, key)

    app._phase6_settings_guard = True
    try:
        if "w" in values:
            app.v_w.set(number_text(values["w"]))
        if "h" in values:
            app.v_h.set(number_text(values["h"]))
        if "d" in values:
            app.v_d.set(number_text(values["d"]))
        for key, var in getattr(app, "left_global_vars", {}).items():
            if key not in values:
                continue
            if key == "ui_text_size":
                var.set(required("ui_text_size_label")(values[key]))
            elif isinstance(var, original.tk.BooleanVar):
                var.set(bool(values[key]))
            else:
                var.set(number_text(values[key]))
        for key, var in getattr(app, "setting_vars", {}).items():
            if key not in values:
                continue
            if key == "ui_text_size":
                var.set(required("ui_text_size_label")(values[key]))
            elif isinstance(var, original.tk.BooleanVar):
                var.set(bool(values[key]))
            else:
                var.set(number_text(values[key]))
    finally:
        app._phase6_settings_guard = False

    if baseline_stage == "state":
        if bool(new_editable) and str(old_model or "") and not bool(old_editable):
            app._corner_transaction_unknown_state = deepcopy(
                app._phase6_corner_state
            )
            app._corner_transaction_unknown_pairs = deepcopy(
                app._phase6_corner_pair_same
            )
        app._corner_editable = bool(new_editable)
        app._phase6_baseline_last_model = str(new_model or "")
        required("_phase6_apply_box_symmetry_policy")(app)
        bend_ui = getattr(app, "bend_ui", None)
        refresh_symmetry = getattr(bend_ui, "_phase6_refresh_symmetry_bar", None)
        if callable(refresh_symmetry):
            refresh_symmetry()

    if baseline_stage == "finalize":
        required("_phase6_invalidate_corner_pages")(app)
        if (
            hasattr(app, "settings_center")
            and getattr(app, "active_part_key", None) is not None
        ):
            self.render_settings_context(
                namespace,
                getattr(app, "settings_context", app.active_part_key),
            )
        corner_data_panel = getattr(app, "corner_data_panel", None)
        if (
            str(getattr(app, "_phase6_3d_display_mode", "") or "")
            == "corner_data"
            and corner_data_panel is not None
            and corner_data_panel.winfo_manager()
        ):
            required("_phase6_refresh_corner_data_parts_panel")(app)
            if getattr(app, "corner_data_canvas", None) is not None:
                required("_phase6_refresh_corner_data_unfold_view")(app)

def settings_application_submit_update_intent(self, namespace, committed):
    """Submit the Settings application update through existing runtime ownership."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    payload = dict(committed or {}) if isinstance(committed, Mapping) else {}
    if payload.get("reason") == "baseline":
        cache = getattr(app, "_phase6_manufacturing_cache_service", None)
        clear_cache = getattr(cache, "clear", None)
        if callable(clear_cache):
            clear_cache()
        app._phase6_last_resolved_manufacturing_geometry = None
        app._phase6_last_resolved_manufacturing_signature = None
        submit = getattr(app, "submit_update_intent", None)
        if callable(submit):
            return submit("baseline", commit=True)
        return required("_phase6_publish_live_state")(
            app, force=bool(payload.get("force", True))
        )

    legacy_job = getattr(app, "_job", None)
    if legacy_job is not None:
        try:
            app.root.after_cancel(legacy_job)
        except Exception:
            pass
        app._job = None
    try:
        return app.do_update()
    except Exception:
        return None

def settings_application_publish_live_state(self, committed, *, partial=False):
    """Publish Settings changes without moving state ownership out of existing owners."""
    app = self.app
    if (
        not getattr(app, "_phase6_transactional_mode", False)
        and app._settings_change_callback is not None
    ):
        payload = (
            dict(committed or {})
            if bool(partial)
            else dict(app._settings_values)
        )
        if payload:
            app._settings_change_callback(payload)

def settings_application_ports(self, namespace):
    """Compose shallow Settings application ports at the application root."""
    app = self.app
    required = lambda name: self._required(namespace, name)

    def read_settings_snapshot():
        return SettingsStateSnapshot(
            settings_values=getattr(app, "_settings_values", {}),
            input_snapshot=getattr(app, "_phase6_input_snapshot", {}),
            box_whd=getattr(app, "_phase6_box_whd", {}),
        )

    def read_profile_snapshot():
        workspace = getattr(app, "designer_workspace", None)
        snapshot = getattr(workspace, "part_profiles_snapshot", None)
        return snapshot() if callable(snapshot) else {}

    def save_current_part():
        app._phase6_applying_settings = True
        try:
            return app._save_current_part()
        finally:
            app._phase6_applying_settings = False

    def render_bending():
        bend_ui = getattr(app, "bend_ui", None)
        render = getattr(bend_ui, "render", None)
        if not callable(render):
            return None
        try:
            return render()
        except Exception:
            return None

    def refresh_settings_panel():
        panel = getattr(app, "settings_panel", None)
        refresh = getattr(panel, "refresh_baseline_data", None)
        if not callable(refresh):
            return None
        try:
            return refresh()
        except Exception:
            return None

    def refresh_topology(*args, **kwargs):
        if kwargs.get("reason") == "baseline":
            result = None
            refresh_parts = getattr(app, "_refresh_part_buttons", None)
            if (
                callable(refresh_parts)
                and getattr(app, "part_choice_menu", None) is not None
            ):
                result = refresh_parts()
            self.refresh_receiving_set_bay_control(namespace)
            self.refresh_back_panel_mode_control(namespace)
            self.refresh_assembly_parts_panel_if_topology_changed(namespace)
            return result
        return required(
            "_phase6_refresh_assembly_parts_panel_if_topology_changed"
        )(app)

    def project_status(*args, **kwargs):
        message = kwargs.get("message")
        if message is None and args:
            message = args[0]
        status_name = (
            "settings_status_var"
            if kwargs.get("settings")
            else "_phase6_status_var"
        )
        status_var = getattr(app, status_name, None)
        setter = getattr(status_var, "set", None)
        if callable(setter) and message is not None:
            setter(str(message))

    return Phase6SettingsApplicationPorts(
        read_settings_snapshot=read_settings_snapshot,
        read_profile_snapshot=read_profile_snapshot,
        save_current_part=save_current_part,
        apply_profile_plan=lambda committed, **kwargs: self.settings_application_apply_profile_plan(
            namespace, committed, **kwargs
        ),
        sync_derived_parts=lambda *args, **kwargs: required(
            "_phase6_sync_authoritative_derived_parts"
        )(app),
        project_ui_values=lambda values, **kwargs: self.settings_application_project_ui_values(
            namespace, values, **kwargs
        ),
        render_bending=render_bending,
        refresh_settings_panel=refresh_settings_panel,
        refresh_topology=refresh_topology,
        refresh_persistent_controls=lambda: required(
            "_phase6_refresh_persistent_structure_controls"
        )(app),
        submit_update_intent=lambda committed: self.settings_application_submit_update_intent(
            namespace, committed
        ),
        publish_live_state=lambda committed, **kwargs: self.settings_application_publish_live_state(
            committed, **kwargs
        ),
        project_status=project_status,
    )

def settings_coordinator(self, ports: Phase6SettingsApplicationPorts):
    """Return the single Phase 5 Settings application sequencing owner."""
    if self._settings_coordinator is None:
        self._settings_coordinator = Phase6FoldDesignerSettingsCoordinator(
            transactions=self.settings_transactions(),
            ports=ports,
        )
    return self._settings_coordinator
