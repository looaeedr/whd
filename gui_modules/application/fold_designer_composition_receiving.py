# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Phase6 Fold Designer composition receiving implementation.

Extracted mechanically from fold_designer_adapter; public composition methods remain thin routes.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
import tkinter as tk
import ae_engine.ae as ae
from ae_engine import manufacturing_api
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
from gui_modules.application.receiving_base_plate_settings_transaction import (
    commit_receiving_base_plate_settings,
)
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

def _receiving_setting_value(set_row, bay_index, kind):
    """Project an actual persisted Bay value through the public Engine API.

    GUI must not import the private shared-setting storage policy or infer
    physical per-Bay values from presentation state.
    """
    value, _linked_bays = manufacturing_api.project_receiving_shared_setting_group(
        set_row, bay_index, kind,
    )
    return value


def _checked_nfb_copy_selection(layout, set_index, selected_bays):
    """Legacy GUI entry, delegated to Engine's strict Bay identity check."""
    return manufacturing_api.select_operator_nfb_copy_bays(
        layout, set_index, selected_bays,
    )


def receiving_layout_applicable(self):
    return self._capabilities.receiving.applicable()

def confirm_receiving_destructive(self, stable_ids):
    from tkinter import messagebox

    labels = "\n".join(str(value) for value in stable_ids)
    return bool(
        messagebox.askyesno(
            "確認刪除受電箱 Set/Bay",
            "此操作會刪除已保存或本次工作階段已修改的尾端資料：\n"
            f"{labels}\n\n確定繼續嗎？",
            parent=getattr(self.app, "root", None),
        )
    )

def receiving_adapter(self, namespace, *, reset=False):
    """Create a Receiving adapter with only its typed layout/identity ports."""
    if not self._capabilities.receiving.applicable():
        return None
    required = lambda name: self._required(namespace, name)
    return self._capabilities.receiving.adapter(
        reset=bool(reset),
        ensure_layout=required("ensure_receiving_layout"),
        stable_ids=required("receiving_layout_stable_ids"),
        adapter_type=required("ReceivingSetBayAdapter"),
        confirm_destructive=self.confirm_receiving_destructive,
    )

def sync_receiving_current_bay(
    self,
    namespace,
    *,
    validate_common=True,
    refresh_controls=True,
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    adapter = self.receiving_adapter(namespace)
    if adapter is None:
        return False
    snapshot = dict(
        getattr(app, "_phase6_input_snapshot", {}) or {}
    )
    snapshot["receiving_layout"] = adapter.layout
    projected = required("project_receiving_bay_legacy_aliases")(
        snapshot,
        set_index=adapter.selection.set_index,
        bay_index=adapter.selection.bay_index,
        validate_common=bool(validate_common),
    )
    required("_phase6_replace_mapping")(
        app, "_phase6_input_snapshot", projected
    )
    required("_phase6_replace_mapping")(
        app,
        "_phase6_box_whd",
        {
            "w": projected["w"],
            "h": projected["h"],
            "d": projected["d"],
        },
    )
    workspace = app.designer_workspace
    feature_plan = manufacturing_api.project_operator_receiving_live_bay_features(
        projected, available_parts=workspace.available_parts,
        layout=adapter.layout,
        set_index=adapter.selection.set_index,
        bay_index=adapter.selection.bay_index,
        existing_box_body_faces=workspace.face_features_for("box_body"),
    )
    for key, features in (*feature_plan.surface_updates,
                          *feature_plan.inner_panel_updates):
        workspace.stash_features(key, features)
    workspace.stash_face_features("box_body", feature_plan.box_body_joint_faces)
    original = required("original")
    number = float if projected.get("active_mode") == "quantity" else original.get_int
    app.state.w = number(projected["w"])
    app.state.h = number(projected["h"])
    app.state.d = number(projected["d"])
    # Do NOT advance _phase6_last_w/_phase6_last_d here. Those fields are the
    # Fold-profile synchronization baseline used by Phase6FoldDesignerApp.do_update().
    # Advancing them before the profile is rebuilt makes a newly selected/resized
    # Receiving Bay look "unchanged" and lets the stale old profile overwrite
    # the new operator W/D on the following authoritative update.
    app._phase6_receiving_set_bay_guard = True
    try:
        for var, value in (
            (getattr(app, "v_w", None), projected["w"]),
            (getattr(app, "v_h", None), projected["h"]),
            (getattr(app, "v_d", None), projected["d"]),
        ):
            if var is not None:
                var.set(required("_setting_number_text")(value))
    finally:
        app._phase6_receiving_set_bay_guard = False
    if refresh_controls:
        self.refresh_receiving_set_bay_control(namespace)
    self.refresh_back_panel_mode_control(namespace)
    return True

def commit_receiving_current_bay_controls(self, namespace):
    app = self.app
    # Fold Designer opens through original.MainApp.__init__, which invokes
    # do_update() once with provisional legacy W500/H600/D200 BEFORE the
    # saved Receiving Set/Bay is projected into the editor.  That bootstrap
    # render is not an operator dimension edit and may never shrink a real
    # W800/H1600 Door partition or alter persisted Bay authority.
    if getattr(app, "_phase6_sync_ready", True) is False:
        return False
    if app._phase6_input_snapshot.get("active_mode") == "quantity" and getattr(app, "_phase6_initializing", False):
        return False
    if getattr(app, "_phase6_receiving_set_bay_guard", False):
        return False
    if app._phase6_input_snapshot.get("active_mode") == "quantity":
        candidate = manufacturing_api.update_common_box(_current_mode_snapshot(self, namespace),
                                     {axis: getattr(app, "v_" + axis).get() for axis in ("w", "h", "d")})
        # Quantity re-creates a source-owned singleton Receiving Set/Bay.
        # dict.update() does not delete the previous Set/Bay runtime pointer,
        # even though project_common_box() removed it from the candidate.
        # A stale pointer would pass to EAR Z export and falsely drift.
        from ae_engine.receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
        app._phase6_input_snapshot.pop(RECEIVING_RUNTIME_SELECTION_KEY, None)
        app._phase6_input_snapshot.update(candidate)
        app.designer_workspace.set_receiving_common_box(candidate["receiving_quantity_box"])
        self.receiving_adapter(namespace, reset=True)
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        return True
    adapter = self.receiving_adapter(namespace)
    if adapter is None:
        return False
    # Operator W/H/D are physical outside dimensions, not rounded UI lengths.
    # The existing public Engine validator owns type, finite, positive and
    # fractional-mm semantics before the Bay transaction can mutate state.
    requested = {
        "width": manufacturing_api.normalize_operator_source_dimension(
            app.v_w.get(), field="w",
        ),
        "height": manufacturing_api.normalize_operator_source_dimension(
            app.v_h.get(), field="h",
        ),
        "depth": manufacturing_api.normalize_operator_source_dimension(
            app.v_d.get(), field="d",
        ),
    }
    current_bay = adapter.current_bay()
    dimensions_changed = any(
        float(current_bay[key]) != float(value) for key, value in requested.items()
    )
    adapter.update_current_bay(**requested)
    app._phase6_input_snapshot["receiving_layout"] = adapter.layout
    self.sync_receiving_current_bay(
        namespace,
        validate_common=not bool(
            getattr(app, "_phase6_initializing", False)
        ),
        refresh_controls=False,
    )
    workspace = getattr(app, "designer_workspace", None)
    if workspace is not None:
        workspace.mark_dirty()
        if dimensions_changed:
            # A physical Door/Bay span change must re-derive the SAME
            # authoritative Divider Y fold profile before the next 3D solve.
            # Otherwise W800→820 creates 816 mm physical material while the
            # workspace retains 796 mm Y: the real contact shifts ±10 mm and
            # certified CROSS correctly refuses the resulting collision.
            # This is an existing source-derived namespace refresh, not a
            # new formula or a relaxation of CROSS collision certification.
            self.sync_authoritative_derived_parts(namespace)
    return True

def back_panel_mode_control_is_applicable(self, namespace):
    """Return whether the Receiving header rear-panel choice applies."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
    if not manufacturing_api.receiving_family_supports_back_panel_mode(snapshot):
        return False
    state = required("_phase6_box_structure_state")(app)
    return manufacturing_api.receiving_back_panel_mode_control_applicable(snapshot, state)

def refresh_back_panel_mode_control(self, namespace):
    """Project canonical rear-panel mode beside the Receiving switch selector."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    frame = getattr(app, "back_panel_mode_control", None)
    var = getattr(app, "back_panel_mode_var", None)
    selector = getattr(app, "back_panel_mode_selector", None)
    if frame is None or var is None or selector is None:
        return False

    if not self.back_panel_mode_control_is_applicable(namespace):
        if frame.winfo_manager():
            frame.pack_forget()
        return False

    adapter = self.receiving_adapter(namespace)
    if adapter is not None:
        current = required("BackPanelMode")(
            str(adapter.current_bay()["back_panel_mode"])
        )
    else:
        current = required("back_panel_mode")(
            required("_phase6_box_structure_state")(app)
        )
    labels = required("_BACK_PANEL_MODE_LABELS")
    label = labels[current]
    if str(var.get() or "") != label:
        var.set(label)

    if not frame.winfo_manager():
        original = required("original")
        frame.pack(side=original.tk.LEFT, padx=(12, 0))
    return True

def select_back_panel_mode(self, namespace, var):
    """Commit the Receiving rear-panel mode through canonical owners."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    mode = required("_BACK_PANEL_MODE_LABEL_TO_MODE").get(
        str(var.get()).strip()
    )
    if mode is None:
        return None
    snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
    if not manufacturing_api.receiving_family_supports_back_panel_mode(snapshot):
        return None
    state = required("_phase6_box_structure_state")(app)
    try:
        adapter = self.receiving_adapter(namespace)
        if adapter is not None:
            adapter.update_current_bay(back_panel_mode=mode.value)
            app._phase6_input_snapshot["receiving_layout"] = adapter.layout
        committed = required("set_side_back_back_panel_mode")(
            state, mode
        )
        required("_phase6_commit_box_structure_state")(
            app, committed, rebuild=True
        )
        if adapter is not None:
            self.sync_receiving_current_bay(
                namespace, refresh_controls=False
            )
    except Exception as exc:
        required("_phase6_box_structure_error")(app, exc)
        required("_phase6_after_box_structure_commit")(
            app, state, rebuild=True
        )
    finally:
        self.refresh_back_panel_mode_control(namespace)
        if (
            str(getattr(app, "_phase6_3d_display_mode", "") or "")
            == "corner_data"
        ):
            self.refresh_corner_data_back_panel_mode_control(namespace)
    return mode

def receiving_switch_adapter(
    self,
    namespace,
    *,
    reset=False,
):
    from gui_modules.application.receiving_set_bay_adapter import ReceivingSwitchProjectionAdapter
    return ReceivingSwitchProjectionAdapter(self.receiving_adapter(namespace, reset=reset))

def mark_receiving_switch_layout_dirty(self, namespace, adapter):
    app = self.app
    app._phase6_input_snapshot["receiving_layout"] = adapter.layout
    app._phase6_input_snapshot.pop("receiving_switch_layout", None)
    workspace = getattr(app, "designer_workspace", None)
    if workspace is not None:
        workspace.mark_dirty()

def refresh_receiving_set_bay_control(self, namespace):
    """Refresh the operator-facing Chinese layer/connection editor."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    controls = getattr(app, "receiving_layer_controls", None)
    frame = getattr(app, "receiving_set_bay_control", None)
    if controls is None or frame is None:
        return False
    _refresh_mode_controls(self, namespace)
    if app._phase6_input_snapshot.get("active_mode") == "quantity":
        frame.pack_forget()
        return True
    if not required("_phase6_receiving_layout_applicable")(app):
        if frame.winfo_manager():
            frame.pack_forget()
        return False

    switch = self.receiving_switch_adapter(namespace)
    controls.switch_brand_var.set(switch.brand)
    original = required("original")
    required("refresh_receiving_layer_rows")(
        controls,
        tk=original.tk,
        ttk=original.ttk,
        connection_counts=switch.connection_counts(),
        on_resize_connections=lambda layer_index, delta: self.resize_receiving_bays(
            namespace, layer_index, delta
        ),
        on_preview=lambda layer_index: self.open_receiving_layer_preview(
            namespace, layer_index
        ),
    )
    # Product functions remain available through the Assembly multi-settings
    # dialog. The original BoxBody controls are hidden, not deleted.
    frame.pack_forget()
    return True

def on_receiving_switch_brand_selected(
    self,
    namespace,
    brand,
):
    switch = self.receiving_switch_adapter(namespace)
    if not switch.set_brand(brand):
        return switch.brand
    self.mark_receiving_switch_layout_dirty(namespace, switch)
    return switch.brand

def add_receiving_layer(self, namespace):
    switch = self.receiving_switch_adapter(namespace)
    switch.add_layer()
    self.mark_receiving_switch_layout_dirty(namespace, switch)
    self.refresh_receiving_set_bay_control(namespace)
    return True

def remove_receiving_layer(self, namespace):
    switch = self.receiving_switch_adapter(namespace)
    if not switch.remove_layer():
        return False
    self.mark_receiving_switch_layout_dirty(namespace, switch)
    self.refresh_receiving_set_bay_control(namespace)
    return True

def resize_receiving_bays(
    self,
    namespace,
    layer_index,
    delta,
    *,
    refresh_controls=True,
):
    """Resize canonical topology; skip redundant hidden panel refresh in modal."""
    switch = self.receiving_switch_adapter(namespace)
    if not switch.resize_connections(
        layer_index, delta,
    ):
        return False
    self.mark_receiving_switch_layout_dirty(namespace, switch)
    if refresh_controls:
        self.refresh_receiving_set_bay_control(namespace)
    return True

def confirm_receiving_opening(
    self,
    namespace,
    layer_index,
    connection_index,
    brand,
):
    app = self.app
    resolver = getattr(
        app, "_phase6_receiving_switch_opening_resolver", None
    )
    if not callable(resolver):
        from tkinter import messagebox

        messagebox.showwarning(
            "開孔規格尚未建立",
            f"{brand} 的 canonical 開孔規格尚未建立；未修改 3D 或截角資料。",
            parent=getattr(app, "root", None),
        )
        return False
    committed = resolver(
        layer_index=int(layer_index),
        connection_index=int(connection_index),
        brand=str(brand),
    )
    if not committed:
        return False
    submit = getattr(app, "submit_update_intent", None)
    if callable(submit):
        submit("geometry", commit=True)
    return True

def _receiving_rebase_preview_world_offsets(request, old_anchor, new_anchor):
    """UI compatibility: only Engine plans physical world-offset translation."""
    from dataclasses import replace
    from phase6_final_scene_contracts import (
        AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
    )
    if not isinstance(request, FinalSceneViewRequest):
        return None
    scene = request.render_data
    if (not isinstance(scene, AssemblySceneRenderData)
            or not scene.preserve_endcap_core_origin
            or scene.interference_probe_parts or scene.show_interference
            or scene.joint_diagnostics or scene.collision_certification_diagnostics
            or not all(isinstance(part, AssemblyScenePart)
                       for part in scene.assembly_parts)):
        return None
    offsets = manufacturing_api.plan_receiving_bay_preview_offset_rebase(
        scene.assembly_parts, old_anchor, new_anchor,
    )
    if offsets is None:
        return None
    parts = tuple(
        replace(part, offset=offset)
        for part, offset in zip(scene.assembly_parts, offsets)
    )
    return replace(request, render_data=replace(
        scene, assembly_parts=parts))


def _receiving_bay_preview_face_features_key(face_features):
    """Legacy preview-cache test/client bridge; Engine owns feature provenance."""
    return manufacturing_api.project_receiving_bay_preview_face_features_key(face_features)


def _receiving_default_local_joints_only(rows):
    """Legacy preview-cache test/client bridge; Engine owns Joint eligibility."""
    return manufacturing_api.receiving_default_local_joints_only(rows)


def _receiving_bay_preview_fingerprint_snapshot(
    snapshot, *, set_index, bay_index,
    allow_upstream_translation=False, allow_suffix_topology_reuse=False,
):
    """Legacy preview-cache bridge; Engine owns all physical dependency decisions."""
    return manufacturing_api.project_receiving_bay_preview_fingerprint_snapshot(
        snapshot, set_index=set_index, bay_index=bay_index,
        allow_upstream_translation=allow_upstream_translation,
        allow_suffix_topology_reuse=allow_suffix_topology_reuse,
    )


def _receiving_cached_bay_inner_door_panel(owner, part_key, payload, factory):
    """Raw source-free physical panel cache: eligibility/signature from Engine."""
    from collections import OrderedDict
    ticket = manufacturing_api.project_receiving_raw_source_cache_ticket(
        part_key, payload,
    )
    if ticket is None or ticket.kind != "panel":
        return factory()
    history = getattr(owner, "_receiving_raw_inner_door_panel_history", None)
    if history is None:
        history = OrderedDict()
        owner._receiving_raw_inner_door_panel_history = history
    if ticket.signature in history:
        history.move_to_end(ticket.signature)
        return history[ticket.signature]
    material = factory()
    history[ticket.signature] = material
    history.move_to_end(ticket.signature)
    while len(history) > 8:
        history.popitem(last=False)
    return material


def _receiving_cached_bay_inner_door_frame(owner, part_key, payload, factory):
    """Only Engine-witnessed A/B/D frame can reuse exact raw material."""
    if manufacturing_api.receiving_raw_source_cache_kind(part_key, payload) != "frame":
        return factory()
    from collections import OrderedDict
    from .fold_designer_manufacturing_projection import _inner_door_frame_from_payload

    # Keep this existing public Engine PartSpec adapter for GUI test/client
    # compatibility; physical key, DXF witness and reuse proof are Engine-owned.
    frame = _inner_door_frame_from_payload(str(part_key or ""), payload)
    ticket = manufacturing_api.project_receiving_raw_source_cache_ticket(
        part_key, payload, typed_part=frame,
    )
    if ticket is None:
        return factory()
    history = getattr(owner, "_receiving_raw_inner_door_frame_history", None)
    if history is None:
        history = OrderedDict()
        owner._receiving_raw_inner_door_frame_history = history
    if ticket.signature in history:
        history.move_to_end(ticket.signature)
        return history[ticket.signature]
    material = factory()
    if manufacturing_api.receiving_raw_source_cache_entry_valid(ticket, material):
        history[ticket.signature] = material
        history.move_to_end(ticket.signature)
        while len(history) > 8:
            history.popitem(last=False)
    return material


def _receiving_cached_bay_box_body_divider(owner, part_key, payload, factory):
    """Engine-witnessed two-DXF source proof controls Divider raw reuse."""
    if manufacturing_api.receiving_raw_source_cache_kind(part_key, payload) != "divider":
        return factory()
    from collections import OrderedDict
    from .fold_designer_manufacturing_projection import _box_body_divider_from_payload

    divider = _box_body_divider_from_payload(str(part_key or ""), payload)
    ticket = manufacturing_api.project_receiving_raw_source_cache_ticket(
        part_key, payload, typed_part=divider,
    )
    if ticket is None:
        return factory()
    history = getattr(owner, "_receiving_raw_divider_history", None)
    if history is None:
        history = OrderedDict()
        owner._receiving_raw_divider_history = history
    if ticket.signature in history:
        history.move_to_end(ticket.signature)
        return history[ticket.signature]
    material = factory()  # Still the real verified-source Factory.
    if manufacturing_api.receiving_raw_source_cache_entry_valid(ticket, material):
        history[ticket.signature] = material
        history.move_to_end(ticket.signature)
        while len(history) > 8:
            history.popitem(last=False)
    return material


def _retain_committed_receiving_bay_preview(cache, key, receipt):
    """Bound immutable exact-state Bay preview receipts by recent use.

    This does not decide validity: the caller must still check the entire
    semantic fingerprint, source witness and world-anchor before any hit.
    Eviction only forces a future canonical re-solve, never weakens accuracy.
    """
    cache.pop(key, None)
    cache[key] = receipt
    while len(cache) > 32:
        cache.pop(next(iter(cache)))
    return receipt


def receiving_bay_preview_request(self, namespace, set_index, bay_index, *, preview_layout=None):
    """用獨立 request 重建指定連；不更動 live app 或 manufacturing cache。"""
    from types import SimpleNamespace
    from copy import deepcopy
    from phase6_manufacturing_adapter import build_manufacturing_request, build_scene_payload_for_app
    from phase6_manufacturing_service import resolve
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from ae_engine.display_dimensions import resolve_operator_finished_dimensions
    app = self.app
    source = dict(app._phase6_input_snapshot)
    if preview_layout is not None:
        # Candidate UI previews use an isolated source, never live layout state.
        source["receiving_layout"] = preview_layout
    operator_inputs = manufacturing_api.project_receiving_bay_preview_operator_inputs(
        source, app._settings_values, set_index=set_index, bay_index=bay_index,
    )
    snapshot = operator_inputs.snapshot
    settings = operator_inputs.settings_values
    from phase6_sync_envelope import stable_fingerprint
    # Engine alone classifies physical Bay reuse and custom source identity.
    workspace = app.designer_workspace
    reuse_policy = manufacturing_api.plan_receiving_bay_preview_reuse_policy(
        snapshot, bay_index=bay_index, candidate=preview_layout is not None,
        available_parts=getattr(workspace, "available_parts", ()),
    )
    live_custom_catalog = None
    if reuse_policy.requires_live_custom_catalog:
        reader = getattr(workspace, "shared_snapshot", None)
        if not callable(reader):
            raise ValueError("RECEIVING_BAY_CUSTOM_PART_AUTHORITY_MISSING")
        live_custom_catalog = reader().get("custom_parts")
        if not live_custom_catalog:
            raise ValueError("RECEIVING_BAY_CUSTOM_PART_AUTHORITY_MISSING")
    key_snapshot = (
        {**snapshot, "custom_parts": live_custom_catalog}
        if live_custom_catalog is not None else snapshot
    )
    # Never let stale project metadata authorize world-offset translation:
    # re-evaluate the physical dependency policy after a live catalog read.
    if live_custom_catalog is not None:
        reuse_policy = manufacturing_api.plan_receiving_bay_preview_reuse_policy(
            key_snapshot, bay_index=bay_index,
            candidate=preview_layout is not None,
            available_parts=getattr(workspace, "available_parts", ()),
        )
    allow_rebase = reuse_policy.allow_upstream_translation
    fingerprint = stable_fingerprint({"snapshot": manufacturing_api.project_receiving_bay_preview_fingerprint_snapshot(
        key_snapshot, set_index=set_index, bay_index=bay_index,
        allow_upstream_translation=allow_rebase,
        allow_suffix_topology_reuse=reuse_policy.allow_suffix_topology_reuse,
    ), "profiles": app.designer_workspace.part_profiles_snapshot(), "features": app.designer_workspace.part_features_snapshot(), "face_features": (manufacturing_api.project_receiving_bay_preview_face_features_key(
        app.designer_workspace.part_face_features_snapshot())
        if reuse_policy.receiving_set_bay
        else app.designer_workspace.part_face_features_snapshot()), "box_profile": app.state.profiles_vault.get("箱身", ()), "corners": app._phase6_corner_state})
    cache = getattr(self, "_receiving_bay_preview_cache", {})
    cache_key = (set_index, bay_index)
    virtual_cache = getattr(self, "_receiving_bay_virtual_preview_cache", {})
    virtual_key = (set_index, bay_index, fingerprint)
    if preview_layout is not None and virtual_key in virtual_cache:
        return virtual_cache[virtual_key]
    cache_witness = manufacturing_api.project_receiving_bay_preview_cache_source_witness(
        snapshot["receiving_layout"], set_index=set_index, bay_index=bay_index,
    )
    prefix = cache_witness.source_prefix
    if preview_layout is None and cache_key in cache and cache[cache_key][0] == fingerprint:
        hit = _retain_committed_receiving_bay_preview(
            cache, cache_key, cache[cache_key],
        )
        if not allow_rebase:
            return hit[1]
        if len(hit) >= 4:
            if hit[3] == prefix:
                return hit[1]
            current_anchor = cache_witness.world_anchor
            rebased = _receiving_rebase_preview_world_offsets(
                hit[1], hit[2], current_anchor)
            if rebased is not None:
                _retain_committed_receiving_bay_preview(
                    cache, cache_key, (fingerprint, rebased, current_anchor, prefix),
                )
                return rebased
        # Missing prior world-anchor proof or unsupported render envelope:
        # do not reuse, use the real canonical manufacturing calculation.
    workspace = app.designer_workspace
    seed = manufacturing_api.project_receiving_bay_preview_physical_seed(
        snapshot, set_index=set_index, bay_index=bay_index,
        existing_box_body_profile=app.state.profiles_vault.get("箱身", ()),
        existing_box_body_faces=workspace.part_face_features_snapshot().get("box_body", {}),
    )
    proxy_workspace = Phase6DesignerWorkspace.from_snapshot({
        **snapshot, "existing_parts": workspace.available_parts,
        # The projected Bay is not allowed to erase existing standalone
        # custom physical sheets from the real workspace catalogue.
        # SharedWorkspaceState.snapshot() owns a deep-copied custom catalog;
        # Phase6DesignerWorkspace has NO custom_parts_snapshot() method.
        "custom_parts": workspace.shared_snapshot().get("custom_parts"),
        "part_profiles": workspace.part_profiles_snapshot(),
        "part_features": {**workspace.part_features_snapshot(), **snapshot.get("part_features", {})},
        "part_face_features": {**workspace.part_face_features_snapshot(), "box_body": seed.box_body_joint_faces},
    })
    proxy_workspace.set_box_body_structure_state(seed.box_body_structure_state)
    for key, profiles in seed.endcap_profiles.items():
        proxy_workspace.stash_profiles(key, profiles)
    proxy = SimpleNamespace(**app.__dict__)
    proxy._phase6_input_snapshot = snapshot
    proxy._settings_values = settings
    proxy._phase6_box_whd = {key: snapshot[key] for key in ("w", "h", "d")}
    proxy.designer_workspace = proxy_workspace
    proxy.state = SimpleNamespace(profiles_vault={"箱身": seed.box_body_profile}, profiles={})
    self.sync_authoritative_derived_parts(
        namespace,
        projected_snapshot=snapshot,
        projected_workspace=proxy.designer_workspace,
        projected_box_render_data=self._required(namespace, "_phase6_box_body_structure_render_data")(proxy),
    )
    def dimensions(key=None):
        return resolve_operator_finished_dimensions(key or "box_body", snapshot=snapshot, settings=settings)
    def feature_payload(key, payload):
        # committed fallback 解凍的 scene payload 是可序列化資料；孔特徵
        # 仍由 workspace 的 typed feature authority 提供，不能送入 legacy hole DTO。
        return {**dict(payload), "features": proxy_workspace.features_for(key), "face_features": proxy_workspace.face_features_for(key)}
    def render_bay_part(key, payload):
        source_payload = feature_payload(key, payload)
        def render():
            try:
                return app._scene_query_callback(key, source_payload)
            except ValueError as exc:
                raise ValueError(
                    f"RECEIVING_BAY_RENDER_SOURCE_DIAGNOSTIC:part={key}; "
                    f"requested_set={set_index},bay={bay_index}; "
                    f"projected_w={snapshot.get('w')!r},h={snapshot.get('h')!r}; "
                    f"projected_selection={snapshot.get('_receiving_runtime_selection')!r}; "
                    f"render_payload_w={source_payload.get('w')!r},h={source_payload.get('h')!r}; "
                    f"render_payload_selection={source_payload.get('_receiving_runtime_selection')!r}; "
                    f"cause={exc}"
                ) from exc
        if preview_layout is not None:
            # Candidate editing is isolated from committed Bay material reuse.
            return render()
        kind = manufacturing_api.receiving_raw_source_cache_kind(
            key, source_payload,
        )
        if kind == "divider":
            return _receiving_cached_bay_box_body_divider(
                self, key, source_payload, render,
            )
        if kind == "frame":
            return _receiving_cached_bay_inner_door_frame(
                self, key, source_payload, render,
            )
        return _receiving_cached_bay_inner_door_panel(
            self, key, source_payload, render,
        )

    request = build_manufacturing_request(
        proxy, scene_payload_builder=lambda key: build_scene_payload_for_app(proxy, key),
        render_data_provider=render_bay_part,
        part_spec_provider=lambda key, payload: app._part_spec_query_callback(key, feature_payload(key, payload)),
        finished_dimensions_provider=dimensions,
    )
    try:
        resolved = resolve(request).geometry
    except ValueError as exc:
        raise ValueError(
            f"RECEIVING_BAY_RESOLVE_SOURCE_DIAGNOSTIC:set={set_index},bay={bay_index}; "
            f"projected_w={snapshot.get('w')!r},h={snapshot.get('h')!r}; "
            f"projected_selection={snapshot.get('_receiving_runtime_selection')!r}; "
            f"cause={exc}"
        ) from exc
    placed = manufacturing_api.project_receiving_bay_preview_assembly_members(
        snapshot["receiving_layout"], resolved.parts,
        set_index=set_index, bay_index=bay_index,
    )
    bay_offset = placed.bay_offset
    parts = tuple(AssemblyScenePart(
        part_key=part.part_key, render_data=part.render_data,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=world_offset,
    ) for part, world_offset in placed.part_placements)
    result = FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(assembly_parts=parts, preserve_endcap_core_origin=True),
        x_profile=(), y_profile=(), part_key="assembly",
        finished_dimensions=dimensions(), thickness=float(snapshot.get("t", 2)),
    )
    if preview_layout is None:
        _retain_committed_receiving_bay_preview(
            cache, cache_key, (fingerprint, result, bay_offset, prefix),
        )
        self._receiving_bay_preview_cache = cache
    else:
        # Small bounded cache prevents every preview-version switch from
        # repeating the real FinalScene solve. Fingerprint invalidates drafts.
        virtual_cache[virtual_key] = result
        while len(virtual_cache) > 8:
            virtual_cache.pop(next(iter(virtual_cache)))
        self._receiving_bay_virtual_preview_cache = virtual_cache
    return result

