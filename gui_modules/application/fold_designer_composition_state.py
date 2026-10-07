"""Phase6 Fold Designer composition state implementation.

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

def corner_transaction_payload(self, namespace):
    """Assemble the live-sync payload from existing canonical owners."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    source = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    graph_state = migrate_legacy_snapshot_joints(source)
    workspace = self.collect_workspace_state(namespace)
    clone = required("clone_profile")
    return {
        "model": str(app.baseline_model_var.get() or "").strip(),
        "settings": dict(getattr(app, "_settings_values", {})),
        "multi_door_enabled": bool(source.get("multi_door_enabled", False)),
        "door_layout_columns": deepcopy(
            source.get("door_layout_columns") or []
        ),
        "door_layout_scope": str(
            source.get("door_layout_scope") or "main"
        ),
        "door_handle_edges": deepcopy(
            source.get("door_handle_edges") or {}
        ),
        "assembly_type": assembly_intent_value(
            getattr(
                app,
                "_phase6_assembly_type",
                CornerTypeId.INSERT_OVERLAY,
            )
        ),
        "assembly_joint_schema_version": graph_state[
            "assembly_joint_schema_version"
        ],
        "assembly_joints": deepcopy(graph_state["assembly_joints"]),
        "endcap_fw": deepcopy(
            getattr(app, "_phase6_endcap_fw_state", None)
            or required("normalize_endcap_fw_state")(
                getattr(app, "_phase6_input_snapshot", {}) or {}
            )
        ),
        "corner_state": deepcopy(
            getattr(app, "_phase6_corner_state", {})
        ),
        "corner_pair_same": deepcopy(
            getattr(app, "_phase6_corner_pair_same", {})
        ),
        "active_part": getattr(app, "active_part_key", None),
        "assembly_relief": self.serialize_assembly_relief_state(namespace),
        "workspace": workspace,
        "existing_parts": list(
            workspace.get("existing_parts", [])
        ),
        "part_profiles": deepcopy(
            workspace.get("part_profiles", {})
        ),
        "box_body_structure": deepcopy(
            workspace.get("box_body_structure", {})
        ),
        "box_body_profile": clone(
            workspace.get("box_body_profile", [])
        ),
        "part_features": deepcopy(
            workspace.get("part_features", {})
        ),
        "part_face_features": deepcopy(
            workspace.get("part_face_features", {})
        ),
        "assembly_placements": deepcopy(
            workspace.get("assembly_placements", {})
        ),
    }

def publish_live_state(self, namespace, *, force=False):
    """Own the live-sync plan -> callback -> application-state effect boundary."""
    app = self.app
    callback = getattr(app, "_live_sync_callback", None)
    if (
        not callable(callback)
        or getattr(app, "_phase6_live_sync_guard", False)
        or getattr(app, "_phase6_initializing", False)
        or not getattr(app, "_phase6_sync_ready", False)
        or not hasattr(app, "baseline_model_var")
        or not hasattr(app, "designer_workspace")
    ):
        return False

    state = self.corner_transaction_payload(namespace)
    input_snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
    host_relief_present = (
        isinstance(input_snapshot, Mapping)
        and "assembly_relief" in input_snapshot
    )
    host_relief = (
        deepcopy(input_snapshot.get("assembly_relief") or {})
        if host_relief_present
        else {}
    )
    plan = plan_live_sync_envelope(
        current_state=state,
        previous_state=getattr(app, "_phase6_last_live_state", None) or {},
        previous_fingerprint=getattr(
            app, "_phase6_last_live_fingerprint", None
        ),
        current_revision=getattr(app, "_phase6_sync_revision", 0),
        active_transaction_id=getattr(
            app, "_phase6_active_transaction_id", ""
        ),
        host_relief_present=host_relief_present,
        host_relief=host_relief,
        force=bool(force),
    )
    if not plan.should_publish:
        return False

    payload = materialize_sync_value(plan.payload)
    app._phase6_live_sync_guard = True
    try:
        callback(deepcopy(payload))
        app._phase6_sync_revision = plan.next_revision
        app._phase6_last_live_state = deepcopy(state)
        app._phase6_last_live_fingerprint = plan.fingerprint
        app._phase6_last_live_payload = deepcopy(payload)
        app._phase6_input_snapshot["assembly_relief"] = (
            materialize_sync_value(plan.host_relief_repair)
        )
    except Exception as exc:
        if hasattr(app, "settings_status_var"):
            app.settings_status_var.set(f"即時同步失敗：{exc}")
        return False
    finally:
        app._phase6_live_sync_guard = False
    return True

