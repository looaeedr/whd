# -*- coding: utf-8 -*-
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



_PHASE6_ASSEMBLY_PLACEMENTS = {
    "box_body": "box_body",
    "head": "top",
    "tail": "bottom",
    "door": "front",
    "indicator_box": "front",
    "indicator_door": "front",
}


def _phase6_door_part_assembly_placement(snapshot, part_key):
    """Return canonical front-plane placement for one formal Door layout cell."""
    key = str(part_key or "")
    columns = tuple(
        (float(row[0]), tuple(float(v) for v in row[1]))
        for row in tuple(dict(snapshot or {}).get("door_layout_columns") or ())
    )
    if not columns:
        raise ValueError(f"門格缺少 authoritative multi-door topology: {key}")
    cells = derive_door_layout_cells(columns)
    cell = next((item for item in cells if door_layout_part_key(item) == key), None)
    if cell is None:
        raise ValueError(f"門格 stable_id 不存在於 authoritative topology: {key}")
    total_w = float(dict(snapshot or {}).get("w", sum(width for width, _ in columns)))
    total_h = float(dict(snapshot or {}).get("h", sum(columns[0][1])))
    x_before = sum(columns[index][0] for index in range(cell.column_index))
    y_before = sum(columns[cell.column_index][1][:cell.row_index])
    center_x = -total_w / 2.0 + x_before + cell.start_width / 2.0
    center_y = total_h / 2.0 - y_before - cell.start_height / 2.0
    return "front", (float(center_x), float(center_y), 0.0)


def _phase6_assembly_placement_for_part(snapshot, part_key):
    key = str(part_key or "")
    family = cabinet_family_policy.canonical_family_name(snapshot)
    if key == "base_plate":
        from ae_engine.assembly_placement import resolve_assembly_placement
        placement = resolve_assembly_placement(snapshot, key)
        return placement.placement_kind, tuple(float(v) for v in placement.world_offset)

    receiving_derived = (
        re.fullmatch(r"door_c\d+_r\d+", key) is not None
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
        or key.startswith("box_body:divider:")
        or key.startswith("inner_door:")
    )
    if family == "受電箱" and receiving_derived:
        # T16: Receiving placement is domain-owned. Never consult a stale
        # workspace origin fallback or recreate Door/front offsets here.
        from ae_engine.assembly_placement import resolve_assembly_placement
        placement = resolve_assembly_placement(snapshot, key)
        return placement.placement_kind, tuple(float(v) for v in placement.world_offset)

    if re.fullmatch(r"door_c\d+_r\d+", key):
        return _phase6_door_part_assembly_placement(snapshot, key)
    if key.startswith("box_body:divider:") or (key.startswith("inner_door:") and key.endswith(":bottom_frame")):
        placements = (
            snapshot.get("assembly_placements")
            or (snapshot.get("workspace") or {}).get("assembly_placements")
            or {}
        )
        if key in placements:
            item = placements[key]
            kind = item.get("placement_kind", "offset")
            offset = tuple(float(v) for v in item.get("world_offset", (0.0, 0.0, 0.0)))
            return kind, offset
        try:
            from ae_engine.assembly_placement import resolve_assembly_placement
            placement = resolve_assembly_placement(snapshot, key)
            return placement.placement_kind, tuple(float(v) for v in placement.world_offset)
        except Exception:
            pass
    return _PHASE6_ASSEMBLY_PLACEMENTS.get(key, "offset"), (0.0, 0.0, 0.0)


def _phase6_relief_polygon_coords(geometry):
    if geometry is None or getattr(geometry, "is_empty", True):
        return []
    if getattr(geometry, "geom_type", "") == "Polygon":
        polygons = [geometry]
    else:
        polygons = [
            geom for geom in getattr(geometry, "geoms", ())
            if getattr(geom, "geom_type", "") == "Polygon" and float(geom.area) > 1e-9
        ]
    out = []
    for polygon in polygons:
        coords = list(polygon.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) >= 3:
            out.append([[float(x), float(y)] for x, y in coords])
    return out