def receiving_layer_preview_payload(self, namespace, layer_index):
    """每連獨立 canonical request；顯示不改製造 precision 或持久化。"""
    switch = self.receiving_switch_adapter(namespace)
    index = int(layer_index)
    count = switch.connection_count(index)
    requests = tuple(self.receiving_bay_preview_request(namespace, index, i) for i in range(count))
    return {
        "connection_count": count,
        "render_request": requests[0],
        "lock_circles": (),
        "assembly_part_keys": tuple(part.part_key for part in requests[0].render_data.assembly_parts),
        "bay_requests": requests,
    }

def receiving_settings_ports(self, namespace, set_index):
    adapter = self.receiving_adapter(namespace)
    adapter.select_set(set_index + 1)

    listeners = []
    def commit():
        self.app._phase6_input_snapshot["receiving_layout"] = adapter.layout
        self.sync_receiving_current_bay(namespace)
        self.app.submit_update_intent("geometry", commit=True)
        for listener in tuple(listeners):
            listener()

    def selected(index):
        adapter.select_bay(index + 1)

    def change(kind, value, indices=None):
        # No explicitly highlighted Bay means no edit. Omitted indices keeps
        # compatibility for the direct one-Bay editor, not the multi GUI.
        targets = ((adapter.selection.bay_index,) if indices is None
                   else tuple(indices))
        if not targets:
            return False
        # One operator Apply is one canonical Engine transaction.  Do not
        # update earlier Bays or move the selection before validating every
        # highlighted physical target.
        adapter.apply_setting_to_bays(kind, value, targets)
        commit()
        return True

    def share(kind, indices):
        adapter.share_setting(kind, indices)
        commit()

    def unlink(kind):
        adapter.unlink_setting(kind)
        commit()

    def dimensions(width, height, depth, door_columns=None):
        changes = {"width": width, "height": height, "depth": depth}
        if door_columns is not None:
            # Validate raw physical Door W/H using the public Engine boundary
            # before changing a Bay or recording any GUI commit.
            manufacturing_api.door_layout_cells(
                door_columns, total_width=width, total_height=height,
            )
            door_state = deepcopy(adapter.current_bay().get("door_state", {}))
            door_state["door_layout_columns"] = [[w, list(heights)] for w, heights in door_columns]
            door_state["multi_door_enabled"] = True
            changes["door_state"] = door_state
        adapter.update_current_bay(**changes)
        commit()

    def alignment(index, depth, height):
        adapter.update_joint_alignment(index, depth_alignment=depth, height_alignment=height)
        commit()

    def brand(value):
        adapter.set_brand(value)
        commit()

    def holes(role, indices=None):
        if indices is not None and not tuple(indices):
            return False
        # Engine owns the selected Bay's physical finished face, source
        # features and reference dimensions; GUI retains Session and sharing.
        context = manufacturing_api.project_receiving_endcap_hole_editor_context(
            self.app._phase6_input_snapshot, adapter.layout,
            set_index=set_index, bay_index=adapter.selection.bay_index, role=role,
        )
        features = context.features
        host = getattr(self.app._scene_query_callback, "__self__", None)
        if host is None or not hasattr(host, "_open_unified_hole_editor"):
            raise ValueError("目前未連接既有 Hole Editor")
        def save_features():
            kind = f"{role}_features"
            current = adapter.selection.bay_index
            targets = (current,) if indices is None else tuple(indices)
            if len(targets) > 1:
                adapter.select_bay(targets[0] + 1)
                adapter.share_setting(kind, targets)
            adapter.update_setting(kind, features)
            adapter.select_bay(current + 1)
            commit()

        host._open_unified_hole_editor(
            role, "封頭" if role == "head" else "封尾",
            context.surface, context.width, context.depth,
            feature_list_override=features,
            sync_callback=save_features,
            reference_guide=context.reference_guide,
        )

    return {
        "row": lambda: adapter.layout["sets"][set_index],
        "select": selected, "change": change, "share": share, "unlink": unlink,
        "dimensions": dimensions, "alignment": alignment, "brand": brand, "holes": holes,
        "subscribe": listeners.append,
    }

def open_receiving_layer_preview(self, namespace, layer_index):
    app = self.app
    required = lambda name: self._required(namespace, name)
    if getattr(app, "receiving_layer_controls", None) is None:
        return False
    switch = self.receiving_switch_adapter(namespace)
    index, brand = int(layer_index), switch.brand
    original = required("original")
    try:
        preview = self.receiving_layer_preview_payload(namespace, index)
    except Exception as exc:
        from tkinter import messagebox
        messagebox.showwarning(
            "2D 預覽失敗",
            str(exc),
            parent=getattr(app, "root", None),
        )
        return False
    return required("open_receiving_layer_preview")(
        app.root,
        tk=original.tk,
        ttk=original.ttk,
        layer_index=index,
        connection_count=preview["connection_count"],
        brand=brand,
        render_request=preview["render_request"],
        lock_circles=preview["lock_circles"],
        settings_ports=self.receiving_settings_ports(namespace, index),
        bay_requests=preview["bay_requests"],
        bay_request_provider=lambda: tuple(self.receiving_bay_preview_request(namespace, index, i) for i in range(preview["connection_count"])),
    )

def settings_panel(self, namespace):
    """Construct the Settings presentation owner through the composition root."""
    app = self.app
    current = getattr(app, "settings_panel", None)
    if current is not None:
        self._settings_panel = current
        return current
    if self._settings_panel is not None:
        return self._settings_panel

    required = lambda name: self._required(namespace, name)
    query = getattr(app, "_baseline_data_query_callback", None)

    def receiving_base_plate_for_current_mode(config):
        # In quantity mode the synthetic current Set/Bay and top-level input
        # aliases are rebuilt from receiving_quantity_box after every redraw.
        # Committing only the root alias loses this physical source and
        # silently falls back to the generic single Base Plate. Reuse the
        # original source/slot transaction on a detached copy, then update
        # the actual quantity common-box owner atomically with the same
        # mode navigation transaction used by other receiving edits.
        if app.designer_workspace.active_mode == "quantity":
            candidate = _current_mode_snapshot(self, namespace)
            commit_receiving_base_plate_settings(
                input_snapshot=candidate,
                settings_values=app._settings_values,
                submit_geometry_update=lambda: None,
                config=config,
            )
            source = manufacturing_api.update_common_box(
                candidate, {"receiving_base_plate": config},
            )
            _apply_mode_snapshot(self, namespace, source)
            return deepcopy(source.get("receiving_base_plate"))
        return commit_receiving_base_plate_settings(
            input_snapshot=app._phase6_input_snapshot,
            settings_values=app._settings_values,
            submit_geometry_update=lambda: app.submit_update_intent(
                "geometry", commit=True,
            ),
            config=config,
        )

    def commit_vault_panel_name(name):
        from ae_engine import manufacturing_api
        if str(app.baseline_model_var.get() or "").strip() != "金庫型":
            raise ValueError("只有金庫型單箱入口可以編輯此盤名")
        source = app._phase6_input_snapshot
        candidate = manufacturing_api.set_cabinet_panel_name(source, name)
        source.update(candidate)
        # Label-only input: no manufacturing solve or preview invalidation.
        return candidate["panel_name"]

    panel = Phase6SettingsPanel(
        values_snapshot=lambda: dict(app._settings_values),
        stage_setting_update=lambda key, value: self.stage_setting_update(
            namespace, key, value
        ),
        flush_settings=lambda: self.flush_pending_settings(namespace),
        save_defaults=lambda context: self.save_settings_context_as_defaults(
            namespace, context
        ),
        query_baseline_rows=(
            (lambda context, model, values: query(context, model, values))
            if query is not None
            else None
        ),
        is_unknown_baseline=lambda model: required(
            "_phase6_is_unknown_baseline"
        )(app, model),
        should_show_baseline_data=lambda context, specs: required(
            "_phase6_should_show_baseline_data"
        )(app, context, specs),
        part_labels=required("PART_LABELS"),
        context_extension_projection=lambda context: self.settings_context_extension_projection(
            namespace, context
        ),
        receiving_base_plate_commit=receiving_base_plate_for_current_mode,
        endcap_fw_value_selected=lambda part_key, value_var: required(
            "_phase6_on_endcap_fw_value_selected"
        )(app, part_key, value_var),
        box_structure_numeric_changed=lambda type_id, field, value_var: required(
            "_phase6_apply_box_structure_numeric"
        )(app, type_id, field, value_var),
        box_back_panel_mode_changed=lambda value_var: self.select_back_panel_mode(
            namespace, value_var
        ),
        box_structure_toggle_advanced=lambda type_id: required(
            "_phase6_toggle_structure_advanced"
        )(app, type_id),
        bottom_wrap_commit=lambda part_key, reserve_u_var, reserve_v_var: required(
            "_phase6_commit_receiving_bottom_wrap_controls"
        )(app, part_key, reserve_u_var, reserve_v_var),
        corner_pair_changed=lambda part_key, pair_key, var: self.corner_pair_var_changed(
            namespace, part_key, pair_key, var
        ),
        corner_type_selected=lambda part_key, target_key: self.corner_type_selected(
            namespace, part_key, target_key
        ),
        corner_mode_selected=lambda part_key, target_key: self.corner_mode_selected(
            namespace, part_key, target_key
        ),
        corner_target_changed=lambda part_key, target_key: self.corner_target_var_changed(
            namespace, part_key, target_key
        ),
        sync_context_extension=lambda state, context: self.sync_settings_panel_extension(
            namespace, state, context
        ),
        baseline_model_changed=lambda: self.on_baseline_model_changed(
            namespace
        ),
        ui_text_size_changed=lambda key: self.apply_ui_text_size(
            namespace, key
        ),
        panel_name_getter=lambda: str(
            app._phase6_input_snapshot.get("panel_name") or ""
        ),
        panel_name_changed=lambda name: commit_vault_panel_name(name),
    )
    self._settings_panel = panel
    app.settings_panel = panel
    return panel


