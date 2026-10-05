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
        self._current_cabinet_type_name()
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
            owner = self._derived_cache_owner = Phase6DerivedCacheOwner()
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


def _snapshot_base_state(self):
    """Project current GUI adapters into the existing Fold Designer snapshot schema."""
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
            self,
            "endcap_bottom_wrap_state",
            normalize_endcap_bottom_wrap_state({"model": self.baseline_var.get()}),
        )),
        "assembly_relief": deepcopy(getattr(self, "assembly_relief_state", {}) or {}),
        "multi_door_enabled": bool(self.multi_door_enabled_var.get())
        if hasattr(self, "multi_door_enabled_var") else False,
        "door_layout_scope": str(getattr(self, "door_layout_scope", "main") or "main"),
        "door_handle_edges": deepcopy(getattr(self, "door_layout_handle_edges", {}) or {}),
        "inner_doors": deepcopy(getattr(self, "receiving_inner_doors", []) or []),
        "door_nameplate_center_datum_top": getattr(self, "door_nameplate_center_datum_top", None),
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
    snapshot["corner_state"] = self._serialize_manual_corner_state()
    snapshot["corner_pair_same"] = deepcopy(self.manual_corner_pair_same)
    snapshot["corner_editable"] = is_unknown_model(self.baseline_var.get())
    snapshot["corner_type_labels"] = {
        type_id.value: CORNER_TYPE_LABELS[type_id]
        for type_id in EDITABLE_CORNER_TYPE_IDS
    }
    baseline_models = self._baseline_model_choices()
    snapshot["baseline_models"] = baseline_models
    snapshot["baseline_unknown_value"] = next(
        (model for model in baseline_models if is_unknown_model(model)), "自訂"
    )
    snapshot["factory_defaults"] = load_factory_defaults_from_ae(ae)
    return snapshot


def _snapshot_workspace_state(self, snapshot):
    """Project authoritative WorkspaceController identity/features into snapshot."""
    box_body_profile = self.workspace_controller.box_body_profile()
    if box_body_profile:
        snapshot["box_body_profile"] = [dict(seg) for seg in box_body_profile]

    committed_profiles = self.workspace_controller.part_profiles_snapshot()
    current_existing = self._phase6_current_existing_parts()
    ordered = [
        key
        for key in (
            "box_body", "head", "tail", "door", "base_plate",
            "indicator_box", "indicator_door",
        )
        if key in current_existing
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
            tuple(
                (float(row[0]), tuple(float(v) for v in row[1]))
                for row in snapshot["door_layout_columns"]
            ),
            getattr(self, "door_layout_features", {}) or {},
        )
        for key, features in formal_door_features.items():
            snapshot["part_features"].setdefault(key, list(features))

    snapshot["part_face_features"] = {
        "box_body": {
            face: list(features)
            for face, features in self.box_body_face_features.items()
        }
    }
    return committed_profiles


def _snapshot_part_dimensions(self, snapshot):
    """Project existing manufacturing dimension APIs; never rebuild geometry here."""
    w, h, d, t, fw = (
        snapshot["w"], snapshot["h"], snapshot["d"], snapshot["t"], snapshot["fw"]
    )
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
    base_w = max(
        1.0,
        w - snapshot["base_plate_shrink_left"] - snapshot["base_plate_shrink_right"],
    )
    base_h = max(
        1.0,
        h - snapshot["base_plate_shrink_top"] - snapshot["base_plate_shrink_bottom"],
    )

    try:
        layers = max(1, int(self.indicator_l_var.get()))
        groups = [int(self.indicator_layer_g_vars[i].get()) for i in range(layers)]
        policy = replace(
            manufacturing_api.resolve_policy(),
            frame_width=float(fw),
            door_gap_w=float(snapshot["door_gap_w"]),
            door_gap_h=float(snapshot["door_gap_h"]),
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
            count = max(1, int(self.door_indicator_l_var.get()))
            snapshot["door_indicator_groups"] = [
                int(self.door_indicator_layer_g_vars[i].get())
                for i in range(count)
            ]
        else:
            snapshot["door_indicator_groups"] = []
    except Exception:
        snapshot["door_indicator_groups"] = []

    snapshot["door_indicator_offset"] = (
        float(self.door_indicator_offset_x),
        float(self.door_indicator_offset_y),
    )
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
    return snapshot


def _make_original_fold_designer_snapshot(self):
    """Compose the existing canonical Fold Designer snapshot from focused projections."""
    snapshot = _snapshot_base_state(self)
    committed_profiles = _snapshot_workspace_state(self, snapshot)
    _snapshot_part_dimensions(self, snapshot)
    if committed_profiles:
        snapshot["part_profiles"] = committed_profiles
    return snapshot


def _payload_topology_context(part_key, payload):
    data = dict(payload or {})
    key = str(part_key or "")
    w = float(data.get("w", ae.W))
    h = float(data.get("h", ae.H))
    d = float(data.get("d", ae.D))
    t = float(data.get("t", ae.T))
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
            (
                cell for cell in derive_door_layout_cells(columns)
                if door_layout_export_filename(cell).removesuffix(".dxf") == key
            ),
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
            (
                cell for cell in derive_door_layout_cells(columns)
                if door_layout_export_filename(cell).removesuffix(".dxf") == owner_door_key
            ),
            None,
        )
        if base_plate_cell is None:
            raise ValueError(f"底板 stable_id 不存在於 authoritative topology: {key}")
        w = float(base_plate_cell.start_width)
        h = float(base_plate_cell.start_height)
    return (
        data, key, w, h, d, t, fw, model, unknown, corner_state,
        features, face_features, door_cell, base_plate_cell,
    )


def _payload_policy(self, data, corner_state, part, fw, unknown, thickness):
    resolved = self._fold_designer_corner_policy_from_payload(corner_state, part, fw)
    if resolved is None and not unknown:
        fallback = known_model_corner_state(
            (part,), cabinet_family=self._current_cabinet_type_name()
        ).get(part)
        resolved = policy_from_corner_state(fallback, fw=fw) if fallback is not None else None
    return self._apply_cabinet_family_endcap_policy(
        resolved,
        part,
        snapshot=data,
        thickness=thickness,
        structure_state=data.get("box_body_structure"),
    )


def _fold_designer_part_spec_from_payload(self, part_key, payload):
    """Convert Fold Designer draft state to the canonical manufacturing request."""
    (
        data, key, w, h, d, t, fw, model, unknown, corner_state,
        features, face_features, door_cell, base_plate_cell,
    ) = _payload_topology_context(part_key, payload)
    payload_policy = lambda part: _payload_policy(
        self, data, corner_state, part, fw, unknown, t
    )
    policy_part = (
        "door" if door_cell is not None
        else ("base_plate" if base_plate_cell is not None else key)
    )
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
            features=features,
            face_features=face_features,
            head_corner_policy=payload_policy("head"),
            tail_corner_policy=payload_policy("tail"),
            fold_profile=data.get("fold_profile"),
            structure_state=data.get("box_body_structure"),
            snapshot=data,
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
        resolved_cuts = data.get("resolved_assembly_relief_cuts")
        if resolved_cuts is None and bool(data.get("_use_committed_relief")):
            resolved_cuts = self._resolved_committed_assembly_relief_cuts(
                key, endcap_values, data.get("fold_profiles") or {}
            )
        formed_fw_left, formed_fw_right = formed_box_body_fw_widths(
            data.get("box_body_profile") or self.workspace_controller.box_body_profile() or (),
            t,
        )
        spec = self._end_cap_part_spec_from_values(
            endcap_values,
            model_name=(None if unknown else model),
            is_tail=(key == "tail"),
            holes=features,
            corner_policy=policy,
            fold_profiles=data.get("fold_profiles"),
            resolved_assembly_relief_cuts=resolved_cuts or (),
            box_body_formed_fw_left=formed_fw_left,
            box_body_formed_fw_right=formed_fw_right,
            box_body_structure_state=(
                data.get("box_body_structure")
                or self.workspace_controller.box_body_structure_state()
            ),
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
            features=features,
            corner_policy=policy,
        )
    elif key == "indicator_box":
        groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
        spec = self._indicator_box_part_spec_from_values({"t": t}, groups, features=features)
    elif key == "indicator_door":
        groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
        spec, context = self._indicator_door_part_spec_from_values(
            {
                "t": t,
                "fw": fw,
                "door_gap_w": float(data.get("door_gap_w", ae.door_gap_w_def)),
                "door_gap_h": float(data.get("door_gap_h", ae.door_gap_h_def)),
                "indicator_door_fold": float(
                    data.get(
                        "indicator_door_fold",
                        getattr(ae, "indicator_small_door_fold_def", 19.0),
                    )
                ),
            },
            groups,
            features=features,
        )
    else:
        raise ValueError(f"未知 3D 板件: {key}")
    return spec, context



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
    FinalScenePortInventoryEntry("blank_text", "fold_designer_bridge.compat", "READ", "APP_TO_FINAL_SCENE", True, "NONE"),
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