def _phase6_assembly_relief_clearance(self):
    var = getattr(self, "assembly_relief_clearance_var", None)
    raw = var.get() if var is not None else "0"
    try:
        value = float(str(raw).strip() or "0")
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, value)


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
    """Apply an already-verified Joint relief to canonical FinalScene without rebuilding PartSpec."""
    from ae_engine.assembly_collision import _scene_with_replaced_primary_cutting
    from ae_engine.manufacturing_api import (
        PartRenderData, material_polygon_from_final_scene, fold_guides_from_final_scene,
        _scene_with_authoritative_fold_profiles,
    )
    material = getattr(part.render_data, "material", None)
    if material is None or getattr(material, "is_empty", True):
        raise ValueError(f"canonical material unavailable: {part.part_key}")
    solved = material.difference(cut_polygon)
    if not solved.is_valid:
        solved = solved.buffer(0)
    if solved.is_empty:
        raise ValueError(f"Joint relief removed all material: {part.part_key}")
    scene = _scene_with_replaced_primary_cutting(part.render_data.scene, solved)
    scene = _scene_with_authoritative_fold_profiles(
        scene, tuple(part.x_profile or ()), tuple(part.y_profile or ())
    )
    render = PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata=dict(getattr(part.render_data, "metadata", {}) or {}),
        unfolded_topology=getattr(part.render_data, "unfolded_topology", None),
    )
    return AssemblyScenePart(
        part_key=part.part_key, render_data=render,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=part.offset,
    )


def _phase6_apply_resolved_cut_to_owner(part, owner_key, cut_polygon):
    """Apply a verified cut to a canonical part or one physical Box Body piece.

    ``owner_key`` may be the canonical part key (``box_body``) or a physical
    piece geometry key such as ``box_body:left_side``.  Mechanical ownership
    remains on the canonical part; this adapter only selects the UV/material
    carrier used by the solver.
    """
    canonical_key = str(part.part_key)
    geometry_key = str(owner_key or canonical_key)
    if geometry_key == canonical_key:
        return _phase6_apply_resolved_cut_to_part(part, cut_polygon)

    prefix = canonical_key + ":"
    if not geometry_key.startswith(prefix):
        raise ValueError(f"geometry owner {geometry_key!r} is not under {canonical_key!r}")
    role = geometry_key[len(prefix):].strip().lower()
    structure = part.render_data
    pieces = tuple(getattr(structure, "pieces", ()) or ())
    if not pieces:
        raise ValueError(f"piece-level geometry unavailable: {geometry_key}")

    from dataclasses import replace
    from ae_engine.manufacturing_api import _exploded_box_body_preview

    replaced = []
    found = False
    for piece in pieces:
        if str(getattr(piece, "role", "") or "").strip().lower() != role:
            replaced.append(piece)
            continue
        found = True
        material = piece.render_data.material
        minx, miny, maxx, maxy = map(float, material.bounds)
        temp_part = AssemblyScenePart(
            part_key=geometry_key,
            render_data=piece.render_data,
            x_profile=tuple(getattr(piece, "fold_profile", ()) or ()),
            y_profile=({"len": max(0.0, maxy - miny), "core": True},),
            placement=part.placement,
            offset=part.offset,
        )
        solved_piece_part = _phase6_apply_resolved_cut_to_part(temp_part, cut_polygon)
        replaced.append(replace(piece, render_data=solved_piece_part.render_data))
    if not found:
        raise ValueError(f"unknown Box Body piece role: {role!r}")

    replaced = tuple(replaced)
    preview = _exploded_box_body_preview(replaced)
    solved_structure = replace(structure, pieces=replaced, preview_render_data=preview)
    return AssemblyScenePart(
        part_key=part.part_key, render_data=solved_structure,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=part.offset,
    )


