"""Pure Phase 2 manufacturing orchestration service.

The service consumes one immutable ManufacturingResolveRequest and returns one
immutable ManufacturingResolveResult.  UI/application adaptation, callbacks,
publication, cache lookup, and compatibility mirrors live outside this module.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from ae_engine.assembly_joint import (
    AssemblyJoint,
    ResolvedAssemblyGraph,
    migrate_legacy_snapshot_joints,
)
from ae_engine.contracts import (
    ResolvedJointDiagnostic,
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
    ResolvedReliefRuleTrace,
)
from ae_engine.manufacturing_api import build_part_render_data
from ae_engine.joint_marking_policy import resolve_joint_marking_foundation_status
from ae_engine.receiving_joint_marking import (
    joint_marking_export_summary as _joint_marking_export_summary,
    resolve_joint_marking_production_status,
    resolve_receiving_joint_markings,
)
from phase6_endcap_semantics import assembly_intent_value
from phase6_final_scene_view import AssemblyScenePart
from phase6_fold_profiles import _num
from phase6_manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingDiagnosticsResult,
    ManufacturingEffects,
    ManufacturingMutationResult,
    ManufacturingResolveRequest,
    ManufacturingResolveResult,
    thaw_manufacturing_value,
)
from phase6_manufacturing_geometry import (
    _phase6_assembly_placement_for_part,
    _phase6_joint_registry_diagnostic_info,
    _phase6_relief_polygon_coords,
    _phase6_request_part,
    _phase6_request_profiles_for_material,
    _phase6_resolve_explicit_joint_reliefs,
    _phase6_resolve_family_divider_reliefs,
    _phase6_solution_is_committable,
)


def _cabinet_family(request: ManufacturingResolveRequest) -> str:
    model = str(request.cabinet_model or "").strip()
    try:
        from ae_engine.cabinet_types.registry import resolve_cabinet_type
        return resolve_cabinet_type(model).canonical_name
    except Exception:
        return model or "金庫型"


def _replay_endcap_render(part_input, solution):
    cuts = tuple(
        tuple((float(x), float(y)) for x, y in polygon)
        for polygon in _phase6_relief_polygon_coords(
            getattr(solution, "cut_polygon_2d", None)
        )
    )
    if part_input.part_spec is not None:
        replay_spec = replace(
            part_input.part_spec,
            resolved_assembly_relief_cuts=cuts,
        )
        return build_part_render_data(
            replay_spec,
            part_input.manufacturing_context,
        )

    # Compatibility fallback for lightweight/headless tests that provide only
    # already-resolved domain render data. Production Fold Designer wiring
    # supplies PartSpec + ManufacturingContext before service entry.
    solved = getattr(solution, "solved_render_data", None)
    if solved is None:
        raise ValueError(
            f"authoritative relief replay unavailable: {part_input.part_key}"
        )
    return solved


def resolve(request):
    """Resolve one canonical manufacturing result from immutable domain input."""
    if not isinstance(request, ManufacturingResolveRequest):
        raise TypeError("request must be ManufacturingResolveRequest")

    fallback_enabled = bool(request.allow_3d_fallback)
    available = {str(key) for key in tuple(request.canonical_part_keys or ())}
    snapshot = thaw_manufacturing_value(request.input_snapshot)
    settings = thaw_manufacturing_value(request.settings)
    if not isinstance(snapshot, dict) or not isinstance(settings, dict):
        raise TypeError("manufacturing request snapshot/settings must thaw to mappings")

    snapshot_for_joints = migrate_legacy_snapshot_joints(dict(snapshot))
    joints = tuple(
        raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw)
        for raw in tuple(snapshot_for_joints.get("assembly_joints", ()) or ())
        if str(
            getattr(
                raw,
                "subject_part",
                raw.get("subject_part", "") if isinstance(raw, dict) else "",
            )
        ) in available
        and str(
            getattr(
                raw,
                "target_part",
                raw.get("target_part", "") if isinstance(raw, dict) else "",
            )
        ) in available
    )
    resolved_joint_graph = ResolvedAssemblyGraph(tuple(sorted(available)), joints)

    parts = []
    for part_input in tuple(request.parts or ()):
        key = str(part_input.part_key)
        if key not in available:
            continue
        render_data = part_input.render_data
        if render_data is None:
            raise ValueError(f"manufacturing render data unavailable: {key}")
        if getattr(render_data, "pieces", None):
            x_profile, y_profile = (), ()
        else:
            if (
                getattr(render_data, "scene", None) is None
                or getattr(render_data, "material", None) is None
            ):
                raise TypeError(
                    "manufacturing render input must contain scene + material "
                    "or physical pieces"
                )
            x_profile, y_profile = _phase6_request_profiles_for_material(
                part_input,
                render_data.material,
            )
        placement, offset = _phase6_assembly_placement_for_part(snapshot, key)
        parts.append(
            AssemblyScenePart(
                part_key=key,
                render_data=render_data,
                x_profile=tuple(dict(seg) for seg in x_profile),
                y_profile=tuple(dict(seg) for seg in y_profile),
                placement=placement,
                offset=offset,
            )
        )
    if not parts:
        raise ValueError("no parts available for assembly 3D display")

    pre_solve_probe_parts = tuple(
        part for part in parts if part.part_key in {"head", "tail"}
    )

    solutions = {}
    errors = {}
    publish_live_state = False
    required = [key for key in ("head", "tail") if key in available]
    dims = thaw_manufacturing_value(request.operator_finished_dimensions)
    thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
    clearance = float(request.relief_clearance or 0.0)

    if required:
        body_part = next(
            (part for part in parts if part.part_key == "box_body"),
            None,
        )
        if body_part is not None:
            from ae_engine.assembly_collision import (
                solve_world_backprojected_endcap_relief,
            )

            by_key = {part.part_key: part for part in parts}
            for key in required:
                part = by_key[key]
                try:
                    solution = solve_world_backprojected_endcap_relief(
                        box_body_render_data=body_part.render_data,
                        endcap_render_data=part.render_data,
                        box_body_x_profile=body_part.x_profile,
                        endcap_x_profile=part.x_profile,
                        endcap_y_profile=part.y_profile,
                        finished_dimensions=dims,
                        endcap_placement=part.placement,
                        sheet_thickness=thickness,
                        clearance=clearance,
                        assembly_intent=assembly_intent_value(
                            request.assembly_intent
                        ),
                        assembly_graph=resolved_joint_graph,
                        endcap_part=key,
                        cabinet_family=_cabinet_family(request),
                        allow_3d_fallback=fallback_enabled,
                        assembly_joint=None,
                    )
                    solutions[key] = solution
                    if not bool(getattr(solution, "verified", False)):
                        if _phase6_solution_is_committable(solution):
                            errors[key] = (
                                "已認證公式與立體影子驗證衝突；正式結果仍採已認證公式"
                            )
                        else:
                            reason = dict(
                                getattr(solution, "shadow_validation", {}) or {}
                            ).get("reason")
                            errors[key] = str(
                                reason or "3D 回折驗證仍有材料穿透"
                            )
                except Exception as exc:
                    errors[key] = str(exc)

            atomic_committable = all(
                key in solutions
                and _phase6_solution_is_committable(solutions[key])
                for key in required
            )

            if atomic_committable:
                publish_live_state = True
                solved_parts = []
                for part in parts:
                    if part.part_key not in required:
                        solved_parts.append(part)
                        continue
                    solution = solutions[part.part_key]
                    part_input = _phase6_request_part(
                        request,
                        part.part_key,
                    )
                    canonical_render = _replay_endcap_render(
                        part_input,
                        solution,
                    )
                    if (
                        canonical_render is None
                        or getattr(canonical_render, "material", None) is None
                    ):
                        raise ValueError(
                            "authoritative relief replay unavailable: "
                            f"{part.part_key}"
                        )
                    solver_material = getattr(
                        getattr(solution, "solved_render_data", None),
                        "material",
                        None,
                    )
                    if solver_material is not None:
                        mismatch = float(
                            canonical_render.material.symmetric_difference(
                                solver_material
                            ).area
                        )
                        if mismatch > 1e-5:
                            raise ValueError(
                                "2D/3D relief replay mismatch: "
                                f"{part.part_key} area={mismatch:.6f}"
                            )
                    solved_parts.append(
                        AssemblyScenePart(
                            part_key=part.part_key,
                            render_data=canonical_render,
                            x_profile=part.x_profile,
                            y_profile=part.y_profile,
                            placement=part.placement,
                            offset=part.offset,
                        )
                    )
                parts = solved_parts
            else:
                canonical_parts = []
                for part in parts:
                    if part.part_key not in required:
                        canonical_parts.append(part)
                        continue
                    part_input = _phase6_request_part(
                        request,
                        part.part_key,
                    )
                    canonical_render = (
                        part_input.committed_render_data
                        or part_input.render_data
                    )
                    if canonical_render is None:
                        raise ValueError(
                            "committed manufacturing render unavailable: "
                            f"{part.part_key}"
                        )
                    canonical_parts.append(
                        AssemblyScenePart(
                            part_key=part.part_key,
                            render_data=canonical_render,
                            x_profile=part.x_profile,
                            y_profile=part.y_profile,
                            placement=part.placement,
                            offset=part.offset,
                        )
                    )
                parts = canonical_parts

    divider_joint_diagnostics = ()
    family_divider_joints = ()
    if any(
        str(part.part_key).startswith("box_body:divider:")
        for part in parts
    ):
        (
            parts,
            divider_joint_diagnostics,
            family_divider_joints,
        ) = _phase6_resolve_family_divider_reliefs(
            tuple(parts),
            finished_dimensions=dims,
            sheet_thickness=thickness,
            clearance=clearance,
        )

    explicit_joint_diagnostics = ()
    explicit_joint_state = {"schema_version": 1, "items": {}}
    snapshot_patch = {}
    if any(
        str(
            getattr(
                getattr(joint, "source", None),
                "value",
                getattr(joint, "source", ""),
            )
        )
        == "USER_ADDED"
        for joint in joints
    ):
        (
            parts,
            explicit_joint_diagnostics,
            explicit_joint_state,
        ) = _phase6_resolve_explicit_joint_reliefs(
            tuple(parts),
            joints,
            finished_dimensions=dims,
            sheet_thickness=thickness,
            clearance=clearance,
            committed_state=snapshot.get("joint_relief_state"),
        )
        snapshot_patch["joint_relief_state"] = deepcopy(
            explicit_joint_state
        )

    resolved_parts = tuple(
        ResolvedManufacturingPart(
            part_key=part.part_key,
            render_data=part.render_data,
            x_profile=tuple(
                dict(seg) for seg in tuple(part.x_profile or ())
            ),
            y_profile=tuple(
                dict(seg) for seg in tuple(part.y_profile or ())
            ),
            placement=part.placement,
            offset=tuple(part.offset),
        )
        for part in parts
    )
    traces = []
    solution_by_part = dict(solutions or {})
    for part_key, solution in solution_by_part.items():
        trust = str(getattr(solution, "trust_level", "") or "")
        rule_id = getattr(solution, "rule_id", None)
        revision = getattr(solution, "rule_revision", None)
        for relief in tuple(
            getattr(solution, "corner_reliefs", ()) or ()
        ):
            shadow = dict(
                getattr(solution, "shadow_validation", {}) or {}
            )
            traces.append(
                ResolvedReliefRuleTrace(
                    part_key=str(part_key),
                    corner_name=str(
                        getattr(relief, "corner_name", "") or ""
                    ),
                    rule_id=rule_id,
                    revision=revision,
                    trust_level=trust,
                    signature=str(
                        getattr(relief, "signature", "") or ""
                    ),
                    geometry_inputs=tuple(
                        str(v)
                        for v in shadow.get(
                            "geometry_inputs",
                            (),
                        )
                        or ()
                    ),
                    geometry_evidence=deepcopy(
                        shadow.get("geometry_evidence")
                    ),
                )
            )

    for resolved_part in resolved_parts:
        metadata = dict(
            getattr(resolved_part.render_data, "metadata", {}) or {}
        )
        bottom_trace = dict(
            metadata.get("receiving_bottom_relief_rule") or {}
        )
        if not bottom_trace:
            continue
        evidence = deepcopy(
            bottom_trace.get("geometry_evidence") or {}
        )
        corners = tuple(
            dict(evidence.get("projection_by_corner") or {}).keys()
        ) or ("bottom",)
        for corner_name in corners:
            traces.append(
                ResolvedReliefRuleTrace(
                    part_key=str(resolved_part.part_key),
                    corner_name=str(corner_name),
                    rule_id=bottom_trace.get("rule_id"),
                    revision=bottom_trace.get("revision"),
                    trust_level=str(
                        bottom_trace.get("trust_level") or ""
                    ),
                    signature="BOTTOM:WRAP",
                    geometry_inputs=tuple(
                        str(v)
                        for v in tuple(
                            evidence.get("geometry_inputs", ()) or ()
                        )
                    ),
                    geometry_evidence=evidence,
                )
            )

    from ae_engine.assembly_collision import joint_relief_ownership

    diagnostics = []
    for joint in joints:
        if (
            str(
                getattr(
                    getattr(joint, "source", None),
                    "value",
                    getattr(joint, "source", ""),
                )
            )
            == "USER_ADDED"
        ):
            continue
        ownership = joint_relief_ownership(joint)
        render_by_part = {
            str(part.part_key): part.render_data
            for part in resolved_parts
        }
        info = _phase6_joint_registry_diagnostic_info(
            joint,
            render_by_part,
            solution_by_part,
        )
        diagnostics.append(
            ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id),
                subject_part=str(joint.subject_part),
                target_part=str(joint.target_part),
                relation=str(
                    getattr(joint.relation, "value", joint.relation)
                ),
                source=str(
                    getattr(joint.source, "value", joint.source)
                ),
                registry_status=info["registry_status"],
                rule_id=info["rule_id"],
                revision=info["revision"],
                trust_level=info["trust_level"],
                preserve_part=str(ownership.preserve_part),
                relief_part=str(ownership.relief_part),
                candidate_status=info["candidate_status"],
                legal_contact=bool(
                    info["verified"]
                    and int(info["post_pair_count"]) > 0
                ),
                illegal_penetration=bool(not info["verified"]),
                pre_pair_count=int(info["pre_pair_count"]),
                post_pair_count=int(info["post_pair_count"]),
                evidence=deepcopy(info["evidence"]),
            )
        )
    diagnostics.extend(tuple(divider_joint_diagnostics or ()))
    diagnostics.extend(tuple(explicit_joint_diagnostics or ()))

    resolved = ResolvedManufacturingGeometry(
        parts=resolved_parts,
        joints=tuple(joints) + tuple(family_divider_joints or ()),
        relief_rules=tuple(traces),
        diagnostics=tuple(diagnostics),
    )

    joint_marking_status = resolve_joint_marking_production_status()
    joint_marking_results = ()
    if _cabinet_family(request) == "受電箱":
        marking_resolution = resolve_receiving_joint_markings(
            snapshot,
            resolved,
            dimensions=dims,
            sheet_thickness=thickness,
            cabinet_family="受電箱",
        )
        resolved = marking_resolution.geometry
        joint_marking_status = marking_resolution.status
        joint_marking_results = tuple(marking_resolution.results)

    return ManufacturingResolveResult(
        geometry=resolved,
        diagnostics=ManufacturingDiagnosticsResult(
            relief_errors=errors,
            relief_solutions=solutions,
            joint_diagnostics=tuple(diagnostics),
            rule_traces=tuple(traces),
            interference_probe_parts=tuple(pre_solve_probe_parts),
            joint_marking_foundation=resolve_joint_marking_foundation_status(),
            joint_marking_status=joint_marking_status,
            joint_marking_results=joint_marking_results,
            joint_marking_export_summary=_joint_marking_export_summary(
                joint_marking_results
            ),
        ),
        mutations=ManufacturingMutationResult(
            snapshot_patch=snapshot_patch
        ),
        effects=ManufacturingEffects(
            publish_live_state=publish_live_state,
            force_live_publish=publish_live_state,
            reason=(
                "atomic relief commit"
                if publish_live_state
                else ""
            ),
        ),
        cache=ManufacturingCacheReceipt(
            signature=str(
                request.cache_key_fingerprint
                or request.source_fingerprint
                or ""
            ),
            hit=False,
            stored=True,
        ),
    )


__all__ = ["resolve"]
