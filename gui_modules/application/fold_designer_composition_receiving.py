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
    if "surface_features" in projected:
        for role in ("head", "tail"):
            if role in projected["surface_features"]:
                app.designer_workspace.stash_features(role, projected["surface_features"][role])
    from ae_engine.receiving_layout import receiving_bay_joint_face_features
    workspace = app.designer_workspace
    workspace.stash_face_features("box_body", receiving_bay_joint_face_features(
        adapter.layout,
        set_index=adapter.selection.set_index,
        bay_index=adapter.selection.bay_index,
        thickness=float(projected.get("t", 2)),
        frame_width=float(projected.get("fw", 29)),
        existing=workspace.face_features_for("box_body"),
    ))
    original = required("original")
    number = float if projected.get("active_mode") == "quantity" else original.get_int
    app.state.w = number(projected["w"])
    app.state.h = number(projected["h"])
    app.state.d = number(projected["d"])
    app._phase6_last_w = app.state.w
    app._phase6_last_d = app.state.d
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
    if getattr(app, "_phase6_receiving_set_bay_guard", False):
        return False
    if app._phase6_input_snapshot.get("active_mode") == "quantity":
        from ae_engine.receiving_quantity_box import update_common_box
        candidate = update_common_box(_current_mode_snapshot(self, namespace),
                                     {axis: getattr(app, "v_" + axis).get() for axis in ("w", "h", "d")})
        app._phase6_input_snapshot.update(candidate)
        app.designer_workspace.set_receiving_common_box(candidate["receiving_quantity_box"])
        self.receiving_adapter(namespace, reset=True)
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        return True
    adapter = self.receiving_adapter(namespace)
    if adapter is None:
        return False
    required = lambda name: self._required(namespace, name)
    original = required("original")
    adapter.update_current_bay(
        width=original.get_int(app.v_w.get()),
        height=original.get_int(app.v_h.get()),
        depth=original.get_int(app.v_d.get()),
    )
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
    return True

def back_panel_mode_control_is_applicable(self, namespace):
    """Return whether the Receiving header rear-panel choice applies."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
    if cabinet_family_policy.canonical_family_name(snapshot) != "受電箱":
        return False
    state = required("_phase6_box_structure_state")(app)
    return (
        str(state.get("active_type") or "")
        == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    )

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
    if cabinet_family_policy.canonical_family_name(snapshot) != "受電箱":
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
    if not frame.winfo_manager():
        before = getattr(getattr(app, "bend_ui", None), "nb", None)
        options = {
            "fill": original.tk.X,
            "pady": (0, 4),
        }
        if (
            before is not None
            and before.winfo_manager()
            and before.master is frame.master
        ):
            options["before"] = before
        frame.pack(**options)
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
):
    """Resize one switch layer's connection count only."""
    switch = self.receiving_switch_adapter(namespace)
    if not switch.resize_connections(
        int(layer_index), int(delta)
    ):
        return False
    self.mark_receiving_switch_layout_dirty(namespace, switch)
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