def final_scene_set_preview_enabled(self, enabled):
    """Apply the FinalScene preview effect through the composition owner."""
    app = self.app
    enabled = bool(enabled)
    app.preview_3d_enabled = enabled
    var = getattr(app, "preview_3d_var", None)
    if var is not None and bool(var.get()) != enabled:
        var.set(enabled)
    widget = app.renderer.canvas.get_tk_widget()
    if enabled:
        if not widget.winfo_manager():
            widget.pack(fill="both", expand=True)
        app.submit_update_intent("display", commit=True)
    elif widget.winfo_manager() == "pack":
        widget.pack_forget()
    return enabled

def status_projection(self, namespace):
    """Project cabinet/part/view state into the existing low-noise status text."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    family = required("_phase6_current_cabinet_family")(app) or "-"
    mode = str(
        getattr(app, "_phase6_3d_display_mode", "single") or "single"
    )
    if mode == "corner_data":
        part_key = (
            getattr(
                app,
                "_phase6_corner_data_selected_part_key",
                None,
            )
            or getattr(app, "active_part_key", None)
        )
    else:
        part_key = getattr(app, "active_part_key", None)
    part_text = (
        required("_phase6_part_label")(part_key)
        if part_key
        else "-"
    )
    return Phase6ProjectController.project_status_projection(
        family=family,
        mode=mode,
        part_text=part_text,
    )

def refresh_status_bar(self, namespace):
    """Refresh the status sink without mutating selection/domain state."""
    app = self.app
    text = self.status_projection(namespace)
    var = getattr(app, "status_projection_var", None)
    if var is not None and hasattr(var, "set"):
        var.set(text)
    return text

def reset_initial_values(self, namespace):
    """Route immutable factory defaults through the Settings coordinator."""
    app = self.app
    self.flush_pending_settings(namespace)
    coordinator = self.settings_coordinator(
        self.settings_application_ports(namespace)
    )
    return coordinator.reset_factory_settings(
        getattr(app, "_factory_defaults", {}) or {}
    )

def save_settings_context_as_defaults(self, namespace, context):
    """Persist one Settings context through the existing project command helper."""
    app = self.app
    self.flush_pending_settings(namespace)
    callback = getattr(app, "_save_defaults_callback", None)
    if callback is None:
        if hasattr(app, "settings_status_var"):
            app.settings_status_var.set("未連接預設值儲存器")
        return False

    payload = self.settings_transactions().settings_defaults_payload(
        context
    )
    try:
        Phase6ProjectController.route_settings_defaults(
            callback, payload
        )
    except Exception as exc:
        if hasattr(app, "settings_status_var"):
            app.settings_status_var.set(f"儲存失敗：{exc}")
        return False
    if hasattr(app, "settings_status_var"):
        app.settings_status_var.set("已儲存到 config.ini")
    return True

def commit_output_draw_stock(self, namespace):
    """Route STOCK through the existing project command owner."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    return Phase6ProjectController.commit_output_stock(
        bool(app.output_draw_stock_var.get()),
        lambda key, value: required("_phase6_stage_setting_update")(
            app, key, value
        ),
    )

def export_selected_dxf_from_3d(self):
    """Route 3D DXF export through the existing project command owner."""
    app = self.app
    return Phase6ProjectController.route_selected_dxf_export(
        getattr(app, "_phase6_export_selected_dxf_callback", None),
        app.flush_pending_settings,
    )

