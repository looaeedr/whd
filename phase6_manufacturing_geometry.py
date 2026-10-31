# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Canonical Phase 1 manufacturing helper owner extracted move-only from fold_designer_bridge."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Mapping

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells, door_layout_part_key
from phase6_endcap_semantics import ENDCAP_FW_PARTS
from phase6_final_scene_view import AssemblyScenePart
from phase6_sync_envelope import stable_fingerprint
from ae_engine.assembly_joint import (
    AssemblyJoint,
    ResolvedAssemblyGraph,
    migrate_legacy_snapshot_joints,
)
from phase6_endcap_semantics import assembly_intent_value
from phase6_fold_profiles import _num
from phase6_part_navigation import is_box_body_physical_piece_key
from phase6_manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingDiagnosticsResult,
    ManufacturingEffects,
    ManufacturingMutationResult,
    ManufacturingResolveRequest,
    ManufacturingResolveResult,
    thaw_manufacturing_value,
)



# Phase6 only retains the historic names for caller compatibility.
from ae_engine import manufacturing_api
_PHASE6_ASSEMBLY_PLACEMENTS = manufacturing_api.SCENE_ASSEMBLY_PLACEMENTS


def _phase6_door_part_assembly_placement(snapshot, part_key):
    return manufacturing_api.resolve_legacy_door_cell_scene_placement(
        snapshot, part_key
    )


def _phase6_assembly_placement_for_part(snapshot, part_key):
    return manufacturing_api.resolve_scene_assembly_placement(
        snapshot, part_key
    )


def _phase6_relief_polygon_coords(geometry):
    """Compat: Engine serializes the actual Joint relief CUT geometry."""
    return manufacturing_api.serialize_joint_relief_polygons(geometry)


def _phase6_assembly_relief_clearance(self):
    """UI-only clearance is nonnegative finite; never widen manufacturing by infinity."""
    from math import isfinite

    var = getattr(self, "assembly_relief_clearance_var", None)
    raw = var.get() if var is not None else "0"
    try:
        value = float(str(raw).strip() or "0")
    except (TypeError, ValueError, OverflowError):
        value = 0.0
    # Keep the existing invalid-text fallback and negative-value clamp, but
    # reject NaN/Inf rather than letting +Inf hide every collision residual.
    return max(0.0, value) if isfinite(value) else 0.0


def _phase6_current_cabinet_family(self):
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    model_var = getattr(self, "baseline_model_var", None)
    model = str(snapshot.get("model") or snapshot.get("cabinet_type") or "").strip()
    try:
        live_model = str(model_var.get() or "").strip() if model_var is not None else ""
    except Exception:
        live_model = ""
    if live_model:
        model = live_model
    try:
        from ae_engine.cabinet_types.registry import resolve_cabinet_type
        return resolve_cabinet_type(model).canonical_name
    except Exception:
        # 自訂/舊基準型號仍可命中 cabinet_family=ANY 的已認證 Assembly 規則。
        return model or "金庫型"


def _phase6_solution_is_committable(solution):
    if bool(getattr(solution, "verified", False)):
        return True
    trust = str(getattr(solution, "trust_level", "") or "")
    return bool(getattr(solution, "rule_id", None)) and trust in {
        "CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"
    }


def _phase6_apply_resolved_cut_to_part(part, cut_polygon):
    """Compatibility: Engine owns real verified Joint material subtraction."""
    return manufacturing_api.apply_verified_joint_cut_to_part(part, cut_polygon)


def _phase6_apply_resolved_cut_to_owner(part, owner_key, cut_polygon):
    """Compatibility: Engine owns physical BoxBody child cut application."""
    return manufacturing_api.apply_verified_joint_cut_to_owner(
        part, owner_key, cut_polygon,
    )


def _phase6_side_wrap_target_corners(preserve_part_key):
    return manufacturing_api.side_wrap_target_corners(preserve_part_key)


def _phase6_box_body_piece_solver_key(body_part, region, *, require_flat_uv):
    return manufacturing_api.resolve_box_body_piece_solver_key(
        body_part, region, require_flat_uv=require_flat_uv,
    )


def _phase6_expand_box_body_fw_world_mid(
    piece, mapped, world_mid_piece, *, sheet_thickness, tolerance=1e-7
):
    """Compatibility: Engine owns formed side-FW physical skin expansion."""
    return manufacturing_api.expand_box_body_fw_world_mid(
        piece, mapped, world_mid_piece,
        sheet_thickness=sheet_thickness, tolerance=tolerance,
    )