def _current_mode_snapshot(self, namespace):
    source = deepcopy(self.app._phase6_input_snapshot)
    source.update(deepcopy(self.app._settings_values))
    source.update(deepcopy(self.app._phase6_box_whd))
    source.update(deepcopy(self.corner_transaction_payload(namespace)))
    source["endcap_bottom_wrap"] = deepcopy(self.app._phase6_endcap_bottom_wrap_state)
    workspace = self.collect_workspace_state(namespace)
    source.update(deepcopy(workspace))
    source["workspace"] = deepcopy(workspace)
    source["model"] = "受電箱"
    return source


def _apply_mode_snapshot(self, namespace, source, *, require_committed=False):
    """Apply validated inputs through the existing workspace/profile owners."""
    from phase6_fold_profiles import build_box_body_profile, clone_profile
    app = self.app
    scheduler = app._phase6_update_scheduler
    previous_defer_publish = getattr(app, "_phase6_defer_input_publish", False)
    app._phase6_defer_input_publish = True
    scheduler.begin()
    try:
        navigation = self.capabilities.workspace.navigation()
        navigation.replace_receiving_mode(source)
        app._phase6_input_snapshot.clear()
        app._phase6_input_snapshot.update(deepcopy(source))
        self.settings_transactions().restore_common_context(source)
        # Receiving single/Set-Bay dimensions are project-local operator
        # inputs. Settings W/H/D are *default seeds*, not the working Bay
        # dimensions. Never reverse-publish confirmed operator sizes into the
        # Settings defaults (and then accidentally persist them to config.ini).
        # Other Family Settings such as T/FW still follow the usual owner.
        settings = {
            key: (value if key in ("w", "h", "d") else source.get(key, value))
            for key, value in app._settings_values.items()
        }
        app._settings_values.clear()
        app._settings_values.update(settings)
        app._phase6_box_whd.clear()
        app._phase6_box_whd.update({axis: source[axis] for axis in ("w", "h", "d")})
        app.state.profiles_vault["箱身"] = clone_profile(source.get("box_body_profile") or build_box_body_profile(source))
        app.active_part_key = None
        self.receiving_adapter(namespace, reset=True)
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        self.refresh_profiles_from_settings(namespace, render=False)
        app.activate_part(source.get("active_part") or "box_body", initial=True)
        self.refresh_receiving_set_bay_control(namespace)
        app.submit_update_intent("geometry", commit=True)
    finally:
        previous_executor = scheduler.executor
        def execute_with_committed_receiving_geometry(reasons):
            result = previous_executor(reasons)
            # A 2D/3D view update may leave the Manufacturing receipt at the
            # previous Set/Bay. Resolve only when its semantic signature differs,
            # within the same single Scheduler calculation flush. Never treat a
            # display-only mesh as evidence of a committed manufacturing result.
            from phase6_manufacturing_adapter import (
                build_manufacturing_cache_key, resolve_for_app,
            )
            current = build_manufacturing_cache_key(app).fingerprint
            if current != getattr(app, "_phase6_last_resolved_manufacturing_signature", None):
                try:
                    resolve_for_app(app)
                except ValueError as exc:
                    if require_committed:
                        raise
                    app.settings_status_var.set(str(exc))
            return result
        scheduler.executor = execute_with_committed_receiving_geometry
        try:
            scheduler.end()
            scheduler.flush_now()
        finally:
            scheduler.executor = previous_executor
            app._phase6_defer_input_publish = previous_defer_publish
    if require_committed:
        from phase6_manufacturing_adapter import build_manufacturing_cache_key
        if build_manufacturing_cache_key(app).fingerprint != getattr(app, "_phase6_last_resolved_manufacturing_signature", None):
            raise ValueError("新箱體製造幾何未完成，原模式已保留")
    self.publish_live_state(namespace)


def _switch_mode(self, namespace, target):
    from phase6_receiving_modes import ReceivingModeSession
    from shapely.errors import GEOSException
    from tkinter import messagebox
    app = self.app
    source = _current_mode_snapshot(self, namespace)
    host = getattr(app._scene_query_callback, "__self__", None)
    owner = getattr(host, "workspace_controller", None)
    session = owner.receiving_mode_session(source) if owner is not None else getattr(self, "_receiving_mode_session", None)
    if session is None:
        session = ReceivingModeSession(source)
    dimensions = None
    initializing = session.needs_initialization(target)
    if initializing:
        # Fresh mode data uses Receiving Family defaults (800x1600x350).
        # There is no operator-facing initialization dialog. Returning to an
        # existing session still restores that session's original dimensions.
        dimensions = manufacturing_api.receiving_default_box_dimensions()
    source = _current_mode_snapshot(self, namespace)
    planned = deepcopy(session)
    was_dirty = app.designer_workspace.dirty
    original_workspace = deepcopy(app.designer_workspace.snapshot())
    applying = False
    try:
        changed = planned.switch(target, dimensions=dimensions, current_snapshot=source)
        if not changed:
            return False
        applying = True
        _apply_mode_snapshot(self, namespace, planned.snapshot(), require_committed=initializing)
    except (ValueError, RuntimeError, OSError, OverflowError, GEOSException) as exc:
        if applying:
            _apply_mode_snapshot(self, namespace, source)
            # A failed first-time new mode must leave the PREVIOUS physical
            # workspace byte-for-byte intact, including currently empty or
            # operator-edited native inner-door Features. Reprojecting the
            # previous Bay alone can silently materialize a second CSV
            # opening into the visible workspace after a failed transaction.
            restored_owner = deepcopy(source)
            restored_owner.update(deepcopy(original_workspace))
            self.capabilities.workspace.navigation().replace_receiving_mode(
                restored_owner,
            )
            if not was_dirty:
                app.designer_workspace.mark_clean()
        messagebox.showwarning("模式未切換", str(exc), parent=app.root)
        self.refresh_receiving_set_bay_control(namespace)
        return False
    if owner is not None:
        owner.adopt_receiving_mode_session(planned)
    else:
        self._receiving_mode_session = planned
    return True


def _common_preview_request(self, namespace):
    """Read committed physical-sheet drawings; the caller is a Scheduler."""
    from phase6_manufacturing_adapter import build_manufacturing_cache_key, resolve_for_app
    manufacturing_api.require_valid_operator_quantity_features(
        _current_mode_snapshot(self, namespace)
    )
    signature = build_manufacturing_cache_key(self.app).fingerprint
    if signature != getattr(self.app, "_phase6_last_resolved_manufacturing_signature", None):
        # The operator may open Common Box just after a mode switch or a
        # Save/Reload, before a manufacturing receipt for this exact snapshot
        # has been cached. Resolve from current committed inputs, not stale
        # Set/Bay geometry; keep errors visible rather than displaying old parts.
        resolve_for_app(self.app)
        if signature != getattr(self.app, "_phase6_last_resolved_manufacturing_signature", None):
            raise ValueError("共用箱體預覽尚未對應目前已提交設定")
    geometry = getattr(self.app, "_phase6_last_resolved_manufacturing_geometry", None)
    if geometry is None:
        raise ValueError("共用箱體製造結果尚未完成")
    parts = tuple(AssemblyScenePart(
        part_key=part.part_key, render_data=part.render_data,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=part.offset,
    ) for part in geometry.parts if part.placement != "standalone")
    return FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(assembly_parts=parts, preserve_endcap_core_origin=True),
        x_profile=(), y_profile=(), part_key="assembly",
        finished_dimensions=tuple(self.app._phase6_box_whd[axis] for axis in ("w", "h", "d")),
        thickness=float(self.app._phase6_input_snapshot.get("t", 2)),
    )


def _open_common_box(self, namespace):
    from .receiving_set_bay_controls import open_receiving_layer_preview
    from .command_router import _Phase6UpdateScheduler
    app = self.app
    # Do not construct a common box from unrelated Set/Bay values: the owner
    # requires explicit quantity-mode initialization before any edit.
    try:
        box = manufacturing_api.normalize_common_box(_current_mode_snapshot(self, namespace).get(manufacturing_api.RECEIVING_QUANTITY_BOX_KEY))
    except ValueError as exc:
        from tkinter import messagebox
        messagebox.showwarning("共用箱體尚未初始化", str(exc), parent=app.root)
        return False
    listeners = []
    def change_common(changes):
        source = _current_mode_snapshot(self, namespace)
        candidate = manufacturing_api.update_common_box(source, changes)
        _apply_mode_snapshot(self, namespace, candidate)
        from .receiving_settings_preview_2d import CommittedPreviewError
        for listener in tuple(listeners):
            try:
                listener()
            except CommittedPreviewError:
                # The committed edit is valid but its current NFB source may
                # require model reselection. The view already invalidated all
                # stale geometry and reported the exact reason. Keep Common
                # Box editable for repair; never turn this into a manufacturing
                # receipt or silently re-use the previous drawing.
                continue
    def dimensions(width, height, depth, door_columns=None):
        changes = {"w": width, "h": height, "d": depth}
        if door_columns is not None:
            door = deepcopy(box.get("door_state", {}))
            door["door_layout_columns"] = [[w, list(hs)] for w, hs in door_columns]
            changes["door_state"] = door
        change_common(changes)
    ports = {
        "row": lambda: manufacturing_api.project_common_box(_current_mode_snapshot(self, namespace))["receiving_layout"]["sets"][0],
        "select": lambda index: None,
        "change": lambda kind, value, indices=(): change_common({kind: value}),
        "dimensions": dimensions,
        "brand": lambda value: change_common({"switch_brand": value}),
        "subscribe": listeners.append,
    }
    def show(reasons):
        preview_error = None
        try:
            request = _common_preview_request(self, namespace)
        except ValueError as exc:
            request, preview_error = None, str(exc)
        return open_receiving_layer_preview(
            app.root, tk=tk, ttk=self._required(namespace, "original").ttk,
            layer_index=0, connection_count=1,
            brand=manufacturing_api.normalize_common_box(_current_mode_snapshot(self, namespace).get(manufacturing_api.RECEIVING_QUANTITY_BOX_KEY))["switch_brand"],
            render_request=request, preview_error=preview_error, settings_ports=ports,
            bay_request_provider=lambda: (_common_preview_request(self, namespace),),
            common_box=True,
        )
    scheduler = _Phase6UpdateScheduler(app, executor=show)
    scheduler.submit("display", immediate=True)
    return True


def _refresh_mode_controls(self, namespace):
    from .receiving_mode_controls import build_mode_controls
    from .quantity_version_ports import quantity_ports
    app = self.app
    controls = getattr(self, "_receiving_mode_controls", None)
    applicable = self.receiving_layout_applicable()
    if controls is None:
        controls = build_mode_controls(
            app.receiving_set_bay_control.master,
            on_switch=lambda target: _switch_mode(self, namespace, target),
            on_common=lambda: _open_common_box(self, namespace) if self.receiving_layout_applicable() else self.settings_panel(namespace).render_context("box_body"),
            quantity_ports=quantity_ports(self, namespace),
        )
        self._receiving_mode_controls = controls
        app.receiving_mode_controls = controls
    if controls is None:
        return False
    if applicable:
        controls.mode_row.pack(fill=tk.X, before=controls.common_button if controls.common_button.winfo_manager() else controls.quantity_editor.frame if controls.quantity_editor.frame.winfo_manager() else None)
    else:
        controls.mode_row.pack_forget()
    controls.refresh(app.designer_workspace.snapshot().get("active_mode", "set_bay"),
                     app.designer_workspace.snapshot().get("quantity"))
    before = app.receiving_set_bay_control if app.receiving_set_bay_control.winfo_manager() else app.bend_ui.nb
    options = {"fill": tk.X, "pady": (0, 4)}
    if before.winfo_manager() and before.master is controls.frame.master:
        options["before"] = before
    # Preserve the original quantity editor for non-Receiving families.
    # Receiving's operator entry is only the Assembly multi-settings dialog.
    if applicable:
        controls.frame.pack_forget()
    else:
        controls.frame.pack(**options)
    return True


