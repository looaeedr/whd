"""Fold Designer application adapter boundary for #295/T7.

This module adapts existing application state to authoritative engine/manufacturing
APIs. It does not own project schema, workspace identity, committed settings, or
manufacturing geometry.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tkinter as tk

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
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from phase6_endcap_semantics import assembly_intent_value, normalize_endcap_bottom_wrap_state
from phase6_settings_center import load_factory_defaults_from_ae
from gui_modules.application.state_sync import Phase6DerivedCacheOwner
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