class Phase6FoldDesignerComposition:
    """Single application composition owner for Phase 4 deep services."""

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

    @staticmethod
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

    def settings_context_extension_projection(self, namespace, context):
        """Project Settings context extensions at the existing composition boundary."""
        app = self.app
        required = lambda name: self._required(namespace, name)
        endcap_fw_parts = required("ENDCAP_FW_PARTS")
        global_context = required("GLOBAL_CONTEXT")
        cross_corner_mode = required("CrossCornerMode")

        def endcap_fw_projection(part_key):
            part_key = str(part_key)
            snapshot = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
            snapshot.update(dict(getattr(app, "_settings_values", {}) or {}))
            state = app._phase6_endcap_fw_state.setdefault(
                part_key,
                {
                    "follow_box": True,
                    "value": required("_num")(snapshot.get("fw", 25), 25),
                },
            )
            return {
                "follow": bool(state.get("follow_box", True)),
                "effective": required("resolve_endcap_fw")(
                    snapshot,
                    part_key,
                    state=app._phase6_endcap_fw_state,
                ),
            }

        def box_structure_projection():
            state = required("_phase6_box_structure_state")(app)
            active = BoxBodyStructureType(state["active_type"])
            cfg = state["configs"][active.value]
            total_w = required("_phase6_box_structure_w")(app)
            piece_values = {}
            mode = "integral"
            if active is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
                mode = "two_w"
                left, right = required("resolve_two_piece_widths")(
                    state, total_w
                )
                piece_values = {
                    "box_body:left": (
                        "width", "W 包外", left, "mm", "left"
                    ),
                    "box_body:right": (
                        "width", "W 包外", right, "mm", "right"
                    ),
                }
            elif active is BoxBodyStructureType.THREE_PIECE_W_SPLIT:
                mode = "three_w"
                left, middle, right = required("resolve_three_piece_widths")(
                    state, total_w
                )
                piece_values = {
                    "box_body:left": (
                        "width", "W 包外", left, "mm", "left"
                    ),
                    "box_body:middle": (
                        "width", "W 包外", middle, "mm", "middle"
                    ),
                    "box_body:right": (
                        "width", "W 包外", right, "mm", "right"
                    ),
                }
            elif active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
                mode = "side_back"
                snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
                outside_family = (
                    cabinet_family_policy.box_body_profile_uses_outside_dimensions(
                        snapshot
                    )
                )
                rear_bend = (
                    required("side_rear_bend_outside_length")(
                        state, float(snapshot.get("t", 2.0))
                    )
                    if outside_family
                    else float(cfg.get("side_rear_bend", 15))
                )
                width_comp_t = float(cfg.get("back_width_comp_t", 0.5))
                piece_values = {
                    "box_body:left_side": (
                        "rear_bend",
                        "後折",
                        rear_bend,
                        "mm",
                        "side_rear_bend",
                    ),
                    "box_body:back": (
                        "width_comp_t",
                        "寬補償",
                        width_comp_t,
                        "T",
                        "back_width_comp_t",
                    ),
                    "box_body:right_side": (
                        "rear_bend",
                        "後折",
                        rear_bend,
                        "mm",
                        "side_rear_bend",
                    ),
                }

            projections = ()
            projection_error = None
            if active is not BoxBodyStructureType.INTEGRAL:
                try:
                    render_data = required(
                        "_phase6_box_body_structure_render_data"
                    )(app)
                    projections = required(
                        "_phase6_box_body_piece_dimension_projections"
                    )(render_data)
                    active_piece_key = str(
                        getattr(app.designer_workspace, "active_part", "")
                        or ""
                    )
                    if required(
                        "_phase6_is_box_body_physical_piece_key"
                    )(active_piece_key):
                        projections = tuple(
                            row
                            for row in projections
                            if row.part_key == active_piece_key
                        )
                except Exception as exc:
                    projection_error = str(exc)

            pieces = []
            for projection in projections:
                part_key = str(projection.part_key)
                spec = piece_values.get(part_key)
                input_spec = None
                if spec is not None:
                    field_key, label, value, suffix, state_field = spec
                    input_spec = {
                        "field_key": field_key,
                        "label": label,
                        "value": value,
                        "suffix": suffix,
                        "state_field": state_field,
                    }
                detail = None
                if active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
                    if part_key in {
                        "box_body:left_side",
                        "box_body:right_side",
                    }:
                        detail = (
                            "成型深度 D："
                            f"{required('_setting_number_text')(required('_phase6_box_structure_d')(app))} mm"
                        )
                    elif part_key == "box_body:back":
                        detail = (
                            "成型寬："
                            f"{required('_setting_number_text')(projection.formed_width)} mm"
                        )
                pieces.append(
                    {
                        "part_key": part_key,
                        "label": projection.label,
                        "formed_width": projection.formed_width,
                        "formed_height": projection.formed_height,
                        "blank_width": projection.blank_width,
                        "blank_height": projection.blank_height,
                        "input": input_spec,
                        "back_panel_selector": None,
                        "detail": detail,
                    }
                )

            advanced_fields = ()
            if mode in {"two_w", "three_w"}:
                advanced_fields = (
                    {
                        "label": "封頭尾額外避讓",
                        "field": "endcap_extra_relief",
                        "value": cfg.get("endcap_extra_relief", 5),
                        "suffix": "mm",
                    },
                    {
                        "label": "封頭尾單邊留肉",
                        "field": "endcap_single_side_meat_t",
                        "value": cfg.get("endcap_single_side_meat_t", 0.5),
                        "suffix": "T",
                    },
                    {
                        "label": "底板避讓總長",
                        "field": "baseplate_relief_length",
                        "value": cfg.get("baseplate_relief_length", 20),
                        "suffix": "mm",
                    },
                    {
                        "label": "底板單邊留肉",
                        "field": "baseplate_single_side_meat_t",
                        "value": cfg.get("baseplate_single_side_meat_t", 0.5),
                        "suffix": "T",
                    },
                )
            advanced_flags = dict(
                getattr(app, "_phase6_box_structure_advanced_open", {}) or {}
            )
            return {
                "active_type": active,
                "mode": mode,
                "pieces": tuple(pieces),
                "projection_error": projection_error,
                "seam_bend": cfg.get("seam_bend", 12),
                "advanced_open": bool(
                    advanced_flags.get(active.value, False)
                ),
                "advanced_fields": advanced_fields,
            }

        def bottom_wrap_projection(part_key):
            snapshot = dict(
                getattr(app, "_phase6_input_snapshot", {}) or {}
            )
            if (
                str(part_key) not in endcap_fw_parts
                or not cabinet_family_policy.supports_bottom_wrap_controls(
                    snapshot
                )
            ):
                return None
            item = required("resolve_endcap_bottom_wrap")(
                snapshot,
                str(part_key),
                state=getattr(
                    app,
                    "_phase6_endcap_bottom_wrap_state",
                    required("normalize_endcap_bottom_wrap_state")(snapshot),
                ),
            )
            if not bool(item.get("enabled", False)):
                return None
            return {
                "reserve_u": item["reserve_u"],
                "reserve_v": item["reserve_v"],
            }

        def corner_projection(part_key):
            part_key = str(part_key)
            if part_key == global_context or part_key == "box_body":
                return {"mode": "none"}

            fixed_summaries = required("_FIXED_CORNER_SUMMARIES")
            if part_key in {"indicator_box", "indicator_door"}:
                summary = fixed_summaries.get(part_key, "")
                if summary:
                    return {"mode": "fixed", "summary": summary}

            type_editable = required("_phase6_corner_type_editable")(
                app, part_key
            )
            params_unlocked = required(
                "_phase6_corner_parameters_unlocked"
            )(app, part_key)
            params_editable = required(
                "_phase6_corner_parameters_editable"
            )(app, part_key)
            if not type_editable and not params_unlocked:
                summary = fixed_summaries.get(part_key, "")
                if summary:
                    return {"mode": "fixed", "summary": summary}

            state, pairs = required("_phase6_ensure_corner_part")(
                app, part_key
            )
            pair_keys = required("_CORNER_PAIR_KEYS")
            type_labels = required("_CORNER_TYPE_LABEL_BY_ID")
            direction_labels = required("_CORNER_DIRECTION_LABEL")
            mode_labels = required("_CORNER_MODE_LABEL")
            pair_rows = []
            for pair_key in ("top", "bottom"):
                targets = (
                    (pair_key,)
                    if pairs[pair_key]
                    else pair_keys[pair_key]
                )
                target_rows = []
                for target_key in targets:
                    physical = (
                        pair_keys[target_key][0]
                        if target_key in pair_keys
                        else target_key
                    )
                    selection = required("_phase6_selection_from_raw")(
                        state[physical]
                    )
                    if (
                        selection.type_id is CornerTypeId.CROSS
                        and selection.cross_mode is cross_corner_mode.RETAIN
                    ):
                        direction_options = ("寬", "高")
                    elif (
                        selection.type_id is CornerTypeId.CROSS
                        and selection.cross_mode
                        is not cross_corner_mode.STANDARD
                    ):
                        direction_options = ("寬＋高", "寬", "高")
                    else:
                        direction_options = ()
                    direction_label = (
                        direction_labels[selection.direction]
                        if selection.type_id is CornerTypeId.CROSS
                        and selection.cross_mode
                        is not cross_corner_mode.STANDARD
                        else ""
                    )
                    target_rows.append(
                        {
                            "target_key": target_key,
                            "side_label": (
                                ""
                                if len(targets) <= 1
                                else (
                                    "左"
                                    if target_key.endswith("left")
                                    else "右"
                                )
                            ),
                            "type_label": type_labels[
                                selection.type_id.value
                            ],
                            "type_options": tuple(type_labels.values()),
                            "type_kind": selection.type_id.name,
                            "top_assembly_owned": (
                                part_key in {"head", "tail"}
                                and pair_key == "top"
                            ),
                            "parameter_summary": required(
                                "_phase6_corner_parameter_summary"
                            )(selection),
                            "amount_t": (
                                selection.amount_t
                                if selection.amount_t is not None
                                else 1.0
                            ),
                            "mode_label": (
                                mode_labels[selection.cross_mode]
                                if selection.type_id is CornerTypeId.CROSS
                                and selection.cross_mode is not None
                                else ""
                            ),
                            "mode_kind": (
                                selection.cross_mode.name
                                if selection.type_id is CornerTypeId.CROSS
                                and selection.cross_mode is not None
                                else ""
                            ),
                            "direction_label": direction_label,
                            "direction_options": direction_options,
                            "secondary_retain_t": (
                                selection.secondary_retain_t
                            ),
                            "secondary_depth_t": (
                                selection.secondary_depth_t
                            ),
                        }
                    )
                pair_rows.append(
                    {
                        "pair_key": pair_key,
                        "label": "上方" if pair_key == "top" else "下方",
                        "same": bool(pairs[pair_key]),
                        "targets": tuple(target_rows),
                    }
                )
            return {
                "mode": "editable",
                "type_editable": bool(type_editable),
                "params_unlocked": bool(params_unlocked),
                "params_editable": bool(params_editable),
                "pairs": tuple(pair_rows),
            }

        context = str(context)
        return {
            "box_structure": (
                box_structure_projection()
                if context == "box_body"
                else None
            ),
            "endcap_fw": (
                endcap_fw_projection(context)
                if context in endcap_fw_parts
                else None
            ),
            "bottom_wrap": (
                bottom_wrap_projection(context)
                if context in endcap_fw_parts
                else None
            ),
            "corner": corner_projection(context),
        }

    def sync_settings_panel_extension(
        self,
        namespace,
        state,
        context,
    ):
        """Mirror extension widgets without moving Settings state ownership."""
        app = self.app
        required = lambda name: self._required(namespace, name)
        state = dict(state or {})
        for name in (
            "corner_pair_vars",
            "corner_pair_checkbuttons",
            "corner_type_vars",
            "corner_mode_vars",
            "corner_direction_vars",
            "corner_amount_vars",
            "corner_secondary_retain_vars",
            "corner_secondary_depth_vars",
            "corner_detail_frames",
        ):
            setattr(app, name, dict(state.get(name, {}) or {}))
        original = required("original")
        app.fixed_corner_summary_var = (
            state.get("fixed_corner_summary_var")
            or original.tk.StringVar(value="")
        )
        app.corner_param_lock_button = state.get(
            "corner_param_lock_button"
        )
        app.bottom_wrap_enabled_var = state.get(
            "bottom_wrap_enabled_var"
        )
        app.bottom_wrap_reserve_u_var = state.get(
            "bottom_wrap_reserve_u_var"
        )
        app.bottom_wrap_reserve_v_var = state.get(
            "bottom_wrap_reserve_v_var"
        )
        app.bottom_wrap_widget = state.get("bottom_wrap_widget")
        app.box_body_piece_input_host = state.get(
            "box_body_piece_input_host"
        )
        app.box_body_piece_input_sections = dict(
            state.get("box_body_piece_input_sections", {}) or {}
        )
        app.box_body_piece_input_vars = dict(
            state.get("box_body_piece_input_vars", {}) or {}
        )
        app.box_body_piece_input_entries = dict(
            state.get("box_body_piece_input_entries", {}) or {}
        )
        if (
            context in required("ENDCAP_FW_PARTS")
            and state.get("endcap_fw_follow_var") is not None
        ):
            snapshot = dict(
                getattr(app, "_phase6_input_snapshot", {}) or {}
            )
            snapshot.update(
                dict(getattr(app, "_settings_values", {}) or {})
            )
            fw_state = app._phase6_endcap_fw_state.setdefault(
                context,
                {
                    "follow_box": True,
                    "value": required("_num")(
                        snapshot.get("fw", 25), 25
                    ),
                },
            )
            follow = bool(fw_state.get("follow_box", True))
            effective = required("resolve_endcap_fw")(
                snapshot,
                context,
                state=app._phase6_endcap_fw_state,
            )
            state["endcap_fw_follow_var"].set(follow)
            state["endcap_fw_value_var"].set(
                required("_setting_number_text")(effective)
            )
            try:
                state["endcap_fw_widget"].configure(state="normal")
            except Exception:
                pass

    def sync_settings_panel_compat(self):
        app = self.app
        panel = app.settings_panel
        app.settings_center = panel.settings_center
        app.settings_fields = panel.settings_fields
        app.settings_title_var = panel.settings_title_var
        app.unfolded_size_var = panel.unfolded_size_var
        app.settings_status_var = panel.settings_status_var
        app.save_settings_button = panel.save_settings_button
        app.setting_vars = panel.setting_vars
        app._settings_page_cache = panel.page_cache
        app._settings_current_page = panel.current_page
        app.settings_context = panel.settings_context
        app.advanced_settings_visible = panel.advanced_settings_visible
        app.advanced_settings_frame = panel.advanced_settings_frame
        app.advanced_toggle_button = panel.advanced_toggle_button
        app.baseline_data_frame = panel.baseline_data_frame
        app.baseline_data_toggle_button = panel.baseline_data_toggle_button
        app.baseline_setting_cells = panel.baseline_setting_cells
        app.left_global_controls = panel.left_global_controls
        app.left_global_vars = panel.left_global_vars
        app.left_global_cells = panel.left_global_cells
        app.baseline_model_var = panel.baseline_model_var
        app.baseline_model_combo = panel.baseline_model_combo
        app.ui_text_size_var = panel.ui_text_size_var
        app.ui_text_size_combo = panel.ui_text_size_combo
        app.save_global_settings_button = panel.save_global_settings_button
        return panel

    def settings_panel_toggle_baseline(self):
        self.app.settings_panel.toggle_baseline_data()
        self.sync_settings_panel_compat()

    def invalidate_settings_page(self, context):
        self.app.settings_panel.invalidate_context(str(context))
        self.sync_settings_panel_compat()

    def render_settings_context(self, namespace, context):
        app = self.app
        required = lambda name: self._required(namespace, name)
        app._phase6_settings_rendering = True
        try:
            page = app.settings_panel.render_context(
                str(context or required("GLOBAL_CONTEXT"))
            )
            self.sync_settings_panel_compat()
            return page
        finally:
            app._phase6_settings_rendering = False

    def save_current_settings_as_defaults(self):
        return self.app.settings_panel.save_current_settings_as_defaults()

    def on_baseline_model_changed(self, namespace, *_args):
        app = self.app
        required = lambda name: self._required(namespace, name)
        if getattr(app, "_phase6_baseline_guard", False):
            return None
        app._phase6_corner_param_unlocked = {}
        new_model = str(app.baseline_model_var.get() or "").strip()
        old_model = str(
            getattr(app, "_phase6_baseline_last_model", "") or ""
        ).strip()
        old_editable = required("_phase6_is_unknown_baseline")(
            app, old_model
        )
        if old_editable:
            app._corner_transaction_unknown_state = deepcopy(
                app._phase6_corner_state
            )
            app._corner_transaction_unknown_pairs = deepcopy(
                app._phase6_corner_pair_same
            )

        editable = required("_phase6_is_unknown_baseline")(
            app, new_model
        )
        needs_fixed_corner_preset = bool(
            (not editable and new_model and new_model != old_model)
            or (editable and old_model and not old_editable)
        )
        fixed_corner_state = (
            required("_phase6_known_model_corner_state")(app)
            if needs_fixed_corner_preset
            else {}
        )
        previous_non_receiving_structure = getattr(
            app,
            "_phase6_non_receiving_structure_state",
            None,
        )
        coordinator = self.settings_coordinator(
            self.settings_application_ports(namespace)
        )
        return coordinator.apply_baseline_transition(
            new_model=new_model,
            old_model=old_model,
            new_editable=editable,
            old_editable=old_editable,
            fixed_corner_state=fixed_corner_state,
            available_parts=tuple(
                getattr(app.designer_workspace, "available_parts", ())
                or ()
            ),
            previous_non_receiving_structure=previous_non_receiving_structure,
        )

    def apply_external_settings(self, namespace, updates):
        app = self.app
        app._phase6_external_apply_guard = True
        try:
            coordinator = self.settings_coordinator(
                self.settings_application_ports(namespace)
            )
            return coordinator.apply_updates(
                updates,
                notify=False,
                external_apply_guard=True,
            )
        finally:
            app._phase6_external_apply_guard = False

    def apply_external_model(self, namespace, model):
        app = self.app
        plan = self.settings_transactions().plan_external_model_change(
            model
        )
        if not plan.changed:
            return False

        app._phase6_external_apply_guard = True
        try:
            model_var = getattr(app, "baseline_model_var", None)
            if model_var is None:
                return False
            if str(model_var.get() or "").strip() != plan.target_model:
                model_var.set(plan.target_model)
            if (
                str(
                    (
                        getattr(app, "_phase6_input_snapshot", {}) or {}
                    ).get("model")
                    or ""
                ).strip()
                != plan.target_model
            ):
                self.on_baseline_model_changed(namespace)
        finally:
            app._phase6_external_apply_guard = False
        return (
            str(
                (
                    getattr(app, "_phase6_input_snapshot", {}) or {}
                ).get("model")
                or ""
            ).strip()
            == plan.target_model
        )

    def apply_external_sync(self, namespace, envelope):
        app = self.app
        plan = self.settings_service().plan_external_sync(envelope)
        if not plan.accepted or not plan.settings:
            return {}
        result = self.apply_external_settings(namespace, plan.settings)
        if (
            str(getattr(app, "_phase6_3d_display_mode", "") or "")
            == "corner_data"
            and getattr(app, "corner_data_canvas", None) is not None
        ):
            self.refresh_corner_data_unfold_view(namespace)
        return result

    def update_left_workspace_width(self, namespace, key=None):
        app = self.app
        required = lambda name: self._required(namespace, name)
        canvas = getattr(app, "left_scroll_canvas", None)
        if canvas is None:
            return None
        value = (
            key
            if key is not None
            else app._settings_values.get("ui_text_size", "small")
        )
        target = required("_phase6_left_workspace_width")(value)
        canvas.configure(width=target)
        try:
            canvas.update_idletasks()
        except Exception:
            pass
        return target

    def apply_ui_text_size(self, namespace, key):
        app = self.app
        required = lambda name: self._required(namespace, name)
        if getattr(app, "_phase6_settings_guard", False):
            return None
        key = required("normalize_ui_text_size")(key)
        app._settings_values["ui_text_size"] = key
        app._phase6_input_snapshot["ui_text_size"] = key
        app._ui_text_controller.apply(key)
        app.state.ui_text_scale = app._ui_text_controller.factor
        self.update_left_workspace_width(namespace, key)
        callback = getattr(app, "_ui_text_size_change_callback", None)
        if (
            callback is not None
            and not getattr(app, "_phase6_external_apply_guard", False)
        ):
            callback(key)
        try:
            app.bend_ui.render()
        except Exception:
            pass
        try:
            app.renderer.render()
        except Exception:
            pass
        return key

    def on_ui_text_size_changed(self, namespace, *_args):
        app = self.app
        panel = getattr(app, "settings_panel", None)
        var = (
            getattr(panel, "ui_text_size_var", None)
            if panel is not None
            else getattr(app, "ui_text_size_var", None)
        )
        if var is None:
            return None
        return self.apply_ui_text_size(namespace, var.get())

    def receiving_layout_applicable(self):
        snapshot = getattr(
            self.app, "_phase6_input_snapshot", {}
        ) or {}
        return (
            cabinet_family_policy.canonical_family_name(snapshot)
            == "受電箱"
        )

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

    def receiving_adapter(
        self,
        namespace,
        *,
        reset=False,
    ):
        app = self.app
        required = lambda name: self._required(namespace, name)
        if not self.receiving_layout_applicable():
            return None
        snapshot = required("ensure_receiving_layout")(
            getattr(app, "_phase6_input_snapshot", {}) or {}
        )
        layout = snapshot.get("receiving_layout")
        if not isinstance(layout, Mapping):
            return None
        adapter = (
            None
            if reset
            else getattr(app, "_phase6_receiving_set_bay_adapter", None)
        )
        if adapter is None:
            adapter = required("ReceivingSetBayAdapter")(
                layout,
                persisted_ids=required("receiving_layout_stable_ids")(
                    layout
                ),
                confirm_destructive=self.confirm_receiving_destructive,
            )
            app._phase6_receiving_set_bay_adapter = adapter
        return adapter

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
        original = required("original")
        app.state.w = original.get_int(projected["w"])
        app.state.h = original.get_int(projected["h"])
        app.state.d = original.get_int(projected["d"])
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
        """Return whether the normal-input rear-panel choice applies."""
        app = self.app
        required = lambda name: self._required(namespace, name)
        workspace = getattr(app, "designer_workspace", None)
        active_part = str(getattr(workspace, "active_part", "") or "")
        if active_part != "box_body:back":
            return False
        snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
        if cabinet_family_policy.canonical_family_name(snapshot) != "受電箱":
            return False
        state = required("_phase6_box_structure_state")(app)
        return (
            str(state.get("active_type") or "")
            == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
        )

    def refresh_back_panel_mode_control(self, namespace):
        """Project canonical rear-panel mode into the normal input region."""
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
            before = getattr(getattr(app, "bend_ui", None), "nb", None)
            original = required("original")
            options = {"fill": original.tk.X, "pady": (0, 4)}
            if before is not None and before.winfo_manager():
                options["before"] = before
            frame.pack(**options)
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
        app = self.app
        required = lambda name: self._required(namespace, name)
        snapshot = dict(
            getattr(app, "_phase6_input_snapshot", {}) or {}
        )
        layout = required("normalize_receiving_switch_layout")(
            snapshot.get(required("RECEIVING_SWITCH_LAYOUT_KEY"))
        )
        fingerprint = required("stable_fingerprint")(layout)
        adapter = (
            None
            if reset
            else getattr(
                app, "_phase6_receiving_switch_layout_adapter", None
            )
        )
        if (
            adapter is None
            or getattr(
                app,
                "_phase6_receiving_switch_layout_fingerprint",
                None,
            )
            != fingerprint
        ):
            adapter = required("ReceivingSwitchLayoutAdapter")(layout)
            app._phase6_receiving_switch_layout_adapter = adapter
            app._phase6_receiving_switch_layout_fingerprint = fingerprint
        return adapter

    def mark_receiving_switch_layout_dirty(
        self,
        namespace,
        adapter,
    ):
        app = self.app
        required = lambda name: self._required(namespace, name)
        layout = adapter.layout
        app._phase6_input_snapshot[
            required("RECEIVING_SWITCH_LAYOUT_KEY")
        ] = layout
        app._phase6_receiving_switch_layout_fingerprint = required(
            "stable_fingerprint"
        )(layout)
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

    def receiving_layer_preview_payload(self, namespace, layer_index):
        """Build a complete display-only assembly preview for one switch layer.

        The preview always resolves the full current assembly, independent of the
        main viewport's current single/assembly mode or visibility toggles. Every
        connection reuses that exact CUTTING mesh, so physical openings remain
        geometry rather than a second preview-only hole table.
        """
        app = self.app
        switch = self.receiving_switch_adapter(namespace)
        index = int(layer_index)
        count = switch.connection_count(index)

        snapshot = ensure_receiving_preview_layout(
            getattr(app, "_phase6_input_snapshot", {}) or {}
        )
        settings = dict(getattr(app, "_settings_values", {}) or {})
        thickness = float(settings.get("t", snapshot.get("t", 2.0)))

        view = self.final_scene_adapter(self.final_scene_ports(namespace))
        assembly_data = view.query_assembly_render_data()
        assembly_data = replace(
            assembly_data,
            visible_part_keys=None,
            visible_box_body_piece_keys=None,
        )
        assembly_part_keys = tuple(
            str(getattr(part, "part_key", "") or "")
            for part in tuple(getattr(assembly_data, "assembly_parts", ()) or ())
        )
        if not assembly_part_keys:
            raise RuntimeError("目前沒有可用的完整組合體 3D 幾何")

        from matplotlib.figure import Figure
        from types import SimpleNamespace

        figure = Figure(figsize=(1.0, 1.0), dpi=40)
        axis = figure.add_subplot(111, projection="3d")
        temp_renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=axis))
        request = FinalSceneViewRequest(
            render_data=assembly_data,
            x_profile=(),
            y_profile=(),
            part_key="assembly",
            alpha_bend=0.86,
            finished_dimensions=operator_finished_dimensions_for_app(app, None),
            thickness=thickness,
        )
        try:
            base_mesh = tuple(temp_renderer.render(request) or ())
        finally:
            figure.clear()
        if not base_mesh:
            raise RuntimeError("完整組合體 3D 幾何為空")

        vertices = [point for tri in base_mesh for point in tri]
        xs, ys, zs = tuple(zip(*vertices))
        min_x, max_x = min(map(float, xs)), max(map(float, xs))
        min_y = min(map(float, ys))
        max_z = max(map(float, zs))
        span_x = float(max_x - min_x)
        if span_x <= 1e-9:
            raise RuntimeError("完整組合體 3D 幾何沒有有效寬度")

        meshes = []
        for connection_index in range(count):
            shift_x = span_x * connection_index
            meshes.append(
                tuple(
                    tuple(
                        (float(point[0]) + shift_x, float(point[1]), float(point[2]))
                        for point in tri
                    )
                    for tri in base_mesh
                )
            )

        layout = resize_receiving_preview_bays(
            snapshot["receiving_layout"],
            set_index=0,
            bay_count=count,
        )
        frame_width = float(settings.get("fw", snapshot.get("fw", 29.0)))
        lock_circles = []
        for joint_index in range(max(count - 1, 0)):
            resolved = resolve_receiving_joint_lock_pattern(
                layout,
                set_index=0,
                joint_index=joint_index,
                thickness=thickness,
                frame_width=frame_width,
            )
            mating_x = min_x + span_x * (joint_index + 1)
            for circle in tuple(resolved.canonical_pattern or ()):
                lock_circles.append(
                    {
                        "joint_index": joint_index,
                        "x": float(mating_x),
                        "y": float(min_y + float(circle.v)),
                        "z": float(max_z - float(circle.u)),
                        "diameter": float(circle.diameter),
                        "layer": str(circle.layer),
                    }
                )

        return {
            "connection_count": count,
            "connection_meshes": tuple(meshes),
            "lock_circles": tuple(lock_circles),
            "assembly_part_keys": assembly_part_keys,
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
                "3D 預覽失敗",
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
            connection_meshes=preview["connection_meshes"],
            lock_circles=preview["lock_circles"],
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

    def registry_collect_rule_form(self):
        """Collect one editable Registry rule record from the existing panel vars."""
        app = self.app
        intent = str(
            app.relief_registry_intent_var.get() or "INSERT_OVERLAY"
        )
        topology = int(
            float(
                app.relief_registry_topology_var.get()
                or (2 if intent == "INSERT_OVERLAY" else 1)
            )
        )
        main_target = str(
            app.relief_registry_target_role_var.get() or "BOX_SIDE"
        )
        region = str(
            app.relief_registry_joint_face_var.get() or "TOP"
        )
        signature = [
            {
                "relation": intent,
                "subject_role": str(
                    app.relief_registry_part_role_var.get()
                    or "HEAD_OR_TAIL"
                ),
                "target_role": main_target,
                "subject_region": region,
                "target_region": (
                    "MATING_ZONE"
                    if intent != "OVERLAY"
                    else "OUTER_SURFACE"
                ),
            }
        ]
        extra = str(
            app.relief_registry_extra_joint_var.get() or "NONE"
        )
        if extra != "NONE":
            signature.append(
                {
                    "relation": extra,
                    "subject_role": str(
                        app.relief_registry_part_role_var.get()
                        or "HEAD_OR_TAIL"
                    ),
                    "target_role": str(
                        app.relief_registry_extra_target_role_var.get()
                        or "REAR_PANEL"
                    ),
                    "subject_region": region,
                    "target_region": (
                        "WRAP_ZONE"
                        if extra == "WRAP"
                        else "MATING_ZONE"
                    ),
                }
            )
        formula = {
            "primary_u": str(
                app.relief_registry_primary_u_var.get()
            ).strip(),
            "primary_v": str(
                app.relief_registry_primary_v_var.get()
            ).strip(),
        }
        if topology == 2:
            formula["secondary_u"] = str(
                app.relief_registry_secondary_u_var.get()
            ).strip()
            formula["secondary_depth"] = str(
                app.relief_registry_secondary_depth_var.get()
            ).strip()
        preconditions = [
            value.strip()
            for value in str(
                app.relief_registry_preconditions_var.get() or ""
            ).split(",")
            if value.strip()
        ]
        return {
            "rule_id": str(
                app.relief_registry_rule_id_var.get() or ""
            ).strip(),
            "cabinet_family": str(
                app.relief_registry_family_var.get() or "ANY"
            ).strip(),
            "part_role": str(
                app.relief_registry_part_role_var.get()
                or "HEAD_OR_TAIL"
            ).strip(),
            "joint_face": region,
            "assembly_intent": intent,
            "joint_signature": signature,
            "topology_levels": topology,
            "preconditions": preconditions,
            "formula": formula,
            "symmetry": str(
                app.relief_registry_symmetry_var.get()
                or "MIRROR_IF_GEOMETRY_SYMMETRIC"
            ),
            "source": str(
                app.relief_registry_source_var.get() or ""
            ).strip(),
        }

    def registry_sample_variables(self):
        """Project the Registry sample controls into evaluator variables."""
        app = self.app
        values = {}
        mapping = {
            "T": app.relief_registry_sample_t_var,
            "FW": app.relief_registry_sample_fw_var,
            "side_fold": app.relief_registry_sample_side_var,
            "ytop1": app.relief_registry_sample_ytop_var,
            "mating_width": app.relief_registry_sample_mating_var,
        }
        for key, var in mapping.items():
            values[key] = float(var.get())
        values["effective_mating_width"] = values["mating_width"]
        values["fold_u"] = values["side_fold"]
        values["fold_v"] = values["ytop1"]
        values["clearance"] = 0.0
        return values

    def registry_validate_formula_form(self):
        """Validate the editable Registry form through the existing controller."""
        from ae_engine.certified_relief_registry import (
            evaluate_relief_formula_record,
            _validate_editable_rule_record,
        )

        app = self.app
        controller = self.registry_diagnostics()
        try:
            result = controller.validate_formula(
                self.registry_collect_rule_form(),
                self.registry_sample_variables(),
                validator=_validate_editable_rule_record,
                evaluator=evaluate_relief_formula_record,
            )
            text = (
                f"公式有效：{result['primary_u']:.3f}"
                f"×{result['primary_v']:.3f}"
            )
            if result.get("secondary_u") is not None:
                text += (
                    f" + {result['secondary_u']:.3f}"
                    f"×{result['secondary_depth']:.3f}"
                )
            app.relief_registry_status_var.set(text)
            app._phase6_last_rule_form_result = result
            return result
        except Exception as exc:
            app.relief_registry_status_var.set(f"公式錯誤：{exc}")
            app._phase6_last_rule_form_result = None
            return None

    def registry_preview_payload(self):
        """Return validated 2D preview data; drawing stays panel-owned."""
        result = self.registry_validate_formula_form()
        geometry = self.corner_data_view().registry_preview_geometry(result)
        return {"result": result, "geometry": geometry}

    def registry_save_candidate_form(self, namespace):
        """Persist one candidate through the existing Registry controller."""
        from ae_engine.certified_relief_registry import (
            save_relief_rule_candidate,
        )

        app = self.app
        required = lambda name: self._required(namespace, name)
        result = self.registry_validate_formula_form()
        if result is None:
            return None
        try:
            record = self.registry_collect_rule_form()
            controller = self.registry_diagnostics()
            item = controller.save_candidate(
                record,
                saver=save_relief_rule_candidate,
            )
            required(
                "_phase6_sync_registry_diagnostics_compatibility_mirrors"
            )(app, controller)
            app.relief_registry_status_var.set(
                "候選已儲存（尚未認證）"
            )
            return item
        except Exception as exc:
            app.relief_registry_status_var.set(
                f"候選儲存失敗：{exc}"
            )
            return None

    def registry_run_formula_matrix(self, namespace):
        """Run the Registry regression matrix through the existing controller."""
        from ae_engine.certified_relief_registry import (
            evaluate_relief_formula_record,
            _validate_editable_rule_record,
        )

        app = self.app
        required = lambda name: self._required(namespace, name)
        try:
            controller = self.registry_diagnostics()
            evidence = controller.run_formula_matrix(
                self.registry_collect_rule_form(),
                self.registry_sample_variables(),
                validator=_validate_editable_rule_record,
                evaluator=evaluate_relief_formula_record,
            )
            required(
                "_phase6_sync_registry_diagnostics_compatibility_mirrors"
            )(app, controller)
            app.relief_registry_status_var.set(
                f"公式矩陣通過：{evidence['cases']} 組；立體零穿透="
                + (
                    "是"
                    if evidence.get("zero_penetration")
                    else "尚未"
                )
            )
            return evidence
        except Exception as exc:
            app.relief_registry_status_var.set(f"回歸失敗：{exc}")
            return None

    def registry_preview_assembly_3d(self, namespace):
        """Sequence candidate-specific 3D evidence without owning the solver."""
        app = self.app
        required = lambda name: self._required(namespace, name)
        controller = self.registry_diagnostics()
        try:
            candidate_id = controller.require_current_candidate(
                self.registry_collect_rule_form()
            )
            record = controller.candidate_record
            evidence3d = required(
                "_phase6_registry_validate_candidate_3d"
            )(app, record, candidate_id=candidate_id)
            evidence = controller.merge_3d_evidence(evidence3d)
            required(
                "_phase6_sync_registry_diagnostics_compatibility_mirrors"
            )(app, controller)
            zero = bool(evidence.get("zero_penetration"))
            app.relief_registry_status_var.set(
                "候選專屬立體組合驗證："
                + ("零非法穿透" if zero else "仍有非法穿透")
            )
            return zero
        except Exception as exc:
            app.relief_registry_status_var.set(
                f"立體組合驗證失敗：{exc}"
            )
            return False

    def registry_promote_form(self):
        """Promote the current candidate through the existing controller."""
        from ae_engine.certified_relief_registry import (
            promote_relief_rule_candidate,
        )

        app = self.app
        controller = self.registry_diagnostics()
        try:
            promoted = controller.promote_candidate(
                self.registry_collect_rule_form(),
                promoter=promote_relief_rule_candidate,
            )
            app.relief_registry_status_var.set(
                f"已認證新版次：{promoted['revision']}"
            )
            panel = self._registry_panel or getattr(
                app, "registry_diagnostics_panel", None
            )
            refresh = getattr(panel, "refresh_rule_rows", None)
            if callable(refresh):
                refresh()
            return promoted
        except Exception as exc:
            message = str(exc)
            if message in {
                "請先儲存候選",
                "表單已變更；請重新儲存候選後再驗證",
            }:
                app.relief_registry_status_var.set(message)
            else:
                app.relief_registry_status_var.set(
                    f"不可認證：{exc}"
                )
            return None

    def corner_pair_var_changed(
        self,
        namespace,
        part_key,
        pair_key,
        var,
    ):
        app = self.app
        required = lambda name: self._required(namespace, name)
        if (
            getattr(app, "_phase6_corner_guard", False)
            or getattr(app, "_phase6_settings_rendering", False)
        ):
            return None
        if not required("_phase6_corner_parameters_editable")(
            app, part_key
        ):
            return None
        self.settings_transactions().commit_corner_pair(
            part_key, pair_key, bool(var.get())
        )
        required("_phase6_notify_corner_change")(app)
        self.invalidate_settings_page(part_key)
        self.render_settings_context(namespace, part_key)
        return True

    def corner_type_selected(self, namespace, part_key, target_key):
        app = self.app
        required = lambda name: self._required(namespace, name)
        if (
            getattr(app, "_phase6_corner_guard", False)
            or getattr(app, "_phase6_settings_rendering", False)
        ):
            return None
        if not required("_phase6_corner_type_editable")(app, part_key):
            return None
        var = app.corner_type_vars.get(target_key)
        if var is None:
            return None
        type_id = required("_CORNER_TYPE_BY_LABEL").get(
            str(var.get()).strip()
        )
        if type_id is None:
            return None
        self.settings_transactions().commit_corner_type(
            part_key, target_key, type_id
        )
        required("_phase6_notify_corner_change")(app)
        self.invalidate_settings_page(part_key)
        self.render_settings_context(namespace, part_key)
        return type_id

    def corner_mode_selected(self, namespace, part_key, target_key):
        app = self.app
        required = lambda name: self._required(namespace, name)
        if (
            getattr(app, "_phase6_corner_guard", False)
            or getattr(app, "_phase6_settings_rendering", False)
        ):
            return None
        if not required("_phase6_corner_parameters_editable")(
            app, part_key
        ):
            return None
        transactions = self.settings_transactions()
        current = transactions.corner_selection(part_key, target_key)
        if current.type_id is not CornerTypeId.CROSS:
            return None
        var = app.corner_mode_vars.get(target_key)
        mode = (
            required("_CORNER_MODE_BY_LABEL").get(str(var.get()).strip())
            if var is not None
            else None
        )
        if mode is None:
            return None
        transactions.commit_corner_mode(part_key, target_key, mode)
        required("_phase6_notify_corner_change")(app)
        self.invalidate_settings_page(part_key)
        self.render_settings_context(namespace, part_key)
        return mode

    def corner_target_var_changed(self, namespace, part_key, target_key):
        """Commit semantic Corner parameter widgets through the T2 owner."""
        app = self.app
        required = lambda name: self._required(namespace, name)
        if (
            getattr(app, "_phase6_corner_guard", False)
            or getattr(app, "_phase6_settings_rendering", False)
        ):
            return None
        if not required("_phase6_corner_parameters_editable")(
            app, part_key
        ):
            return None

        transactions = self.settings_transactions()
        current = transactions.corner_selection(part_key, target_key)
        try:
            amount_var = app.corner_amount_vars.get(target_key)
            amount = (
                float(amount_var.get())
                if amount_var is not None
                else current.amount_t
            )
            mode_var = app.corner_mode_vars.get(target_key)
            mode = (
                required("_CORNER_MODE_BY_LABEL").get(
                    str(mode_var.get()).strip(), current.cross_mode
                )
                if mode_var is not None
                else current.cross_mode
            )
            direction_var = app.corner_direction_vars.get(target_key)
            direction = (
                required("_CORNER_DIRECTION_BY_LABEL").get(
                    str(direction_var.get()).strip(), current.direction
                )
                if direction_var is not None
                else current.direction
            )
            retain_var = app.corner_secondary_retain_vars.get(target_key)
            depth_var = app.corner_secondary_depth_vars.get(target_key)
            retain = (
                float(retain_var.get())
                if retain_var is not None
                else current.secondary_retain_t
            )
            depth = (
                float(depth_var.get())
                if depth_var is not None
                else current.secondary_depth_t
            )
            transactions.commit_corner_parameters(
                part_key,
                target_key,
                amount_t=amount,
                cross_mode=mode,
                direction=direction,
                secondary_retain_t=retain,
                secondary_depth_t=depth,
            )
        except (
            TypeError,
            ValueError,
            required("original").tk.TclError,
        ):
            return None
        required("_phase6_notify_corner_change")(app)
        return True

    def refresh_active_endcap_from_linked(
        self, namespace, linked
    ):
        app = self.app
        required = lambda name: self._required(namespace, name)
        key = str(app.designer_workspace.active_part or "")
        if key not in required("ENDCAP_FW_PARTS") or key not in linked:
            return None
        profiles = linked[key]
        clone_profile = required("clone_profile")
        app.state.profiles = {
            "X": clone_profile(profiles.get("X", ())),
            "Y": clone_profile(profiles.get("Y", ())),
        }
        try:
            app.bend_ui.rebuild_tabs()
        except Exception:
            pass
        return app.state.profiles

    def commit_endcap_fw_state(self, namespace):
        app = self.app
        required = lambda name: self._required(namespace, name)
        linked = required("_phase6_rebuild_linked_endcaps")(app)
        self.refresh_active_endcap_from_linked(namespace, linked)
        try:
            app.do_update()
        except Exception:
            pass
        return linked

    def set_endcap_fw_override(
        self, namespace, part_key, value
    ):
        self.settings_transactions().commit_endcap_fw_override(
            str(part_key), value
        )
        return self.commit_endcap_fw_state(namespace)

    def on_endcap_fw_value_selected(
        self, namespace, part_key, value_var
    ):
        try:
            value = float(value_var.get())
        except (TypeError, ValueError):
            return None
        return self.set_endcap_fw_override(
            namespace, part_key, value
        )

    def on_box_symmetry_changed(self, namespace):
        app = self.app
        required = lambda name: self._required(namespace, name)
        var = getattr(app, "v_sy", None)
        if var is None:
            return None
        if not required("_phase6_box_symmetry_allowed")(app):
            required("_phase6_apply_box_symmetry_policy")(app)
            target = bool(getattr(app.state, "symmetric", False))
            if hasattr(app, "bend_ui"):
                app.bend_ui._phase6_refresh_symmetry_bar()
        else:
            try:
                target = bool(var.get())
            except Exception:
                return None
        self.settings_transactions().commit_symmetry(app.state, target)

        pending = getattr(app, "_job", None)
        root = getattr(app, "root", None)
        if pending and root is not None:
            try:
                root.after_cancel(pending)
            except Exception:
                pass
            app._job = None
        try:
            app.do_update()
        except Exception:
            pass
        return target

    def on_endcap_edge_relation_selected(
        self, namespace, part_key, edge
    ):
        app = self.app
        required = lambda name: self._required(namespace, name)
        part_key = str(part_key)
        edge = str(edge).upper()
        var = dict(getattr(app, "endcap_joint_vars", {}) or {}).get(edge)
        if var is None:
            return None
        relation = required("_ENDCAP_LABEL_TO_RELATION").get(
            str(var.get()).strip()
        )
        if relation is None:
            return None
        self.settings_transactions().commit_endcap_edge_relation(
            part_key, edge, relation
        )
        try:
            app.do_update()
        except Exception:
            pass
        return relation

    def ensure_drawing_edge_hosts(self, namespace):
        app = self.app
        required = lambda name: self._required(namespace, name)
        existing = getattr(app, "drawing_edge_hosts", None)
        if existing is not None:
            try:
                if all(
                    host.winfo_exists()
                    for host in (
                        existing.top,
                        existing.bottom,
                        existing.left,
                        existing.right,
                    )
                ):
                    return existing
            except Exception:
                pass

        original = required("original")
        canvas = app.renderer.canvas.get_tk_widget()
        hosts = required("Phase6DrawingEdgeHosts")(
            top=original.ttk.Frame(canvas, padding=(4, 2)),
            bottom=original.ttk.Frame(canvas, padding=(4, 2)),
            left=original.ttk.Frame(canvas, padding=(4, 2)),
            right=original.ttk.Frame(canvas, padding=(4, 2)),
            center=canvas,
        )
        app.drawing_edge_hosts = hosts
        return hosts

    def clear_drawing_edge_controls(self):
        app = self.app
        hosts = getattr(app, "drawing_edge_hosts", None)
        if hosts is None:
            return None
        for host in (hosts.top, hosts.bottom, hosts.left, hosts.right):
            try:
                for child in host.winfo_children():
                    child.destroy()
                host.place_forget()
            except Exception:
                pass
        return None

    def render_endcap_edge_controls(
        self, namespace, *, part_key
    ):
        app = self.app
        required = lambda name: self._required(namespace, name)
        rows = required("_phase6_endcap_joint_policy_rows")(app, part_key)
        self.clear_drawing_edge_controls()
        app.endcap_joint_vars = {}
        app.endcap_joint_widgets = {}
        app.endcap_joint_allowed = {}
        if not rows:
            return None

        hosts = self.ensure_drawing_edge_hosts(namespace)
        edge_hosts = {
            "TOP": hosts.top,
            "BOTTOM": hosts.bottom,
            "LEFT": hosts.left,
            "RIGHT": hosts.right,
        }
        original = required("original")
        labels = required("_ENDCAP_EDGE_LABELS")
        build_choice_menubutton = required("build_choice_menubutton")
        place_host = required("_phase6_place_drawing_edge_host")
        for row in rows:
            edge = row["edge"]
            host = edge_hosts[edge]
            original.ttk.Label(
                host, text=f"{labels[edge]}："
            ).pack(side=original.tk.LEFT)
            var = original.tk.StringVar(
                master=host, value=row["value"]
            )
            widget = build_choice_menubutton(
                host,
                variable=var,
                values=row["allowed"],
                state=("normal" if row["editable"] else "disabled"),
                width=5,
                command=lambda p=part_key, e=edge: self.on_endcap_edge_relation_selected(
                    namespace, p, e
                ),
            )
            widget.pack(side=original.tk.LEFT)
            app.endcap_joint_vars[edge] = var
            app.endcap_joint_widgets[edge] = widget
            app.endcap_joint_allowed[edge] = tuple(row["allowed"])
            place_host(host, edge)
        return hosts

    def commit_base_plate_edge_shrink(
        self, namespace, edge, raw_value
    ):
        app = self.app
        required = lambda name: self._required(namespace, name)
        edge = str(edge).upper()
        key = required("_BASE_PLATE_EDGE_SETTING_KEYS").get(edge)
        if key is None:
            return False
        original = required("original")
        try:
            value = float(raw_value)
        except (TypeError, ValueError, original.tk.TclError):
            return False
        if value < 0:
            return False
        self.stage_setting_update(namespace, key, value)
        self.flush_pending_settings(namespace)
        var = dict(
            getattr(app, "base_plate_edge_shrink_vars", {}) or {}
        ).get(edge)
        if var is not None:
            text = required("_setting_number_text")(
                app._settings_values.get(key, value)
            )
            if var.get() != text:
                var.set(text)
        return True

    def render_base_plate_edge_controls(self, namespace):
        app = self.app
        required = lambda name: self._required(namespace, name)
        self.clear_drawing_edge_controls()
        app.endcap_joint_vars = {}
        app.endcap_joint_widgets = {}
        app.endcap_joint_allowed = {}
        app.base_plate_edge_shrink_vars = {}
        app.base_plate_edge_shrink_widgets = {}

        hosts = self.ensure_drawing_edge_hosts(namespace)
        edge_hosts = {
            "TOP": hosts.top,
            "BOTTOM": hosts.bottom,
            "LEFT": hosts.left,
            "RIGHT": hosts.right,
        }
        values = dict(getattr(app, "_settings_values", {}) or {})
        values.update(
            dict(getattr(app, "_phase6_input_snapshot", {}) or {})
        )
        original = required("original")
        labels = required("_ENDCAP_EDGE_LABELS")
        place_host = required("_phase6_place_drawing_edge_host")
        number_text = required("_setting_number_text")
        for edge, key in required(
            "_BASE_PLATE_EDGE_SETTING_KEYS"
        ).items():
            host = edge_hosts[edge]
            original.ttk.Label(
                host, text=f"{labels[edge]}縮："
            ).pack(side=original.tk.LEFT)
            var = original.tk.StringVar(
                master=host,
                value=number_text(values.get(key, 55.0)),
            )
            entry = original.ttk.Entry(
                host,
                textvariable=var,
                width=7,
                justify=original.tk.CENTER,
            )
            entry.pack(side=original.tk.LEFT)
            entry.bind(
                "<Return>",
                lambda _e, ed=edge, v=var: self.commit_base_plate_edge_shrink(
                    namespace, ed, v.get()
                ),
            )
            entry.bind(
                "<FocusOut>",
                lambda _e, ed=edge, v=var: self.commit_base_plate_edge_shrink(
                    namespace, ed, v.get()
                ),
            )
            app.base_plate_edge_shrink_vars[edge] = var
            app.base_plate_edge_shrink_widgets[edge] = entry
            place_host(host, edge)
        return hosts

    def render_active_drawing_edge_controls(self, namespace):
        app = self.app
        required = lambda name: self._required(namespace, name)
        mode = str(
            getattr(app, "_phase6_3d_display_mode", "single") or "single"
        )
        part_key = str(getattr(app, "active_part_key", None) or "")
        if mode != "single":
            self.clear_drawing_edge_controls()
            app.endcap_joint_vars = {}
            app.endcap_joint_widgets = {}
            app.endcap_joint_allowed = {}
            app.base_plate_edge_shrink_vars = {}
            app.base_plate_edge_shrink_widgets = {}
            return None
        if part_key in required("ENDCAP_FW_PARTS"):
            app.base_plate_edge_shrink_vars = {}
            app.base_plate_edge_shrink_widgets = {}
            return self.render_endcap_edge_controls(
                namespace, part_key=part_key
            )
        if part_key == "base_plate":
            return self.render_base_plate_edge_controls(namespace)
        self.clear_drawing_edge_controls()
        app.endcap_joint_vars = {}
        app.endcap_joint_widgets = {}
        app.endcap_joint_allowed = {}
        app.base_plate_edge_shrink_vars = {}
        app.base_plate_edge_shrink_widgets = {}
        return None

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
            blank_text_provider=required(
                "_phase6_format_unfolded_blank_text"
            ),
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

    def sync_authoritative_derived_parts(self, namespace):
        """Compose cross-domain derived topology, then delegate the unique workspace mutation."""
        app = self.app
        required = lambda name: self._required(namespace, name)
        snapshot = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
        workspace = getattr(app, "designer_workspace", None)
        navigation = self.workspace_navigation()
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

    def workspace_navigation(self):
        """Return the single workspace/navigation application controller."""
        app = self.app
        workspace = getattr(app, "designer_workspace", None)
        controller = self._workspace_navigation_controller
        if controller is None or getattr(controller, "workspace", None) is not workspace:
            current = getattr(app, "_phase6_workspace_navigation_controller", None)
            if (
                isinstance(current, Phase6WorkspaceNavigationController)
                and getattr(current, "workspace", None) is workspace
            ):
                controller = current
            else:
                legacy_memory = getattr(app, "__dict__", {}).get(
                    "_phase6_box_body_active_piece_key"
                )
                controller = Phase6WorkspaceNavigationController(
                    workspace,
                    remembered_box_body_child=legacy_memory,
                )
            self._workspace_navigation_controller = controller
            app._phase6_workspace_navigation_controller = controller
        return controller

    def registry_diagnostics(self):
        """Return the single Registry diagnostics application controller."""
        app = self.app
        controller = self._registry_diagnostics_controller
        if controller is None:
            current = getattr(app, "_phase6_registry_diagnostics_controller", None)
            if isinstance(current, Phase6RegistryDiagnosticsController):
                controller = current
            else:
                controller = Phase6RegistryDiagnosticsController(
                    candidate_id=getattr(app, "_phase6_registry_candidate_id", ""),
                    candidate_record=getattr(
                        app, "_phase6_registry_candidate_record", {}
                    ),
                    regression_evidence=getattr(
                        app, "_phase6_registry_regression_evidence", {}
                    ),
                    rule_records=getattr(app, "_phase6_registry_rule_records", {}),
                    promotion_candidates=getattr(
                        app, "_phase6_last_relief_promotion_candidates", {}
                    ),
                )
            self._registry_diagnostics_controller = controller
            app._phase6_registry_diagnostics_controller = controller
        return controller

    def settings_service(self):
        if self._settings_service is None:
            app = self.app
            self._settings_service = Phase6SettingsTransactionService(
                settings_values=getattr(app, "_settings_values", {}),
                input_snapshot=getattr(app, "_phase6_input_snapshot", {}),
                box_whd=getattr(app, "_phase6_box_whd", {}),
                pending_settings=getattr(app, "_phase6_pending_settings", {}),
            )
        return self._settings_service

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

        navigation = self.workspace_navigation()
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
        blank_text = required("_phase6_format_unfolded_blank_text")
        corner_text = required("_phase6_render_data_corner_dimension_text")

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
