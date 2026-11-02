"""Fold Designer project-snapshot projection seam.

Projection only: authoritative state remains owned by the existing controllers/services.
"""
from copy import deepcopy
import tkinter as tk

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from phase6_endcap_semantics import assembly_intent_value, normalize_endcap_bottom_wrap_state
from phase6_settings_center import load_factory_defaults_from_ae

def _read_snapshot_numeric_control(var, fallback=0.0, *, physical_field=None):
    """Read only GUI input; Engine rejects unavailable physical source data."""
    try:
        raw = var.get()
    except (TypeError, ValueError, tk.TclError) as exc:
        if physical_field is not None:
            raise ValueError(
                f"{physical_field.upper()} 實體尺寸來源無法讀取，禁止使用預設值"
            ) from exc
        return float(fallback)
    if physical_field is not None:
        return manufacturing_api.normalize_operator_source_dimension(
            raw, field=physical_field,
        )
    try:
        return float(raw)
    except (TypeError, ValueError, OverflowError):
        return float(fallback)


def _snapshot_base_state(self):
    """Project current GUI adapters into the existing Fold Designer snapshot schema."""
    number = _read_snapshot_numeric_control

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
        "w": number(self.w_var, ae.W, physical_field="w"),
        "h": number(self.h_var, ae.H, physical_field="h"),
        "d": number(self.d_var, ae.D, physical_field="d"),
        "t": number(self.t_var, ae.T, physical_field="t"),
        "fw": number(self.fw_z_var, ae.FW, physical_field="fw"),
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
        "door_layout_indicator_states": (
            manufacturing_api.project_operator_door_layout_indicator_snapshot_states(
                getattr(self, "door_layout_indicator_states", None) or {}
            )
        ),
        "door_layout_indicator_box_features": deepcopy(
            getattr(self, "door_layout_indicator_box_features", {}) or {}
        ),
        "door_layout_indicator_door_features": deepcopy(
            getattr(self, "door_layout_indicator_door_features", {}) or {}
        ),
        "box_body_active_piece": box_body_active_piece,
    }
    if getattr(self, "door_layout_columns", None):
        snapshot["door_layout_columns"] = [
            [float(width), [float(v) for v in heights]]
            for width, heights in self.get_door_layout_columns()
        ]
    else:
        snapshot["door_layout_columns"] = []

    settings = dict(self._collect_main_setting_values())
    snapshot.update({key: value for key, value in settings.items() if key in snapshot})
    # Settings overlays cannot bypass the input validator. Preserve the
    # identical fractional physical source in Snapshot and Settings payload.
    physical_source = manufacturing_api.normalize_operator_source_dimensions(
        snapshot
    )
    snapshot.update(physical_source)
    settings.update({
        key: value for key, value in physical_source.items()
        if key in settings
    })
    snapshot["settings"] = dict(settings)
    snapshot["corner_state"] = self._serialize_manual_corner_state()
    snapshot["corner_pair_same"] = deepcopy(self.manual_corner_pair_same)
    baseline_models = self._baseline_model_choices()
    corner_catalog = manufacturing_api.project_operator_corner_selection_catalog(
        snapshot["model"], baseline_models,
    )
    snapshot["corner_editable"] = corner_catalog.editable
    snapshot["corner_type_labels"] = dict(corner_catalog.labels)
    snapshot["baseline_models"] = baseline_models
    snapshot["baseline_unknown_value"] = corner_catalog.custom_model_name
    snapshot["factory_defaults"] = load_factory_defaults_from_ae(ae)
    designer = getattr(self, "fold_designer_app", None)
    stored = (
        getattr(designer, "_phase6_input_snapshot", None)
        or getattr(self, "_phase6_input_snapshot", None)
        or {}
    )
    # Engine alone decides whether this Family owns a physical BasePlate.
    # Only carry a detached *committed* source; never derive a pattern here.
    snapshot.update(manufacturing_api.project_operator_receiving_base_plate_snapshot_source(
        snapshot, stored,
    ))
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
    for key in ("active_mode", "quantity", "receiving_quantity_box", "receiving_layout"):
        if key in workspace_state:
            snapshot[key] = deepcopy(workspace_state[key])
    # Engine alone decides whether root Door controls own the sole Receiving Bay.
    bay_layout = manufacturing_api.project_receiving_single_bay_door_controls(snapshot)
    if bay_layout is not None:
        snapshot["receiving_layout"] = bay_layout
    custom = workspace_state.get("custom_parts")
    if custom is not None:
        snapshot["custom_parts"] = deepcopy(custom)

    joint_state = manufacturing_api.project_operator_assembly_joint_snapshot(
        getattr(self, "assembly_joint_state", None),
        existing_parts=ordered,
        assembly_type=snapshot["assembly_type"],
    )
    self.assembly_joint_state = joint_state
    snapshot["assembly_joint_schema_version"] = joint_state["assembly_joint_schema_version"]
    snapshot["assembly_joints"] = deepcopy(joint_state["assembly_joints"])

    active = self.workspace_controller.active_part
    snapshot["active_part"] = active if active in ordered else (ordered[0] if ordered else None)
    _snapshot_part_features(self, snapshot)

    snapshot["part_face_features"] = {
        "box_body": {
            face: list(features)
            for face, features in self.box_body_face_features.items()
        }
    }
    return committed_profiles

def _snapshot_part_features(self, snapshot):
    """Save operator Feature stores from one canonical Engine identity projection."""
    snapshot["part_features"] = manufacturing_api.project_fold_designer_snapshot_part_features(
        snapshot,
        getattr(self, "surface_features", None),
        getattr(self, "door_layout_features", None),
    )
    return snapshot


def _snapshot_part_dimensions(self, snapshot):
    """Collect operator inputs; Engine validates Indicator and physical sizes.

    Disabled Indicator controls retain the legacy display-only seed, but an
    enabled malformed group may never be saved as a fabricated (1,) or ().
    No snapshot mutation occurs before both enabled sources are valid.
    """
    box_enabled = bool(self.is_indicator_box_var.get())
    door_enabled = bool(self.is_door_indicator_var.get())

    def read_groups(layer_var, group_vars, *, label):
        try:
            count = manufacturing_api.normalize_fold_designer_indicator_groups(
                (layer_var.get(),)
            )[0]
            raw_groups = [group_vars[i].get() for i in range(count)]
        except Exception as exc:
            raise ValueError(f"{label}層數／組數無效，拒絕保存快照") from exc
        return manufacturing_api.normalize_fold_designer_indicator_groups(
            raw_groups
        )

    groups = (
        read_groups(self.indicator_l_var, self.indicator_layer_g_vars, label="指示燈盒")
        if box_enabled else (1,)
    )
    direct_groups = (
        read_groups(self.door_indicator_l_var,
                    self.door_indicator_layer_g_vars, label="門板指示燈")
        if door_enabled else ()
    )
    dimensions = manufacturing_api.project_fold_designer_snapshot_dimensions(
        snapshot, groups,
    )
    offsets = (
        float(self.door_indicator_offset_x),
        float(self.door_indicator_offset_y),
    )
    snapshot["indicator_layer_groups"] = list(dimensions.indicator_layer_groups)
    snapshot["door_indicator_groups"] = list(direct_groups)
    snapshot["door_indicator_offset"] = offsets
    snapshot["door_indicator_box_enabled"] = box_enabled
    snapshot["part_dimensions"] = {
        key: dict(size) for key, size in dimensions.part_dimensions.items()
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
