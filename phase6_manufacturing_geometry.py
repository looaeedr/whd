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
                    piece, mapped, world_mid_piece,
                    sheet_thickness=sheet_thickness,
                )
                world_mid_piece = _phase6_shift_multistage_terminal_fold_world_mid(
                    piece, mapped, world_mid_piece
                )
                world_mid_piece = _phase6_fit_receiving_left_zl1_outside_world_mid(
                    piece, mapped, world_mid_piece, sheet_thickness=sheet_thickness,
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