def _phase6_shift_multistage_terminal_fold_world_mid(piece, mapped, world_mid_piece, *, tolerance=1e-7):
    """Compatibility: Engine owns terminal fold physical tangent correction."""
    return manufacturing_api.shift_multistage_terminal_fold_world_mid(
        piece, mapped, world_mid_piece, tolerance=tolerance,
    )


def _phase6_fit_receiving_left_zl1_outside_world_mid(
    piece, mapped, world_mid_piece, *, sheet_thickness, tolerance=1e-7,
):
    """Compatibility: Engine owns Receiving zl1 formed outside skin."""
    return manufacturing_api.fit_receiving_left_zl1_world_mid(
        piece, mapped, world_mid_piece,
        sheet_thickness=sheet_thickness, tolerance=tolerance,
    )


def _phase6_joint_relief_state_item_matches(item, joint, source_material):
    return manufacturing_api.joint_relief_state_item_matches(
        item, joint, source_material,
    )


def _phase6_cut_geometry_from_state_item(item):
    """Compat: Engine validates the saved provisional Joint cut geometry."""
    return manufacturing_api.restore_joint_relief_cut_geometry(item)


def _phase6_signature_canonical_value(value):
    """Normalize representation-only differences before manufacturing caching."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        from math import isfinite

        # An invalid manufacturing dimension may NEVER share a cache key
        # with a literal marker such as "__NaN__", or another invalid value.
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("nonfinite manufacturing signature value") from exc
        if not isfinite(number):
            raise ValueError("nonfinite manufacturing signature value")
        return round(number, 12)
    if isinstance(value, Mapping):
        return {str(key): _phase6_signature_canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_phase6_signature_canonical_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        normalized = [_phase6_signature_canonical_value(item) for item in value]
        return tuple(sorted(normalized, key=repr))
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return _phase6_signature_canonical_value(enum_value)
    return repr(value)


def _phase6_manufacturing_state_signature(self):
    """Stable key for canonical manufacturing inputs; persistence/view mirrors excluded."""
    workspace = getattr(self, "designer_workspace", None)
    available = tuple(getattr(workspace, "available_parts", ()) or ())
    profiles = {}
    if workspace is not None:
        for key in available:
            try:
                profiles[key] = deepcopy(workspace.profiles_for(key, {}) or {})
            except Exception:
                profiles[key] = {}

    settings = deepcopy(dict(getattr(self, "_settings_values", {}) or {}))
    # Typography is UI-only and must never invalidate canonical manufacturing.
    settings.pop("ui_text_size", None)
    snapshot = deepcopy(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    if str(snapshot.get("model") or "") in {"受電箱", "RECEIVING"}:
        # Receiving Settings W/H/D only seed NEW cabinets. Both the
        # manufacturing DTO and physical preview already consume live Bay/
        # Quantity dimensions; the cache key must use that same authority.
        # Never write working dimensions back to persisted Settings defaults.
        working_box = dict(getattr(self, "_phase6_box_whd", {}) or {})
        settings.update({
            axis: working_box[axis] for axis in ("w", "h", "d")
            if axis in working_box
        })
    # These fields are either owned independently below or derived/persistence
    # mirrors. Saving an unchanged editor may materialize them, but that is not a
    # manufacturing mutation and must not destroy an otherwise valid cache hit.
    mirror_keys = set(settings) | {
        "settings", "endcap_fw", "endcap_bottom_wrap", "assembly_type",
        "corner_state", "corner_pair_same", "active_part", "part_dimensions",
    }
    snapshot = {key: value for key, value in snapshot.items() if key not in mirror_keys}

    state = (
        snapshot,
        settings,
        deepcopy(dict(getattr(self, "_phase6_box_whd", {}) or {})),
        deepcopy(dict(getattr(self, "_phase6_corner_state", {}) or {})),
        deepcopy(dict(getattr(self, "_phase6_endcap_fw_state", {}) or {})),
        deepcopy(dict(getattr(self, "_phase6_endcap_bottom_wrap_state", {}) or {})),
        available,
        profiles,
        getattr(getattr(self, "_phase6_assembly_type", None), "value", getattr(self, "_phase6_assembly_type", None)),
        bool(getattr(getattr(self, "assembly_ignore_fixed_corner_var", None), "get", lambda: False)()),
        _phase6_assembly_relief_clearance(self),
    )
    return stable_fingerprint(_phase6_signature_canonical_value(state))


def _phase6_joint_registry_diagnostic_info(joint, render_by_part, solution_by_part):
    """Compatibility: Engine owns Certified Joint diagnostic evidence."""
    return manufacturing_api.joint_registry_diagnostic_info(
        joint, render_by_part, solution_by_part,
    )


def _phase6_build_joint_world_geometry(parts, finished_dimensions, sheet_thickness):
    """Phase6 compatibility: world/UV collision geometry is Engine-owned."""
    return manufacturing_api.build_joint_world_geometry(
        parts, finished_dimensions, sheet_thickness,
    )


def _phase6_resolve_explicit_joint_reliefs(
    parts, joints, *, finished_dimensions, sheet_thickness, clearance=0.0,
    committed_state=None,
):
    """Resolve USER_ADDED reliefs through the bounded Phase 7 A6 pipeline."""
    from phase6_explicit_joint_pipeline import (
        ExplicitJointPipelineOps,
        resolve_explicit_joint_reliefs,
    )

    ops = ExplicitJointPipelineOps(
        box_body_piece_solver_key=_phase6_box_body_piece_solver_key,
        side_wrap_target_corners=_phase6_side_wrap_target_corners,
        build_world_geometry=_phase6_build_joint_world_geometry,
        state_item_matches=_phase6_joint_relief_state_item_matches,
        cut_geometry_from_state_item=_phase6_cut_geometry_from_state_item,
        apply_cut_to_owner=_phase6_apply_resolved_cut_to_owner,
        apply_cut_to_part=_phase6_apply_resolved_cut_to_part,
        relief_polygon_coords=_phase6_relief_polygon_coords,
    )
    return resolve_explicit_joint_reliefs(
        parts,
        joints,
        finished_dimensions=finished_dimensions,
        sheet_thickness=sheet_thickness,
        clearance=clearance,
        committed_state=committed_state,
        ops=ops,
    )

def _phase6_resolve_family_divider_reliefs(
    parts, *, finished_dimensions, sheet_thickness, clearance=0.0
):
    """Compatibility: Engine resolves physical Family Divider relief and evidence."""
    return manufacturing_api.resolve_family_divider_reliefs(
        parts, finished_dimensions=finished_dimensions,
        sheet_thickness=sheet_thickness, clearance=clearance,
    )


def _phase6_request_part(request, part_key):
    key = str(part_key or "")
    for item in tuple(request.parts or ()):
        if str(item.part_key) == key:
            return item
    raise KeyError(key)


def _phase6_request_profiles_for_material(part_input, material):
    """Reproduce Phase 1 mesh-profile normalization from immutable request data."""
    key = str(part_input.part_key or "")
    x_prof = [dict(seg) for seg in tuple(part_input.x_profile or ())]
    y_prof = [dict(seg) for seg in tuple(part_input.y_profile or ())]

    def material_span(axis):
        # Only the whole Box Body and a one-axis frame/divider need this
        # geometric fallback. Other physical pieces already own both fold
        # profiles; inspecting unrelated bounds could abort valid assembly.
        from math import isfinite
        try:
            raw = tuple(material.bounds)
            if len(raw) != 4 or any(isinstance(v, bool) for v in raw):
                raise ValueError("material bounds must have four real values")
            minx, miny, maxx, maxy = (float(value) for value in raw)
            if not all(isfinite(value) for value in (minx, miny, maxx, maxy)):
                raise ValueError("material bounds must be finite")
            span = (maxx - minx) if axis == "x" else (maxy - miny)
            if not isfinite(span) or span <= 0.0:
                raise ValueError("derived material span must be positive")
            return span
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("physical material bounds unavailable for mesh profile") from exc

    if key == "box_body":
        return x_prof, [{"len": material_span("y")}]
    if key.startswith("box_body:divider:") or (
        key.startswith("inner_door:") and key.endswith("_frame")
    ):
        if x_prof and not y_prof:
            y_prof = [{"len": material_span("y")}]
        elif y_prof and not x_prof:
            x_prof = [{"len": material_span("x")}]
    return x_prof, y_prof
