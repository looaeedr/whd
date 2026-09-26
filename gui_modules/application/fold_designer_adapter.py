"""Fold Designer application adapter boundary for #295/T7.

This module adapts existing application state to authoritative engine/manufacturing
APIs. It does not own project schema, workspace identity, committed settings, or
manufacturing geometry.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
import hashlib
import json
import tkinter as tk
import traceback

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as cabinet_family_policy
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
from phase6_settings_contracts import SettingsStateSnapshot
from phase6_settings_transaction_controller import Phase6SettingsTransactionController
from phase6_workspace_navigation_controller import Phase6WorkspaceNavigationController
from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController
from phase6_registry_diagnostics_panel import Phase6RegistryDiagnosticsPanel
from phase6_settings_panel import Phase6SettingsPanel
from phase6_workspace_shell import (
    WorkspaceShellActions,
    WorkspaceShellOwner,
    WorkspaceShellState,
)
from phase6_box_body_structure import BoxBodyStructureType
from whd_theme import WHD_THEME
from phase6_final_scene_contracts import (
    AssemblyScenePart,
    AssemblySceneRenderData,
    FinalSceneDependencies,
)
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_corner_data_view_adapter import Phase6CornerDataViewAdapter
from phase6_assembly_panel import Phase6AssemblyPanel
from phase6_manufacturing_adapter import operator_finished_dimensions_for_app
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from gui_modules.application.state_sync import Phase6DerivedCacheOwner
from gui_modules.application.fold_designer_settings_coordinator import (
    Phase6FoldDesignerSettingsCoordinator,
    Phase6SettingsApplicationPorts,
)
from gui_modules.application.command_router import _Phase6UpdateScheduler
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

    @staticmethod
    def _required(namespace, name):
        try:
            return namespace[name]
        except KeyError as exc:
            raise RuntimeError(
                f"Fold Designer composition port is unavailable: {name}"
            ) from exc

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
            stage_setting_update=lambda key, value: required(
                "_phase6_stage_setting_update"
            )(app, key, value),
            flush_settings=lambda: required("_phase6_flush_pending_settings")(app),
            save_defaults=lambda context: required(
                "_phase6_save_settings_context_as_defaults"
            )(app, context),
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
            context_extension_projection=lambda context: required(
                "_phase6_settings_context_extension_projection"
            )(app, context),
            endcap_fw_value_selected=lambda part_key, value_var: required(
                "_phase6_on_endcap_fw_value_selected"
            )(app, part_key, value_var),
            box_structure_numeric_changed=lambda type_id, field, value_var: required(
                "_phase6_apply_box_structure_numeric"
            )(app, type_id, field, value_var),
            box_back_panel_mode_changed=lambda value_var: required(
                "_phase6_select_back_panel_mode"
            )(app, value_var),
            box_structure_toggle_advanced=lambda type_id: required(
                "_phase6_toggle_structure_advanced"
            )(app, type_id),
            bottom_wrap_commit=lambda part_key, reserve_u_var, reserve_v_var: required(
                "_phase6_commit_receiving_bottom_wrap_controls"
            )(app, part_key, reserve_u_var, reserve_v_var),
            corner_pair_changed=lambda part_key, pair_key, var: required(
                "_phase6_corner_pair_var_changed"
            )(app, part_key, pair_key, var),
            corner_type_selected=lambda part_key, target_key: required(
                "_phase6_corner_type_selected"
            )(app, part_key, target_key),
            corner_mode_selected=lambda part_key, target_key: required(
                "_phase6_corner_mode_selected"
            )(app, part_key, target_key),
            corner_target_changed=lambda part_key, target_key: required(
                "_phase6_corner_target_var_changed"
            )(app, part_key, target_key),
            sync_context_extension=lambda state, context: required(
                "_phase6_sync_settings_panel_extension"
            )(app, state, context),
            baseline_model_changed=lambda: required(
                "_phase6_on_baseline_model_changed"
            )(app),
            ui_text_size_changed=lambda key: required(
                "_phase6_apply_ui_text_size"
            )(app, key),
        )
        self._settings_panel = panel
        app.settings_panel = panel
        return panel

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
        panel = Phase6RegistryDiagnosticsPanel(
            owner=app,
            present_token=lambda value, **kwargs: required(
                "_phase6_registry_present_token"
            )(value, **kwargs),
            formula_display=lambda value, presentation_field="formula": required(
                "_phase6_registry_formula_display"
            )(value, presentation_field=presentation_field),
            formula_raw=required("_phase6_formula_raw"),
            preconditions_display=required("_phase6_preconditions_display"),
            preconditions_raw=required("_phase6_preconditions_raw"),
            source_display=lambda value, presentation_field="source": required(
                "_phase6_registry_source_display"
            )(value, presentation_field=presentation_field),
            source_raw=required("_phase6_source_raw"),
            validate_formula=lambda: required(
                "_phase6_registry_validate_formula_form"
            )(app),
            preview_payload=lambda: required("_phase6_registry_preview_payload")(app),
            preview_assembly_3d=lambda: required(
                "_phase6_registry_preview_assembly_3d"
            )(app),
            save_candidate=lambda: required("_phase6_registry_save_candidate_form")(app),
            run_formula_matrix=lambda: required(
                "_phase6_registry_run_formula_matrix"
            )(app),
            promote_candidate=lambda: required("_phase6_registry_promote_form")(app),
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
            sync_settings_panel_compat=lambda: required(
                "_phase6_sync_settings_panel_compat"
            )(app),
            get_left_global_controls=lambda: app.left_global_controls,
            get_left_global_cells=lambda: app.left_global_cells,
            get_ui_text_size_var=lambda: app.ui_text_size_var,
            set_ui_text_size_combo=lambda combo: setattr(
                app.settings_panel, "ui_text_size_combo", combo
            ),
            toggle_parameter_panel=lambda: required(
                "_phase6_toggle_parameter_panel"
            )(app),
            select_structure_type=lambda var: required(
                "_phase6_select_box_structure_type"
            )(app, var),
            select_assembly_type=lambda: required(
                "_phase6_on_assembly_type_selected"
            )(app),
            refresh_persistent_structure_controls=lambda: required(
                "_phase6_refresh_persistent_structure_controls"
            )(app),
            commit_output_draw_stock=lambda: required(
                "_phase6_commit_output_draw_stock"
            )(app),
            export_selected_dxf=lambda: required(
                "_phase6_export_selected_dxf_from_3d"
            )(app),
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
            toggle_fullscreen=lambda: required("_phase6_toggle_fullscreen")(app),
        )
        owner = WorkspaceShellOwner(shell_state, actions)
        self._workspace_shell_owner = owner
        app._phase6_workspace_shell_owner = owner
        return owner

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
                refresh_parts = getattr(app, "_refresh_part_buttons", None)
                if (
                    callable(refresh_parts)
                    and getattr(app, "part_choice_menu", None) is not None
                ):
                    return refresh_parts()
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
            apply_profile_plan=lambda committed, **kwargs: required(
                "_phase6_settings_application_apply_profile_plan"
            )(app, committed, **kwargs),
            sync_derived_parts=lambda *args, **kwargs: required(
                "_phase6_sync_authoritative_derived_parts"
            )(app),
            project_ui_values=lambda values, **kwargs: required(
                "_phase6_settings_application_project_ui_values"
            )(app, values, **kwargs),
            render_bending=render_bending,
            refresh_settings_panel=refresh_settings_panel,
            refresh_topology=refresh_topology,
            refresh_persistent_controls=lambda: required(
                "_phase6_refresh_persistent_structure_controls"
            )(app),
            submit_update_intent=lambda committed: required(
                "_phase6_settings_application_submit_update_intent"
            )(app, committed),
            publish_live_state=lambda committed, **kwargs: required(
                "_phase6_settings_application_publish_live_state"
            )(app, committed, **kwargs),
            project_status=project_status,
        )

    def settings_coordinator(self, ports: Phase6SettingsApplicationPorts):
        """Return the single Phase 5 Settings application sequencing owner."""
        if self._settings_coordinator is None:
            app = self.app

            def begin_update_batch():
                scheduler = getattr(app, "_phase6_update_scheduler", None)
                if not isinstance(scheduler, _Phase6UpdateScheduler):
                    scheduler = _Phase6UpdateScheduler(app)
                    app._phase6_update_scheduler = scheduler
                scheduler.begin()
                return True

            def end_update_batch(commit=True):
                scheduler = getattr(app, "_phase6_update_scheduler", None)
                if not isinstance(scheduler, _Phase6UpdateScheduler):
                    return False
                scheduler.end()
                if bool(commit):
                    return scheduler.flush_now()
                scheduler.cancel_pending()
                return False

            self._settings_coordinator = Phase6FoldDesignerSettingsCoordinator(
                transactions=self.settings_transactions(),
                ports=ports,
                begin_update_batch=begin_update_batch,
                end_update_batch=end_update_batch,
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
                self._final_scene_renderer = Phase6FinalSceneRenderer(
                    raw_renderer,
                    number_text=number_text,
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

        def record_visible_scene_commit(request=None):
            if not getattr(app, "_phase6_visible_scene_transition_active", False):
                return None
            records = getattr(app, "_phase6_visible_scene_commit_records", None)
            if not isinstance(records, list):
                records = []
                app._phase6_visible_scene_commit_records = records
            transition_id = str(
                getattr(app, "_phase6_visible_scene_transition_id", "") or ""
            )
            transition_stage = str(
                getattr(app, "_phase6_visible_scene_transition_stage", "") or ""
            )
            cabinet_family = str(
                required("_phase6_current_cabinet_family")(app) or ""
            )
            workspace = getattr(app, "designer_workspace", None)
            inventory = tuple(
                sorted(
                    str(part_key)
                    for part_key in tuple(
                        getattr(workspace, "available_parts", ()) or ()
                    )
                )
            )
            final_scene = getattr(app, "final_scene_view", None)
            scene_summary = {
                "cabinet_family": cabinet_family,
                "physical_inventory": inventory,
                "active_part": str(getattr(workspace, "active_part", "") or ""),
                "request_part": str(getattr(request, "part_key", "") or ""),
                "display_mode": str(
                    getattr(app, "_phase6_3d_display_mode", "single") or "single"
                ),
                "cutting_mesh_count": len(
                    tuple(getattr(final_scene, "last_cutting_mesh", ()) or ())
                ),
                "collection_count": len(
                    tuple(getattr(app.renderer.ax3d, "collections", ()) or ())
                ),
                "line_count": len(
                    tuple(getattr(app.renderer.ax3d, "lines", ()) or ())
                ),
            }
            encode = lambda value: json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
            records.append(
                {
                    "transition_id": transition_id,
                    "sequence": len(records) + 1,
                    "scene_fingerprint": hashlib.sha256(
                        encode(scene_summary)
                    ).hexdigest(),
                    "cabinet_family": cabinet_family,
                    "physical_inventory_fingerprint": hashlib.sha256(
                        encode(inventory)
                    ).hexdigest(),
                    "transition_stage": transition_stage,
                    "invalid_visible_commit": transition_stage != "finalize",
                    "call_stack": (
                        traceback.format_stack(limit=24)
                        if transition_stage != "finalize"
                        else ()
                    ),
                }
            )
            if transition_stage == "finalize":
                app._phase6_visible_scene_transition_active = False
            return None

        final_scene_renderer = self.final_scene_renderer(number_text=number_text)
        if final_scene_renderer is not None:
            final_scene_renderer.visible_commit_hook = record_visible_scene_commit

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
                return required("_phase6_final_scene_set_preview_enabled")(
                    app, True
                )
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
            publish_live_state=lambda **kwargs: required(
                "_phase6_publish_live_state"
            )(app, **kwargs),
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
                "_phase6_active_mesh_profiles"
            )(app, material),
            assembly_render_data_cls=AssemblySceneRenderData,
            assembly_part_cls=AssemblyScenePart,
            final_render_provider=lambda: required(
                "_phase6_query_final_render_data"
            )(app),
            assembly_render_provider=lambda: required(
                "_phase6_query_assembly_render_data"
            )(app),
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
            set_preview_enabled=lambda enabled: required(
                "_phase6_final_scene_set_preview_enabled"
            )(app, enabled),
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
