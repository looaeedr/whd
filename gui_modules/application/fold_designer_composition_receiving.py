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
    if app._phase6_input_snapshot.get("active_mode") == "quantity" and getattr(app, "_phase6_initializing", False):
        return False
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
        int(layer_index), int(delta)
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
    """Translate an immutable FinalScene preview; never rebuild or mutate sheets.

    This is valid only after the local PartSpec/Joint fingerprint matches.
    Unsupported/custom scene envelopes fail closed to the full solve caller.
    """
    from dataclasses import replace
    from math import isfinite
    from phase6_final_scene_contracts import (
        AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
    )
    if not isinstance(request, FinalSceneViewRequest):
        return None
    scene = request.render_data
    if (not isinstance(scene, AssemblySceneRenderData)
            or not scene.preserve_endcap_core_origin
            or scene.interference_probe_parts or scene.show_interference
            or scene.joint_diagnostics or scene.collision_certification_diagnostics):
        return None
    if len(old_anchor) != 3 or len(new_anchor) != 3:
        return None
    delta = tuple(float(b) - float(a) for a, b in zip(old_anchor, new_anchor))
    if not all(isfinite(v) for v in delta):
        return None
    parts = []
    for part in scene.assembly_parts:
        if (not isinstance(part, AssemblyScenePart)
                or part.placement == "standalone" or len(part.offset) != 3):
            return None
        offset = tuple(float(v) + shift for v, shift in zip(part.offset, delta))
        if not all(isfinite(v) for v in offset):
            return None
        parts.append(replace(part, offset=offset))
    return replace(request, render_data=replace(
        scene, assembly_parts=tuple(parts)))


def _receiving_bay_preview_face_features_key(face_features):
    """Ignore only transient Joint locks which the real per-Bay solver replaces.

    receiving_bay_joint_face_features removes the source_type below from
    existing BoxBody faces and reconstructs the selected Bay's locks using
    receiving_layout and the actual W/H/D/T/FW. Both remain in the preview
    fingerprint. Authored faces and all non-BoxBody features still invalidate.
    Never mutate the Designer workspace or the manufacturing input.
    """
    if not isinstance(face_features, dict):
        return face_features
    box_faces = face_features.get("box_body")
    if not isinstance(box_faces, dict):
        return face_features
    if not all(isinstance(values, (list, tuple))
               for values in box_faces.values()):
        return face_features  # unknown schema: preserve full key
    retained = {
        face: remaining
        for face, values in box_faces.items()
        if (remaining := [feature for feature in values
                         if getattr(feature, "source_type", "") !=
                         "receiving_joint_side_lock"])
    }
    if retained == box_faces:
        return face_features
    return {**face_features, "box_body": retained}


def _receiving_bay_preview_fingerprint_snapshot(snapshot, *, set_index, bay_index,
                                                 allow_upstream_translation=False,
                                                 allow_suffix_topology_reuse=False):
    """Read-only key projection for provably unrelated *trailing* Bay dimensions.

    The requesting Bay's own W/H/D, its left/right Joint participants and
    every preceding Bay remain part of the key: the left chain controls
    assembly X/Y/Z, and the immediate right neighbor controls side locks.
    Only distant prefixes (with world-offset rebasing) and Bays strictly
    AFTER the right neighbor are independent of this Bay's local sheet.
    For tail-only topology resize, drop distant suffix rows AND the matching
    unused per-Bay setting refs/values from the key; a SHARED setting value
    referenced by this Bay or its neighbor is always retained.
    All relevant IDs, nearby Joints, NFB, features, other Sets, model and
    global geometry authority remain included and fail closed.
    NEVER use this deliberately incomplete copy as a saved/solved layout.
    """
    # Copy-on-write only the key's suffix path. Deep-copying the entire
    # projected project on every display refresh would itself be a slowdown.
    fingerprint_snapshot = dict(snapshot)
    if fingerprint_snapshot.get("model") not in ("受電箱", "RECEIVING"):
        return fingerprint_snapshot
    if fingerprint_snapshot.get("active_mode", "set_bay") != "set_bay":
        return fingerprint_snapshot
    layout = fingerprint_snapshot.get("receiving_layout")
    if not isinstance(layout, dict) or layout.get("schema") != "receiving-layout-v1":
        return fingerprint_snapshot
    sets = layout.get("sets")
    if not isinstance(sets, list) or type(set_index) is not int:
        return fingerprint_snapshot
    if not 0 <= set_index < len(sets) or type(bay_index) is not int:
        return fingerprint_snapshot
    selected = sets[set_index]
    if not isinstance(selected, dict):
        return fingerprint_snapshot
    bays = selected.get("bays")
    joints = selected.get("joints")
    if not isinstance(bays, list) or not isinstance(joints, list):
        return fingerprint_snapshot
    if not 0 <= bay_index < len(bays) or len(joints) != len(bays) - 1:
        return fingerprint_snapshot
    if not all(isinstance(row, dict) and row.get("stable_id")
               for row in bays):
        return fingerprint_snapshot
    # Custom joints, custom parts and committed Joint relief may connect
    # non-neighboring Bays. Even with both optimization flags disabled, the
    # ordinary path below would still hide trailing dimensions. Never reuse
    # a possibly stale FinalScene: retain the entire authoritative key.
    if any(fingerprint_snapshot.get(field)
           for field in ("assembly_joints", "custom_parts", "joint_relief_state")):
        return fingerprint_snapshot
    keep_count = min(len(bays), bay_index + 2)
    trim_suffix = allow_suffix_topology_reuse and keep_count < len(bays)
    new_settings = None
    if trim_suffix and "settings" in selected:
        from collections.abc import Mapping
        raw = selected["settings"]
        if not isinstance(raw, Mapping):
            return fingerprint_snapshot
        included = tuple(str(row["stable_id"]) for row in bays[:keep_count])
        new_settings = {}
        for kind, row in raw.items():
            if (not isinstance(row, Mapping) or set(row) != {"refs", "values"}
                    or not isinstance(row["refs"], Mapping)
                    or not isinstance(row["values"], Mapping)):
                return fingerprint_snapshot
            if any(bay_id not in row["refs"] for bay_id in included):
                return fingerprint_snapshot
            refs = {bay_id:row["refs"][bay_id] for bay_id in included}
            if any(ref not in row["values"] for ref in refs.values()):
                return fingerprint_snapshot
            values = {ref:row["values"][ref] for ref in refs.values()}
            new_settings[kind] = {"refs":refs, "values":values}
    hidden = (() if trim_suffix else tuple(range(bay_index + 2, len(bays))))
    if allow_upstream_translation and bay_index >= 2:
        hidden += tuple(range(0, bay_index - 1))
    if not hidden and not trim_suffix:
        return fingerprint_snapshot
    # Copy-on-write: only a derived *cache key*, never an output or saved DTO.
    shallow_layout = dict(layout)
    shallow_sets = list(sets)
    shallow_set = dict(selected)
    shallow_bays = list(bays[:keep_count] if trim_suffix else bays)
    for position in hidden:
        later = dict(bays[position])
        for axis in ("width", "height", "depth"):
            later.pop(axis, None)
        shallow_bays[position] = later
    shallow_set["bays"] = shallow_bays
    if trim_suffix:
        shallow_set["joints"] = list(joints[:keep_count - 1])
        if new_settings is not None:
            shallow_set["settings"] = new_settings
    shallow_sets[set_index] = shallow_set
    shallow_layout["sets"] = shallow_sets
    fingerprint_snapshot["receiving_layout"] = shallow_layout
    return fingerprint_snapshot