def receiving_bay_preview_request(self, namespace, set_index, bay_index):
    """用獨立 request 重建指定連；不更動 live app 或 manufacturing cache。"""
    from types import SimpleNamespace
    from copy import deepcopy
    from phase6_manufacturing_adapter import build_manufacturing_request, build_scene_payload_for_app
    from phase6_manufacturing_service import resolve
    from phase6_fold_profiles import merge_box_body_profile, build_endcap_xy_profiles
    from phase6_settings_profile_projection import project_part_dimensions
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
    from ae_engine.display_dimensions import resolve_operator_finished_dimensions
    app = self.app
    snapshot = project_receiving_bay_legacy_aliases(
        app._phase6_input_snapshot, set_index=set_index, bay_index=bay_index,
    )
    settings = {**dict(app._settings_values), **{key: snapshot[key] for key in ("w", "h", "d")}}
    snapshot.update(settings)
    snapshot["part_dimensions"] = project_part_dimensions(snapshot)
    from phase6_sync_envelope import stable_fingerprint
    fingerprint = stable_fingerprint({"snapshot": snapshot, "profiles": app.designer_workspace.part_profiles_snapshot(), "features": app.designer_workspace.part_features_snapshot(), "face_features": app.designer_workspace.part_face_features_snapshot(), "box_profile": app.state.profiles_vault.get("箱身", ()), "corners": app._phase6_corner_state})
    cache = getattr(self, "_receiving_bay_preview_cache", {})
    cache_key = (set_index, bay_index)
    if cache_key in cache and cache[cache_key][0] == fingerprint:
        return cache[cache_key][1]
    box_profile = merge_box_body_profile(app.state.profiles_vault.get("箱身", ()), snapshot)
    profile_map = {key: build_endcap_xy_profiles(snapshot, part_key=key) for key in ("head", "tail")}
    workspace = app.designer_workspace
    structure = snapshot.get("workspace", {}).get("box_body_structure", snapshot.get("box_body_structure", {}))
    from ae_engine.receiving_layout import receiving_bay_joint_face_features
    joint_faces = receiving_bay_joint_face_features(
        snapshot["receiving_layout"], set_index=set_index, bay_index=bay_index,
        thickness=float(snapshot.get("t", 2)), frame_width=float(snapshot.get("fw", 29)),
        existing=workspace.face_features_for("box_body"),
    )
    proxy_workspace = Phase6DesignerWorkspace.from_snapshot({
        **snapshot, "existing_parts": workspace.available_parts,
        "part_profiles": workspace.part_profiles_snapshot(),
        "part_features": {**workspace.part_features_snapshot(), **snapshot.get("part_features", {})},
        "part_face_features": {**workspace.part_face_features_snapshot(), "box_body": joint_faces},
    })
    proxy_workspace.set_box_body_structure_state(structure)
    for key, profiles in profile_map.items():
        proxy_workspace.stash_profiles(key, profiles)
    proxy = SimpleNamespace(**app.__dict__)
    proxy._phase6_input_snapshot = snapshot
    proxy._settings_values = settings
    proxy._phase6_box_whd = {key: snapshot[key] for key in ("w", "h", "d")}
    proxy.designer_workspace = proxy_workspace
    proxy.state = SimpleNamespace(profiles_vault={"箱身": box_profile}, profiles={})
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
    request = build_manufacturing_request(
        proxy, scene_payload_builder=lambda key: build_scene_payload_for_app(proxy, key),
        render_data_provider=lambda key, payload: app._scene_query_callback(key, feature_payload(key, payload)),
        part_spec_provider=lambda key, payload: app._part_spec_query_callback(key, feature_payload(key, payload)),
        finished_dimensions_provider=dimensions,
    )
    resolved = resolve(request).geometry
    from ae_engine.receiving_layout import receiving_bay_assembly_offsets
    bay_offset = receiving_bay_assembly_offsets(snapshot["receiving_layout"], set_index=set_index)[bay_index]
    parts = tuple(AssemblyScenePart(
        part_key=part.part_key, render_data=part.render_data,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=tuple(a + b for a, b in zip(part.offset, bay_offset)),
    ) for part in resolved.parts)
    result = FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(assembly_parts=parts, preserve_endcap_core_origin=True),
        x_profile=(), y_profile=(), part_key="assembly",
        finished_dimensions=dimensions(), thickness=float(snapshot.get("t", 2)),
    )
    cache[cache_key] = (fingerprint, result)
    self._receiving_bay_preview_cache = cache
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
    from ae_engine.receiving_shared_settings import setting_value
    from ae_engine.sheetmetal_features import (
        resolve_endcap_finished_face_guide, feature_surface_from_rect, RectGuide, Vec2,
    )
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

    def change(kind, value, indices=()):
        current = adapter.selection.bay_index
        for index in tuple(indices) or (current,):
            adapter.select_bay(index + 1)
            adapter.update_setting(kind, value)
        adapter.select_bay(current + 1)
        commit()

    def share(kind, indices):
        adapter.share_setting(kind, indices)
        commit()

    def unlink(kind):
        adapter.unlink_setting(kind)
        commit()

    def dimensions(width, height, depth, door_columns=None):
        from ae_engine.sheetmetal_part_adapters import validate_door_layout_dimensions
        changes = {"width": width, "height": height, "depth": depth}
        if door_columns is not None:
            validate_door_layout_dimensions(door_columns, total_width=width, total_height=height)
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

    def holes(role, indices=()):
        bay = adapter.current_bay()
        width, depth = float(bay["width"]), float(bay["depth"])
        thickness = float(self.app._phase6_input_snapshot.get("t", 2))
        guide = resolve_endcap_finished_face_guide(width, depth, thickness)
        surface = feature_surface_from_rect(f"{role}_finished_face", guide.min_point, guide.max_point)
        row = adapter.layout["sets"][set_index]
        features = setting_value(row, adapter.selection.bay_index, f"{role}_features")
        host = getattr(self.app._scene_query_callback, "__self__", None)
        if host is None or not hasattr(host, "_open_unified_hole_editor"):
            raise ValueError("目前未連接既有 Hole Editor")
        def save_features():
            kind = f"{role}_features"
            current = adapter.selection.bay_index
            targets = tuple(indices) or (current,)
            if len(targets) > 1:
                adapter.select_bay(targets[0] + 1)
                adapter.share_setting(kind, targets)
            adapter.update_setting(kind, features)
            adapter.select_bay(current + 1)
            commit()

        host._open_unified_hole_editor(
            role, "封頭" if role == "head" else "封尾", surface, width, depth,
            feature_list_override=features,
            sync_callback=save_features,
            reference_guide=RectGuide(Vec2(0, 0), Vec2(width, depth), "finished_boundary"),
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
        settings = {key: source.get(key, value) for key, value in app._settings_values.items()}
        settings.update({axis: source[axis] for axis in ("w", "h", "d")})
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
        def execute_without_preview(reasons):
            result = previous_executor(reasons)
            # Manufacturing is independent of whether the user displays 3D.
            # This remains inside the sole Scheduler calculation executor.
            from phase6_manufacturing_adapter import resolve_for_app
            try:
                resolve_for_app(app)
            except ValueError as exc:
                if require_committed:
                    raise
                app.settings_status_var.set(str(exc))
            return result
        if not getattr(app, "preview_3d_enabled", True):
            scheduler.executor = execute_without_preview
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
    from .receiving_mode_controls import ask_initial_dimensions
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
        dimensions = ask_initial_dimensions(app.root, target)
        if dimensions is None:
            self.refresh_receiving_set_bay_control(namespace)
            return False
    source = _current_mode_snapshot(self, namespace)
    planned = deepcopy(session)
    was_dirty = app.designer_workspace.dirty
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
    from ae_engine.receiving_quantity_box import require_valid_quantity_features
    from phase6_manufacturing_adapter import build_manufacturing_cache_key
    require_valid_quantity_features(_current_mode_snapshot(self, namespace))
    signature = build_manufacturing_cache_key(self.app).fingerprint
    if signature != getattr(self.app, "_phase6_last_resolved_manufacturing_signature", None):
        raise ValueError("共用箱體預覽尚未對應目前已提交設定")
    geometry = getattr(self.app, "_phase6_last_resolved_manufacturing_geometry", None)
    if geometry is None:
        raise ValueError("共用箱體製造結果尚未完成")
    parts = tuple(AssemblyScenePart(
        part_key=part.part_key, render_data=part.render_data,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=part.offset,
    ) for part in geometry.parts)
    return FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(assembly_parts=parts, preserve_endcap_core_origin=True),
        x_profile=(), y_profile=(), part_key="assembly",
        finished_dimensions=tuple(self.app._phase6_box_whd[axis] for axis in ("w", "h", "d")),
        thickness=float(self.app._phase6_input_snapshot.get("t", 2)),
    )