def _phase6_side_wrap_target_corners(preserve_part_key):
    """Return the two physical target-piece end corners touched by an EndCap side WRAP."""
    key = str(preserve_part_key or "").strip().lower()
    if key == "head":
        return ("top_left", "top_right")
    if key == "tail":
        return ("bottom_left", "bottom_right")
    raise ValueError(f"side WRAP preserve part must be head/tail, got {preserve_part_key!r}")


def _phase6_box_body_piece_solver_key(body_part, region, *, require_flat_uv):
    """Resolve a Box Body Joint region to one physical piece solver key.

    Multi-piece structures may expose an aggregate world solid for preserve-side
    collision checks, but relief/backprojection requires one unambiguous piece UV
    plane.  This adapter deliberately maps only stable physical region names.
    """
    pieces = tuple(getattr(getattr(body_part, "render_data", None), "pieces", ()) or ())
    if not pieces:
        return "box_body"
    by_role = {str(getattr(piece, "role", "") or "").strip().lower(): piece for piece in pieces}
    normalized = str(region or "").strip().lower().replace("-", "_").replace(" ", "_")

    role = None
    if normalized in {"rear_mating", "rear_panel", "back", "back_panel", "rear", "outer_surface", "wrap_zone"}:
        role = "back"
    elif normalized in {"left_mating", "left_mating_zone", "left_side", "left", "top_left", "bottom_left"}:
        role = "left_side"
    elif normalized in {"right_mating", "right_mating_zone", "right_side", "right", "top_right", "bottom_right"}:
        role = "right_side"

    if role is not None and role in by_role:
        return f"box_body:{role}"
    if require_flat_uv:
        raise ValueError(
            f"piece-level relief region is ambiguous for multi-piece Box Body: {region!r}"
        )
    return "box_body"


def _phase6_expand_box_body_fw_world_mid(piece, mapped, world_mid_piece, *, tolerance=1e-7):
    """Expand BoxBody FW physical face about its material segment center.

    Flat/material fold geometry and bend datums remain unchanged. A side-piece
    FW segment may carry an authoritative `formed_length`; only its already
    placed world mid-face triangles are expanded along cabinet W/X about the
    original segment center before sheet-thickness skins are built.
    """
    role = str(getattr(piece, "role", "") or "").strip().lower()
    fw_key = {"left_side": "fw_left", "right_side": "fw_right"}.get(role)
    if fw_key is None:
        return tuple(world_mid_piece or ())

    cursor = 0.0
    band = None
    target = None
    for row in tuple(getattr(piece, "fold_profile", ()) or ()):
        length = float(getattr(row, "length", 0.0) or 0.0)
        end = cursor + length
        if str(getattr(row, "phase6_key", "") or "") == fw_key:
            raw = getattr(row, "formed_length", None)
            if raw is not None:
                target = float(raw)
                band = (float(cursor), float(end))
            break
        cursor = end
    if band is None or target is None or target <= float(tolerance):
        return tuple(world_mid_piece or ())

    selected = []
    for index, item in enumerate(tuple(mapped or ())):
        flat = tuple(getattr(item, "flat", ()) or ())
        if len(flat) != 3:
            continue
        centroid_u = sum(float(point[0]) for point in flat) / 3.0
        if band[0] + float(tolerance) < centroid_u < band[1] - float(tolerance):
            selected.append(index)
    if not selected:
        return tuple(world_mid_piece or ())

    rows = [tuple(tuple(float(v) for v in point) for point in tri) for tri in tuple(world_mid_piece or ())]
    xs = [float(point[0]) for index in selected for point in rows[index]]
    if not xs:
        return tuple(rows)
    lo, hi = min(xs), max(xs)
    span = float(hi - lo)
    if span <= float(tolerance):
        return tuple(rows)
    center = (float(lo) + float(hi)) / 2.0
    scale = float(target) / span
    for index in selected:
        rows[index] = tuple(
            (center + (float(point[0]) - center) * scale, float(point[1]), float(point[2]))
            for point in rows[index]
        )
    return tuple(rows)


