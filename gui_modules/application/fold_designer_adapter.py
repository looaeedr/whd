"""Fold Designer application adapter boundary for #295/T7.

This module adapts existing application state to authoritative engine/manufacturing
APIs. It does not own project schema, workspace identity, committed settings, or
manufacturing geometry.
"""
from dataclasses import replace
from pathlib import Path

import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
from ae_engine.corner_type_ui import (
    is_unknown_model,
    known_model_corner_state,
    policy_from_corner_state,
)
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    normalize_corner_selection,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
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

