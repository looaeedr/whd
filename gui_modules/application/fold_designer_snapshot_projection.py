"""Fold Designer project-snapshot projection seam.

Projection only: authoritative state remains owned by the existing controllers/services.
"""
from copy import deepcopy
from dataclasses import replace
import tkinter as tk

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.contracts import ManufacturingContext
from ae_engine.corner_type_ui import is_unknown_model
from ae_engine.sheetmetal_geometry import EDITABLE_CORNER_TYPE_IDS, CORNER_TYPE_LABELS
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges, door_layout_feature_map_to_part_features
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from phase6_endcap_semantics import assembly_intent_value, normalize_endcap_bottom_wrap_state
from phase6_settings_center import load_factory_defaults_from_ae

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
    workspace_state = self.workspace_controller.workspace_snapshot()
    ordered.extend(key for key in workspace_state["existing_parts"]
                   if key in current_existing and key not in ordered)
    snapshot["existing_parts"] = ordered
    custom = workspace_state.get("custom_parts")
    if custom is not None:
        snapshot["custom_parts"] = deepcopy(custom)

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