def _phase6_shift_multistage_terminal_fold_world_mid(piece, mapped, world_mid_piece, *, tolerance=1e-7):
    """Resolve the straight-face tangent offset of an outer multi-stage fold.

    Flat UV and the sharp-bend material midline remain material-space authority.
    For a side piece where the FW face has two or more non-core folds outside it,
    the outermost terminal straight leg is offset away from its adjacent bend by
    its topology-derived outside/material delta.  This models the real straight
    physical face used by collision without stretching the material segment.

    A single terminal fold outside FW (Receiving right side) is intentionally
    unchanged; its physical collision is already owned by the primary FW/edge
    relationship.
    """
    import math

    role = str(getattr(piece, "role", "") or "").strip().lower()
    fw_key = {"left_side": "fw_left", "right_side": "fw_right"}.get(role)
    if fw_key is None:
        return tuple(world_mid_piece or ())

    segs = list(tuple(getattr(piece, "fold_profile", ()) or ()))
    if not segs:
        return tuple(world_mid_piece or ())

    fw_indices = [
        i for i, row in enumerate(segs)
        if str(getattr(row, "phase6_key", "") or "") == fw_key
    ]
    core_indices = [
        i for i, row in enumerate(segs)
        if bool(getattr(row, "core", None))
    ]
    if len(fw_indices) != 1 or not core_indices:
        return tuple(world_mid_piece or ())
    fw_index = fw_indices[0]
    core_index = min(core_indices, key=lambda i: abs(i - fw_index))

    if core_index > fw_index:
        outward = list(range(0, fw_index))
        terminal_index = 0
        away_sign = -1.0
    else:
        outward = list(range(fw_index + 1, len(segs)))
        terminal_index = len(segs) - 1
        away_sign = 1.0

    # One fold outside FW has no secondary-stage tangent correction. The
    # correction is for the outer terminal leg of a multi-stage front fold.
    if len(outward) < 2 or terminal_index not in outward:
        return tuple(world_mid_piece or ())

    terminal = segs[terminal_index]
    material_len = float(getattr(terminal, "length", 0.0) or 0.0)
    raw_formed = getattr(terminal, "formed_length", None)
    if raw_formed is None:
        return tuple(world_mid_piece or ())
    tangent_offset = float(raw_formed) - material_len
    if tangent_offset <= float(tolerance):
        return tuple(world_mid_piece or ())

    start = sum(float(getattr(row, "length", 0.0) or 0.0) for row in segs[:terminal_index])
    end = start + material_len

    selected = []
    for index, item in enumerate(tuple(mapped or ())):
        flat = tuple(getattr(item, "flat", ()) or ())
        if len(flat) != 3:
            continue
        centroid_u = sum(float(point[0]) for point in flat) / 3.0
        if start - float(tolerance) <= centroid_u <= end + float(tolerance):
            selected.append(index)
    if not selected:
        return tuple(world_mid_piece or ())

    rows = [
        tuple(tuple(float(v) for v in point) for point in tri)
        for tri in tuple(world_mid_piece or ())
    ]
    tangents = []
    mapped_all = tuple(mapped or ())
    for index in selected:
        flat = tuple(getattr(mapped_all[index], "flat", ()) or ())
        world = rows[index]
        for i in range(3):
            for j in range(i + 1, 3):
                du = float(flat[j][0]) - float(flat[i][0])
                dv = float(flat[j][1]) - float(flat[i][1])
                if abs(du) <= float(tolerance) or abs(dv) > abs(du) * 1.0e-4:
                    continue
                vec = tuple((float(world[j][k]) - float(world[i][k])) / du for k in range(3))
                mag = math.sqrt(sum(value * value for value in vec))
                if mag > float(tolerance):
                    tangents.append(tuple(value / mag for value in vec))
    if not tangents:
        return tuple(rows)

    reference = tangents[0]
    aligned = []
    for tangent in tangents:
        dot = sum(tangent[k] * reference[k] for k in range(3))
        aligned.append(tangent if dot >= 0.0 else tuple(-value for value in tangent))
    tangent = tuple(
        sum(row[k] for row in aligned) / len(aligned)
        for k in range(3)
    )
    mag = math.sqrt(sum(value * value for value in tangent))
    if mag <= float(tolerance):
        return tuple(rows)
    tangent = tuple(value / mag for value in tangent)
    delta = tuple(float(away_sign) * float(tangent_offset) * value for value in tangent)

    for index in selected:
        rows[index] = tuple(
            tuple(float(point[k]) + delta[k] for k in range(3))
            for point in rows[index]
        )
    return tuple(rows)