def collect_workspace_state(self, namespace):
    """Assemble one application snapshot around the canonical workspace owner."""
    from ae_engine.assembly_placement import resolve_assembly_placement

    app = self.app
    required = lambda name: self._required(namespace, name)
    clone = required("clone_profile")
    workspace = app.designer_workspace
    active = workspace.active_part
    live_active_profiles = None
    if active and active != "box_body":
        profiles = getattr(app.state, "profiles", {}) or {}
        live_x = profiles.get("X", ()) or ()
        live_y = profiles.get("Y", ()) or ()
        if live_x or live_y:
            live_active_profiles = {
                "X": clone(live_x),
                "Y": clone(live_y),
            }

    owner = workspace.export_shared_snapshot(
        live_active_profiles=live_active_profiles
    )
    owner["part_features"] = workspace.part_features_snapshot()
    owner["part_face_features"] = workspace.part_face_features_snapshot()
    owner["assembly_placements"] = workspace.assembly_placements_snapshot()
    try:
        owner["assembly_placements"] = (
            workspace.resolve_and_store_assembly_placements(
                dict(
                    getattr(app, "_phase6_input_snapshot", {}) or {}
                ),
                resolver=resolve_assembly_placement,
            )
        )
    except Exception:
        pass

    graph_state = migrate_legacy_snapshot_joints(
        dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    )
    return {
        "assembly_type": assembly_intent_value(
            getattr(
                app,
                "_phase6_assembly_type",
                CornerTypeId.INSERT_OVERLAY,
            )
        ),
        "assembly_joint_schema_version": graph_state[
            "assembly_joint_schema_version"
        ],
        "assembly_joints": deepcopy(graph_state["assembly_joints"]),
        "endcap_fw": deepcopy(
            getattr(app, "_phase6_endcap_fw_state", None)
            or required("normalize_endcap_fw_state")(
                getattr(app, "_phase6_input_snapshot", {}) or {}
            )
        ),
        "box_body_profile": clone(
            app.state.profiles_vault.get("箱身", [])
        ),
        **owner,
    }

def current_relief_source_signature(self, namespace, required_parts):
    """Collect current mechanical identity for persisted relief replay."""
    from ae_engine.assembly_joint import resolved_joint_graph_fingerprint
    from phase6_assembly_relief_state import build_current_source_signature

    app = self.app
    required = lambda name: self._required(namespace, name)
    source = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    source.update(dict(getattr(app, "_settings_values", {}) or {}))
    source.update(dict(getattr(app, "_phase6_box_whd", {}) or {}))
    source["assembly_type"] = assembly_intent_value(
        getattr(app, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)
    )

    clone = required("clone_profile")
    box_profile = clone(
        (getattr(app.state, "profiles_vault", {}) or {}).get("箱身", ()) or ()
    )
    formed_left, formed_right = formed_box_body_fw_widths(
        box_profile,
        float(source.get("t", 0.0) or 0.0),
    )
    graph_snapshot = migrate_legacy_snapshot_joints(
        dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    )
    wanted = tuple(str(key) for key in tuple(required_parts or ()))
    return build_current_source_signature(
        scalar_source=source,
        joint_graph_fingerprint=resolved_joint_graph_fingerprint(graph_snapshot),
        structure_state=deepcopy(
            app.designer_workspace.box_body_structure_state() or {}
        ),
        cabinet_family=str(
            source.get("model") or source.get("cabinet_type") or ""
        ),
        formed_left=formed_left,
        formed_right=formed_right,
        box_body_profile=box_profile,
        part_profiles={
            key: deepcopy(app.designer_workspace.profiles_for(key, {}) or {})
            for key in wanted
        },
    )

def serialize_assembly_relief_state(self, namespace):
    """Serialize resolved relief through the canonical persisted-state owner."""
    from phase6_assembly_relief_state import build_persisted_relief_state

    app = self.app
    required = lambda name: self._required(namespace, name)
    enabled_var = getattr(app, "assembly_ignore_fixed_corner_var", None)
    fallback_enabled = (
        bool(enabled_var.get()) if enabled_var is not None else True
    )
    solutions = dict(
        getattr(app, "_phase6_last_relief_solutions", {}) or {}
    )
    available = set(
        getattr(app.designer_workspace, "available_parts", ()) or ()
    )
    required_parts = tuple(
        key for key in ("head", "tail") if key in available
    )
    source_signature = dict(
        self.current_relief_source_signature(
            namespace, required_parts
        )
        or {}
    )
    prior = deepcopy(
        (getattr(app, "_phase6_input_snapshot", {}) or {}).get(
            "assembly_relief"
        )
        or {}
    )
    return build_persisted_relief_state(
        required_parts=required_parts,
        solutions=solutions,
        source_signature=source_signature,
        prior_state=prior,
        fallback_enabled=fallback_enabled,
        clearance=required("_phase6_assembly_relief_clearance")(app),
    )

