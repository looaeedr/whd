# -*- coding: utf-8 -*-
"""Bounded explicit-joint manufacturing relief pipeline.

Phase 7 A6 owns orchestration boundaries only. Mechanical truth remains in the
existing manufacturing/collision helpers injected through ExplicitJointPipelineOps.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable

from ae_engine.assembly_joint import AssemblyJointSource
from ae_engine.assembly_collision import (
    discover_joint_relief_candidate,
    joint_relief_ownership,
    project_joint_interference_to_relief_owner,
    verify_joint_candidate_replay,
)
from ae_engine.contracts import ResolvedJointDiagnostic
from phase6_final_scene_view import AssemblyScenePart


EXPLICIT_JOINT_PIPELINE_STAGES = (
    "normalize_candidate_inventory",
    "decide_owner_registry",
    "query_world_geometry",
    "solve_explicit_joint_candidate",
    "apply_resolved_cut",
    "assemble_diagnostics_evidence",
    "assemble_mutation_result",
)


@dataclass(frozen=True)
class ExplicitJointPipelineOps:
    box_body_piece_solver_key: Callable
    side_wrap_target_corners: Callable
    build_world_geometry: Callable
    state_item_matches: Callable
    cut_geometry_from_state_item: Callable
    apply_cut_to_owner: Callable
    apply_cut_to_part: Callable
    relief_polygon_coords: Callable


@dataclass(frozen=True)
class ExplicitJointPipelineRequest:
    parts: tuple
    joints: tuple
    finished_dimensions: object
    sheet_thickness: float
    clearance: float
    committed_state: object


@dataclass
class ExplicitJointCandidateInventory:
    current: dict
    explicit: tuple
    old_items: dict
    new_state: dict
    diagnostics: list


@dataclass(frozen=True)
class ExplicitJointOwnerDecision:
    joint: object
    relief_key: str
    preserve_key: str
    relief_part: object
    preserve_part: object
    relation: str
    source: str
    edge: str
    is_piece_side_wrap: bool
    registry_status: str = "MISS"


def normalize_candidate_inventory(parts, joints, committed_state):
    """Stage 1: normalize canonical part inventory and USER_ADDED candidates."""
    current = {str(part.part_key): part for part in tuple(parts or ())}
    old_items = (
        dict((committed_state or {}).get("items", {}) or {})
        if isinstance(committed_state, dict)
        else {}
    )
    explicit = tuple(
        joint
        for joint in tuple(joints or ())
        if str(
            getattr(
                getattr(joint, "source", None),
                "value",
                getattr(joint, "source", ""),
            )
        )
        == AssemblyJointSource.USER_ADDED.value
    )
    return ExplicitJointCandidateInventory(
        current=current,
        explicit=explicit,
        old_items=old_items,
        new_state={"schema_version": 1, "items": {}},
        diagnostics=[],
    )


def decide_owner_registry(inventory, joint):
    """Stage 2: preserve the existing owner decision and registry MISS semantics."""
    ownership = joint_relief_ownership(joint)
    relief_key = str(ownership.relief_part)
    preserve_key = str(ownership.preserve_part)
    relief_part = inventory.current.get(relief_key)
    preserve_part = inventory.current.get(preserve_key)
    relation = str(
        getattr(
            getattr(joint, "relation", None),
            "value",
            getattr(joint, "relation", ""),
        )
    )
    source = str(
        getattr(
            getattr(joint, "source", None),
            "value",
            getattr(joint, "source", ""),
        )
    )
    edge = str(getattr(joint, "edge", "") or "").strip().upper()
    return ExplicitJointOwnerDecision(
        joint=joint,
        relief_key=relief_key,
        preserve_key=preserve_key,
        relief_part=relief_part,
        preserve_part=preserve_part,
        relation=relation,
        source=source,
        edge=edge,
        is_piece_side_wrap=(
            relation == "WRAP"
            and relief_key == "box_body"
            and relief_part is not None
            and bool(getattr(relief_part.render_data, "pieces", None))
            and preserve_key in {"head", "tail"}
            and edge in {"LEFT", "RIGHT"}
        ),
    )


def query_world_geometry(parts, finished_dimensions, sheet_thickness, ops):
    """Stage 3: query the single existing world-geometry authority."""
    return ops.build_world_geometry(
        tuple(parts or ()), finished_dimensions, sheet_thickness
    )


def solve_explicit_joint_candidate(
    operation,
    joint,
    world,
    relief_component,
    topology_levels,
    clearance,
    relief_geometry_key=None,
    source_geometry_key=None,
    corner_name_override=None,
    candidate=None,
    rebuild_mapped_skins=None,
):
    """Stage 4: call only the canonical assembly-collision solve APIs."""
    if operation == "discover":
        return discover_joint_relief_candidate(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            topology_levels=topology_levels,
            relief_component=relief_component,
            clearance=float(clearance),
            relief_geometry_key=relief_geometry_key,
            source_geometry_key=source_geometry_key,
            corner_name_override=corner_name_override,
        )
    if operation == "project":
        return project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            relief_geometry_key=relief_geometry_key,
            source_geometry_key=source_geometry_key,
        )
    if operation == "verify":
        return verify_joint_candidate_replay(
            joint,
            candidate,
            world_triangles_by_part=world["world_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            rebuild_mapped_skins=rebuild_mapped_skins,
        )
    raise ValueError(f"unsupported explicit-joint solve operation: {operation!r}")


def apply_resolved_cut(part, cut_polygon, geometry_key, ops):
    """Stage 5: route one verified cut to the existing canonical cut applicator."""
    if geometry_key is None:
        return ops.apply_cut_to_part(part, cut_polygon)
    return ops.apply_cut_to_owner(part, geometry_key, cut_polygon)


def assemble_diagnostics_evidence(diagnostics):
    """Stage 6: freeze the accumulated canonical diagnostics/evidence."""
    return tuple(diagnostics or ())


def assemble_mutation_result(inventory, original_parts, diagnostics):
    """Stage 7: assemble the legacy-compatible result identity."""
    ordered = tuple(
        inventory.current[str(part.part_key)] for part in tuple(original_parts or ())
    )
    return ordered, tuple(diagnostics or ()), inventory.new_state


def _diagnostic(decision, **kwargs):
    joint = decision.joint
    return ResolvedJointDiagnostic(
        joint_id=str(joint.joint_id),
        subject_part=str(joint.subject_part),
        target_part=str(joint.target_part),
        relation=decision.relation,
        source=decision.source,
        registry_status=decision.registry_status,
        preserve_part=decision.preserve_key,
        relief_part=decision.relief_key,
        **kwargs,
    )


def _world_direction_segment(world_map, joint):
    def centroid(part_key):
        tris = tuple((world_map or {}).get(str(part_key), ()) or ())
        points = [
            point
            for tri in tris
            for point in tri
            if isinstance(point, (tuple, list)) and len(point) >= 3
        ]
        if not points:
            return None
        try:
            return tuple(
                sum(float(point[index]) for point in points) / len(points)
                for index in range(3)
            )
        except (TypeError, ValueError):
            return None

    a = centroid(joint.subject_part)
    b = centroid(joint.target_part)
    return (a, b) if a is not None and b is not None else None


def _replay_saved_cut(inventory, decision, raw_material, geometry_key, ops):
    saved = inventory.old_items.get(str(decision.joint.joint_id))
    if geometry_key is not None:
        if str((saved or {}).get("relief_geometry_key") or "") != geometry_key:
            return False
    if not ops.state_item_matches(saved, decision.joint, raw_material):
        return False
    cut = ops.cut_geometry_from_state_item(saved)
    if cut is None or getattr(cut, "is_empty", True):
        return False

    inventory.current[decision.relief_key] = apply_resolved_cut(
        inventory.current[decision.relief_key], cut, geometry_key, ops
    )
    replayed = dict(saved)
    replayed["trust_level"] = "PROVISIONAL_3D"
    inventory.new_state["items"][str(decision.joint.joint_id)] = replayed
    evidence = dict(saved.get("evidence", {}) or {})
    inventory.diagnostics.append(
        _diagnostic(
            decision,
            trust_level="PROVISIONAL_3D",
            candidate_status="PROVISIONAL_3D_REPLAYED",
            legal_contact=True,
            illegal_penetration=False,
            pre_pair_count=int(evidence.get("pre_pair_count", 0) or 0),
            post_pair_count=int(evidence.get("post_pair_count", 0) or 0),
            relief_segments=tuple(),
            evidence={"replayed": True, **evidence},
        )
    )
    return True


def _resolve_piece_side_wrap(request, inventory, decision, ops):
    from shapely.ops import unary_union

    joint = decision.joint
    try:
        relief_region = str(
            getattr(
                joint,
                "target_region"
                if decision.relief_key == str(joint.target_part)
                else "subject_region",
                "",
            )
            or ""
        )
        relief_geometry_key = ops.box_body_piece_solver_key(
            decision.relief_part,
            relief_region or f"{decision.edge.lower()}_mating_zone",
            require_flat_uv=True,
        )
        raw_world = query_world_geometry(
            tuple(inventory.current.values()),
            request.finished_dimensions,
            request.sheet_thickness,
            ops,
        )
        raw_material = raw_world["flat_material_by_part"][relief_geometry_key]
    except Exception as exc:
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status="PIECE_LEVEL_UV_UNAVAILABLE",
                illegal_penetration=True,
                evidence={"reason": str(exc)},
            )
        )
        return

    if _replay_saved_cut(
        inventory, decision, raw_material, relief_geometry_key, ops
    ):
        return

    target_corners = ops.side_wrap_target_corners(decision.preserve_key)
    base_relief_part = inventory.current[decision.relief_key]
    working_world = raw_world
    accumulated_cut_polygons = []
    all_projection_segments = []
    pre_pairs = 0
    post_pairs = 0
    solver_iterations = 0
    proposed_relief = None
    residual = None
    failure_status = None
    failure_reason = ""
    no_initial_penetration = False
    previous_cut_area = 0.0

    while solver_iterations < 32:
        solver_iterations += 1
        working_material = working_world["flat_material_by_part"].get(
            relief_geometry_key
        )
        if working_material is None or getattr(working_material, "is_empty", True):
            failure_status = "PIECE_LEVEL_UV_UNAVAILABLE"
            failure_reason = f"missing working material: {relief_geometry_key}"
            break

        round_candidates = []
        blocked_candidate = None
        try:
            for corner_name in target_corners:
                candidate = solve_explicit_joint_candidate(
                    "discover",
                    joint,
                    working_world,
                    working_material,
                    None,
                    request.clearance,
                    relief_geometry_key=relief_geometry_key,
                    source_geometry_key=decision.preserve_key,
                    corner_name_override=corner_name,
                )
                projection = getattr(candidate, "projection", None)
                flat_projection = getattr(projection, "projection", None)
                pair_count = int(getattr(flat_projection, "pair_count", 0) or 0)
                if solver_iterations == 1:
                    pre_pairs = max(pre_pairs, pair_count)
                all_projection_segments.extend(
                    tuple(getattr(flat_projection, "segments_world", ()) or ())
                )
                status = str(getattr(candidate, "status", "UNKNOWN") or "UNKNOWN")
                if status == "CANDIDATE":
                    round_candidates.append(candidate)
                elif bool(getattr(projection, "illegal_penetration", False)):
                    blocked_candidate = candidate
                    break
        except Exception as exc:
            failure_status = "DISCOVERY_FAILED"
            failure_reason = str(exc)
            break

        if blocked_candidate is not None:
            failure_status = str(
                getattr(blocked_candidate, "status", "UNKNOWN") or "UNKNOWN"
            )
            failure_reason = str(
                dict(getattr(blocked_candidate, "evidence", {}) or {}).get("reason")
                or "ILLEGAL_UNFITTED_REGION"
            )
            break
        if not round_candidates:
            if solver_iterations == 1:
                no_initial_penetration = True
            else:
                failure_status = "REPLAY_FAILED"
                failure_reason = (
                    "RESIDUAL_ILLEGAL_PENETRATION_WITHOUT_NEW_CANDIDATE"
                )
            break

        round_cut_polygons = tuple(
            candidate.cut_polygon_2d
            for candidate in round_candidates
            if getattr(candidate, "cut_polygon_2d", None) is not None
            and not getattr(candidate.cut_polygon_2d, "is_empty", True)
        )
        if not round_cut_polygons:
            failure_status = "FIT_FAILED"
            failure_reason = "CANDIDATE_WITHOUT_CUT"
            break

        accumulated_cut_polygons.extend(round_cut_polygons)
        atomic_cut = unary_union(tuple(accumulated_cut_polygons))
        cut_area = float(getattr(atomic_cut, "area", 0.0) or 0.0)
        if cut_area <= previous_cut_area + 1e-7:
            failure_status = "REPLAY_FAILED"
            failure_reason = "NO_GEOMETRIC_PROGRESS"
            break
        previous_cut_area = cut_area

        try:
            proposed_relief = apply_resolved_cut(
                base_relief_part, atomic_cut, relief_geometry_key, ops
            )
            proposed_parts = tuple(
                proposed_relief if key == decision.relief_key else value
                for key, value in inventory.current.items()
            )
            proposed_world = query_world_geometry(
                proposed_parts,
                request.finished_dimensions,
                request.sheet_thickness,
                ops,
            )
            residual = solve_explicit_joint_candidate(
                "project",
                joint,
                proposed_world,
                None,
                None,
                request.clearance,
                relief_geometry_key=relief_geometry_key,
                source_geometry_key=decision.preserve_key,
            )
        except Exception as exc:
            failure_status = "REPLAY_FAILED"
            failure_reason = str(exc)
            residual = None
            break

        residual_projection = getattr(residual, "projection", None)
        post_pairs = int(getattr(residual_projection, "pair_count", 0) or 0)
        if not bool(getattr(residual, "illegal_penetration", False)):
            break
        working_world = proposed_world
    else:
        failure_status = "REPLAY_FAILED"
        failure_reason = "FIXED_POINT_MAX_ITERATIONS"

    direction_segment = _world_direction_segment(
        raw_world.get("world_triangles_by_part", {}), joint
    )
    if no_initial_penetration:
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status="NO_ILLEGAL_PENETRATION",
                legal_contact=True,
                illegal_penetration=False,
                pre_pair_count=pre_pairs,
                post_pair_count=pre_pairs,
                contact_segments=tuple(all_projection_segments),
                direction_segment=direction_segment,
                evidence={
                    "relief_geometry_key": relief_geometry_key,
                    "corner_names": list(target_corners),
                    "solver_iterations": solver_iterations,
                },
            )
        )
        return

    if (
        failure_status is not None
        or residual is None
        or bool(getattr(residual, "illegal_penetration", False))
    ):
        residual_projection = (
            getattr(residual, "projection", None) if residual is not None else None
        )
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status=str(failure_status or "REPLAY_FAILED"),
                illegal_penetration=True,
                pre_pair_count=pre_pairs,
                post_pair_count=int(
                    getattr(residual_projection, "pair_count", post_pairs or pre_pairs)
                    or 0
                ),
                penetration_segments=tuple(all_projection_segments),
                direction_segment=direction_segment,
                evidence={
                    "reason": failure_reason or "RESIDUAL_ILLEGAL_PENETRATION",
                    "relief_geometry_key": relief_geometry_key,
                    "solver_iterations": solver_iterations,
                },
            )
        )
        return

    inventory.current[decision.relief_key] = proposed_relief
    state_item = {
        "joint_id": str(joint.joint_id),
        "subject_part": str(joint.subject_part),
        "target_part": str(joint.target_part),
        "relation": decision.relation,
        "source": decision.source,
        "relief_part": decision.relief_key,
        "relief_geometry_key": relief_geometry_key,
        "topology_levels": None,
        "verified": True,
        "trust_level": "PROVISIONAL_3D",
        "corner_names": list(target_corners),
        "source_material_bounds": [float(value) for value in raw_material.bounds],
        "source_material_area": float(raw_material.area),
        "cut_polygons": [
            coords
            for polygon in tuple(accumulated_cut_polygons)
            for coords in ops.relief_polygon_coords(polygon)
        ],
        "evidence": {
            "pre_pair_count": pre_pairs,
            "post_pair_count": post_pairs,
            "post_illegal_penetration": False,
            "relief_geometry_key": relief_geometry_key,
            "corner_names": list(target_corners),
            "solver_iterations": solver_iterations,
            "policy": (
                "ATOMIC_MULTI_CORNER_FIXED_POINT_REPLAY_AND_ZERO_"
                "ILLEGAL_PENETRATION"
            ),
        },
    }
    inventory.new_state["items"][str(joint.joint_id)] = state_item
    inventory.diagnostics.append(
        _diagnostic(
            decision,
            trust_level="PROVISIONAL_3D",
            candidate_status="PROVISIONAL_3D",
            legal_contact=bool(getattr(residual, "has_contact", False)),
            illegal_penetration=False,
            pre_pair_count=pre_pairs,
            post_pair_count=post_pairs,
            penetration_segments=tuple(all_projection_segments),
            relief_segments=tuple(all_projection_segments),
            preserve_segments=tuple(all_projection_segments),
            direction_segment=direction_segment,
            evidence=deepcopy(state_item["evidence"]),
        )
    )


def _resolve_generic_joint(request, inventory, decision, ops):
    joint = decision.joint
    if getattr(decision.relief_part.render_data, "pieces", None) or getattr(
        decision.preserve_part.render_data, "pieces", None
    ):
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status="PIECE_LEVEL_UV_UNAVAILABLE",
                evidence={
                    "reason": "MULTI_PIECE_PART_REQUIRES_PIECE_LEVEL_UV_ADAPTER"
                },
            )
        )
        return

    raw_material = decision.relief_part.render_data.material
    if _replay_saved_cut(inventory, decision, raw_material, None, ops):
        return

    constraints = dict(getattr(joint, "solver_constraints", {}) or {})
    try:
        topology_levels = int(constraints.get("topology_levels"))
    except Exception:
        topology_levels = 0
    if topology_levels not in (1, 2):
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status="TOPOLOGY_UNSPECIFIED",
                illegal_penetration=False,
                evidence={
                    "reason": "EXPLICIT_TOPOLOGY_LEVEL_REQUIRED_FOR_DISCOVERY"
                },
            )
        )
        return
    if topology_levels == 2:
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status="TWO_STAGE_COMPONENT_REQUIRED",
                illegal_penetration=False,
                evidence={
                    "reason": "CERTIFIED_TWO_STAGE_TOPOLOGY_COMPONENT_REQUIRED"
                },
            )
        )
        return

    try:
        world = query_world_geometry(
            tuple(inventory.current.values()),
            request.finished_dimensions,
            request.sheet_thickness,
            ops,
        )
        candidate = solve_explicit_joint_candidate(
            "discover",
            joint,
            world,
            raw_material,
            topology_levels,
            request.clearance,
        )
    except Exception as exc:
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status="DISCOVERY_FAILED",
                illegal_penetration=True,
                evidence={"reason": str(exc)},
            )
        )
        return

    projection = getattr(candidate, "projection", None)
    flat_projection = getattr(projection, "projection", None)
    pre_pairs = int(getattr(flat_projection, "pair_count", 0) or 0)
    penetration_segments = tuple(
        getattr(flat_projection, "segments_world", ()) or ()
    )
    direction_segment = _world_direction_segment(
        world.get("world_triangles_by_part", {}), joint
    )
    status = str(getattr(candidate, "status", "UNKNOWN") or "UNKNOWN")
    if status != "CANDIDATE":
        legal = bool(
            getattr(projection, "has_contact", False)
            and not getattr(projection, "illegal_penetration", False)
        )
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status=status,
                legal_contact=legal,
                illegal_penetration=bool(
                    getattr(projection, "illegal_penetration", False)
                ),
                pre_pair_count=pre_pairs,
                post_pair_count=pre_pairs,
                penetration_segments=penetration_segments,
                contact_segments=penetration_segments if legal else (),
                direction_segment=direction_segment,
                evidence=dict(getattr(candidate, "evidence", {}) or {}),
            )
        )
        return

    def rebuild_mapped_skins(part_key, solved_material):
        base = inventory.current[str(part_key)]
        temp_render = SimpleNamespace(
            scene=base.render_data.scene,
            material=solved_material,
            fold_guides=tuple(getattr(base.render_data, "fold_guides", ()) or ()),
            metadata={},
        )
        temp_part = AssemblyScenePart(
            part_key=base.part_key,
            render_data=temp_render,
            x_profile=base.x_profile,
            y_profile=base.y_profile,
            placement=base.placement,
            offset=base.offset,
        )
        temp_parts = tuple(
            temp_part if key == str(part_key) else value
            for key, value in inventory.current.items()
        )
        rebuilt = query_world_geometry(
            temp_parts,
            request.finished_dimensions,
            request.sheet_thickness,
            ops,
        )
        return tuple(
            rebuilt["mapped_skin_triangles_by_part"].get(str(part_key), ()) or ()
        )

    try:
        verification = solve_explicit_joint_candidate(
            "verify",
            joint,
            world,
            raw_material,
            topology_levels,
            request.clearance,
            candidate=candidate,
            rebuild_mapped_skins=rebuild_mapped_skins,
        )
    except Exception as exc:
        verification = None
        verify_error = str(exc)
    else:
        verify_error = ""

    if verification is None or not bool(getattr(verification, "verified", False)):
        residual = (
            getattr(verification, "residual", None)
            if verification is not None
            else None
        )
        residual_projection = getattr(residual, "projection", None)
        inventory.diagnostics.append(
            _diagnostic(
                decision,
                candidate_status="REPLAY_FAILED",
                illegal_penetration=True,
                pre_pair_count=pre_pairs,
                post_pair_count=int(
                    getattr(residual_projection, "pair_count", pre_pairs) or 0
                ),
                penetration_segments=penetration_segments,
                direction_segment=direction_segment,
                evidence={
                    "reason": verify_error or "RESIDUAL_ILLEGAL_PENETRATION"
                },
            )
        )
        return

    cut = candidate.cut_polygon_2d
    inventory.current[decision.relief_key] = apply_resolved_cut(
        inventory.current[decision.relief_key], cut, None, ops
    )
    residual = verification.residual
    residual_projection = getattr(residual, "projection", None)
    post_pairs = int(getattr(residual_projection, "pair_count", 0) or 0)
    measurement = getattr(
        getattr(candidate, "corner_relief", None), "measurement", None
    )
    state_item = {
        "joint_id": str(joint.joint_id),
        "subject_part": str(joint.subject_part),
        "target_part": str(joint.target_part),
        "relation": decision.relation,
        "source": decision.source,
        "relief_part": decision.relief_key,
        "topology_levels": topology_levels,
        "verified": True,
        "trust_level": "PROVISIONAL_3D",
        "corner_name": str(getattr(measurement, "corner_name", "") or ""),
        "source_material_bounds": [float(value) for value in raw_material.bounds],
        "source_material_area": float(raw_material.area),
        "cut_polygons": ops.relief_polygon_coords(cut),
        "evidence": {
            **dict(getattr(candidate, "evidence", {}) or {}),
            **dict(getattr(verification, "evidence", {}) or {}),
        },
    }
    inventory.new_state["items"][str(joint.joint_id)] = state_item
    inventory.diagnostics.append(
        _diagnostic(
            decision,
            trust_level="PROVISIONAL_3D",
            candidate_status="PROVISIONAL_3D",
            legal_contact=bool(getattr(residual, "has_contact", False)),
            illegal_penetration=False,
            pre_pair_count=pre_pairs,
            post_pair_count=post_pairs,
            penetration_segments=penetration_segments,
            relief_segments=penetration_segments,
            preserve_segments=penetration_segments,
            direction_segment=direction_segment,
            evidence=deepcopy(state_item["evidence"]),
        )
    )


def resolve_explicit_joint_reliefs(
    parts,
    joints,
    *,
    finished_dimensions,
    sheet_thickness,
    clearance=0.0,
    committed_state=None,
    ops,
):
    """Resolve USER_ADDED Joint reliefs through the approved seven stages."""
    request = ExplicitJointPipelineRequest(
        parts=tuple(parts or ()),
        joints=tuple(joints or ()),
        finished_dimensions=finished_dimensions,
        sheet_thickness=float(sheet_thickness),
        clearance=float(clearance),
        committed_state=committed_state,
    )
    inventory = normalize_candidate_inventory(
        request.parts, request.joints, request.committed_state
    )
    for joint in inventory.explicit:
        decision = decide_owner_registry(inventory, joint)
        if decision.relief_part is None or decision.preserve_part is None:
            inventory.diagnostics.append(
                _diagnostic(
                    decision,
                    candidate_status="MISSING_PART_GEOMETRY",
                    illegal_penetration=False,
                    evidence={"reason": "JOINT_ENDPOINT_NOT_IN_CANONICAL_PARTS"},
                )
            )
            continue
        if decision.is_piece_side_wrap:
            _resolve_piece_side_wrap(request, inventory, decision, ops)
        else:
            _resolve_generic_joint(request, inventory, decision, ops)

    diagnostics = assemble_diagnostics_evidence(inventory.diagnostics)
    return assemble_mutation_result(inventory, request.parts, diagnostics)