def _phase6_joint_relief_state_item_matches(item, joint, source_material):
    """Return True only when a persisted provisional cut still targets the same raw geometry."""
    if not isinstance(item, dict):
        return False
    relation = str(getattr(getattr(joint, "relation", None), "value", getattr(joint, "relation", "")))
    if (
        str(item.get("joint_id") or "") != str(joint.joint_id)
        or str(item.get("subject_part") or "") != str(joint.subject_part)
        or str(item.get("target_part") or "") != str(joint.target_part)
        or str(item.get("relation") or "") != relation
        or not bool(item.get("verified"))
    ):
        return False
    try:
        saved_bounds = tuple(float(v) for v in item.get("source_material_bounds", ()))
        saved_area = float(item.get("source_material_area"))
        current_bounds = tuple(float(v) for v in source_material.bounds)
        current_area = float(source_material.area)
    except Exception:
        return False
    return len(saved_bounds) == 4 and all(abs(a-b) <= 1e-6 for a,b in zip(saved_bounds,current_bounds)) and abs(saved_area-current_area) <= 1e-6


def _phase6_cut_geometry_from_state_item(item):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polygons = []
    for coords in tuple((item or {}).get("cut_polygons", ()) or ()):
        try:
            polygon = Polygon([(float(x), float(y)) for x, y in coords])
        except Exception:
            continue
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if not polygon.is_empty and float(polygon.area) > 1e-9:
            polygons.append(polygon)
    return unary_union(polygons) if polygons else None