def build_project_snapshot(self, namespace):
    """Capture one complete reloadable Fold Designer project payload."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    try:
        app._save_current_part(notify=False)
    except Exception:
        pass
    model_var = getattr(app, "baseline_model_var", None)
    model = str(
        model_var.get()
        if model_var is not None
        else getattr(app, "_phase6_baseline_initial_model", "") or ""
    ).strip()
    owner_workspace = app.designer_workspace.snapshot()
    workspace = self.collect_workspace_state(namespace)
    base_snapshot = deepcopy(
        getattr(app, "_phase6_input_snapshot", {}) or {}
    )
    callback = getattr(app, "_scene_query_callback", None)
    final_geometry = required("collect_final_geometry_diagnostics")(
        list(owner_workspace.get("existing_parts") or ()),
        lambda key: required("_phase6_scene_query_payload_for_part")(app, key),
        callback if callable(callback) else None,
    )
    return Phase6ProjectController.build_designer_payload(
        schema=required("_phase6_project_file").PROJECT_SCHEMA,
        model=model,
        base_snapshot=base_snapshot,
        settings=getattr(app, "_settings_values", {}) or {},
        box_whd=getattr(app, "_phase6_box_whd", {}) or {},
        assembly_type=assembly_intent_value(
            getattr(
                app,
                "_phase6_assembly_type",
                CornerTypeId.INSERT_OVERLAY,
            )
        ),
        endcap_fw=deepcopy(
            getattr(
                app,
                "_phase6_endcap_fw_state",
                normalize_endcap_fw_state(base_snapshot),
            )
        ),
        corner_state=getattr(app, "_phase6_corner_state", {}) or {},
        corner_pair_same=getattr(app, "_phase6_corner_pair_same", {}) or {},
        owner_workspace=owner_workspace,
        workspace=workspace,
        box_body_profile=required("clone_profile")(
            workspace.get("box_body_profile", [])
        ),
        assembly_relief=self.serialize_assembly_relief_state(
            namespace
        ),
        final_geometry=final_geometry,
    )

def load_project_file(self, namespace):
    """Open a Phase6 project through the existing host project-load callback."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    project_file = required("_phase6_project_file")
    from tkinter import filedialog, messagebox

    path = filedialog.askopenfilename(
        parent=app.root,
        title="讀檔：Phase6 折彎專案",
        filetypes=[
            ("Phase6 折彎專案", f"*{project_file.PROJECT_EXTENSION}"),
            ("所有檔案", "*.*"),
        ],
    )
    if not path:
        return None

    callback = getattr(app, "_project_load_callback", None)
    if not callable(callback):
        messagebox.showerror(
            "讀檔失敗",
            "目前工作區沒有可用的專案讀檔入口。",
            parent=app.root,
        )
        return None

    try:
        Phase6ProjectController.validate_project_load(
            path, project_file.read_project
        )
        callback(str(path))
        return str(path)
    except Exception as exc:
        try:
            messagebox.showerror(
                "讀檔失敗",
                f"無法讀取 Phase6 專案：\n{exc}",
                parent=app.root,
            )
        except Exception:
            pass
        return None

