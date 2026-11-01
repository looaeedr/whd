# -*- coding: utf-8 -*-
"""Canonical Engine-owned manufacturing Relief rule trace and Joint diagnostic projection.

Move-only of the existing Phase6 canonical manufacturing evidence assembly:
the Certified Registry, world solver and original metadata remain authority.
"""
from __future__ import annotations

from copy import deepcopy

from .assembly_collision import joint_relief_ownership
from .assembly_joint import joint_registry_diagnostic_info
from .contracts import ResolvedJointDiagnostic, ResolvedReliefRuleTrace


def resolve_manufacturing_relief_evidence(resolved_parts, solutions, joints):
    """Return (rule_traces, registry_joint_diagnostics) from resolved Engine inputs.

    Explicit USER_ADDED Joint diagnostics are produced by the separate physical
    explicit-joint pipeline, not reclassified as registry-generated evidence.
    """
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
        info = joint_registry_diagnostic_info(
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
    return tuple(traces), tuple(diagnostics)