def _receiving_cached_bay_inner_door_panel(owner, part_key, payload, factory):
    """Memoize only the exact source-free raw panel used by a real Bay request.

    Per-Bay construction routes its own projected payload through a callback
    bound to the primary GUI host; that host has a different current snapshot.
    This cache therefore belongs to the Receiving composition, not the host
    and not the global manufacturing result. All Joint/relief/collision/world
    transforms still execute in the downstream full resolver. Frame/Divider
    material reads certified DXF files and is never served by this helper.
    """
    key = str(part_key or "")
    if not (key.startswith("inner_door:") and key.endswith(":panel")
            and isinstance(payload, Mapping)
            and payload.get("model") in ("受電箱", "RECEIVING")
            and payload.get("active_mode") == "set_bay"):
        return factory()
    from collections import OrderedDict
    from ae_engine.cabinet_types import policy as family_policy
    from phase6_manufacturing_contracts import manufacturing_fingerprint

    panels = family_policy.derive_inner_door_panels(dict(payload))
    panel = next((part for part in panels if part.stable_id == key), None)
    if panel is None:
        return factory()  # Let the canonical factory raise on invalid topology.
    features = tuple(payload.get("features") or ())
    try:
        signature = manufacturing_fingerprint({
            "panel": panel, "features": features,
        })
    except (TypeError, ValueError, OverflowError):
        return factory()  # Unknown Feature DTO: never guess equivalence.
    history = getattr(owner, "_receiving_raw_inner_door_panel_history", None)
    if history is None:
        history = OrderedDict()
        owner._receiving_raw_inner_door_panel_history = history
    if signature in history:
        history.move_to_end(signature)
        return history[signature]
    material = factory()
    history[signature] = material
    history.move_to_end(signature)
    while len(history) > 8:
        history.popitem(last=False)
    return material