def open_receiving_multi_settings(self, namespace, *, single=False, embedded_inner_parent=None):
    """Route one Assembly dialog to existing Set/Bay and quantity owners."""
    if not self.receiving_layout_applicable():
        return False
    from .receiving_multi_settings_window import open_multi_settings
    # Verified source/panel evidence is per currently edited Set/Bay, ephemeral.
    # Nothing here is saved to the project or allowed to bypass #1500.
    # Reuse session-only verification between the embedded Hole Editor tab
    # and Multi-connection operator view. Every consumer still revalidates
    # the exact saved Bay/source before manufacturing actions.
    evidence = getattr(self.app, "_receiving_nfb_ui_session_evidence", None)
    if evidence is None:
        evidence = {"pending": {}, "committed": {}}
        self.app._receiving_nfb_ui_session_evidence = evidence
    pending_verified_nfb = evidence["pending"]
    committed_nfb_evidence = evidence["committed"]  # NEVER serialized
    # Only exact operator-export receipts; not a saved MFG-1 capability.
    verified_pair_exports = evidence.setdefault("verified_pair_exports", {})

    def nfb_physical_bay_snapshot(set_index,bay_index):
        """Real selected Bay authority, not the unprojected root UI snapshot."""
        source=_current_mode_snapshot(self,namespace)
        source["receiving_layout"]=candidate_adapter().layout
        return manufacturing_api.project_receiving_bay_legacy_aliases(
            source,set_index=set_index,bay_index=bay_index,
        )

    def select_bay(set_index, bay_index):
        # Reuse canonical selection; no new data owner or manufacturing draw.
        adapter = self.receiving_adapter(namespace)
        adapter.select_set(int(set_index) + 1)
        adapter.select_bay(int(bay_index) + 1)

    def rename_bay(set_index, bay_index, name):
        adapter = self.receiving_adapter(namespace)
        changed = adapter.rename_bay(int(set_index), int(bay_index), name)
        if changed:
            # GUI only updates the authoritative source DTO. A text-only rename
            # must not invalidate or rebuild FinalScene manufacturing geometry.
            self.mark_receiving_switch_layout_dirty(namespace, adapter)
        return changed

    def select_existing_setting(set_index, bay_index, kind):
        """Bind the list choice to the original per-bay setting value/owner.

        No editor popup, duplicated parser, or manufacturing calculation is
        initiated merely by selecting a category in the Listbox.
        """
        ports = self.receiving_settings_ports(namespace, int(set_index))
        ports["select"](int(bay_index))
        return _receiving_setting_value(ports["row"](), int(bay_index), kind)

    def single_brand():
        # Quantity's selected version owns the parent; no Tk-side model policy.
        return manufacturing_api.project_receiving_quantity_nfb_parent_brand(
            _current_mode_snapshot(self, namespace),
        )

    def set_single_brand(value):
        candidate, changed = manufacturing_api.update_receiving_quantity_nfb_parent_brand(
            _current_mode_snapshot(self, namespace), value,
        )
        if changed:
            _apply_mode_snapshot(self, namespace, candidate)
        return changed

    def preview_parent_brand_impact(value):
        # Operator chooses the scope; only Engine may count physical NFB slots.
        source = (_current_mode_snapshot(self, namespace)
                  if single else self.receiving_adapter(namespace).layout)
        return manufacturing_api.project_receiving_parent_brand_change_impact(
            source, value, mode="quantity" if single else "set_bay",
        )

    def set_global_brand(value):
        # The original Receiving layout is the one NFB authority. In the
        # modal, edit data only; geometry rebuild on ComboboxSelected blocks
        # Tk's UI thread (noticeably on the first selection).
        adapter = self.receiving_adapter(namespace)
        if not adapter.set_global_brand(value):
            return False
        self.mark_receiving_switch_layout_dirty(namespace, adapter)
        return True

    def current_nfb_parent_brand():
        """The SAME Set→layer→unit inheritance uses the active mode's owner.

        Set/Bay reads the existing Set brand; Quantity reads its selected
        version NFB parent. Historical common-box brand is migration-only.
        Every saved V5 hole keeps its original source/override identity.
        """
        if _current_mode_snapshot(self, namespace).get("active_mode") == "quantity":
            return single_brand()
        return self.receiving_switch_adapter(namespace).brand

    def finalize_global_brand():
        # After the modal has closed, project and submit once for the latest
        # selected brand. The operator can change brands without a 3D reload.
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        self.app.submit_update_intent("geometry", commit=True)

    def existing_door_marks(set_index, bay_index):
        # The baseline scene owner is GUI; selection of physical Bay cells is Engine.
        from .receiving_multi_settings_window import extract_original_door_marks

        host = getattr(self.app._scene_query_callback, "__self__", None)
        if host is None or not hasattr(host, "_door_layout_baseline_scene"):
            return ()
        snapshot = dict(self.app._phase6_input_snapshot)
        snapshot["receiving_layout"] = self.receiving_adapter(namespace).layout
        selection = manufacturing_api.project_receiving_operator_door_cell_sources(
            snapshot, set_index=int(set_index), bay_index=int(bay_index),
        )
        if selection is None:
            return ()
        projected, cells = selection
        result = []
        for cell in cells:
            scene, _status = host._door_layout_baseline_scene(cell, projected)
            if scene is None:
                return ()
            result.append(extract_original_door_marks(scene))
        return tuple(result)

    def cached_initial_door_marks():
        """Only draw the exact Engine-identified Door pair from committed Assembly."""
        from .receiving_multi_settings_window import extract_original_door_marks

        scenes = manufacturing_api.project_receiving_initial_door_source_scenes(
            self.app._phase6_input_snapshot,
            getattr(self.app, "_phase6_last_resolved_manufacturing_geometry", None),
        )
        if not scenes:
            return ()
        return (tuple(extract_original_door_marks(scene) for scene in scenes),)

    def resize_sets(delta):
        switch = self.receiving_switch_adapter(namespace)
        if delta > 0:
            switch.add_layer()
        elif delta < 0 and not switch.remove_layer():
            return False
        elif delta == 0:
            return False
        self.mark_receiving_switch_layout_dirty(namespace, switch)
        return True

    def dimension_group(set_index, highlighted, width, height, depth, count):
        adapter = self.receiving_adapter(namespace)
        changed = adapter.apply_dimensions_to_bays(
            set_index, highlighted, width=width, height=height, depth=depth,
            expected_count=count,
        )
        if changed:
            # This exact operator action changes only W/H/D inputs. Keep raw
            # certified PartSpec material for unrelated Bays, but invalidate
            # all assembled geometry as usual. The manufacturing solver still
            # rechecks placement, Joint relief and collision on the new state.
            derived = getattr(self.app, "_derived_cache_owner", None)
            if derived is not None:
                derived.invalidate("geometry", changed_keys=("w", "h", "d"))
            self.mark_receiving_switch_layout_dirty(namespace, adapter)
            self.sync_receiving_current_bay(namespace, refresh_controls=False)
            # One modal confirmation only stages manufacturing. Actual
            # assembly/Joint solve belongs to the final close boundary;
            # Save/Export flush_now() can still force it early, fail-closed.
            self.app._phase6_update_scheduler.stage("geometry")
        return changed

    def single_size_quantity():
        from phase6_quantity_model import QuantityModel
        snapshot = _current_mode_snapshot(self, namespace)
        if snapshot.get("active_mode") != "quantity":
            raise ValueError("單只設定必須使用單箱體數量模式")
        box = manufacturing_api.normalize_common_box(snapshot.get("receiving_quantity_box"))
        model = QuantityModel.from_payload(snapshot.get("quantity"))
        return {"width": box["w"], "height": box["h"], "depth": box["d"],
                "count": model.selected_piece_count,
                "total_count": model.total_piece_count,
                "version_count": model.version_count}

    def set_single_size_quantity(width, height, depth, count):
        from phase6_quantity_model import QuantityModel, positive_piece_count
        new_count = positive_piece_count(count)
        snapshot = _current_mode_snapshot(self, namespace)
        if snapshot.get("active_mode") != "quantity":
            raise ValueError("單只設定必須使用單箱體數量模式")
        model = QuantityModel.from_payload(snapshot.get("quantity"))
        model.set_piece_count(new_count)
        candidate = manufacturing_api.update_common_box(snapshot, {"w": width, "h": height, "d": depth})
        candidate["quantity"] = model.snapshot()
        manufacturing_api.require_valid_operator_quantity_features(candidate)
        _apply_mode_snapshot(self, namespace, candidate)
        return True

    def edit_single_holes(role):
        from .quantity_version_ports import quantity_ports
        return quantity_ports(self, namespace)["holes"](role)

    # Candidate versions are project-wide and separate from QuantityModel and
    # per-Bay shared settings.  Only Apply copies a candidate into highlighted
    # receiving_layout Bays.
    from ae_engine.receiving_hole_candidates import (
        candidates_for, candidate_features, create_candidate, update_candidate,
        delete_candidate, duplicate_candidate, normalize_candidates,
    )
    def candidate_adapter():
        return self.receiving_adapter(namespace)

    def candidate_library():
        # A single project-level authority survives mode switches and Save.
        # It is neither part of any Set/Bay nor the QuantityModel.
        return normalize_candidates(
            self.app._phase6_input_snapshot.get("receiving_hole_candidates")
        )

    def persist_candidates(library):
        self.app._phase6_input_snapshot["receiving_hole_candidates"] = (
            normalize_candidates(library)
        )
        workspace = getattr(self.app, "designer_workspace", None)
        if workspace is not None:
            workspace.mark_dirty()

    def edit_candidate(role, version_id, after_saved):
        adapter = candidate_adapter()
        original = candidate_library()
        # An editor opens on the active Bay's finished face as a coordinate
        # guide, but its candidate data has no Bay assignment until Apply.
        bay = adapter.current_bay()
        geometry = manufacturing_api.project_operator_hole_editor_endcap(
            role, width=bay["width"], depth=bay["depth"],
            thickness=self.app._phase6_input_snapshot.get("t", 2),
        )
        draft = [] if version_id is None else candidate_features(original, role, version_id)
        host = getattr(self.app._scene_query_callback, "__self__", None)
        if host is None or not hasattr(host, "_open_unified_hole_editor"):
            raise ValueError("目前未連接既有 Hole Editor")

        def confirmed():
            # The Hole Editor's preview-sync fires on BOTH Confirm and Cancel.
            # Persist ONLY from its new Confirm-only transaction callback.
            latest = candidate_library()
            if version_id is None:
                saved, selected = create_candidate(latest, role, draft)
            else:
                saved = update_candidate(latest, role, version_id, draft)
                selected = version_id
            persist_candidates(saved)
            after_saved(selected)

        return host._open_unified_hole_editor(
            role, "封頭" if role == "head" else "封尾",
            geometry.surface, geometry.width, geometry.height,
            feature_list_override=draft,
            sync_callback=lambda: None,
            on_confirm=confirmed,
            reference_guide=geometry.reference_guide,
        )

    def copy_candidate(role, version_id, destination):
        library, created = duplicate_candidate(
            candidate_library(), role, version_id, destination
        )
        persist_candidates(library)
        return created

    def remove_candidate(role, version_id):
        library = delete_candidate(
            candidate_library(), role, version_id
        )
        persist_candidates(library)

    def apply_candidate(role, version_id, set_index, highlighted):
        if version_id is None or not highlighted:
            raise ValueError("請選擇候選版本及簡易圖高亮的連")
        adapter = candidate_adapter()
        features = candidate_features(candidate_library(), role, version_id)
        # Submit the original highlighted physical Bay identities unchanged.
        # The Engine transaction validates every index before any mutation:
        # GUI set(highlighted) would turn (1, True) into a valid-looking (1,)
        # and bypass the Engine's explicit rejection of boolean Bay aliases.
        adapter.apply_candidate_to_bays(
            role, set_index, highlighted, features, version_id=version_id,
        )
        self.mark_receiving_switch_layout_dirty(namespace, adapter)
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        self.app.submit_update_intent("geometry", commit=True)
        return True

    def apply_quantity_configuration(role, quantities, assigned, expected_counts):
        adapter = candidate_adapter()
        result = adapter.apply_quantity_configuration(
            role, candidate_library(), quantities, assigned,
            expected_counts=expected_counts,
        )
        self.mark_receiving_switch_layout_dirty(namespace, adapter)
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        self.app.submit_update_intent("geometry", commit=True)
        return result

    def apply_live_label(role, set_index, highlighted):
        """Tag the existing physical config 即時; no candidate or geometry mutation."""
        adapter = candidate_adapter()
        applied_bays = adapter.mark_live_version_for_bays(role, set_index, highlighted)
        self.mark_receiving_switch_layout_dirty(namespace, adapter)
        # A display-label mutation must never rebuild FinalScene.
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        return applied_bays

    def candidate_ports():
        return {
            "versions": lambda role: candidates_for(candidate_library(), role),
            "edit": edit_candidate,
            "copy": copy_candidate,
            "delete": remove_candidate,
            "apply": apply_candidate,
            "apply_live": apply_live_label,
            "apply_quantity": apply_quantity_configuration,
        }

    # Independent inner-door candidate data. It shares the UX mechanics with
    # endcaps, but never reads/writes receiving_hole_candidates or QuantityModel.
    from ae_engine.receiving_inner_door_candidates import (
        KEY as INNER_KEY, ROLE as INNER_ROLE,
        normalize_inner_candidates, inner_versions, inner_config,
        create_inner_candidate, update_inner_candidate,
        delete_inner_candidate, duplicate_inner_candidate,
    )
    from ae_engine.receiving_switch_model_catalog import INDEX_PATH
    from ae_engine.receiving_nfb_model_identity import (
        display_model_ref, validate_stored_model_ref,
    )
    from ae_engine.receiving_nfb_numeric_catalog import brand_csv_path

    def inner_library():
        return normalize_inner_candidates(
            self.app._phase6_input_snapshot.get(INNER_KEY)
        )

    def persist_inner(library):
        self.app._phase6_input_snapshot[INNER_KEY] = (
            normalize_inner_candidates(library)
        )
        workspace = getattr(self.app, "designer_workspace", None)
        if workspace is not None:
            workspace.mark_dirty()

    def inner_edit(role, version_id, after_saved, *, embed_parent=None,
                   after_closed=None):
        if role != INNER_ROLE:
            raise ValueError("內門版本權責錯誤")
        from tkinter import ttk, messagebox
        import tkinter as tk
        operator_brand_choices = manufacturing_api.receiving_operator_switch_brand_choices()
        from .receiving_nfb_source_preview import NfbDxfSourcePreviewPanel
        from ae_engine.receiving_nfb_ui1a_edits import (
            NfbUi1aEditSession, editable_nfb_draft, insert_nfb_slot,
            delete_nfb_slot, move_nfb_slot, replace_nfb_slot_model,
            set_nfb_manual_x, set_nfb_layer_rotation,
            set_nfb_slot_rotation, effective_nfb_rotation,
            nfb_x_reset_impact,
        )
        from ae_engine.receiving_nfb_brand_transition import (
            draft_new_reselections,
        )
        from ae_engine.receiving_nfb_ui1a import (
            INHERIT, OVERRIDE, NEEDS_RESELECTION, new_nfb_ui1a_draft,
            reconcile_set_brand, set_nfb_draft_layer_count,
            set_nfb_layer_brand, set_nfb_slot_brand, add_nfb_draft_slot,
            select_nfb_slot_model, remove_nfb_draft_slot,
            effective_nfb_layer_brand, effective_nfb_slot_brand, nfb_ui1a_preview,
        )

        if version_id is None:
            adapter = candidate_adapter()
            set_row = adapter.layout["sets"][adapter.selection.set_index]
            bi = adapter.selection.bay_index
            initial = {
                "layers": _receiving_setting_value(set_row, bi, "inner_door_layers"),
                "models": _receiving_setting_value(set_row, bi, "inner_door_models"),
                "layer_heights_mm": _receiving_setting_value(set_row, bi, "inner_door_layer_heights_mm"),
            }
        else:
            initial = inner_config(inner_library(), version_id)
        if embed_parent is not None:
            owner_editor = embed_parent.winfo_toplevel()
            if self.app.designer_workspace.active_mode == "quantity":
                # Quantity single box is NOT a multi-Bay shared setting.
                # Read its own selected physical box instead of stale Bay UI.
                quantity = _current_mode_snapshot(self, namespace)
                initial = {
                    "layers": quantity.get("receiving_inner_door_layers", 1),
                    "models": quantity.get("receiving_inner_door_models", ["", ""]),
                    "layer_heights_mm": quantity.get(
                        "receiving_inner_door_layer_heights_mm",
                        manufacturing_api.receiving_inner_door_legacy_layer_height_defaults(),
                    ),
                }
            staged = getattr(owner_editor, "_receiving_staged_config", None)
            if staged is not None:
                initial = manufacturing_api.validate_receiving_inner_door_config(staged)
            elif (version_id is None and
                    getattr(owner_editor, "_receiving_settings_mode", None)
                    in ("single", "candidate")):
                # Old saved Set/Bay projects can have two committed CSV
                # model identities but only a one-model UI alias. Restore
                # them as a reversible draft for the SELECTED physical Bay,
                # including a new candidate based on that Bay. Never borrow
                # its physical Features: candidate Confirm All creates only
                # a candidate until explicit highlighted-Bay Apply.
                from ae_engine.receiving_legacy_nfb_editor_bootstrap import (
                    recover_submitted_nfb_models_for_editor,
                )
                source = current_inner_editor_snapshot()
                initial = recover_submitted_nfb_models_for_editor(
                    initial, source,
                )
        if initial.get("layer_heights_mm") is None:
            # Legacy configurations without operator heights keep their
            # previously saved Y until the user explicitly edits the rows.
            initial["layer_heights_mm"] = list(
                manufacturing_api.receiving_inner_door_legacy_layer_height_defaults()
            )
        # Existing drafts retain saved heights; new one-tier initializers use
        # the shared 550 rule, and a two-tier selection uses 330/830.
        # Explicit old-project heights are retained without migration.
        # Fresh Single NFB UI: show one real Shihlin 2P400 by default,
        # sourced from its current CSV. This is only a transient editor
        # draft. A Cancel never persists it; native Confirm All remains the
        # authority for the actual NFB CUTTING source identity.
        # Existing selections, an alternate explicit global brand, and
        # staged edits are never overwritten.
        if embed_parent is not None:
            from ae_engine.receiving_fresh_nfb_defaults import (
                initial_fresh_receiving_nfb_models,
            )
            initial["models"] = initial_fresh_receiving_nfb_models(
                initial["models"],
                layer_count=initial["layers"],
                selected_brand=current_nfb_parent_brand(),
            )
        parent_modal = getattr(self.app.root, "_receiving_multi_settings_window", None)
        from .receiving_inner_door_hole_editor import inner_door_commit_target
        # Read the actual opening editor entry. Stored Set/Bay state and
        # unrelated modal dialogs may NEVER choose the persistence target.
        entry_mode = (getattr(embed_parent.winfo_toplevel(),
                              "_receiving_settings_mode", None)
                      if embed_parent is not None else "candidate")
        direct_to_drawing = inner_door_commit_target(entry_mode) == "physical"
        owner = parent_modal if (parent_modal is not None
                                 and parent_modal.winfo_exists()) else self.app.root
        if embed_parent is None:
            modal = tk.Toplevel(owner)
            modal.title("內門版本編輯")
            modal.transient(owner)
            modal.geometry("820x750")
        else:
            # Use a removable frame so Confirm/Cancel can replace this draft
            # without closing the parent Unified Hole Editor.
            modal = ttk.Frame(embed_parent)
            modal.pack(fill="both", expand=True)
        from .receiving_scroll_view import make_scrollable_frame
        modal_scroll, modal_content, modal_viewport = make_scrollable_frame(
            modal, tk=tk, ttk=ttk, width=790, height=680,
        )
        modal_scroll.pack(fill="both", expand=True)
        frame = ttk.Frame(modal_content, padding=14)
        frame.pack(fill="both", expand=True)
        modal._receiving_editor_scroll = modal_scroll
        ttk.Label(frame, text="內門｜" + ("即時" if version_id is None
                        else manufacturing_api.receiving_candidate_version_label(version_id))).pack(anchor="w")
        # Inner-door layer count IS the NFB mounting tier count. One Tk
        # value drives original candidate data, UI-1A draft and preview.
        # Keep the old name as an alias for stable existing test/GUI ports,
        # never create a second writable tier-count variable.
        layers = tk.IntVar(master=modal, value=initial["layers"])
        nfb_physical_layers = layers
        layer_height_vars = tuple(
            tk.StringVar(master=modal, value=f"{float(v):g}")
            for v in initial["layer_heights_mm"]
        )
        def read_layer_heights():
            try:
                heights = [float(field.get().strip()) for field in layer_height_vars]
            except (TypeError, ValueError) as exc:
                raise ValueError("請輸入有效的第一層、第二層高度（mm）") from exc
            return manufacturing_api.validate_receiving_nfb_layer_heights_for_work_area(
                _current_mode_snapshot(self, namespace), heights,
                layer_count=layers.get(),
            )
        summary_row = ttk.Frame(frame)
        summary_row.pack(fill="x", pady=(4, 6))
        controls = ttk.Frame(summary_row)
        controls.pack(side="left", anchor="n")
        ttk.Label(controls, text="內門版本層數").pack(side="left")
        # No fake inventory thumbnail: true real geometry is shown from the
        # selected version in the separate movable FinalScene window.
        preview_status = tk.StringVar(master=modal)
        ttk.Label(summary_row, textvariable=preview_status).pack(
            side="right", anchor="ne",
        )
        # The retired extra NFB physical-tier row must not be created:
        # the visible inner-door layer selector is the sole writer.
        chosen = [list(manufacturing_api.receiving_nfb_switch_filenames_in_layer(slot))
                  for slot in initial["models"]]
        layer_rows = []
        warning = tk.StringVar(master=modal, value="")
        # UI-1A transient state; NOT persisted to .p6fold and NOT a second
        # ReceivingLayout owner. Existing candidate saving below stays intact.
        # All existing #1491 controls still set draft_state["draft"], but
        # this single transient session captures every edit for #1493 Undo.
        # It does not persist a second Hole Editor/project authority.
        class _NfbDraftState(dict):
            session = None
            def __setitem__(self,key,value):
                if key=="draft" and self.session is not None:
                    self.session.apply("NFB_UI1A_EDIT",lambda _before:value)
                    value=self.session.current
                dict.__setitem__(self,key,value)
        draft_state = _NfbDraftState({"draft": new_nfb_ui1a_draft(
            set_brand=current_nfb_parent_brand(),
            layer_count=nfb_physical_layers.get(), model_layers=initial["models"],
        )})
        edit_session = NfbUi1aEditSession(draft_state["draft"])
        draft_state.session = edit_session
        dict.__setitem__(draft_state,"draft",edit_session.current)
        source_state = {"files": [(), ()], "signature": [None, None]}
        draft_summary = tk.StringVar(master=modal, value="")
        # AC-18: the computed datum/preview-only warning was previously
        # hidden in a StringVar with no Tk display. Show it beside the sole
        # layer-count control, not as another source of configuration.
        ttk.Label(frame, textvariable=draft_summary, wraplength=760,
                  justify="left").pack(fill="x", anchor="w", pady=(0, 3))
        initial_nfb_draft = deepcopy(draft_state["draft"])
        nfb_preview_panel = {"panel": None}
        nfb_source_viewed = {"value": False}

        def show_x_clear_impact(before, layer_index):
            impact = nfb_x_reset_impact(before, draft_state["draft"], layer_index)
            if impact.count:
                warning.set(
                    f"第{layer_index + 1}層已清除 {impact.count} 顆 X 位移／基準快照；"
                    "其他層不變，按「復原 NFB」可還原"
                )
            else:
                warning.set(f"第{layer_index + 1}層沒有 X 位移被清除；其他層不變")
            return impact

        def sync_chosen():
            for layer in range(2):
                chosen[layer][:] = [
                    slot["filename"] for slot in
                    draft_state["draft"]["layers"][layer]["slots"]
                    if slot["filename"] is not None
                ]

        def view_source_catalog(index):
            d = draft_state["draft"]
            row = layer_rows[index]
            sel = row["assigned"].curselection()
            if sel and sel[0] < len(d["layers"][index]["slots"]):
                return effective_nfb_slot_brand(d, index, sel[0])
            return effective_nfb_layer_brand(d, index)

        def paint_draft_preview():
            try:
                staged_heights = read_layer_heights()
            except (ValueError, TypeError, KeyError) as exc:
                preview_status.set(str(exc))
                return
            config = {
                "layer_heights_mm": staged_heights,
                "layers": layers.get(),
                "models": [
                    manufacturing_api.pack_receiving_nfb_switch_layer(chosen[0]),
                    manufacturing_api.pack_receiving_nfb_switch_layer(chosen[1]) if layers.get() == 2 else "",
                ],
            }
            before = {
                "layer_heights_mm": initial["layer_heights_mm"],
                "layers": initial["layers"],
                "models": [
                    manufacturing_api.pack_receiving_nfb_switch_layer(manufacturing_api.receiving_nfb_switch_filenames_in_layer(initial["models"][0])),
                    manufacturing_api.pack_receiving_nfb_switch_layer(manufacturing_api.receiving_nfb_switch_filenames_in_layer(initial["models"][1]))
                    if initial["layers"] == 2 else "",
                ],
            }
            preview_status.set(
                "尚未儲存的變更" if config != before else "與已載入版本相同"
            )
            try:
                adapter = candidate_adapter()
                selection = adapter.selection
                width = adapter.layout["sets"][selection.set_index]["bays"][
                    selection.bay_index]["width"]
                snapshot = _current_mode_snapshot(self, namespace)
                # Same Engine work-area authority as the editor input gate.
                height = manufacturing_api.project_receiving_nfb_work_area_height_mm(
                    snapshot,
                )
                projection = nfb_ui1a_preview(
                    draft_state["draft"], bay_width_mm=width,
                    upper_cell_height_mm=height,
                    layer_heights_mm=staged_heights,
                )
                segments = []
                for entry in projection["layers"]:
                    pitch = entry["adjacent_x_mm"]
                    # Adjacent pitch is never an approved per-unit or
                    # per-row absolute X datum.
                    x_label = ("X 基準未定（相鄰孔距 " +
                               "／".join(f"{p:g}" for p in pitch) + " mm，僅參考）"
                               if pitch is not None else "X 基準未定")
                    y = entry["nominal_y_from_top_mm"]
                    # Entered tier height in a non-1100 work area is useful
                    # to preview, but never licenses a nominal approved Y.
                    y_label = (
                        f"Y 未定（草稿高度 {y:g} mm，未核准定位）"
                        if abs(height - 1100.0) >= 1e-6 and y is not None
                        else (f"名義 Y {y:g} mm（僅預覽）" if y is not None
                              else "Y 未定")
                    )
                    stale = sum(x["status"] == NEEDS_RESELECTION
                                for x in entry["slots"])
                    segments.append(
                        f"第{entry['layer_index']+1}層 {x_label}、{y_label}"
                        + (f"｜{stale} 顆待重選" if stale else "")
                    )
                pad = projection["pad_depth_preview"]
                pad_status = pad["status"]
                if pad_status == "PAD_DIFFERENT_DEPTH_REVIEW_ONLY":
                    candidate = pad["shallower_unit_index"] + 1
                    pad_text = (
                        f"｜墊高候選：第{candidate}顆較淺，"
                        f"深度差 {pad['candidate_delta_mm']:g} mm（未核准墊高實體）"
                    )
                elif pad_status == "PAD_NOT_NEEDED_SAME_DEPTH":
                    pad_text = "｜兩顆深度相同，不需墊高片"
                elif pad_status == "PAD_DEPTH_SOURCE_UNKNOWN":
                    pad_text = "｜兩顆深度未齊：請檢查 CSV「深」欄及品牌來源"
                else:
                    pad_text = ""  # other layer/count configurations never create PAD
                draft_summary.set("｜".join(segments) + pad_text + "｜僅預覽、不提交製造")
            except (ValueError,TypeError,KeyError) as exc:
                draft_summary.set(f"NFB 名義幾何未定：{exc}｜僅預覽")


        def repaint(index):
            entry = layer_rows[index]
            selected = entry["assigned"].curselection()
            entry["assigned"].delete(0, tk.END)
            slots = draft_state["draft"]["layers"][index]["slots"]
            for slot in slots:
                entry["assigned"].insert(
                    tk.END,
                    (display_model_ref(slot["filename"]) if slot["filename"] else "（空槽）")
                )
            if selected and selected[0] < len(slots):
                entry["assigned"].selection_set(selected[0])
            entry["count"].set(
                f"實體 {len(slots)} 槽／開關 {sum(bool(s['filename']) for s in slots)} 顆"
            )
            if "slot_brand_var" in entry:
                selected_now = entry["assigned"].curselection()
                if selected_now:
                    brand_state = slots[selected_now[0]]["brand"]
                    entry["slot_brand_var"].set(
                        "繼承本層" if brand_state["mode"] == INHERIT
                        else brand_state["value"]
                    )
                    # Programmatic Undo/repaint does not emit the Tk listbox
                    # selection event. Never leave a stale X or angle in its
                    # operator field after restoring the prior datum snapshot.
                    selected_slot = slots[selected_now[0]]
                    angle = selected_slot.get("rotation", {"mode": INHERIT, "value": None})
                    entry["unit_rotation_var"].set(
                        "跟隨本層" if angle["mode"] == INHERIT else str(angle["value"])
                    )
                    mm = selected_slot.get("manual_x_mm")
                    entry["manual_x_var"].set("" if mm is None else f"{mm:g}")
                else:
                    entry["slot_brand_var"].set("繼承本層")
                    entry["unit_rotation_var"].set("跟隨本層")
                    entry["manual_x_var"].set("")
            paint_draft_preview()

        def refresh_source(*, force=False):
            if not modal.winfo_exists():
                return
            current_owner = current_nfb_parent_brand()
            if current_owner != draft_state["draft"]["set_brand"]:
                draft_state["draft"] = reconcile_set_brand(
                    draft_state["draft"], current_owner,
                )
            for index, entry in enumerate(layer_rows):
                if index >= draft_state["draft"]["layer_count"]:
                    continue
                brand = view_source_catalog(index)
                try:
                    stat = brand_csv_path(brand).stat()
                    stamp = (stat.st_mtime_ns, stat.st_size)
                except OSError:
                    stamp = (None, None)
                signature = (brand, *stamp)
                if not force and signature == source_state["signature"][index]:
                    continue
                source_state["signature"][index] = signature
                try:
                    files = manufacturing_api.list_receiving_nfb_model_refs(brand)
                except (ValueError,OSError,UnicodeError) as exc:
                    files = ()
                    warning.set("NFB數值規格.csv 讀取失敗：" + str(exc))
                source_state["files"][index] = files
                entry["available"].delete(0, tk.END)
                for filename in files:
                    entry["available"].insert(tk.END, display_model_ref(filename))

        poll_job = {"id": None}

        def cancel_poll_source(event=None):
            # A parent Hole Editor can destroy the embedded NFB settings
            # widget without using close_editor().  Cancel the Tcl timer
            # before widget destruction removes the Python callback command.
            if event is not None and event.widget is not modal:
                return
            job = poll_job["id"]
            if job is None:
                return
            poll_job["id"] = None
            try:
                modal.after_cancel(job)
            except tk.TclError:
                pass

        modal.bind("<Destroy>", cancel_poll_source, add="+")

        def poll_source():
            if not modal.winfo_exists():
                return
            refresh_source()
            poll_job["id"] = modal.after(1800, poll_source)

        # An operator adding the second NFB must see its real editable
        # CUTTING outline in the original Hole Editor immediately, not only
        # after pressing a second tab-level Confirm button. This is an
        # undoable *preview* in the existing session, never a Bay/project write.
        # Keep the exact pre-tab CSV draft and staged config for Cancel.
        live_nfb_preview = {
            "dirty": False, "ready": False,
            "prior_config": None, "prior_csv": (),
        }
        if embed_parent is not None:
            owner_editor = embed_parent.winfo_toplevel()
            live_nfb_preview["prior_config"] = deepcopy(
                getattr(owner_editor, "_receiving_staged_config", None)
            )
            initial_pending = getattr(owner_editor, "_receiving_pending_features", None)
            if callable(initial_pending):
                live_nfb_preview["prior_csv"] = tuple(
                    feature for feature in initial_pending()
                    if getattr(feature, "source_type", None) == "NFB_CSV_SOURCE"
                )

        def stage_live_nfb_openings():
            if embed_parent is None or not live_nfb_preview["ready"]:
                return
            from ae_engine.receiving_nfb_model_identity import is_numeric_model_ref
            selected = [ref for row in chosen[:layers.get()] for ref in row]
            if selected and not all(is_numeric_model_ref(ref) for ref in selected):
                # Legacy DXF preview cannot produce a numeric CSV cutting
                # feature; retain its existing explicit verification gate.
                return
            owner = embed_parent.winfo_toplevel()
            stage = getattr(owner, "_receiving_stage_config", None)
            pending = getattr(owner, "_receiving_pending_features", None)
            if not callable(stage) or not callable(pending):
                raise ValueError("內門主開孔編輯器沒有暫存預覽入口")
            config = {
                "layers": layers.get(),
                "layer_heights_mm": read_layer_heights(),
                "models": [
                    manufacturing_api.pack_receiving_nfb_switch_layer(chosen[0]),
                    manufacturing_api.pack_receiving_nfb_switch_layer(chosen[1]) if layers.get() == 2 else "",
                ],
                "features": deepcopy(initial.get("features", {})),
            }
            openings = manufacturing_api.editor_nfb_features_from_csv(
                current_inner_editor_snapshot(), config,
                current_features=pending(),
            )
            # Validate the entire new set before replacing anything; the
            # shared native session rejects a wrong door/out-of-face contour.
            stage(config, openings)
            live_nfb_preview["dirty"] = True

        def refresh_live_nfb_after_edit():
            try:
                stage_live_nfb_openings()
            except (ValueError, TypeError, KeyError, OSError) as exc:
                # Do not misrepresent a list selection as a visible hole.
                # Main Hole Editor remains at the last validated draft.
                warning.set("新增孔尚未顯示：" + str(exc))

        def rollback_live_nfb_preview():
            if not live_nfb_preview["dirty"] or embed_parent is None:
                return
            owner = embed_parent.winfo_toplevel()
            stage = getattr(owner, "_receiving_stage_config", None)
            if callable(stage):
                stage(
                    deepcopy(live_nfb_preview["prior_config"]),
                    live_nfb_preview["prior_csv"],
                )
            live_nfb_preview["dirty"] = False

        # Keep the native tab rollback on its actual modal, not as an
        # unbound callback name in the independently tested close_editor.
        modal._receiving_live_nfb_rollback = rollback_live_nfb_preview

        def add_switch(index):
            before_x_change = deepcopy(draft_state["draft"])
            selected = layer_rows[index]["available"].curselection()
            if not selected:
                warning.set("請先選擇 CSV 開關型號")
                return
            filename = source_state["files"][index][selected[0]]
            expected_brand = view_source_catalog(index)
            if filename not in manufacturing_api.list_receiving_nfb_model_refs(expected_brand):
                warning.set("CSV 已變動，請重新選擇")
                refresh_source(force=True)
                return
            added = insert_nfb_slot(
                draft_state["draft"], index,
                len(draft_state["draft"]["layers"][index]["slots"]),
                filename=filename, brand=expected_brand,
            )
            # Source brand override and the physical insert are ONE undo step.
            if expected_brand != effective_nfb_layer_brand(added,index):
                added = set_nfb_slot_brand(
                    added, index,
                    len(added["layers"][index]["slots"])-1,
                    mode=OVERRIDE, value=expected_brand,
                )
            draft_state["draft"] = added
            # The single layer-count control already transitions untouched
            # 550 -> 330/830 on choosing two tiers. Adding a switch must not
            # silently rewrite a custom operator height or force legacy 300.
            sync_chosen()
            repaint(index)
            show_x_clear_impact(before_x_change, index)
            refresh_live_nfb_after_edit()

        def add_empty_slot(index):
            before_x_change = deepcopy(draft_state["draft"])
            draft_state["draft"] = insert_nfb_slot(
                draft_state["draft"],index,
                len(draft_state["draft"]["layers"][index]["slots"]),
            )
            sync_chosen()
            repaint(index)
            show_x_clear_impact(before_x_change, index)
            refresh_live_nfb_after_edit()

        def replace_selected_slot(index):
            selected = layer_rows[index]["assigned"].curselection()
            choice = layer_rows[index]["available"].curselection()
            if not selected or not choice:
                warning.set("請選擇原槽與新的 CSV 型號")
                return
            brand = view_source_catalog(index)
            filename = source_state["files"][index][choice[0]]
            draft_state["draft"] = replace_nfb_slot_model(
                draft_state["draft"],index,selected[0],filename,
                catalog={brand:manufacturing_api.list_receiving_nfb_model_refs(brand)},
            )
            sync_chosen()
            repaint(index)
            warning.set("")
            refresh_live_nfb_after_edit()

        def remove_switch(index):
            before_x_change = deepcopy(draft_state["draft"])
            selected = layer_rows[index]["assigned"].curselection()
            if not selected:
                return
            draft_state["draft"] = delete_nfb_slot(
                draft_state["draft"], index, selected[0],
            )
            sync_chosen()
            repaint(index)
            refresh_source(force=True)
            show_x_clear_impact(before_x_change, index)

        def preview_available(index):
            selected = layer_rows[index]["available"].curselection()
            files = source_state["files"][index]
            if selected and selected[0] < len(files):
                nfb_preview_panel["panel"].show(view_source_catalog(index),files[selected[0]])
                nfb_source_viewed["value"] = True

        def preview_assigned(index):
            selected = layer_rows[index]["assigned"].curselection()
            if selected:
                slot = draft_state["draft"]["layers"][index]["slots"][selected[0]]
                brand = effective_nfb_slot_brand(draft_state["draft"],index,selected[0])
                # A saved/fully verified prior pair can disclose its exact
                # physical scope on the ASSIGNED model, not on the source
                # catalogue. Any draft edit or changed active Bay invalidates
                # the label; this UI note never grants another DXF export.
                proof = live = None
                if (version_id is None and embed_parent is None
                        and draft_state["draft"] == initial_nfb_draft):
                    try:
                        sel = candidate_adapter().selection
                        proof = verified_pair_exports.get(
                            (sel.set_index, sel.bay_index)
                        )
                        if proof is not None:
                            live = nfb_physical_bay_snapshot(
                                sel.set_index, sel.bay_index
                            )
                    except (ValueError, TypeError, KeyError, IndexError,
                            AttributeError, OSError):
                        proof = live = None
                nfb_preview_panel["panel"].show(
                    brand, slot["filename"], verified_export_proof=proof,
                    verified_snapshot=live,
                )
                nfb_source_viewed["value"] = True

        def reposition_nfb_slot(index,direction):
            selected=layer_rows[index]["assigned"].curselection()
            if not selected:
                warning.set("請先選取要換序的 NFB 顆位")
                return
            old=selected[0]
            dest=old+direction
            count=len(draft_state["draft"]["layers"][index]["slots"])
            if not 0<=dest<count:return
            try:
                before_x_change = deepcopy(draft_state["draft"])
                draft_state["draft"]=move_nfb_slot(draft_state["draft"],index,old,dest)
                sync_chosen()
                repaint(index)
                layer_rows[index]["assigned"].selection_clear(0,tk.END)
                layer_rows[index]["assigned"].selection_set(dest)
                show_x_clear_impact(before_x_change, index)
                refresh_live_nfb_after_edit()
            except (ValueError,IndexError) as exc:
                warning.set(str(exc))

        def undo_nfb_draft():
            try:
                receipt = edit_session.undo()
                dict.__setitem__(draft_state,"draft",edit_session.current)
                sync_chosen()
                nfb_physical_layers.set(edit_session.current["layer_count"])
                for i,row in enumerate(layer_rows):
                    brand=edit_session.current["layers"][i]["brand"]
                    row["layer_brand_var"].set(
                        "繼承本套" if brand["mode"]==INHERIT else brand["value"]
                    )
                    row["layer_rotation_var"].set(
                        str(edit_session.current["layers"][i]["rotation_deg"])
                    )
                    repaint(i)
                change_layers_visibility_only()
                refresh_source(force=True)
                restored = [
                    (i, nfb_x_reset_impact(receipt.old_draft, receipt.new_draft, i).count)
                    for i in range(receipt.old_draft["layer_count"])
                ]
                impact_text = "、".join(
                    f"第{i + 1}層 {count} 顆" for i, count in restored if count
                )
                warning.set(
                    f"已復原 {impact_text}的 X 位移與基準快照；其他層不變"
                    if impact_text else "已復原 NFB 草稿上一筆交易"
                )
                refresh_live_nfb_after_edit()
            except ValueError as exc:
                warning.set(str(exc))

        def change_layers_visibility_only():
            if nfb_physical_layers.get()==1:
                layer_rows[1]["section"].pack_forget()
            elif not layer_rows[1]["section"].winfo_manager():
                layer_rows[1]["section"].pack(
                    fill="x",pady=(4,6),after=layer_rows[0]["section"],
                )

        def set_rotation_in_draft(index,*,unit=False):
            row=layer_rows[index]
            try:
                if unit:
                    selected=row["assigned"].curselection()
                    if not selected:
                        raise ValueError("請先選擇要旋轉的 NFB 顆位")
                    text=row["unit_rotation_var"].get()
                    draft_state["draft"]=set_nfb_slot_rotation(
                        draft_state["draft"],index,selected[0],
                        mode=INHERIT if text=="跟隨本層" else OVERRIDE,
                        value=None if text=="跟隨本層" else int(text),
                    )
                else:
                    draft_state["draft"]=set_nfb_layer_rotation(
                        draft_state["draft"],index,int(row["layer_rotation_var"].get()),
                    )
                warning.set("角度僅保存草稿；來源主孔中心未認證，不能當製造旋轉")
                paint_draft_preview()
            except (ValueError,IndexError) as exc:
                warning.set(str(exc))

        def set_x_in_draft(index):
            row=layer_rows[index]
            selected=row["assigned"].curselection()
            if not selected:
                warning.set("請先選擇要編輯 X 位移的 NFB 顆位")
                return
            typed=row["manual_x_var"].get().strip()
            try:
                before_x_change = deepcopy(draft_state["draft"])
                value=None if not typed else float(typed)
                draft_state["draft"]=set_nfb_manual_x(
                    draft_state["draft"],index,selected[0],value,
                )
                if value is None:
                    show_x_clear_impact(before_x_change, index)
                else:
                    warning.set("X 位移保留為未驗證草稿，不是絕對製造座標")
                paint_draft_preview()
            except ValueError as exc:
                warning.set(str(exc))

        editor_body = ttk.Frame(frame)
        editor_body.pack(fill="both", expand=True, pady=(4, 6))
        slot_columns = ttk.Frame(editor_body)
        slot_columns.pack(side="left", fill="both", expand=True)
        # AC-03/15: selection already calls show() on this original
        # source-only panel. It must be mapped for the operator to see it.
        # This does not publish CUTTING or create another editor/owner.
        nfb_preview_panel["panel"] = NfbDxfSourcePreviewPanel(editor_body)

        def sync_visible_layers():
            change_layers()

        for count in (1, 2):
            ttk.Radiobutton(
                controls, text=str(count), value=count, variable=layers,
                # The retired physical-layer selector follows the visible
                # inner-door layer choice so a two-layer save remains valid.
                command=lambda: sync_visible_layers(),
            ).pack(side="left", padx=8)
 
        for idx in range(2):
            section = ttk.LabelFrame(slot_columns, text=f"第 {idx+1} 層開關")
            section.pack(fill="x", pady=(4, 6))
            # Height belongs directly beside the CSV model selector, not
            # a detached control underneath the two source lists.
            height_row = ttk.Frame(section)
            height_row.grid(row=0, column=0, sticky="w", padx=5)
            ttk.Label(height_row, text="CSV 型號｜僅預覽").pack(side="left")
            ttk.Label(height_row, text="高度（距上緣 mm）").pack(
                side="left", padx=(8, 3),
            )
            height_entry = ttk.Entry(
                height_row, textvariable=layer_height_vars[idx], width=9,
            )
            height_entry.pack(side="left")
            height_entry.bind("<Return>", lambda _event: paint_draft_preview())
            height_entry.bind("<FocusOut>", lambda _event: paint_draft_preview())
            section.columnconfigure(0, weight=1)
            section.columnconfigure(2, weight=1)
            # This is a *source* list. The selected CSV model alone is not a
            # Set/Bay/version/physical-part manufacturing approval; expose
            # the difference beside the model list without decorating names.
            ttk.Label(
                section,
                text="型號僅預覽｜製造資格以本連已提交配置及真實板件驗證為準",
                wraplength=340, justify="left",
            ).grid(row=2, column=0, sticky="w", padx=5, pady=(0, 3))
            ttk.Label(section, text="本層開關（可重複）").grid(
                row=0, column=2, sticky="w", padx=5)
            available = tk.Listbox(section, selectmode=tk.BROWSE,
                                   exportselection=False, height=6)
            available.grid(row=1, column=0, sticky="nsew", padx=5)
            buttons_area = ttk.Frame(section)
            buttons_area.grid(row=1, column=1, padx=7)
            ttk.Button(buttons_area, text="－移除",
                       command=lambda idx=idx: remove_switch(idx)).pack(
                pady=3)
            ttk.Button(buttons_area, text="＋加入",
                       command=lambda idx=idx: add_switch(idx)).pack(pady=3)
            ttk.Button(buttons_area, text="＋空槽",
                       command=lambda idx=idx: add_empty_slot(idx)).pack(pady=3)
            ttk.Button(buttons_area, text="替換所選",
                       command=lambda idx=idx: replace_selected_slot(idx)).pack(pady=3)
            ttk.Button(buttons_area, text="↑ 前移",
                       command=lambda idx=idx: reposition_nfb_slot(idx,-1)).pack(pady=2)
            ttk.Button(buttons_area, text="↓ 後移",
                       command=lambda idx=idx: reposition_nfb_slot(idx,1)).pack(pady=2)
            # Restore the user's compact editor: only +加入 and −移除.
            for extra in buttons_area.winfo_children()[2:]:
                extra.pack_forget()
            assigned = tk.Listbox(section, selectmode=tk.BROWSE,
                                  exportselection=False, height=6)
            assigned.grid(row=1, column=2, sticky="nsew", padx=5)
            count_text = tk.StringVar(master=modal)
            ttk.Label(section, textvariable=count_text).grid(
                row=2, column=2, sticky="w", padx=(5, 0), pady=(0, 3))
            # Set.switch_brand is the ONLY Set owner; these two selectors
            # are explicit layer/unit override controls on a transient draft.
            brand_row = ttk.Frame(section)
            brand_row.grid(row=3, column=0, columnspan=3, sticky="w", pady=(2, 4))
            ttk.Label(brand_row, text="本層品牌").pack(side="left")
            brand_choices = ("繼承本套", *operator_brand_choices)
            layer_brand_var = tk.StringVar(master=modal, value="繼承本套")
            layer_brand_select = ttk.Combobox(
                brand_row, textvariable=layer_brand_var, values=brand_choices,
                width=12, state="readonly",
            )
            layer_brand_select.pack(side="left", padx=(3, 12))
            ttk.Label(brand_row, text="所選顆品牌").pack(side="left")
            slot_brand_var = tk.StringVar(master=modal, value="繼承本層")
            slot_brand_select = ttk.Combobox(
                brand_row, textvariable=slot_brand_var,
                values=("繼承本層", *operator_brand_choices),
                width=12, state="readonly",
            )
            slot_brand_select.pack(side="left", padx=3)
            # AC-20/SWT-13: do not hide the only real layer/unit brand
            # override widgets. Their effective parent remains the existing
            # Set or currently selected Quantity version, not a second owner.
            rotation_row=ttk.Frame(section)
            rotation_row.grid(row=4,column=0,columnspan=3,sticky="w",pady=(2,4))
            ttk.Label(rotation_row,text="本層角度").pack(side="left")
            layer_rotation_var=tk.StringVar(master=modal,value="0")
            layer_rotation_select=ttk.Combobox(
                rotation_row,textvariable=layer_rotation_var,
                values=("0","90","180","270"),width=5,state="readonly",
            )
            layer_rotation_select.pack(side="left",padx=(4,10))
            ttk.Label(rotation_row,text="所選顆角度").pack(side="left")
            unit_rotation_var=tk.StringVar(master=modal,value="跟隨本層")
            unit_rotation_select=ttk.Combobox(
                rotation_row,textvariable=unit_rotation_var,
                values=("跟隨本層","0","90","180","270"),
                width=9,state="readonly",
            )
            unit_rotation_select.pack(side="left",padx=(4,10))
            ttk.Label(rotation_row,text="X 位移 mm").pack(side="left")
            manual_x_var=tk.StringVar(master=modal,value="")
            ttk.Entry(rotation_row,textvariable=manual_x_var,width=8).pack(
                side="left",padx=(4,3),
            )
            ttk.Button(
                rotation_row,text="設定",
                command=lambda idx=idx:set_x_in_draft(idx),
            ).pack(side="left")
            rotation_row.grid_remove()
            layer_rows.append({
                "section": section, "available": available,
                "assigned": assigned, "count": count_text,
                "layer_brand_var": layer_brand_var,
                "slot_brand_var": slot_brand_var,
                "layer_rotation_var": layer_rotation_var,
                "unit_rotation_var": unit_rotation_var,
                "manual_x_var": manual_x_var,
            })

            def layer_brand_changed(_event=None, idx=idx):
                value = layer_rows[idx]["layer_brand_var"].get()
                before = draft_state["draft"]
                proposed = set_nfb_layer_brand(
                    before, idx, mode=INHERIT if value=="繼承本套" else OVERRIDE,
                    value=None if value=="繼承本套" else value,
                )
                affected = draft_new_reselections(before, proposed)
                if affected and not messagebox.askyesno(
                    "確認更改本層 NFB 廠牌",
                    f"第{idx + 1}層有 {affected} 顆 NFB 原型號將待重選，是否繼續？",
                    parent=modal.winfo_toplevel(),
                ):
                    previous = before["layers"][idx]["brand"]
                    layer_rows[idx]["layer_brand_var"].set(
                        "繼承本套" if previous["mode"] == INHERIT
                        else previous["value"]
                    )
                    return
                draft_state["draft"] = proposed
                refresh_source(force=True)
                repaint(idx)

            def slot_brand_changed(_event=None, idx=idx):
                selected = layer_rows[idx]["assigned"].curselection()
                if not selected:
                    warning.set("請先選取一個實際 NFB 顆位或空槽")
                    # A readonly Combobox changes its text before firing the
                    # selection event; never leave an uncommitted fake choice.
                    layer_rows[idx]["slot_brand_var"].set("繼承本層")
                    return
                value = layer_rows[idx]["slot_brand_var"].get()
                before = draft_state["draft"]
                slot_index = selected[0]
                proposed = set_nfb_slot_brand(
                    before, idx, slot_index,
                    mode=INHERIT if value=="繼承本層" else OVERRIDE,
                    value=None if value=="繼承本層" else value,
                )
                affected = draft_new_reselections(before, proposed)
                if affected and not messagebox.askyesno(
                    "確認更改單顆 NFB 廠牌",
                    f"第{idx + 1}層有 {affected} 顆 NFB 原型號將待重選，是否繼續？",
                    parent=modal.winfo_toplevel(),
                ):
                    previous = before["layers"][idx]["slots"][slot_index]["brand"]
                    layer_rows[idx]["slot_brand_var"].set(
                        "繼承本層" if previous["mode"] == INHERIT
                        else previous["value"]
                    )
                    return
                draft_state["draft"] = proposed
                refresh_source(force=True)
                repaint(idx)

            layer_brand_select.bind("<<ComboboxSelected>>",layer_brand_changed)
            slot_brand_select.bind("<<ComboboxSelected>>",slot_brand_changed)
            layer_rotation_select.bind(
                "<<ComboboxSelected>>",
                lambda _event,i=idx:set_rotation_in_draft(i),
            )
            unit_rotation_select.bind(
                "<<ComboboxSelected>>",
                lambda _event,i=idx:set_rotation_in_draft(i,unit=True),
            )
            def selected_slot_changed(_event=None, idx=idx):
                selected = layer_rows[idx]["assigned"].curselection()
                slots = draft_state["draft"]["layers"][idx]["slots"]
                if selected and selected[0] < len(slots):
                    unit = slots[selected[0]]["brand"]
                    layer_rows[idx]["slot_brand_var"].set(
                        "繼承本層" if unit["mode"] == INHERIT else unit["value"]
                    )
                    rotation=slots[selected[0]].get(
                        "rotation",{"mode":INHERIT,"value":None},
                    )
                    layer_rows[idx]["unit_rotation_var"].set(
                        "跟隨本層" if rotation["mode"]==INHERIT else str(rotation["value"])
                    )
                    manual=slots[selected[0]].get("manual_x_mm")
                    layer_rows[idx]["manual_x_var"].set(
                        "" if manual is None else f"{manual:g}"
                    )
                else:
                    layer_rows[idx]["slot_brand_var"].set("繼承本層")
                    layer_rows[idx]["unit_rotation_var"].set("跟隨本層")
                    layer_rows[idx]["manual_x_var"].set("")
                # Pure highlight/selection must not re-read every brand CSV
                # and rebuild the available model list. A changed effective
                # brand or source mtime/size still refreshes via signature.
                refresh_source()

            assigned.bind("<<ListboxSelect>>", lambda event, i=idx: (
                selected_slot_changed(event,i), preview_assigned(i),
            ))
            available.bind("<<ListboxSelect>>",lambda event,i=idx: preview_available(i))
            repaint(idx)

        def change_layers():
            previous_count = draft_state["draft"]["layer_count"]
            try:
                draft_state["draft"] = set_nfb_draft_layer_count(
                    draft_state["draft"], nfb_physical_layers.get(),
                )
                if previous_count != nfb_physical_layers.get():
                    from ae_engine.receiving_shared_settings import (
                        transition_receiving_nfb_layer_heights,
                    )
                    try:
                        heights = [float(field.get().strip())
                                   for field in layer_height_vars]
                        updated = transition_receiving_nfb_layer_heights(
                            heights, old_count=previous_count,
                            new_count=nfb_physical_layers.get(),
                        )
                    except (ValueError, TypeError):
                        # Keep invalid user input visible; Save/Preview
                        # continues to reject it instead of hiding a bad Y.
                        pass
                    else:
                        for field, height in zip(layer_height_vars, updated):
                            field.set(f"{height:g}")
            except ValueError as exc:
                nfb_physical_layers.set(draft_state["draft"]["layer_count"])
                warning.set(str(exc))
            if nfb_physical_layers.get() == 1:
                layer_rows[1]["section"].pack_forget()
            elif not layer_rows[1]["section"].winfo_manager():
                layer_rows[1]["section"].pack(
                    fill="x", pady=(4, 6),
                    after=layer_rows[0]["section"],
                )
            paint_draft_preview()
            refresh_live_nfb_after_edit()
            refresh_source(force=True)

        change_layers()
        live_nfb_preview["ready"] = True
        # Native CSV features can be missing from an OLD submitted Bay even
        # though its NFBConfig already holds two model occurrences. Showing
        # a one-hole assembly would silently mask that missing editor source.
        # Only bootstrap reversible draft geometry when the actual native
        # editor has fewer CSV slots than the physical selections. The user
        # must Confirm All; Cancel restores the exact prior feature state.
        if (embed_parent is not None and (
                initial.get("_restored_saved_nfb_models")
                or (direct_to_drawing and sum(
                    len(row) for row in chosen[:layers.get()]
                ) > 1)
        )):
            # Do NOT stage a fresh single default NFB merely by opening the
            # native tab. An untouched entry is not an operator-confirmed
            # physical change (SWT-05). Only repair genuinely missing second
            # slots or an explicitly recovered legacy multiple-NFB draft.
            owner_editor = embed_parent.winfo_toplevel()
            pending = getattr(owner_editor, "_receiving_pending_features", None)
            if callable(pending):
                current = {
                    (dict(f.source_params).get("layer_index"),
                     dict(f.source_params).get("slot_index"))
                    for f in pending()
                    if getattr(f, "source_type", None) == "NFB_CSV_SOURCE"
                }
                wanted = {
                    (tier, slot)
                    for tier in range(layers.get())
                    for slot, _ in enumerate(chosen[tier])
                }
                if wanted - current:
                    refresh_live_nfb_after_edit()
                    if live_nfb_preview["dirty"]:
                        warning.set(
                            "已恢復已選 NFB 的開孔草稿；請核對每孔位置，"
                            "按主開孔編輯器「確定全部」才會更新實體組合體。"
                        )
        # Nominal NFB draft/workflow summary is not part of the approved UI.
        ttk.Label(frame, textvariable=warning).pack(anchor="w")
        refresh_source(force=True)
        poll_job["id"] = modal.after(1800, poll_source)
        modal._receiving_inner_switch_state = {
            "layer_heights_mm": layer_height_vars,
            "direct_to_drawing": direct_to_drawing,
            "chosen": chosen, "layers": layers,
            "edit_session": edit_session,
            "nfb_physical_layers": nfb_physical_layers,
            "rows": layer_rows, "warning": warning,
            "nfb_draft": draft_state, "nfb_draft_status": draft_summary,
        }
        modal._receiving_inner_refresh_switch_models = refresh_source
        modal._receiving_inner_preview_status = preview_status
        modal._receiving_inner_nfb_dxf_panel = nfb_preview_panel["panel"]

        # Main Hole Editor owns opening placement/editing. The former CSV
        # world-X/opening verification popup was a separate, unnecessary
        # operator gate: keep NFB model selection as metadata only.

        def confirm():
            try:
                # Physical CSV/legacy model and source-brand qualification belongs
                # to the Engine; this only selects which original editor route
                # receives the validated transient NFB draft.
                confirmation = manufacturing_api.plan_receiving_nfb_editor_confirm(
                    draft_state["draft"], edit_session.current, chosen,
                    layer_count=nfb_physical_layers.get(),
                    embedded=embed_parent is not None,
                    parent_brand=current_nfb_parent_brand(),
                )
                config = {
                    "layers": layers.get(),
                    "layer_heights_mm": read_layer_heights(),
                    "models": [
                        manufacturing_api.pack_receiving_nfb_switch_layer(chosen[0]),
                        manufacturing_api.pack_receiving_nfb_switch_layer(chosen[1]) if layers.get() == 2 else "",
                    ],
                    "features": deepcopy(initial.get("features", {})),
                }
                stage_in_editor = (
                    getattr(modal.winfo_toplevel(), "_receiving_stage_config", None)
                    if embed_parent is not None else None
                )
                if embed_parent is not None:
                    # Embedded NFB Confirm only stages a draft for the
                    # original Hole Editor. Regardless of active_mode or an
                    # existing multi-dialog, NEVER write a candidate/Bay here.
                    if not callable(stage_in_editor):
                        raise ValueError("主開孔編輯器尚未連接 NFB 交易暫存")
                    openings = None
                    if (confirmation.current_numeric_editor
                            or not confirmation.has_source_models):
                        parent_editor = modal.winfo_toplevel()
                        pending = getattr(parent_editor, "_receiving_pending_features", None)
                        openings = manufacturing_api.editor_nfb_features_from_csv(
                            current_inner_editor_snapshot(), config,
                            current_features=(pending() if callable(pending) else ()),
                        )
                    stage_in_editor(config, openings)
                    after_saved(version_id)
                    close_editor(saved=True)
                    return
                # Standalone candidate-version manager (outside the original
                # Hole Editor) retains its existing explicit version save.
                if version_id is None:
                    saved, vid = create_inner_candidate(inner_library(), config)
                else:
                    saved = update_inner_candidate(
                        inner_library(), version_id, config,
                    )
                    vid = version_id
                persist_inner(saved)
                after_saved(vid)
                close_editor(saved=True)
            except (ValueError, OSError, UnicodeError) as exc:
                warning.set(str(exc))
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(10, 0))
        ttk.Button(buttons, text="取消", command=lambda: close_editor()).pack(
            side="left", padx=5,
        )
        # A single operator Undo beside Confirm/Cancel, not extra slot
        # controls: Q5/Q6/Q7 must actually be reversible in this GUI.
        ttk.Button(buttons, text="復原 NFB", command=undo_nfb_draft).pack(
            side="left", padx=5,
        )
        ttk.Button(buttons, text="確定", command=confirm).pack(side="left")
        # Restore the parent multi-settings grab after this editor closes.
        parent_modal = getattr(
            self.app.root, "_receiving_multi_settings_window", None
        )
        def close_editor(*, saved=False):
            # #1901: Cancel from a Single/Multi Receiving tab must always
            # discard only this tab's draft and return to the original editor.
            # The unchanged physical-part legacy route retains its old prompt.
            settings_embedded = embed_parent is not None
            # Merely viewing a DXF/source preview is not an edit. Conversely,
            # unsaved layer heights/models must not be lost without a prompt
            # on the standalone UI-1A window. Embedded settings Cancel is
            # governed by the parent Hole Editor transaction (#1901).
            pending_changes = (
                draft_state["draft"] != initial_nfb_draft
                or layers.get() != initial["layers"]
                or any(
                    field.get().strip() != f"{float(original):g}"
                    for field, original in zip(
                        layer_height_vars, initial["layer_heights_mm"]
                    )
                )
                or chosen != [
                    list(manufacturing_api.receiving_nfb_switch_filenames_in_layer(item))
                    for item in initial["models"]
                ]
            )
            if (not saved and not settings_embedded and pending_changes
                    and not messagebox.askyesno(
                        "捨棄未提交的 NFB 草稿？",
                        "目前 NFB 物理層、空槽或品牌選型的預覽尚未提交。確定捨棄？",
                        parent=modal.winfo_toplevel(),
                    )):
                return
            # Cancel the Tk timer before destroying its Tcl callback command.
            if poll_job["id"] is not None:
                try:
                    modal.after_cancel(poll_job["id"])
                except tk.TclError:
                    pass
                poll_job["id"] = None
            if not saved:
                rollback = getattr(modal, "_receiving_live_nfb_rollback", None)
                if callable(rollback):
                    rollback()
            if modal.grab_current() is modal:
                modal.grab_release()
            modal.destroy()
            if embed_parent is not None:
                if not saved and callable(after_closed) and embed_parent.winfo_exists():
                    embed_parent.after_idle(after_closed)
            elif parent_modal is not None and parent_modal.winfo_exists():
                if parent_modal.grab_current() is None:
                    parent_modal.grab_set()
                parent_modal.lift()
                parent_modal.focus_set()
        if embed_parent is None:
            modal.protocol("WM_DELETE_WINDOW", close_editor)
            modal.bind("<Escape>",lambda _event:close_editor())
        for widget in buttons.winfo_children():
            if widget.cget("text") == "取消":
                widget.configure(command=close_editor)
        if embed_parent is None:
            if owner.grab_current() is owner:
                owner.grab_release()
            modal.grab_set()
            modal.lift()
            modal.focus_set()
        return modal

    def inner_copy(role, version_id, destination):
        if role != INNER_ROLE or destination != INNER_ROLE:
            raise ValueError("內門版本不能複製到封頭尾")
        updated, vid = duplicate_inner_candidate(inner_library(), version_id)
        persist_inner(updated)
        return vid

    def inner_delete(role, version_id):
        if role != INNER_ROLE:
            raise ValueError("內門版本權責錯誤")
        persist_inner(delete_inner_candidate(inner_library(), version_id))

    def verify_inner_models(config):
        # Source eligibility is Engine-owned, shared by GUI and headless callers.
        return manufacturing_api.validate_receiving_inner_door_source_models(
            config, current_nfb_parent_brand(),
        )

    def inner_apply(role, version_id, set_index, highlighted):
        if role != INNER_ROLE or version_id is None or not highlighted:
            raise ValueError("請選內門版本及實際連位")
        adapter = candidate_adapter()
        config = inner_config(inner_library(), version_id)
        verify_inner_models(config)
        adapter.apply_inner_door_candidate_to_bays(
            config, set_index, highlighted, version_id=version_id,
        )
        self.mark_receiving_switch_layout_dirty(namespace, adapter)
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        self.app.submit_update_intent("geometry", commit=True)
        return True

    def inner_validate_quantity(quantities, assigned, expected_counts):
        plan = manufacturing_api.validate_receiving_inner_door_allocation(
            candidate_adapter().layout, inner_library(), quantities, assigned,
            expected_counts=expected_counts,
        )
        for _si, _bi, config in plan:
            verify_inner_models(config)
        return plan

    def inner_apply_quantity(role, quantities, assigned, expected_counts):
        if role != INNER_ROLE:
            raise ValueError("內門版本權責錯誤")
        inner_validate_quantity(quantities, assigned, expected_counts)
        adapter = candidate_adapter()
        count = adapter.apply_inner_door_quantity_configuration(
            inner_library(), quantities, assigned,
            expected_counts=expected_counts,
        )
        self.mark_receiving_switch_layout_dirty(namespace, adapter)
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        self.app.submit_update_intent("geometry", commit=True)
        return count

    def inner_candidate_ports():
        return {
            "versions": lambda role: (
                inner_versions(inner_library()) if role == INNER_ROLE else ()
            ),
            "edit": inner_edit,
            "copy": inner_copy,
            "delete": inner_delete,
            "apply": inner_apply,
            "apply_live": apply_live_label,
            "apply_quantity": inner_apply_quantity,
            "validate_quantity": inner_validate_quantity,
        }

    def nfb_transaction_ports():
        """Single Receiving authority, with real source-verified transient stage."""
        def stage_verified(bundle):
            if not isinstance(bundle, manufacturing_api.NfbVerifiedDraftSubmission):
                raise TypeError("NFB 必須提供真實來源與內門物理位置驗證")
            adapter=candidate_adapter()
            manufacturing_api.assert_live_verified_nfb(
                adapter,bundle,current_snapshot=nfb_physical_bay_snapshot(
                    bundle.set_index,bundle.bay_index,
                ),
            )
            pending_verified_nfb[(bundle.set_index,bundle.bay_index)]=bundle
            return True

        def eligible_bundle(set_index,bay_index):
            bundle=pending_verified_nfb.get((set_index,bay_index))
            if bundle is None:
                return None,"尚未取得當前連的原始 DXF、實體世界 X 與內門板驗證"
            try:
                manufacturing_api.assert_live_verified_nfb(
                    candidate_adapter(),bundle,
                    current_snapshot=nfb_physical_bay_snapshot(
                    bundle.set_index,bundle.bay_index,
                ),
                )
            except (ValueError,TypeError,KeyError,IndexError,OSError) as exc:
                pending_verified_nfb.pop((set_index,bay_index),None)
                return None,"已配置 NFB 驗證過期，必須重新檢查："+str(exc)
            return bundle,""

        def copy_pair(set_index, selected_bays):
            """Use Engine's verified-source/target choice; GUI only stages proofs.

            All target readiness evidence is checked *live* before asking
            Engine to select a unique direction. The canonical Engine copy
            transaction independently rechecks the chosen pair on Confirm.
            """
            layout = candidate_adapter().layout
            indices, _ = _checked_nfb_copy_selection(
                layout, set_index, selected_bays,
            )
            verified_targets = []
            bundles = {}
            for target_bi in indices:
                if (set_index, target_bi) not in pending_verified_nfb:
                    continue
                bundle, reason = eligible_bundle(set_index, target_bi)
                if bundle is not None and bundle.can_submit:
                    verified_targets.append(target_bi)
                    bundles[target_bi] = bundle
            source_bi, target_bi = manufacturing_api.plan_operator_nfb_copy_direction(
                layout, set_index, indices,
                verified_target_indices=tuple(verified_targets),
            )
            return source_bi, bundles[target_bi]


        def physical_manifest(set_index,bay_index):
            """Read-only live status from current saved NFB + original source."""
            adapter=candidate_adapter()
            owner=adapter.layout["sets"][set_index]
            bay=owner["bays"][bay_index]
            if bay.get("nfb_config_submitted") is not True:
                return {
                    "status":"LEGACY","reason":"未配置 NFB：保留原有開孔流程",
                    "actual_export_count":None,"rows":(),
                    "unresolved_dependencies":(),
                }
            bundle=committed_nfb_evidence.get((set_index,bay_index))
            if bundle is None:
                # Existing numeric CSV NFB source has no legacy DXF receipt.
                # Ask the public Engine to decide actual Door/Base identity,
                # dependencies and source status. The temporary scene remains
                # a read-only witness, never a manufacturing authorization.
                current = nfb_physical_bay_snapshot(set_index, bay_index)
                physical_parts = ()
                try:
                    preview_layout = manufacturing_api.project_receiving_nfb_unsubmitted_preview_layout(
                        adapter.layout,
                        set_index=set_index, bay_index=bay_index,
                    )
                    actual = self.receiving_bay_preview_request(
                        namespace, set_index, bay_index,
                        preview_layout=preview_layout,
                    )
                    physical_parts = actual.render_data.assembly_parts
                except (ValueError, TypeError, KeyError, IndexError,
                        AttributeError, OSError):
                    # Fail closed: no resolved real FinalScene means no
                    # independently evidenced unaffected physical sheets.
                    physical_parts = ()
                v5 = manufacturing_api.project_receiving_current_v5_nfb_physical_diagnostics(
                    bay,
                    physical_snapshot=current,
                    set_id=str(owner["stable_id"]),
                    bay_id=str(bay["stable_id"]),
                    version_id=_receiving_setting_value(
                        owner, bay_index, "inner_door_version_id",
                    ),
                    physical_parts=physical_parts,
                )
                if v5 is not None:
                    return v5
                # Numeric CSV is the CURRENT committed NFB source.  The old
                # DXF proof cache is deliberately empty for this route; never
                # tell the operator a valid CSV pair is unmanufacturable only
                # because an obsolete manufacturer DXF receipt is absent.
                # This read-only view is NOT an export approval or a piece
                # count. The existing pair PART_ONLY writer revalidates both
                # original physical material sources at the actual click.
                try:
                    csv_scoped = current_csv_pair_source(
                        set_index, bay_index,
                    )
                except (ValueError, TypeError, KeyError, IndexError, OSError):
                    csv_scoped = False
                if csv_scoped:
                    return {
                        "status":"CSV_SOURCE_RECHECK_ONLY",
                        "reason":"現行 CSV 已提交；內門＋底板部分 DXF 須於出圖時重新驗證",
                        "actual_export_count":None,"rows":(),
                        "unresolved_dependencies":(
                            "WHOLE_CABINET_MANUFACTURING_NOT_APPROVED",
                        ),
                    }
                return {
                    "status":"BLOCKED","reason":"現行 CSV 或舊版 NFB 實體來源尚未重新核對",
                    "actual_export_count":0,"rows":(),
                    "unresolved_dependencies":("SOURCE_REVALIDATION_REQUIRED",),
                }
            try:
                current=nfb_physical_bay_snapshot(set_index,bay_index)
                # Report-only geometry fingerprint; manufacturing remains
                # gated again by #1497/#1498 and the part-export writer.
                from .receiving_nfb_partial_export_action import (
                    nfb_verification_geometry_changed,
                )
                if nfb_verification_geometry_changed(
                    current, bundle.snapshot_at_verification,
                ):
                    raise ValueError("內門幾何已變更，來源驗證必須重新執行")
                details=manufacturing_api.project_receiving_verified_nfb_partial_manifest(
                    scope=bundle.scope,
                    saved_bay=bay,
                    set_brand=owner["switch_brand"],
                    source_inventory=bundle.source_inventory,
                    verified_inner_door=bundle.verified_door,
                    source_path=bundle.source_path,
                )
                # This is a view, NOT the exporter authority itself.
                return details
            except (ValueError,TypeError,KeyError,IndexError,OSError) as exc:
                committed_nfb_evidence.pop((set_index,bay_index),None)
                return {
                    "status":"BLOCKED","reason":"NFB 證據已過期："+str(exc),
                    "actual_export_count":0,"rows":(),
                    "unresolved_dependencies":("SOURCE_REVALIDATION_REQUIRED",),
                }

        def export_partial_nfb_inner_door(set_index, bay_index, output_path):
            """Operator-requested NFB-only partial DXF; not legacy whole export."""
            from .receiving_nfb_partial_export_action import (
                export_verified_receiving_nfb_inner_door,
            )
            bundle = committed_nfb_evidence.get((set_index, bay_index))
            if bundle is None:
                raise ValueError("此連已提交 NFB，但來源／世界 X 尚未在本次操作重新驗證")
            adapter = candidate_adapter()
            # Source proof and actual saved Bay are revalidated before writing.
            return export_verified_receiving_nfb_inner_door(
                bundle,
                layout=adapter.layout,
                current_snapshot=nfb_physical_bay_snapshot(set_index, bay_index),
                output_path=output_path,
            )

        def export_partial_nfb_base_plate(set_index, bay_index, output_directory):
            """Real NFB Base Plate PART_ONLY export, not whole-cabinet release."""
            from .receiving_nfb_base_partial_export_action import (
                export_verified_receiving_nfb_base_plate,
            )
            bundle = committed_nfb_evidence.get((set_index, bay_index))
            if bundle is None:
                raise ValueError("受電箱底板無已提交的 NFB 原始來源及實體孔位驗證")
            current = nfb_physical_bay_snapshot(set_index, bay_index)
            # Reuse the original manufacturing PartSpec owner.  In
            # particular, this must not synthesize base_plate_cN_rN.
            spec, _ = self.app._part_spec_query_callback("base_plate", current)
            return export_verified_receiving_nfb_base_plate(
                bundle,
                layout=candidate_adapter().layout,
                current_snapshot=current,
                base_spec=spec,
                output_directory=output_directory,
            )

        def current_csv_pair_source(set_index, bay_index):
            """Read current CSV physical-source eligibility through public Engine API."""
            current = nfb_physical_bay_snapshot(set_index, bay_index)
            return (
                manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
                    current,
                ) is not None
            )

        def export_partial_nfb_door_base_pair(set_index, bay_index, output_directory):
            """Existing PART_ONLY button: canonical CSV first; old DXF for old data."""
            from .receiving_nfb_pair_partial_export_action import (
                export_verified_receiving_nfb_door_base_pair,
                export_current_csv_nfb_door_base_pair,
            )
            current = nfb_physical_bay_snapshot(set_index, bay_index)
            layer_count = manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
                current,
            )
            if layer_count is not None:
                # The same actual Bay assembly displayed in 2D/3D owns one
                # real root or two real tier blanks; do not request a fake
                # generic root PartSpec for a two-tier physical assembly.
                spec = None
                if layer_count == 1:
                    spec, _ = self.app._part_spec_query_callback(
                        "base_plate", current,
                    )
                request = self.receiving_bay_preview_request(
                    namespace, set_index, bay_index,
                    preview_layout=candidate_adapter().layout,
                )
                exported = export_current_csv_nfb_door_base_pair(
                    current, base_spec=spec,
                    assembly_parts=request.render_data.assembly_parts,
                    output_directory=output_directory,
                )
                from .receiving_nfb_verified_scope_display import (
                    capture_verified_v5_pair_display,
                )
                proof = capture_verified_v5_pair_display(current, exported)
                # Discard any earlier receipt even if newly captured proof
                # fails closed. Source snapshots and generated files remain
                # unmodified, and there is never a stored approval flag.
                verified_pair_exports.pop((set_index, bay_index), None)
                if proof is not None:
                    verified_pair_exports[(set_index, bay_index)] = proof
                return exported
            bundle = committed_nfb_evidence.get((set_index, bay_index))
            if bundle is None:
                raise ValueError("NFB 成對出圖缺少現行 CSV 或舊版已驗證來源")
            spec, _ = self.app._part_spec_query_callback("base_plate", current)
            return export_verified_receiving_nfb_door_base_pair(
                bundle, layout=candidate_adapter().layout,
                current_snapshot=current, base_spec=spec,
                output_directory=output_directory,
            )

        def state(set_index, bay_index, selected_bays=()):
            adapter = candidate_adapter()
            row = adapter.layout["sets"][set_index]["bays"][bay_index]
            submitted = row.get("nfb_config_submitted") is True
            bundle,reason=eligible_bundle(set_index,bay_index)
            csv_pair_ready = False
            if submitted:
                try:
                    csv_pair_ready = current_csv_pair_source(set_index, bay_index)
                except (ValueError, TypeError, KeyError, IndexError, OSError):
                    csv_pair_ready = False
            try:
                copy_pair(set_index,selected_bays)
                can_copy=True
            except (ValueError,IndexError,KeyError):
                can_copy=False
            return {
                "submitted": submitted,
                "can_submit": bundle is not None and bundle.can_submit,
                "can_copy": can_copy,
                "can_restore": submitted,
                "can_undo": adapter.nfb_can_undo,
                "base_partial_ready": bool(
                    csv_pair_ready or (
                        submitted
                        and (set_index, bay_index) in committed_nfb_evidence
                        and nfb_physical_bay_snapshot(set_index, bay_index).get("receiving_base_plate")
                    )
                ),
                "reason": (
                    "來源已提交，且目標連的獨立實體來源已驗證，可複製"
                    if can_copy else
                    "現行 CSV 已提交；僅限來源驗證後的內門＋底板部分出圖"
                    if csv_pair_ready else
                    reason or "目前尚無可提交的來源核對交易"
                ),
            }

        def submit(set_index,bay_indices,confirm):
            targets=tuple(bay_indices)
            if len(targets)!=1:
                raise ValueError("NFB MFG-1 本次僅驗證單一實體連，跨連須逐連確認")
            bi=targets[0]
            bundle,reason=eligible_bundle(set_index,bi)
            if bundle is None:
                raise ValueError(reason)
            result=manufacturing_api.submit_live_verified_nfb(
                candidate_adapter(),bundle,
                current_snapshot=nfb_physical_bay_snapshot(
                    bundle.set_index,bundle.bay_index,
                ),
                confirm=confirm,
            )
            if result.changed:
                pending_verified_nfb.pop((set_index,bi),None)
                committed_nfb_evidence[(set_index,bi)]=bundle
                flush()
            return result.changed

        def copy(set_index,bay_indices,confirm):
            source_bi,target_bundle=copy_pair(set_index,bay_indices)
            result=manufacturing_api.copy_live_verified_nfb(
                candidate_adapter(),source_bay_index=source_bi,
                target_bundle=target_bundle,
                current_snapshot=nfb_physical_bay_snapshot(
                    target_bundle.set_index,target_bundle.bay_index,
                ),
                confirm=confirm,
            )
            if result.changed:
                pending_verified_nfb.pop(
                    (target_bundle.set_index,target_bundle.bay_index),None
                )
                committed_nfb_evidence[
                    (target_bundle.set_index,target_bundle.bay_index)
                ]=target_bundle
                flush()
            return result.changed

        def flush():
            adapter = candidate_adapter()
            self.mark_receiving_switch_layout_dirty(namespace, adapter)
            self.sync_receiving_current_bay(namespace, refresh_controls=False)
            self.app.submit_update_intent("geometry", commit=True)

        def restore(set_index, bay_indices, confirm):
            adapter = candidate_adapter()
            result = adapter.restore_nfb_unconfigured(
                set_index=set_index, bay_indices=bay_indices, confirm=confirm,
            )
            if result.changed:
                for bi in bay_indices:
                    committed_nfb_evidence.pop((set_index,bi),None)
                    pending_verified_nfb.pop((set_index,bi),None)
                flush()
            return result.changed

        def undo():
            adapter = candidate_adapter()
            receipt = adapter.undo_last_nfb_transaction()
            committed_nfb_evidence.clear()  # Undo invalidates old physical evidence
            pending_verified_nfb.clear()
            flush()
            return receipt

        def verified_for_editor(set_index, bay_index):
            bundle, reason = eligible_bundle(set_index, bay_index)
            if bundle is None or not bundle.verified_door.manufacturing_ready:
                raise ValueError(reason or "沒有已驗證的實體 NFB 來源與開口")
            return bundle

        return {"state": state, "stage_verified": stage_verified,
                "verified_for_editor": verified_for_editor,
                "submit": submit, "copy": copy, "manifest": physical_manifest,
                "partial_export": export_partial_nfb_inner_door,
                "base_partial_export": export_partial_nfb_base_plate,
                "pair_partial_export": export_partial_nfb_door_base_pair,
                "restore": restore, "undo": undo}

    def real_cut_preview_request(role, version_id, set_index, bay_index):
        """True canonical FinalScene, candidate-injected in memory, no mutation."""
        if version_id is None:
            # Read the active canonical Set/Bay layout, not a possibly stale
            # application snapshot; it is still resolved in an isolated scene.
            return self.receiving_bay_preview_request(
                namespace, set_index, bay_index,
                preview_layout=candidate_adapter().layout,
            )
        from .receiving_set_bay_adapter import ReceivingSetBayAdapter
        temporary = ReceivingSetBayAdapter(candidate_adapter().layout)
        if role == "inner-door":
            config = inner_config(inner_library(), version_id)
            temporary.apply_inner_door_candidate_to_bays(
                config, set_index, (bay_index,), version_id=version_id,
            )
        elif role in ("head", "tail"):
            features = candidate_features(candidate_library(), role, version_id)
            temporary.apply_candidate_to_bays(
                role, set_index, (bay_index,), features, version_id=version_id,
            )
        else:
            raise ValueError("不支援的真實截角資料預覽部位")
        return self.receiving_bay_preview_request(
            namespace, set_index, bay_index, preview_layout=temporary.layout,
        )

    def applied_version_labels(set_index):
        """Read ONLY persisted per-Bay identifiers from the current layout."""
        selected_set = candidate_adapter().layout["sets"][set_index]
        return tuple({
            role: _receiving_setting_value(selected_set, bi, kind)
            for role, kind in (
                ("head", "head_version_id"),
                ("tail", "tail_version_id"),
                ("inner-door", "inner_door_version_id"),
            )
        } for bi in range(len(selected_set["bays"])))

    def current_inner_editor_config():
        adapter = candidate_adapter()
        selected = adapter.selection
        row = adapter.layout["sets"][selected.set_index]
        config = {
            "layers": _receiving_setting_value(row, selected.bay_index, "inner_door_layers"),
            "models": _receiving_setting_value(row, selected.bay_index, "inner_door_models"),
            "features": _receiving_setting_value(row, selected.bay_index, "inner_door_features"),
        }
        heights = _receiving_setting_value(row, selected.bay_index, "inner_door_layer_heights_mm")
        if heights is not None:
            config["layer_heights_mm"] = heights
        return config

    def current_inner_editor_snapshot():
        source = _current_mode_snapshot(self, namespace)
        if source.get("active_mode") == "set_bay":
            selected = candidate_adapter().selection
            return nfb_physical_bay_snapshot(
                selected.set_index, selected.bay_index,
            )
        # Single quantity box W/H/D and inner-door geometry must not
        # accidentally inherit the currently highlighted multi-Bay size.
        return source

    def current_inner_editor_part_key():
        return manufacturing_api.resolve_receiving_upper_inner_door_editor_part_key(
            current_inner_editor_snapshot(),
        )

    def launch_inner_editor(part_key, *, mode, version_id=None, initial_features=None,
                            after_saved=None):
        from .receiving_inner_door_hole_editor import open_inner_door_hole_editor

        def confirmed(actual_part, features, staged_config):
            if actual_part != part_key:
                raise ValueError("內門開孔編輯返回錯誤的實體板件")
            if mode == "single" and self.app.designer_workspace.active_mode == "quantity":
                if staged_config is not None:
                    quantity = self.app.designer_workspace.quantity_model
                    projected, typed = manufacturing_api.preview_quantity_inner_door_confirm(
                        self.app._phase6_input_snapshot, quantity, part_key,
                        features, staged_config,
                    )
                    # A detached Engine Family/source check MUST precede live
                    # version mutation. None means native-only features.
                    if typed is not None:
                        quantity.set_version_nfb_config(
                            quantity.selected_version_id, submitted=True,
                            config=typed,
                        )
                    # Reset only the transient Set/Bay selector: CURRENT
                    # quantity's fresh synthetic Bay must never inherit a
                    # pointer into an obsolete persisted Set. Keep the strict
                    # manufacturing identity guard intact.
                    from ae_engine.receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
                    self.app._phase6_input_snapshot.pop(RECEIVING_RUNTIME_SELECTION_KEY, None)
                    self.app._phase6_input_snapshot.update(projected)
                    # The workspace is the in-memory canonical mode owner.
                    # The next scheduler/SetBay sync otherwise restores its
                    # previous quantity-box value and silently discards NFB
                    # layer count, CSV model identities and operator heights.
                    self.app.designer_workspace.set_receiving_common_box(
                        projected["receiving_quantity_box"]
                    )
                    self.receiving_adapter(namespace, reset=True)
                    self.sync_receiving_current_bay(
                        namespace, refresh_controls=False,
                    )
                # Quantity's current physical sheet is the live workspace owner;
                # it is NOT a Set/Bay candidate or a synthetic version X.
                self.app.designer_workspace.stash_features(part_key, features)
                if str(self.app.designer_workspace.active_part) == part_key:
                    self.app._load_part_holes(part_key)
                if staged_config is not None:
                    # NFB tier source IDs changed, not just CUTTING Features.
                    # Refresh operator 2D navigation and derived part owners
                    # BEFORE publishing the geometry redraw; otherwise the
                    # workbench still lists the obsolete single root sheet.
                    self._required(
                        namespace, "_phase6_sync_authoritative_derived_parts"
                    )(self.app)
                self.app.submit_update_intent("geometry", commit=True)
                return
            if mode == "single":
                adapter = candidate_adapter()
                selected = adapter.selection
                row = adapter.layout["sets"][selected.set_index]
                bay = row["bays"][selected.bay_index]
                if bay.get("nfb_config_submitted") is True:
                    # The previous blanket prohibition made old submitted
                    # NFBConfig (two models, zero native Features) impossible
                    # to repair from the original Hole Editor. Permit ONLY a
                    # complete, explicitly Confirm-All validated CSV
                    # replacement via the existing atomic Set/Bay adapter.
                    if (staged_config is None or not any(
                            getattr(feature, "source_type", None) == "NFB_CSV_SOURCE"
                            for feature in features)):
                        raise ValueError(
                            "已提交 NFB 的內門須用完整 CSV 主孔重新確認後才可替換"
                        )
                # Single owns the *existing* physical Bay, never a candidate.
                # Both settings and actual CUTTING must survive Bay reprojection.
                source = (staged_config if staged_config is not None
                          else current_inner_editor_config())
                current = manufacturing_api.prepare_receiving_inner_door_physical_confirm(
                    source, part_key, features,
                )
                # Reuse the adapter's atomic Set/Bay update; no version library
                # is created and no other Bay is touched.
                adapter.apply_inner_door_candidate_to_bays(
                    current, selected.set_index, (selected.bay_index,), version_id="",
                )
                self.mark_receiving_switch_layout_dirty(namespace, adapter)
                self.sync_receiving_current_bay(namespace, refresh_controls=False)
                self.app.submit_update_intent("geometry", commit=True)
                return
            if mode != "candidate":
                raise ValueError("未知的內門儲存目標")
            config = (inner_config(inner_library(), version_id) if version_id is not None
                      else current_inner_editor_config())
            if staged_config is not None:
                config = staged_config
            config = manufacturing_api.prepare_receiving_inner_door_physical_confirm(
                config, part_key, features,
            )
            if version_id is None:
                updated, selected_version = create_inner_candidate(inner_library(), config)
            else:
                updated = update_inner_candidate(inner_library(), version_id, config)
                selected_version = version_id
            # An uncommitted verification uses the future real candidate ID
            # but cannot mint a different ID (for example after another edit).
            if any(getattr(f, "source_type", None) == "NFB_VERIFIED_SOURCE"
                   for f in features):
                selected = candidate_adapter().selection
                proof = pending_verified_nfb.get(
                    (selected.set_index, selected.bay_index)
                )
                if proof is None or proof.version_id != selected_version:
                    raise ValueError("NFB 原始來源驗證與候選版本編號已不同，請重新確認")
            # No changes to a committed Bay before explicit 套用.
            persist_inner(updated)
            if callable(after_saved):
                after_saved(selected_version)

        physical = current_inner_editor_snapshot()
        return open_inner_door_hole_editor(
            self.app, part_key, settings_mode=mode,
            initial_features=initial_features, physical_snapshot=physical,
            selected_candidate_version=version_id,
            on_settings_confirm=confirmed,
        )

    def edit_single_inner_door():
        return launch_inner_editor(current_inner_editor_part_key(), mode="single")

    def edit_multi_inner_door(version_id, after_saved):
        part_key = current_inner_editor_part_key()
        source = (inner_config(inner_library(), version_id) if version_id is not None
                  else current_inner_editor_config())
        typed = source.get("features", {})
        # Existing candidates never implicitly consume another Bay's live holes.
        if part_key in typed:
            draft_features = deepcopy(typed[part_key])
        else:
            # A new candidate starts empty. Never borrow the selected Bay or
            # Single's current physical holes before explicit version Apply.
            draft_features = []
        return launch_inner_editor(
            part_key, mode="candidate", version_id=version_id,
            initial_features=draft_features, after_saved=after_saved,
        )

    if embedded_inner_parent is not None:
        from .receiving_inner_door_hole_editor import inner_door_commit_target
        # Keep the original Corner Data / physical-part double-click editor.
        # Only the NEW Single/Multi settings button opts into staged save.
        editor = embedded_inner_parent.winfo_toplevel()
        # Two native tabs belong to the SAME original Hole Editor.  Editing
        # this configuration stages a draft only; the editor's 確定全部 owns
        # all persistence, and its 取消全部 owns rollback.
        from tkinter import ttk
        container = embedded_inner_parent
        editor = container.winfo_toplevel()
        mode = getattr(editor, "_receiving_settings_mode", None)
        # Explicit entry identity, not project state: only the multi-settings
        # "candidate" entry saves a version on the MAIN Confirm All.
        save_target = inner_door_commit_target(mode)
        selected_version = getattr(editor, "_receiving_candidate_version", None)
        if save_target == "candidate" and selected_version is not None:
            inner_config(inner_library(), selected_version)
        state = {"version": selected_version if save_target == "candidate" else None}
        bar = ttk.Frame(container)
        bar.pack(fill="x", padx=8, pady=(5, 3))
        status = ttk.Label(
            bar, text=("多連設定｜主頁籤確定全部才存入候選版本 X"
                       if save_target == "candidate"
                       else "一般／單只入口｜主頁籤確定全部才套用現有板件"),
        )
        status.pack(anchor="w")
        tabs = getattr(editor, "_receiving_config_tabs", None)

        def go_to_main_tab():
            if tabs is not None and tabs.winfo_exists():
                tabs.select(0)   # native 開孔編輯 tab, not a new popup
                # Notebook page was hidden while the NFB list was edited:
                # repaint the ACTUAL main Canvas once it is visible again.
                redraw = getattr(editor, "_receiving_redraw_main_holes", None)
                if callable(redraw):
                    tabs.after_idle(
                        lambda: redraw() if tabs.winfo_exists()
                        and tabs.index(tabs.select()) == 0 else None
                    )

        def stage_inner_config(config, openings=None):
            # Both changes stay inside the original editor's undoable draft.
            # A failed geometry stage cannot leave new settings behind.
            if openings is not None:
                accept = getattr(editor, "_receiving_stage_selected_nfb_openings", None)
                if not callable(accept):
                    raise ValueError("主開孔編輯器尚未連接 NFB 暫存開孔")
                accept(openings)
            editor._receiving_staged_config = deepcopy(config)

        editor._receiving_stage_config = stage_inner_config
        editor_host = ttk.Frame(container)
        editor_host.pack(fill="both", expand=True)

        def canceled_inner_tab():
            # The settings tab does not write to the original Hole Editor
            # until its own Confirm. Cancel discards all new NFB selections,
            # preserves previously staged/main features and returns to Main.
            go_to_main_tab()

        def saved_inner_version(_version_id):
            status.configure(text="受電箱 NFB 開孔已放入主編輯器草稿；尚未寫入板件或版本")
            go_to_main_tab()

        def mount_inner_editor():
            if not editor_host.winfo_exists() or editor_host.winfo_children():
                return
            inner_edit(
                INNER_ROLE, state["version"], saved_inner_version,
                embed_parent=editor_host, after_closed=canceled_inner_tab,
            )

        if tabs is not None:
            def restore_tab_editor(_event=None):
                if tabs.winfo_exists() and tabs.select() == str(container):
                    mount_inner_editor()
            tabs.bind("<<NotebookTabChanged>>", restore_tab_editor, add="+")
        mount_inner_editor()
        return container

    return open_multi_settings(
        self.app.root,
        # Avoid copying the entire workspace merely to read the mode.
        get_snapshot=lambda: {
            "active_mode": self.app.designer_workspace.active_mode,
        },
        get_switch=lambda: self.receiving_switch_adapter(namespace),
        switch_mode=lambda mode: _switch_mode(self, namespace, mode),
        resize_connections=lambda index, delta: self.resize_receiving_bays(
            namespace, index, delta, refresh_controls=False
        ),
        resize_sets=resize_sets,
        get_candidate_ports=candidate_ports,
        get_inner_candidate_ports=inner_candidate_ports,
        get_nfb_transaction_ports=nfb_transaction_ports,
        select_bay=select_bay,
        rename_bay=rename_bay,
        on_setting_selected=select_existing_setting,
        get_brand=(single_brand if single else
                   lambda: self.receiving_switch_adapter(namespace).brand),
        set_brand=set_single_brand if single else set_global_brand,
        get_brand_change_impact=preview_parent_brand_impact,
        get_settings_ports=lambda index: self.receiving_settings_ports(namespace, index),
        get_original_door_marks=existing_door_marks,
        get_initial_door_marks=cached_initial_door_marks,
        get_applied_version_labels=applied_version_labels,
        get_real_cut_preview_request=real_cut_preview_request,
        get_dimension_group=dimension_group,
        get_single_size_quantity=single_size_quantity,
        set_single_size_quantity=set_single_size_quantity,
        edit_single_holes=edit_single_holes,
        edit_single_inner_door=edit_single_inner_door,
        edit_multi_inner_door=edit_multi_inner_door,
        on_brand_close=None if single else finalize_global_brand,
        on_close=lambda: _restore_receiving_assembly_after_modal(self, namespace),
        dialog_kind="single" if single else "multi",
    )