def save_project_file(self, namespace, *, save_as=False):
    """Save through committed host ownership or the existing project file owner."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    project_file = required("_phase6_project_file")
    callback = getattr(app, "_project_save_callback", None)
    if callable(callback):
        return callback(
            save_as=bool(save_as),
            active_part=getattr(app, "active_part_key", None),
        )

    from tkinter import filedialog, messagebox

    if getattr(app, "_phase6_pending_settings", None):
        try:
            app.flush_pending_settings()
        except Exception:
            pass

    current = str(
        getattr(app, "_phase6_current_project_path", "") or ""
    ).strip()
    path = current
    if save_as or not path:
        model_var = getattr(app, "baseline_model_var", None)
        model = (
            str(model_var.get() if model_var is not None else "").strip()
            or "自訂"
        )
        safe_model = "".join(
            ch if ch not in '\\/:*?"<>|' else "_" for ch in model
        )
        extension = project_file.PROJECT_EXTENSION
        initial = Path(current).name if current else f"{safe_model}{extension}"
        path = filedialog.asksaveasfilename(
            parent=app.root,
            title="另存新檔：Phase6 專案" if save_as else "儲存專案：Phase6",
            defaultextension=extension,
            filetypes=[
                ("Phase6 折彎專案", f"*{extension}"),
                ("所有檔案", "*.*"),
            ],
            initialfile=initial,
        )
        if not path:
            return None

    try:
        payload = self.build_project_snapshot(namespace)
        payload.get("snapshot", {}).pop("_runtime_project_path", None)
        target = Phase6ProjectController.write_designer_project(
            path, payload, project_file.write_project
        )
        app._phase6_current_project_path = str(target)
        path_callback = getattr(app, "_project_path_change_callback", None)
        if callable(path_callback):
            path_callback(str(target))
        if hasattr(app, "settings_status_var"):
            app.settings_status_var.set(
                f"已存專案：{Path(target).name}（全部板件）"
            )
        return str(target)
    except Exception as exc:
        messagebox.showerror(
            "存檔失敗",
            f"無法儲存 Phase6 專案：\n{exc}",
            parent=app.root,
        )
        return None

def toggle_parameter_panel(self, namespace):
    """Toggle the existing settings surface without creating state ownership."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    app._phase6_parameters_unlocked = not bool(
        getattr(app, "_phase6_parameters_unlocked", False)
    )
    unlocked = app._phase6_parameters_unlocked
    button = getattr(app, "parameter_lock_button", None)
    if button is not None:
        button.configure(text=("參數解鎖" if unlocked else "參數鎖定"))

    center = getattr(app, "settings_center", None)
    active = str(getattr(app, "active_part_key", None) or "box_body")
    assembly_selected = (
        str(getattr(app, "_phase6_3d_display_mode", "single") or "single")
        == "assembly"
    )
    diagnostics = getattr(app, "assembly_diagnostics_frame", None)
    if unlocked and assembly_selected:
        if center is not None and center.winfo_manager():
            center.pack_forget()
        if diagnostics is not None and not diagnostics.winfo_manager():
            required("_phase6_pack_right_panel_above_canvas")(app, diagnostics)
        self.update_assembly_diagnostic_status(namespace)
    elif unlocked:
        if diagnostics is not None and diagnostics.winfo_manager():
            diagnostics.pack_forget()
        self.invalidate_settings_page(active)
        self.render_settings_context(namespace, active)
        if center is not None and not center.winfo_manager():
            required("_phase6_pack_right_panel_above_canvas")(app, center)
    else:
        if center is not None and center.winfo_manager():
            center.pack_forget()
        if diagnostics is not None and diagnostics.winfo_manager():
            diagnostics.pack_forget()
    return unlocked

def _required(namespace, name):
    try:
        return namespace[name]
    except KeyError as exc:
        raise RuntimeError(
            f"Fold Designer composition port is unavailable: {name}"
        ) from exc

def flush_pending_settings(self, namespace):
    """Apply one drained Settings batch through the existing coordinator."""
    app = self.app
    service = self.settings_service()
    plan = service.drain_pending()
    if plan.cancel_job is not None:
        try:
            app.root.after_cancel(plan.cancel_job)
        except Exception:
            pass
    if not plan.pending:
        return {}
    coordinator = self.settings_coordinator(
        self.settings_application_ports(namespace)
    )
    return coordinator.apply_updates(
        plan.pending,
        notify=True,
        external_apply_guard=bool(
            getattr(app, "_phase6_external_apply_guard", False)
        ),
    )

def stage_setting_update(self, namespace, key, value):
    """Own Tk debounce timing while the Settings service owns pending state."""
    app = self.app
    service = self.settings_service()
    plan = service.stage_setting_update(
        key,
        value,
        destroying=bool(getattr(app, "_phase6_destroying", False)),
    )
    if not plan.changed:
        return None
    if plan.cancel_job is not None:
        try:
            app.root.after_cancel(plan.cancel_job)
        except Exception:
            pass
    job = app.root.after(
        plan.schedule_after_ms,
        lambda: self.flush_pending_settings(namespace),
    )
    service.install_debounce_job(job)
    return job