def receiving_bay_preview_request(self, namespace, set_index, bay_index, *, preview_layout=None):
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
    source = dict(app._phase6_input_snapshot)
    if preview_layout is not None:
        # Candidate previews run on an isolated layout clone, NEVER live state.
        source["receiving_layout"] = preview_layout
    snapshot = project_receiving_bay_legacy_aliases(
        source, set_index=set_index, bay_index=bay_index,
    )
    settings = {**dict(app._settings_values), **{key: snapshot[key] for key in ("w", "h", "d")}}
    snapshot.update(settings)
    snapshot["part_dimensions"] = project_part_dimensions(snapshot)
    from phase6_sync_envelope import stable_fingerprint
    # Only normal committed Bay previews may rebase world placement. Candidate
    # editors and user-defined/cross-part joints keep the full prefix key.
    allow_rebase = (preview_layout is None and bay_index >= 2
                    and snapshot.get("model") in ("受電箱", "RECEIVING")
                    and snapshot.get("active_mode", "set_bay") == "set_bay"
                    and not any(snapshot.get(k) for k in (
                        "assembly_joints", "custom_parts", "joint_relief_state")))
    fingerprint = stable_fingerprint({"snapshot": _receiving_bay_preview_fingerprint_snapshot(
        snapshot, set_index=set_index, bay_index=bay_index,
        allow_upstream_translation=allow_rebase,
        allow_suffix_topology_reuse=(preview_layout is None),
    ), "profiles": app.designer_workspace.part_profiles_snapshot(), "features": app.designer_workspace.part_features_snapshot(), "face_features": (_receiving_bay_preview_face_features_key(
        app.designer_workspace.part_face_features_snapshot())
        if snapshot.get("model") in ("受電箱", "RECEIVING")
        and snapshot.get("active_mode", "set_bay") == "set_bay"
        else app.designer_workspace.part_face_features_snapshot()), "box_profile": app.state.profiles_vault.get("箱身", ()), "corners": app._phase6_corner_state})
    cache = getattr(self, "_receiving_bay_preview_cache", {})
    cache_key = (set_index, bay_index)
    virtual_cache = getattr(self, "_receiving_bay_virtual_preview_cache", {})
    virtual_key = (set_index, bay_index, fingerprint)
    if preview_layout is not None and virtual_key in virtual_cache:
        return virtual_cache[virtual_key]
    prefix = tuple(
        (float(bay["width"]), float(bay["height"]), float(bay["depth"]))
        for bay in snapshot["receiving_layout"]["sets"][set_index]["bays"][:bay_index + 1]
    )
    if preview_layout is None and cache_key in cache and cache[cache_key][0] == fingerprint:
        hit = cache[cache_key]
        if not allow_rebase:
            return hit[1]
        if len(hit) >= 4:
            if hit[3] == prefix:
                return hit[1]
            from ae_engine.receiving_layout import receiving_bay_assembly_offsets
            current_anchor = receiving_bay_assembly_offsets(
                snapshot["receiving_layout"], set_index=set_index)[bay_index]
            rebased = _receiving_rebase_preview_world_offsets(
                hit[1], hit[2], current_anchor)
            if rebased is not None:
                cache[cache_key] = (fingerprint, rebased, current_anchor, prefix)
                return rebased
        # Missing prior world-anchor proof or unsupported render envelope:
        # do not reuse, use the real canonical manufacturing calculation.
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
    def render_bay_part(key, payload):
        source_payload = feature_payload(key, payload)
        render = lambda: app._scene_query_callback(key, source_payload)
        if preview_layout is not None:
            # Candidate editing is isolated from committed Bay material reuse.
            return render()
        return _receiving_cached_bay_inner_door_panel(
            self, key, source_payload, render,
        )

    request = build_manufacturing_request(
        proxy, scene_payload_builder=lambda key: build_scene_payload_for_app(proxy, key),
        render_data_provider=render_bay_part,
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
    ) for part in resolved.parts if part.placement != "standalone")
    result = FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(assembly_parts=parts, preserve_endcap_core_origin=True),
        x_profile=(), y_profile=(), part_key="assembly",
        finished_dimensions=dimensions(), thickness=float(snapshot.get("t", 2)),
    )
    if preview_layout is None:
        cache[cache_key] = (fingerprint, result, bay_offset, prefix)
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

    def change(kind, value, indices=None):
        # No explicitly highlighted Bay means no edit. Omitted indices keeps
        # compatibility for the direct one-Bay editor, not the multi GUI.
        targets = ((adapter.selection.bay_index,) if indices is None
                   else tuple(indices))
        if not targets:
            return False
        current = adapter.selection.bay_index
        for index in targets:
            adapter.select_bay(index + 1)
            adapter.update_setting(kind, value)
        adapter.select_bay(current + 1)
        commit()
        return True

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

    def holes(role, indices=None):
        if indices is not None and not tuple(indices):
            return False
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
            targets = (current,) if indices is None else tuple(indices)
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
        receiving_base_plate_commit=lambda config: commit_receiving_base_plate_settings(
            input_snapshot=app._phase6_input_snapshot,
            settings_values=app._settings_values,
            submit_geometry_update=lambda: app.submit_update_intent("geometry", commit=True),
            config=config,
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
    from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS
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
        dimensions = {key: int(BOX_BODY_DEFAULTS[key]) for key in ("w", "h", "d")}
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
    ) for part in geometry.parts if part.placement != "standalone")
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
    from ae_engine.receiving_quantity_box import normalize_common_box
    # Do not construct a common box from unrelated Set/Bay values: the owner
    # requires explicit quantity-mode initialization before any edit.
    try:
        box = normalize_common_box(_current_mode_snapshot(self, namespace).get(BOX_KEY))
    except ValueError as exc:
        from tkinter import messagebox
        messagebox.showwarning("共用箱體尚未初始化", str(exc), parent=app.root)
        return False
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
            door = deepcopy(box.get("door_state", {}))
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
            brand=normalize_common_box(_current_mode_snapshot(self, namespace).get(BOX_KEY))["switch_brand"],
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

    def nfb_physical_bay_snapshot(set_index,bay_index):
        """Real selected Bay authority, not the unprojected root UI snapshot."""
        from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
        source=_current_mode_snapshot(self,namespace)
        source["receiving_layout"]=candidate_adapter().layout
        return project_receiving_bay_legacy_aliases(
            source,set_index=set_index,bay_index=bay_index,
        )

    def select_bay(set_index, bay_index):
        # Reuse canonical selection; no new data owner or manufacturing draw.
        adapter = self.receiving_adapter(namespace)
        adapter.select_set(int(set_index) + 1)
        adapter.select_bay(int(bay_index) + 1)

    def select_existing_setting(set_index, bay_index, kind):
        """Bind the list choice to the original per-bay setting value/owner.

        No editor popup, duplicated parser, or manufacturing calculation is
        initiated merely by selecting a category in the Listbox.
        """
        from ae_engine.receiving_shared_settings import setting_value
        ports = self.receiving_settings_ports(namespace, int(set_index))
        ports["select"](int(bay_index))
        return setting_value(ports["row"](), int(bay_index), kind)

    def single_brand():
        from ae_engine.receiving_quantity_box import normalize_common_box
        source = _current_mode_snapshot(self, namespace)
        return normalize_common_box(source.get("receiving_quantity_box"))["switch_brand"]

    def set_single_brand(value):
        from ae_engine.receiving_quantity_box import update_common_box
        source = _current_mode_snapshot(self, namespace)
        if source.get("active_mode") != "quantity":
            raise ValueError("單只品牌需在單箱體模式設定")
        if single_brand() == value:
            return False
        candidate = update_common_box(source, {"switch_brand": value})
        _apply_mode_snapshot(self, namespace, candidate)
        return True

    def set_global_brand(value):
        # The original Receiving layout is the one NFB authority. In the
        # modal, edit data only; geometry rebuild on ComboboxSelected blocks
        # Tk's UI thread (noticeably on the first selection).
        adapter = self.receiving_adapter(namespace)
        if not adapter.set_global_brand(value):
            return False
        self.mark_receiving_switch_layout_dirty(namespace, adapter)
        return True

    def finalize_global_brand():
        # After the modal has closed, project and submit once for the latest
        # selected brand. The operator can change brands without a 3D reload.
        self.sync_receiving_current_bay(namespace, refresh_controls=False)
        self.app.submit_update_intent("geometry", commit=True)

    def existing_door_marks(set_index, bay_index):
        # The lightweight diagram reuses ONLY the existing Door baseline.
        # Do not synthesize handle/nameplate positions when source is missing.
        from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
        from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
        from .receiving_multi_settings_window import extract_original_door_marks

        host = getattr(self.app._scene_query_callback, "__self__", None)
        if host is None or not hasattr(host, "_door_layout_baseline_scene"):
            return ()
        snapshot = dict(self.app._phase6_input_snapshot)
        snapshot["receiving_layout"] = self.receiving_adapter(namespace).layout
        projected = project_receiving_bay_legacy_aliases(
            snapshot, set_index=int(set_index), bay_index=int(bay_index)
        )
        columns = projected.get("door_layout_columns") or ()
        if not projected.get("multi_door_enabled") or not columns:
            return ()
        cells = derive_door_layout_cells(columns)
        # The operator sketch has two Door faces in a single column.
        # Do not invent a projection for unsupported multi-column topology.
        if len(cells) != 2 or any(cell.column_index != 0 for cell in cells):
            return ()
        result = []
        for cell in sorted(cells, key=lambda item: item.row_index):
            scene, _status = host._door_layout_baseline_scene(cell, projected)
            if scene is None:
                return ()
            result.append(extract_original_door_marks(scene))
        return tuple(result)

    def cached_initial_door_marks():
        """Show original handle/nameplate from committed Assembly, no DXF read.

        The pre-rendered scenes are only a preview source. Never use a stale
        scene from another family or invent positions from nominal sizes.
        Applied Set/Bay sketches continue to load their exact source through
        existing_door_marks().
        """
        from .receiving_multi_settings_window import extract_original_door_marks

        if str(self.app._phase6_input_snapshot.get("model") or "") not in {
            "受電箱", "RECEIVING"
        }:
            return ()
        resolved = getattr(
            self.app, "_phase6_last_resolved_manufacturing_geometry", None
        )
        parts = {
            str(part.part_key): getattr(part.render_data, "scene", None)
            for part in tuple(getattr(resolved, "parts", ()) or ())
            if str(getattr(part, "part_key", "") or "") in {
                "door_c1_r1", "door_c1_r2"
            }
        }
        if any(parts.get(key) is None for key in ("door_c1_r1", "door_c1_r2")):
            return ()
        return ((
            extract_original_door_marks(parts["door_c1_r1"]),
            extract_original_door_marks(parts["door_c1_r2"]),
        ),)

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
        from ae_engine.receiving_quantity_box import normalize_common_box
        from phase6_quantity_model import QuantityModel
        snapshot = _current_mode_snapshot(self, namespace)
        if snapshot.get("active_mode") != "quantity":
            raise ValueError("單只設定必須使用單箱體數量模式")
        box = normalize_common_box(snapshot.get("receiving_quantity_box"))
        model = QuantityModel.from_payload(snapshot.get("quantity"))
        return {"width": box["w"], "height": box["h"], "depth": box["d"],
                "count": model.selected_piece_count,
                "total_count": model.total_piece_count,
                "version_count": model.version_count}

    def set_single_size_quantity(width, height, depth, count):
        from ae_engine.receiving_quantity_box import (
            update_common_box, require_valid_quantity_features,
        )
        from phase6_quantity_model import QuantityModel, positive_piece_count
        new_count = positive_piece_count(count)
        snapshot = _current_mode_snapshot(self, namespace)
        if snapshot.get("active_mode") != "quantity":
            raise ValueError("單只設定必須使用單箱體數量模式")
        model = QuantityModel.from_payload(snapshot.get("quantity"))
        model.set_piece_count(new_count)
        candidate = update_common_box(snapshot, {"w": width, "h": height, "d": depth})
        candidate["quantity"] = model.snapshot()
        require_valid_quantity_features(candidate)
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
    from ae_engine.sheetmetal_features import (
        resolve_endcap_finished_face_guide, feature_surface_from_rect, RectGuide, Vec2,
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
        width, depth = float(bay["width"]), float(bay["depth"])
        t = float(self.app._phase6_input_snapshot.get("t", 2))
        guide = resolve_endcap_finished_face_guide(width, depth, t)
        surface = feature_surface_from_rect(
            f"{role}_finished_face", guide.min_point, guide.max_point,
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
            surface, width, depth,
            feature_list_override=draft,
            sync_callback=lambda: None,
            on_confirm=confirmed,
            reference_guide=RectGuide(
                Vec2(0, 0), Vec2(width, depth), "finished_boundary"
            ),
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
        sets = adapter.layout["sets"]
        if type(set_index) is not int or not 0 <= set_index < len(sets):
            raise ValueError("請先選擇要套用的套")
        targets = tuple(sorted(set(highlighted)))
        if any(type(i) is not int or not 0 <= i < len(sets[set_index]["bays"]) for i in targets):
            raise ValueError("簡易圖高亮的連已無效")
        features = candidate_features(candidate_library(), role, version_id)
        # One validated all-or-nothing update; retains the active editor
        # selection and avoids the old per-Bay UI/geometry churn.
        adapter.apply_candidate_to_bays(
            role, set_index, targets, features, version_id=version_id,
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
    from ae_engine.receiving_inner_door_pairing import validate_inner_door_allocation
    from ae_engine.receiving_hole_candidates import version_label
    from ae_engine.receiving_shared_settings import setting_value, switch_filenames_in_layer, pack_switch_layer, validate_setting, SETTING_DEFAULTS
    from ae_engine.receiving_switch_model_catalog import model_filenames, display_model, INDEX_PATH

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
        from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
        from .receiving_nfb_source_preview import NfbDxfSourcePreviewPanel
        from ae_engine.receiving_nfb_ui1a_edits import (
            NfbUi1aEditSession, editable_nfb_draft, insert_nfb_slot,
            delete_nfb_slot, move_nfb_slot, replace_nfb_slot_model,
            set_nfb_manual_x, set_nfb_layer_rotation,
            set_nfb_slot_rotation, effective_nfb_rotation,
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
                "layers": setting_value(set_row, bi, "inner_door_layers"),
                "models": setting_value(set_row, bi, "inner_door_models"),
                "layer_heights_mm": setting_value(set_row, bi, "inner_door_layer_heights_mm"),
            }
        else:
            initial = inner_config(inner_library(), version_id)
        if initial.get("layer_heights_mm") is None:
            # Legacy already-verified NFB stays at its old Y until the
            # operator explicitly saves the 330/830 editor defaults.
            initial["layer_heights_mm"] = list(
                SETTING_DEFAULTS["inner_door_layer_heights_mm"]
            )
        parent_modal = getattr(self.app.root, "_receiving_multi_settings_window", None)
        multi_entry = bool(
            parent_modal is not None and parent_modal.winfo_exists()
            and self.app.designer_workspace.active_mode == "set_bay"
        )
        # The Set/Bay version editor (standalone) writes candidate X;
        # ordinary Hole Editor tab entries update the currently drawn Bay.
        direct_to_drawing = embed_parent is not None and not multi_entry
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
                        else version_label(version_id))).pack(anchor="w")
        # Legacy inner-door candidate layers and NFB physical layers are
        # DIFFERENT concepts. The #1491 draft must not rewrite either owner.
        layers = tk.IntVar(master=modal, value=initial["layers"])
        nfb_physical_layers = tk.IntVar(master=modal, value=initial["layers"])
        layer_height_vars = tuple(
            tk.StringVar(master=modal, value=f"{float(v):g}")
            for v in initial["layer_heights_mm"]
        )
        def read_layer_heights():
            try:
                heights = [float(field.get().strip()) for field in layer_height_vars]
            except (TypeError, ValueError) as exc:
                raise ValueError("請輸入有效的第一層、第二層高度（mm）") from exc
            heights = validate_setting("inner_door_layer_heights_mm", heights)
            snapshot = _current_mode_snapshot(self, namespace)
            columns = snapshot.get("door_layout_columns") or ()
            from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
            cells = derive_door_layout_cells(columns) if columns else ()
            upper_cells = [item for item in cells if item.row_index == 0]
            work_height = (
                float(upper_cells[0].start_height) if len(upper_cells) == 1
                else float(snapshot.get("h", 0.0))
            )
            if work_height <= 0 or heights[layers.get()-1] >= work_height:
                raise ValueError("層高必須在目前內門作業區內，且第一層須在第二層上方")
            return heights
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
        # Keep legacy draft in memory but remove its unapproved controls.
        physical_row = ttk.Frame(frame)
        ttk.Label(physical_row, text="NFB 物理層（未提交草稿）").pack(side="left")
        chosen = [list(switch_filenames_in_layer(slot))
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
            set_brand=self.receiving_switch_adapter(namespace).brand,
            layer_count=nfb_physical_layers.get(), model_layers=initial["models"],
        )})
        edit_session = NfbUi1aEditSession(draft_state["draft"])
        draft_state.session = edit_session
        dict.__setitem__(draft_state,"draft",edit_session.current)
        source_state = {"files": [(), ()], "signature": [None, None]}
        draft_summary = tk.StringVar(master=modal, value="")
        initial_nfb_draft = deepcopy(draft_state["draft"])
        nfb_preview_panel = {"panel": None}
        nfb_source_viewed = {"value": False}

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
                    pack_switch_layer(chosen[0]),
                    pack_switch_layer(chosen[1]) if layers.get() == 2 else "",
                ],
            }
            before = {
                "layer_heights_mm": initial["layer_heights_mm"],
                "layers": initial["layers"],
                "models": [
                    pack_switch_layer(switch_filenames_in_layer(initial["models"][0])),
                    pack_switch_layer(switch_filenames_in_layer(initial["models"][1]))
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
                columns = snapshot.get("door_layout_columns") or ()
                from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
                cells = derive_door_layout_cells(columns) if columns else ()
                upper = [c for c in cells if c.row_index == 0]
                height = float(upper[0].start_height) if len(upper) == 1 else -1.0
                projection = nfb_ui1a_preview(
                    draft_state["draft"], bay_width_mm=width,
                    upper_cell_height_mm=height,
                    layer_heights_mm=staged_heights,
                )
                segments = []
                for entry in projection["layers"]:
                    pitch = entry["adjacent_x_mm"]
                    x_label = ("相鄰 " + "／".join(str(int(p)) for p in pitch) + " mm"
                               if pitch is not None else "X 基準未定")
                    y = entry["nominal_y_from_top_mm"]
                    y_label = (f"名義 Y {y:g} mm" if y is not None else "Y 未定")
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
                    (display_model(slot["filename"]) if slot["filename"] else "（空槽）")
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
                else:
                    entry["slot_brand_var"].set("繼承本層")
            paint_draft_preview()

        def refresh_source(*, force=False):
            if not modal.winfo_exists():
                return
            current_owner = self.receiving_switch_adapter(namespace).brand
            if current_owner != draft_state["draft"]["set_brand"]:
                draft_state["draft"] = reconcile_set_brand(
                    draft_state["draft"], current_owner,
                )
            try:
                stat = INDEX_PATH.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                stamp = (None, None)
            for index, entry in enumerate(layer_rows):
                if index >= draft_state["draft"]["layer_count"]:
                    continue
                brand = view_source_catalog(index)
                signature = (brand, *stamp)
                if not force and signature == source_state["signature"][index]:
                    continue
                source_state["signature"][index] = signature
                try:
                    files = model_filenames(brand)
                except (ValueError,OSError,UnicodeError) as exc:
                    files = ()
                    warning.set("開關索引.csv 讀取失敗：" + str(exc))
                source_state["files"][index] = files
                entry["available"].delete(0, tk.END)
                for filename in files:
                    entry["available"].insert(tk.END, display_model(filename))

        def poll_source():
            if not modal.winfo_exists():
                return
            refresh_source()
            modal.after(1800, poll_source)

        def add_switch(index):
            selected = layer_rows[index]["available"].curselection()
            if not selected:
                warning.set("請先選擇 CSV 開關型號")
                return
            filename = source_state["files"][index][selected[0]]
            expected_brand = view_source_catalog(index)
            if filename not in model_filenames(expected_brand):
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
            sync_chosen()
            repaint(index)
            warning.set("")

        def add_empty_slot(index):
            draft_state["draft"] = insert_nfb_slot(
                draft_state["draft"],index,
                len(draft_state["draft"]["layers"][index]["slots"]),
            )
            sync_chosen()
            repaint(index)

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
                catalog={brand:model_filenames(brand)},
            )
            sync_chosen()
            repaint(index)
            warning.set("")

        def remove_switch(index):
            selected = layer_rows[index]["assigned"].curselection()
            if not selected:
                return
            draft_state["draft"] = delete_nfb_slot(
                draft_state["draft"], index, selected[0],
            )
            sync_chosen()
            repaint(index)
            refresh_source(force=True)

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
                nfb_preview_panel["panel"].show(brand,slot["filename"])
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
                draft_state["draft"]=move_nfb_slot(draft_state["draft"],index,old,dest)
                sync_chosen()
                repaint(index)
                layer_rows[index]["assigned"].selection_clear(0,tk.END)
                layer_rows[index]["assigned"].selection_set(dest)
                warning.set("已調整順序：本層 X 位移重設，其他層不變")
            except (ValueError,IndexError) as exc:
                warning.set(str(exc))

        def undo_nfb_draft():
            try:
                edit_session.undo()
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
                warning.set("已復原 NFB 草稿上一筆交易")
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
                value=None if not typed else float(typed)
                draft_state["draft"]=set_nfb_manual_x(
                    draft_state["draft"],index,selected[0],value,
                )
                warning.set(
                    "X 位移保留為未驗證草稿，不是絕對製造座標"
                    if value is not None else "本顆位移已清除"
                )
                paint_draft_preview()
            except ValueError as exc:
                warning.set(str(exc))

        editor_body = ttk.Frame(frame)
        editor_body.pack(fill="both", expand=True, pady=(4, 6))
        slot_columns = ttk.Frame(editor_body)
        slot_columns.pack(side="left", fill="both", expand=True)
        nfb_preview_panel["panel"] = NfbDxfSourcePreviewPanel(editor_body)
        nfb_preview_panel["panel"].frame.pack_forget()

        def sync_visible_layers():
            nfb_physical_layers.set(layers.get())
            change_layers()

        for count in (1, 2):
            ttk.Radiobutton(
                controls, text=str(count), value=count, variable=layers,
                # The retired physical-layer selector follows the visible
                # inner-door layer choice so a two-layer save remains valid.
                command=lambda: sync_visible_layers(),
            ).pack(side="left", padx=8)
            ttk.Radiobutton(
                physical_row, text=str(count), value=count,
                variable=nfb_physical_layers,
                command=lambda: change_layers(),
            ).pack(side="left", padx=7)

        for idx in range(2):
            section = ttk.LabelFrame(slot_columns, text=f"第 {idx+1} 層開關")
            section.pack(fill="x", pady=(4, 6))
            height_row = ttk.Frame(section)
            height_row.grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=(5, 7))
            ttk.Label(height_row, text=f"第 {idx+1} 層高度（距作業區上緣 mm）").pack(side="left")
            height_entry = ttk.Entry(
                height_row, textvariable=layer_height_vars[idx], width=10,
            )
            height_entry.pack(side="left", padx=(8, 0))
            height_entry.bind("<Return>", lambda _event: paint_draft_preview())
            height_entry.bind("<FocusOut>", lambda _event: paint_draft_preview())
            section.columnconfigure(0, weight=1)
            section.columnconfigure(2, weight=1)
            ttk.Label(section, text="CSV 型號").grid(
                row=0, column=0, sticky="w", padx=5)
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
            brand_choices = ("繼承本套", *RECEIVING_SWITCH_BRANDS)
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
                values=("繼承本層", *RECEIVING_SWITCH_BRANDS),
                width=12, state="readonly",
            )
            slot_brand_select.pack(side="left", padx=3)
            brand_row.grid_remove()
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
                draft_state["draft"] = set_nfb_layer_brand(
                    draft_state["draft"],idx,mode=INHERIT if value=="繼承本套" else OVERRIDE,
                    value=None if value=="繼承本套" else value,
                )
                refresh_source(force=True)
                repaint(idx)

            def slot_brand_changed(_event=None, idx=idx):
                selected = layer_rows[idx]["assigned"].curselection()
                if not selected:
                    warning.set("請先選取一個實際 NFB 顆位或空槽")
                    return
                value = layer_rows[idx]["slot_brand_var"].get()
                draft_state["draft"] = set_nfb_slot_brand(
                    draft_state["draft"],idx,selected[0],
                    mode=INHERIT if value=="繼承本層" else OVERRIDE,
                    value=None if value=="繼承本層" else value,
                )
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
                refresh_source(force=True)

            assigned.bind("<<ListboxSelect>>", lambda event, i=idx: (
                selected_slot_changed(event,i), preview_assigned(i),
            ))
            available.bind("<<ListboxSelect>>",lambda event,i=idx: preview_available(i))
            repaint(idx)

        def change_layers():
            try:
                draft_state["draft"] = set_nfb_draft_layer_count(
                    draft_state["draft"], nfb_physical_layers.get(),
                )
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
            refresh_source(force=True)

        change_layers()
        # Nominal NFB draft/workflow summary is not part of the approved UI.
        ttk.Label(frame, textvariable=warning).pack(anchor="w")
        refresh_source(force=True)
        modal.after(1800, poll_source)
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

        def open_nfb_world_x_dialog():
            """Operator enters absolute world-X; UI-1A draft offset is not X."""
            if version_id is None:
                warning.set("請先儲存內門版本，再進行 NFB 實體確認")
                return
            from ae_engine.receiving_nfb_ui1b_runtime import verify_current_nfb_ui_draft
            current=edit_session.current
            active=[
                (i,j,slot)
                for i,layer in enumerate(current["layers"][:current["layer_count"]])
                for j,slot in enumerate(layer["slots"])
                if slot["filename"] is not None
            ]
            if not active:
                warning.set("尚未選擇可驗證的 NFB 型號")
                return
            popup=tk.Toplevel(modal)
            popup.title("NFB 物理世界 X｜正式提交前驗證")
            popup.geometry("540x440")
            from .receiving_scroll_view import make_scrollable_frame
            world_scroll, world_content, _world_view = make_scrollable_frame(
                popup, tk=tk, ttk=ttk, width=510, height=410,
            )
            world_scroll.pack(fill="both", expand=True)
            body=ttk.Frame(world_content,padding=14)
            body.pack(fill="both",expand=True)
            popup._receiving_world_scroll = world_scroll
            ttk.Label(
                body,text="輸入受電箱基準的實際世界 X（mm），不是名義間距或 X 位移。",
                wraplength=490,
            ).pack(anchor="w",pady=(0,7))
            ttk.Label(
                body,text="僅士林已具備輪廓資料的型號可試；實際 DXF/SHA、內門板、1100 Y"
                          " 與孔位碰撞全部須通過才會準備提交。",
                wraplength=490,
            ).pack(anchor="w",pady=(0,9))
            # Explicit file chooser; a numbered copy still requires real SHA
            # and Color150 matching in the canonical #1497 verifier.
            source_choice={"path":None}
            source_caption=tk.StringVar(
                master=popup,
                value="來源：基準檔/開孔/NFB（缺檔可選原始 DXF）",
            )
            def choose_original_dxf():
                from tkinter import filedialog
                picked=filedialog.askopenfilename(
                    parent=popup,title="選擇原始 NFB DXF",
                    filetypes=(("DXF","*.dxf"),("所有檔案","*.*")),
                )
                if picked:
                    source_choice["path"]=picked
                    source_caption.set("已指定原始 DXF："+picked)
            ttk.Button(
                body,text="選取原始 DXF",command=choose_original_dxf,
            ).pack(anchor="w")
            ttk.Label(body,textvariable=source_caption,wraplength=500).pack(
                anchor="w",pady=(2,7),
            )
            world_values={}
            for layer_i,slot_i,slot in active:
                line=ttk.Frame(body)
                line.pack(fill="x",anchor="w",pady=3)
                ttk.Label(
                    line,text=f"第 {layer_i+1} 層 第 {slot_i+1} 顆"
                              f"｜{slot['filename'][:-4]}",
                    width=40,
                ).pack(side="left")
                var=tk.StringVar(master=popup,value="")
                ttk.Entry(line,textvariable=var,width=11).pack(side="right")
                world_values[slot["unit_id"]]=var
            # W800/T2/top-1100/complete three-unit source is derived from
            # the real manufactured 723 mm inner-door CUTTING, never from a
            # customer's DXF bbox or a guessed 800/2. Unsupported layouts
            # keep the existing explicit-world-X editor.
            canonical_prefilled=False
            try:
                from ae_engine.receiving_nfb_ui1b_runtime import (
                    derive_w800_three_world_x_by_unit,
                )
                selection_for_x=candidate_adapter().selection
                physical_for_x=nfb_physical_bay_snapshot(
                    selection_for_x.set_index,selection_for_x.bay_index,
                )
                canonical_x=derive_w800_three_world_x_by_unit(
                    edit_session.current,snapshot=physical_for_x,
                )
                if set(canonical_x)==set(world_values):
                    for unit_id,physical_x in canonical_x.items():
                        world_values[unit_id].set(str(physical_x))
                    canonical_prefilled=True
            except (ValueError,TypeError,KeyError,IndexError):
                pass
            outcome=tk.StringVar(
                master=popup,
                value=("已帶入 WHD 實際板件驗證的 W800×3 世界 X，提交前會再次核對。"
                       if canonical_prefilled else
                       "目前尚未驗證，未修改專案。"),
            )
            ttk.Label(body,textvariable=outcome,wraplength=500).pack(
                anchor="w",pady=(8,4),
            )

            def close_world_dialog():
                if popup.grab_current() is popup:
                    popup.grab_release()
                popup.destroy()
                if modal.winfo_exists():
                    modal.lift()
                    modal.focus_set()

            def prepare():
                try:
                    coords={}
                    for unit_id,var in world_values.items():
                        value=var.get().strip()
                        if not value:
                            raise ValueError("每顆 NFB 的世界 X 都須明確輸入，0 亦可")
                        coords[unit_id]=float(value)
                    adapter=candidate_adapter()
                    selected=adapter.selection
                    bundle=verify_current_nfb_ui_draft(
                        edit_session.current,layout=adapter.layout,
                        set_index=selected.set_index,
                        bay_index=selected.bay_index,
                        version_id=version_id,
                        projected_snapshot=nfb_physical_bay_snapshot(
                            selected.set_index,selected.bay_index,
                        ),
                        world_x_by_unit=coords,
                        selected_source_path=source_choice["path"],
                        canonical_w800_three=canonical_prefilled,
                    )
                    nfb_transaction_ports()["stage_verified"](bundle)
                    outcome.set("已完成真實來源／內門實體驗證，仍須回主視窗按「確認套用（NFB）」")
                    close_world_dialog()
                    after_saved(version_id)  # UI refresh only, no candidate write
                    close_editor(saved=True)  # verified stage returns to parent
                except (ValueError,TypeError,KeyError,IndexError,OSError) as exc:
                    outcome.set("尚未通過驗證："+str(exc))
            actions=ttk.Frame(body)
            actions.pack(anchor="e",pady=(9,0))
            ttk.Button(actions,text="取消",command=close_world_dialog).pack(
                side="left",padx=5,
            )
            ttk.Button(actions,text="驗證實體來源",command=prepare).pack(side="left")
            popup.protocol("WM_DELETE_WINDOW",close_world_dialog)
            popup.lift()

        def confirm():
            try:
                # #1491 is transient UI-1A only. Distinct NFB physical layer
                # count cannot be flattened into legacy inner-door layers.
                if nfb_physical_layers.get() != layers.get():
                    raise ValueError("NFB 物理層與內門版本層數不同，不能覆寫成舊候選")
                # Existing candidate serializer also lacks physical empty
                # slots and brand overrides. Fail rather than lose user data.
                active = draft_state["draft"]["layers"][:nfb_physical_layers.get()]
                for row in active:
                    if row["brand"]["mode"] == OVERRIDE:
                        raise ValueError("本層品牌覆寫仍是 NFB 草稿，尚不可存成舊版內門候選")
                    if row["rotation_deg"]!=0:
                        raise ValueError("NFB 草稿角度不能被舊版內門層數格式丟失")
                    for slot in row["slots"]:
                        if slot["filename"] is None or slot["brand"]["mode"] == OVERRIDE:
                            raise ValueError("空槽或單顆品牌覆寫仍是 NFB 草稿，不能丟失後儲存")
                        if (slot["rotation"]["mode"]==OVERRIDE
                                or slot["manual_x_state"]!="NONE"
                                or slot["manual_x_mm"] is not None):
                            raise ValueError("NFB 逐顆角度／X 位移尚未正式提交，不能丟失後儲存")
                        if slot["source_brand"] != draft_state["draft"]["set_brand"]:
                            raise ValueError("品牌已變更，原型號待重選，不可直接存入舊版")
                latest_files = set(model_filenames(
                    self.receiving_switch_adapter(namespace).brand
                ))
                relevant = chosen[:layers.get()]
                if any(filename not in latest_files
                       for layer_items in relevant for filename in layer_items):
                    raise ValueError("開關索引.csv 已變動或來源型號失效")
                config = {
                    "layers": layers.get(),
                    "layer_heights_mm": read_layer_heights(),
                    "models": [
                        pack_switch_layer(chosen[0]),
                        pack_switch_layer(chosen[1]) if layers.get() == 2 else "",
                    ],
                }
                if direct_to_drawing:
                    # No candidate/version creation on Single or ordinary Hole
                    # Editor entry. Commit existing current-Bay shared settings
                    # and re-project the graph through the normal scheduler.
                    adapter = candidate_adapter()
                    sel = adapter.selection
                    bay = adapter.layout["sets"][sel.set_index]["bays"][sel.bay_index]
                    if bay.get("nfb_config_submitted") is True:
                        raise ValueError("此連 NFB 已驗證提交，請先取消／重新驗證實體孔位，不能偷偷移動已認證的孔")
                    for kind, value in (
                        ("inner_door_layers", config["layers"]),
                        ("inner_door_models", config["models"]),
                        ("inner_door_layer_heights_mm", config["layer_heights_mm"]),
                        ("inner_door_version_id", ""),
                    ):
                        adapter.unlink_setting(kind)
                        adapter.update_setting(kind, value)
                    self.mark_receiving_switch_layout_dirty(namespace, adapter)
                    self.sync_receiving_current_bay(namespace, refresh_controls=False)
                    self.app._phase6_input_snapshot[
                        "receiving_inner_door_layer_heights_mm"
                    ] = list(config["layer_heights_mm"])
                    self.app.designer_workspace.mark_dirty()
                    self.app.submit_update_intent("geometry", commit=True)
                    after_saved(None)
                else:
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
        ttk.Button(buttons, text="確認", command=confirm).pack(side="left")
        # Restore the parent multi-settings grab after this editor closes.
        parent_modal = getattr(
            self.app.root, "_receiving_multi_settings_window", None
        )
        def close_editor(*, saved=False):
            if (not saved and (draft_state["draft"] != initial_nfb_draft
                               or nfb_source_viewed["value"])
                    and not messagebox.askyesno(
                        "捨棄未提交的 NFB 草稿？",
                        "目前 NFB 物理層、空槽或品牌選型的預覽尚未提交。確定捨棄？",
                        parent=modal.winfo_toplevel(),
                    )):
                return
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
        allowed = set(model_filenames(
            self.receiving_switch_adapter(namespace).brand
        ))
        for layer_slot in config["models"][:config["layers"]]:
            for name in switch_filenames_in_layer(layer_slot):
                if name not in allowed:
                    raise ValueError(
                        "內門版本型號已不在開關索引.csv，請重新編輯選擇：" + name
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
        plan = validate_inner_door_allocation(
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
        from ae_engine.receiving_nfb_ui1b_bridge import (
            NfbVerifiedDraftSubmission, assert_live_verified_nfb,
            submit_live_verified_nfb, copy_live_verified_nfb,
        )

        def stage_verified(bundle):
            if not isinstance(bundle, NfbVerifiedDraftSubmission):
                raise TypeError("NFB 必須提供真實來源與內門物理位置驗證")
            adapter=candidate_adapter()
            assert_live_verified_nfb(
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
                assert_live_verified_nfb(
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
            """Select one committed source and one separately verified target.

            The highlighter, not a second selection popup, chooses exactly
            two Bays. The source may be active or the destination may be
            active. If both directions could apply, fail closed.
            """
            indices=tuple(selected_bays)
            if (len(indices)!=2 or len(indices)!=len(set(indices))):
                raise ValueError("NFB 複製請在同一套高亮來源連及目標連（恰好兩連）")
            layout=candidate_adapter().layout
            try:
                bays=layout["sets"][set_index]["bays"]
                selected={i:bays[i] for i in indices}
            except (IndexError,KeyError,TypeError) as exc:
                raise ValueError("NFB 複製的連位已不存在") from exc
            options=[]
            for source_bi in indices:
                if selected[source_bi].get("nfb_config_submitted") is not True:
                    continue
                for target_bi in indices:
                    if target_bi==source_bi:
                        continue
                    if (set_index,target_bi) not in pending_verified_nfb:
                        continue
                    bundle,reason=eligible_bundle(set_index,target_bi)
                    if bundle is not None and bundle.can_submit:
                        options.append((source_bi,bundle))
            if len(options)!=1:
                raise ValueError(
                    "請先從已提交來源連複製，並在另一目標連核對獨立世界 X／真 DXF；"
                    "不可使用未配置來源或不明確的複製方向"
                )
            return options[0]

        def physical_manifest(set_index,bay_index):
            """Read-only live status from current saved NFB + original source."""
            from ae_engine.receiving_nfb_export_manifest import (
                NfbActualPart,INNER_DOOR,BASE_PLATE,MIDDLE_PLATE,
                derive_nfb_partial_export_manifest,
            )
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
                return {
                    "status":"BLOCKED","reason":"已提交，但尚未重新核對原始 DXF／物理孔位",
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
                scope=bundle.scope
                physical=[
                    NfbActualPart(scope.inner_door_part_id,INNER_DOOR),
                    *(NfbActualPart(p,BASE_PLATE)
                      for p in scope.base_plate_part_ids),
                    *(NfbActualPart(p,MIDDLE_PLATE)
                      for p in scope.middle_plate_part_ids),
                ]
                manifest=derive_nfb_partial_export_manifest(
                    scope=scope,actual_parts=physical,
                    saved_bay=bay,set_brand=owner["switch_brand"],
                    source_inventory=bundle.source_inventory,
                    verified_inner_door=bundle.verified_door,
                    source_path=bundle.source_path,
                )
                details=manifest.report()
                details["status"]=(
                    "WHOLE_READY" if manifest.whole_ready else "PARTIAL_ONLY"
                )
                details["reason"]=(
                    "可匯出僅限以下已通過的實體板件；PAD／EAR 仍延期"
                    if manifest.authorized_part_ids else
                    "尚無可放行 NFB 加工板件"
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

        def export_partial_nfb_door_base_pair(set_index, bay_index, output_directory):
            """Atomic PART_ONLY actual inner-door + physical Receiving Base Plate."""
            from .receiving_nfb_pair_partial_export_action import (
                export_verified_receiving_nfb_door_base_pair,
            )
            bundle = committed_nfb_evidence.get((set_index, bay_index))
            if bundle is None:
                raise ValueError("NFB 成對出圖缺少本連已提交原始來源及實體孔位驗證")
            current = nfb_physical_bay_snapshot(set_index, bay_index)
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
                    submitted
                    and (set_index, bay_index) in committed_nfb_evidence
                    and nfb_physical_bay_snapshot(set_index, bay_index).get("receiving_base_plate")
                ),
                "reason": ("來源已配置、目標連獨立世界 X 與 DXF 已驗證，可複製提交"
                           if can_copy else
                           (reason or "當前 NFB 已核對來源／世界 X／實體內門，可確認套用")),
            }

        def submit(set_index,bay_indices,confirm):
            targets=tuple(bay_indices)
            if len(targets)!=1:
                raise ValueError("NFB MFG-1 本次僅驗證單一實體連，跨連須逐連確認")
            bi=targets[0]
            bundle,reason=eligible_bundle(set_index,bi)
            if bundle is None:
                raise ValueError(reason)
            result=submit_live_verified_nfb(
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
            result=copy_live_verified_nfb(
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

        return {"state": state, "stage_verified": stage_verified,
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
        from ae_engine.receiving_shared_settings import setting_value
        selected_set = candidate_adapter().layout["sets"][set_index]
        return tuple({
            role: setting_value(selected_set, bi, kind)
            for role, kind in (
                ("head", "head_version_id"),
                ("tail", "tail_version_id"),
                ("inner-door", "inner_door_version_id"),
            )
        } for bi in range(len(selected_set["bays"])))

    if embedded_inner_parent is not None:
        # The unified Hole Editor already owns the window and its modal grab.
        # Reuse the same inner candidate editor inside the 受電箱 tab.
        from tkinter import ttk, messagebox
        from ae_engine.receiving_shared_settings import setting_value
        container = embedded_inner_parent
        adapter = candidate_adapter()
        selection = adapter.selection
        stored = setting_value(
            adapter.layout["sets"][selection.set_index],
            selection.bay_index, "inner_door_version_id",
        )
        ids = {item["id"] for item in inner_versions(inner_library())}
        state = {"version": stored if stored in ids else None}
        if self.app.designer_workspace.active_mode != "set_bay":
            state["version"] = None
        bar = ttk.Frame(container)
        bar.pack(fill="x", padx=8, pady=(5, 3))
        status = ttk.Label(
            bar,
            text=("受電箱內門｜直接套用目前圖面" if self.app.designer_workspace.active_mode != "set_bay"
                  else "受電箱內門｜版本 X 另行套用到連"),
        )
        status.pack(side="left")
        def apply_saved_version():
            version = state["version"]
            if version is None:
                messagebox.showwarning("內門版本", "請先確認並儲存內門版本", parent=container.winfo_toplevel())
                return
            try:
                selected = candidate_adapter().selection
                inner_apply(INNER_ROLE, version, selected.set_index,
                            (selected.bay_index,))
                status.configure(text="已套用到目前選取的內門")
            except (ValueError, IndexError, RuntimeError) as exc:
                messagebox.showwarning("內門版本", str(exc), parent=container.winfo_toplevel())
        apply_button = ttk.Button(
            bar, text="套用到目前連", command=apply_saved_version,
            state="normal" if state["version"] is not None else "disabled",
        )
        if self.app.designer_workspace.active_mode == "set_bay":
            apply_button.pack(side="right")
        editor_host = ttk.Frame(container)
        editor_host.pack(fill="both", expand=True)
        def mount_inner_editor():
            if not editor_host.winfo_exists():
                return
            for child in editor_host.winfo_children():
                child.destroy()
            inner_edit(
                INNER_ROLE, state["version"], saved_inner_version,
                embed_parent=editor_host, after_closed=mount_inner_editor,
            )
        def saved_inner_version(version_id):
            if version_id is None:
                state["version"] = None
                status.configure(text="高度已套用目前圖面；未建立版本 X")
            else:
                state["version"] = version_id
                apply_button.configure(state="normal")
                status.configure(text="內門版本已儲存；按「套用到目前連」才會改變配置")
            editor_host.after_idle(mount_inner_editor)
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
        on_setting_selected=select_existing_setting,
        get_brand=(single_brand if single else
                   lambda: self.receiving_switch_adapter(namespace).brand),
        set_brand=set_single_brand if single else set_global_brand,
        get_settings_ports=lambda index: self.receiving_settings_ports(namespace, index),
        get_original_door_marks=existing_door_marks,
        get_initial_door_marks=cached_initial_door_marks,
        get_applied_version_labels=applied_version_labels,
        get_real_cut_preview_request=real_cut_preview_request,
        get_dimension_group=dimension_group,
        get_single_size_quantity=single_size_quantity,
        set_single_size_quantity=set_single_size_quantity,
        edit_single_holes=edit_single_holes,
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
                resolve_for_app(designer)
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