def _open_common_box(self, namespace):
    from .receiving_set_bay_controls import open_receiving_layer_preview
    from ae_engine.receiving_quantity_box import update_common_box, project_common_box, BOX_KEY
    from .command_router import _Phase6UpdateScheduler
    app = self.app
    listeners = []
    def change_common(changes):
        source = _current_mode_snapshot(self, namespace)
        candidate = update_common_box(source, changes)
        _apply_mode_snapshot(self, namespace, candidate)
        for listener in tuple(listeners):
            listener()
    def dimensions(width, height, depth, door_columns=None):
        changes = {"w": width, "h": height, "d": depth}
        if door_columns is not None:
            door = deepcopy(app._phase6_input_snapshot[BOX_KEY].get("door_state", {}))
            door["door_layout_columns"] = [[w, list(hs)] for w, hs in door_columns]
            changes["door_state"] = door
        change_common(changes)
    ports = {
        "row": lambda: project_common_box(_current_mode_snapshot(self, namespace))["receiving_layout"]["sets"][0],
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
            brand=app._phase6_input_snapshot[BOX_KEY]["switch_brand"],
            render_request=request, preview_error=preview_error, settings_ports=ports,
            bay_request_provider=lambda: (_common_preview_request(self, namespace),),
            common_box=True,
        )
    scheduler = _Phase6UpdateScheduler(app, executor=show)
    scheduler.submit("display", immediate=True)
    return True


def _refresh_mode_controls(self, namespace):
    from .receiving_mode_controls import build_mode_controls
    app = self.app
    controls = getattr(self, "_receiving_mode_controls", None)
    applicable = self.receiving_layout_applicable()
    if controls is None and applicable:
        controls = build_mode_controls(
            app.receiving_set_bay_control.master,
            on_switch=lambda target: _switch_mode(self, namespace, target),
            on_common=lambda: _open_common_box(self, namespace),
        )
        self._receiving_mode_controls = controls
        app.receiving_mode_controls = controls
    if controls is None:
        return False
    if not applicable:
        controls.frame.pack_forget()
        return False
    controls.refresh(app._phase6_input_snapshot.get("active_mode", "set_bay"),
                     app.designer_workspace.snapshot().get("quantity"))
    before = app.receiving_set_bay_control if app.receiving_set_bay_control.winfo_manager() else app.bend_ui.nb
    options = {"fill": tk.X, "pady": (0, 4)}
    if before.winfo_manager() and before.master is controls.frame.master:
        options["before"] = before
    controls.frame.pack(**options)
    return True