def _phase6_signature_canonical_value(value):
    """Normalize representation-only differences before manufacturing caching."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 12)
    if isinstance(value, Mapping):
        return {str(key): _phase6_signature_canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_phase6_signature_canonical_value(item) for item in value)
    if isinstance(value, set):
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
    """Resolve registry/verification evidence for exactly one AssemblyJoint."""
    edge = str(getattr(joint, "edge", "") or "").upper()
    relation = str(getattr(getattr(joint, "relation", None), "value", getattr(joint, "relation", "")) or "")
    endcap_part = next((p for p in (str(getattr(joint, "subject_part", "")), str(getattr(joint, "target_part", ""))) if p in ENDCAP_FW_PARTS), "")

    if edge == "BOTTOM":
        if relation == "WRAP" and endcap_part:
            render = render_by_part.get(endcap_part)
            trace = dict(dict(getattr(render, "metadata", {}) or {}).get("receiving_bottom_relief_rule") or {})
            if trace:
                evidence = deepcopy(trace.get("geometry_evidence") or {})
                return {
                    "registry_status": "HIT",
                    "rule_id": trace.get("rule_id"),
                    "revision": trace.get("revision"),
                    "trust_level": str(trace.get("trust_level") or ""),
                    "candidate_status": "CERTIFIED",
                    "verified": True,
                    "pre_pair_count": 0,
                    "post_pair_count": 0,
                    "evidence": evidence,
                }
            return {
                "registry_status": "MISS", "rule_id": None, "revision": None,
                "trust_level": "", "candidate_status": "UNSUPPORTED", "verified": False,
                "pre_pair_count": 0, "post_pair_count": 0, "evidence": None,
            }
        # No BOTTOM semantic delta: STANDARD is the canonical mother geometry.
        return {
            "registry_status": "MISS", "rule_id": None, "revision": None,
            "trust_level": "STANDARD", "candidate_status": "STANDARD", "verified": True,
            "pre_pair_count": 0, "post_pair_count": 0, "evidence": {"owner": "STANDARD"},
        }

    solution = solution_by_part.get(endcap_part) if endcap_part else None
    if solution is None:
        return {
            "registry_status": "MISS", "rule_id": None, "revision": None,
            "trust_level": "", "candidate_status": "UNKNOWN", "verified": False,
            "pre_pair_count": 0, "post_pair_count": 0, "evidence": None,
        }
    rule_id = getattr(solution, "rule_id", None)
    pre_pairs = sum(int(getattr(p, "pair_count", 0) or 0) for p in tuple(getattr(solution, "projections", ()) or ()))
    post_pairs = int(getattr(getattr(solution, "residual_projection", None), "pair_count", 0) or 0)
    trust = str(getattr(solution, "trust_level", "") or "")
    return {
        "registry_status": "HIT" if rule_id else "MISS",
        "rule_id": rule_id,
        "revision": getattr(solution, "rule_revision", None),
        "trust_level": trust,
        "candidate_status": "CERTIFIED" if rule_id else trust,
        "verified": bool(getattr(solution, "verified", False)),
        "pre_pair_count": pre_pairs, "post_pair_count": post_pairs,
        "evidence": deepcopy(getattr(solution, "shadow_validation", None)),
    }


def _phase6_build_joint_world_geometry(parts, finished_dimensions, sheet_thickness):
    """Build Joint Solver v2 world/UV maps from canonical AssemblyScenePart objects.

    Multi-piece Box Body structures expose one world-space aggregate for preserve
    checks plus one UV-aware entry per physical piece.  The aggregate intentionally
    has no flat-material map: unrelated piece UV planes must never be forged into a
    single backprojection coordinate system.
    """
    from ae_engine.assembly_geometry import (
        folded_mesh_with_flat_uv_from_polygon,
        world_skin_with_flat_uv, endcap_world_skin_with_flat_uv,
        place_assembly_triangles, place_assembly_points,
        place_box_body_structure_points, MappedSkinTriangle, _triangle_unit_normal,
    )

    by_key = {str(part.part_key): part for part in tuple(parts or ())}
    flat_material_by_part = {}
    mapped_skin_triangles_by_part = {}
    world_triangles_by_part = {}
    body_world_mid = ()

    body = by_key.get("box_body")
    if body is not None:
        body_pieces = tuple(getattr(body.render_data, "pieces", ()) or ())
        if body_pieces:
            total_w = max(float(getattr(piece, "formed_w_end", 0.0)) for piece in body_pieces)
            mapped_rows = []
            structure_mid = []
            piece_counts = []
            for piece in body_pieces:
                data = piece.render_data
                _minx, miny, _maxx, maxy = map(float, data.material.bounds)
                y_profile = ({"len": max(0.0, maxy - miny), "core": True},)
                x_profile = tuple(getattr(piece, "fold_profile", ()) or ())
                mapped = folded_mesh_with_flat_uv_from_polygon(
                    data.material, x_profile, y_profile,
                    fold_guides=tuple(getattr(data, "fold_guides", ()) or ()),
                )
                piece_structure = []
                for item in mapped:
                    placed = place_box_body_structure_points(
                        item.local, piece, total_w=total_w,
                        thickness=sheet_thickness, x_profile=x_profile,
                    )
                    piece_structure.append(tuple(placed))
                mapped_rows.append((piece, tuple(mapped), tuple(piece_structure)))
                structure_mid.extend(piece_structure)
                piece_counts.append(len(piece_structure))

            structure_mid = tuple(structure_mid)
            if structure_mid:
                all_points = [point for tri in structure_mid for point in tri]
                placed_points = place_assembly_points(
                    all_points, structure_mid, body.placement,
                    finished_dimensions, body.offset,
                )
                body_world_mid = tuple(
                    tuple(placed_points[i:i + 3])
                    for i in range(0, len(placed_points), 3)
                )

            half = max(0.0, float(sheet_thickness or 0.0)) / 2.0
            cursor = 0
            aggregate_skins = []
            for piece, mapped, _piece_structure in mapped_rows:
                count = len(mapped)
                world_mid_piece = body_world_mid[cursor:cursor + count]
                cursor += count
                world_mid_piece = _phase6_expand_box_body_fw_world_mid(
                    piece, mapped, world_mid_piece
                )
                world_mid_piece = _phase6_shift_multistage_terminal_fold_world_mid(
                    piece, mapped, world_mid_piece
                )
                skins = []
                for item, world_mid in zip(mapped, world_mid_piece):
                    normal = _triangle_unit_normal(world_mid)
                    if normal is None:
                        continue
                    for side in (-1, 1):
                        delta = tuple(float(side) * half * value for value in normal)
                        world = tuple(
                            tuple(float(point[i]) + delta[i] for i in range(3))
                            for point in world_mid
                        )
                        skins.append(MappedSkinTriangle(flat=item.flat, world=world, side=side))
                piece_key = f"box_body:{str(getattr(piece, 'role', '') or '').strip().lower()}"
                flat_material_by_part[piece_key] = piece.render_data.material
                mapped_skin_triangles_by_part[piece_key] = tuple(skins)
                world_triangles_by_part[piece_key] = tuple(item.world for item in skins)
                aggregate_skins.extend(item.world for item in skins)
            world_triangles_by_part["box_body"] = tuple(aggregate_skins)
        else:
            mapped = folded_mesh_with_flat_uv_from_polygon(
                body.render_data.material, tuple(body.x_profile or ()), tuple(body.y_profile or ()),
                fold_guides=tuple(getattr(body.render_data, "fold_guides", ()) or ()),
            )
            body_world_mid = place_assembly_triangles(
                tuple(item.local for item in mapped), body.placement, finished_dimensions, body.offset
            )
            skins = world_skin_with_flat_uv(
                mapped, body.placement, finished_dimensions, offset=body.offset,
                sheet_thickness=sheet_thickness,
            )
            flat_material_by_part["box_body"] = body.render_data.material
            mapped_skin_triangles_by_part["box_body"] = tuple(skins)
            world_triangles_by_part["box_body"] = tuple(item.world for item in skins)

    for key, part in by_key.items():
        if key == "box_body" or getattr(part.render_data, "pieces", None):
            continue
        mapped = folded_mesh_with_flat_uv_from_polygon(
            part.render_data.material, tuple(part.x_profile or ()), tuple(part.y_profile or ()),
            fold_guides=tuple(getattr(part.render_data, "fold_guides", ()) or ()),
        )
        placement = str(part.placement or "offset")
        if placement in {"top", "head", "bottom", "tail"} and body_world_mid:
            skins = endcap_world_skin_with_flat_uv(
                mapped, placement, body_world_mid, offset=part.offset,
                sheet_thickness=sheet_thickness,
                reference_triangles=tuple(item.local for item in mapped),
                preserve_core_origin=True,
            )
        else:
            skins = world_skin_with_flat_uv(
                mapped, placement, finished_dimensions, offset=part.offset,
                sheet_thickness=sheet_thickness,
            )
        flat_material_by_part[key] = part.render_data.material
        mapped_skin_triangles_by_part[key] = tuple(skins)
        world_triangles_by_part[key] = tuple(item.world for item in skins)

    return {
        "flat_material_by_part": flat_material_by_part,
        "mapped_skin_triangles_by_part": mapped_skin_triangles_by_part,
        "world_triangles_by_part": world_triangles_by_part,
    }


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
    """Delegate Divider physical solve to manufacturing domain."""
    from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
    from ae_engine.contracts import ResolvedJointDiagnostic
    from ae_engine.divider_manufacturing import resolve_divider_final_geometry
    current = {str(part.part_key): part for part in tuple(parts or ())}
    divider_keys = sorted(key for key in current if key.startswith("box_body:divider:"))
    if not divider_keys or "box_body" not in current:
        return tuple(current.values()), (), ()
    diagnostics, family_joints = [], []
    for divider_key in divider_keys:
        divider = current[divider_key]
        joint = AssemblyJoint(
            joint_id=f"{divider_key}:box_body:family-relief", subject_part=divider_key, target_part="box_body",
            subject_region="front_fold_relief", target_region="divider_mating_zone",
            relation=AssemblyJointRelation.INSERT, source=AssemblyJointSource.FAMILY_GEOMETRY,
            solver_constraints={"relief_mode": "FRONT_FOLD_DOMAIN"},
        )
        family_joints.append(joint)
        world = _phase6_build_joint_world_geometry(tuple(current.values()), finished_dimensions, sheet_thickness)
        source_keys = tuple(key for key in ("box_body:left_side", "box_body:right_side") if key in world["world_triangles_by_part"])
        if not source_keys:
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=joint.joint_id, subject_part=divider_key, target_part="box_body", relation=joint.relation.value,
                source=joint.source.value, registry_status="MISS", trust_level="PROVISIONAL_3D",
                preserve_part="box_body", relief_part=divider_key, candidate_status="MISSING_SIDE_PIECE_GEOMETRY",
                legal_contact=False, illegal_penetration=True,
                evidence={"reason": "Receiving Divider relief requires left/right physical Box Body pieces"},
            ))
            continue
        def refold_world(solved_divider):
            return _phase6_build_joint_world_geometry(
                tuple(solved_divider if key == divider_key else part for key, part in current.items()),
                finished_dimensions, sheet_thickness,
            )
        result = resolve_divider_final_geometry(
            divider=divider, box_body=current["box_body"], joint=joint, world=world,
            source_geometry_keys=source_keys, refold_world=refold_world,
            clearance=float(clearance), sheet_thickness=float(sheet_thickness),
        )
        placement = result.placement_evidence.as_dict()
        relief = result.relief_evidence
        evidence = {**dict(relief.source_evidence or {}), "placement": placement}
        if relief.post_evidence is not None:
            evidence["post"] = dict(relief.post_evidence)
        if result.verified:
            current[divider_key] = result.solved_part
        status = str(relief.candidate_status)
        certified_hit = status.startswith("CERTIFIED_REGISTRY_")
        diagnostics.append(ResolvedJointDiagnostic(
            joint_id=joint.joint_id, subject_part=divider_key, target_part="box_body", relation=joint.relation.value,
            source=joint.source.value,
            registry_status=("HIT" if certified_hit else "MISS"),
            trust_level=("CERTIFIED" if certified_hit else "PROVISIONAL_3D"),
            preserve_part="box_body", relief_part=divider_key, candidate_status=status,
            legal_contact=(
                bool(relief.retained_contact_segments)
                if status in {"PROVISIONAL_3D_VERIFIED", "CERTIFIED_REGISTRY_VERIFIED"}
                else status == "NO_FRONT_FOLD_PENETRATION"
            ),
            illegal_penetration=bool(result.illegal_penetration), pre_pair_count=int(relief.pre_pair_count),
            post_pair_count=int(relief.post_pair_count), evidence=evidence,
        ))
    return tuple(current.values()), tuple(diagnostics), tuple(family_joints)

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
    minx, miny, maxx, maxy = material.bounds

    if key == "box_body":
        return x_prof, [{"len": float(maxy - miny)}]
    if key.startswith("box_body:divider:") or (
        key.startswith("inner_door:") and key.endswith("_frame")
    ):
        if x_prof and not y_prof:
            y_prof = [{"len": float(maxy - miny)}]
        elif y_prof and not x_prof:
            x_prof = [{"len": float(maxx - minx)}]
    return x_prof, y_prof