def _restore_receiving_assembly_after_modal(owner, namespace):
    """Settle Receiving + Assembly state, then commit one final close-boundary update."""
    # Modal +連/−連 intentionally avoids a heavyweight 3D solve on every click.
    # Project the final selected Set/Bay first, but do not manufacture yet:
    # restoring Assembly/navigation can itself queue or materialize canonical
    # state, so an earlier receipt can become stale before close() returns.
    owner.sync_receiving_current_bay(namespace, refresh_controls=False)
    # Reconcile topology-derived physical identities against the now-current
    # Receiving Bay before manufacturing. Keep this close-boundary contract
    # generic: applicability/manufacturing policy for any individual derived
    # part belongs to that part's own authority and acceptance.
    owner.sync_authoritative_derived_parts(namespace)

    from phase6_manufacturing_adapter import (
        build_manufacturing_cache_key,
        resolve_for_app,
    )

    designer = owner.app
    scheduler = designer._phase6_update_scheduler
    previous_executor = getattr(scheduler, "executor", None)

    # Any calculation that does run during this close transaction must leave a
    # manufacturing receipt for the post-calculation semantic state. Equivalent
    # state remains a cache/no-op and does not manufacture a second time.
    if callable(previous_executor):
        def execute_with_receiving_receipt(reasons):
            result = previous_executor(reasons)
            if build_manufacturing_cache_key(designer).fingerprint != getattr(
                designer, "_phase6_last_resolved_manufacturing_signature", None
            ):
                try:
                    resolve_for_app(designer)
                except ValueError as exc:
                    # Switching a Quantity version brand can invalidate a
                    # previously inherited NFB CSV model. The operator must
                    # still be able to close the settings dialog and reselect
                    # that model; manufacturing remains blocked with no new
                    # receipt or stale source success.
                    if not str(exc).startswith(
                        "NFB_QUANTITY_INHERITED_MODEL_NEEDS_RESELECTION:"
                    ):
                        raise
                    designer.settings_status_var.set(str(exc))
            return result
        scheduler.executor = execute_with_receiving_receipt

    try:
        owner.refresh_receiving_set_bay_control(namespace)
        # Use the Fold Designer that owns the Assembly mode, not the unrelated
        # GUI scene callback host (whose identity lacks designer_workspace).
        if getattr(designer, "_phase6_3d_display_mode", None) != "assembly":
            show_assembly = namespace.get("_phase6_show_assembly")
            if callable(show_assembly):
                show_assembly(designer)
            else:
                raise RuntimeError("原組合體導覽入口尚未連接")
        else:
            mount = namespace.get("_phase6_mount_shared_content")
            if callable(mount):
                mount(designer, "assembly")
            else:
                raise RuntimeError("組合體左側內容掛載入口尚未連接")
            selection = getattr(designer, "part_var", None)
            if selection is not None:
                current = getattr(selection, "get", None)
                # Tk traces fire even on an equal StringVar.set(). Avoid
                # inventing a new intent when Assembly is already selected.
                if not callable(current) or current() != "組合體":
                    selection.set("組合體")

        current_signature = build_manufacturing_cache_key(designer).fingerprint
        receipt_signature = getattr(
            designer, "_phase6_last_resolved_manufacturing_signature", None
        )
        signature_changed = current_signature != receipt_signature
        pending_dirty = bool(
            getattr(scheduler, "dirty", ()) or getattr(scheduler, "staged", ())
        )

        # Do not route this final queue through designer.submit_update_intent():
        # that public facade rebinds scheduler.executor to the normal executor,
        # which would discard the receipt wrapper installed for this close
        # transaction. Queue on the already-owned Scheduler instead, then drain
        # exactly once after *all* close-boundary state has settled.
        if signature_changed:
            submit = getattr(scheduler, "submit", None)
            if callable(submit):
                submit("geometry", immediate=False)
            else:
                # Compatibility for focused legacy/test schedulers only.
                designer.submit_update_intent("geometry", commit=False)
        if signature_changed or pending_dirty:
            scheduler.flush_now()
    finally:
        if callable(previous_executor):
            scheduler.executor = previous_executor
