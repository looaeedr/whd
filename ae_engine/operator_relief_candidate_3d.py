"""Engine-only candidate-specific Registry formula and 3D collision shadow check.

Does not mutate Certified Registry, author CUTTING, or certify manufacturing.
"""
from __future__ import annotations

from typing import Mapping

from .assembly_placement import SCENE_ASSEMBLY_PLACEMENTS
from .certified_relief_registry import (
    _validate_editable_rule_record,
    evaluate_editable_endcap_rule_record,
)
from .assembly_collision import solve_world_backprojected_endcap_relief


def validate_operator_relief_registry_candidate_3d(
    record: Mapping[str, object],
    *,
    candidate_id: str,
    assembly_intent: str,
    part_inputs: Mapping[str, tuple],
    finished_dimensions,
    sheet_thickness: float,
    clearance: float,
    box_body_structure_state,
    cabinet_family: str,
) -> dict[str, object]:
    """Return shadow evidence from original physical BoxBody, Head, Tail inputs.

    Each part input has (PartRenderData, X Fold Profile, Y Fold Profile).
    Only the existing canonical Registry evaluator and world collision solver
    decide the candidate geometry. Success never promotes the Registry rule.
    """
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        raise ValueError("candidate-specific 3D validation requires candidate_id")
    raw = _validate_editable_rule_record(record)
    intent = str(raw.get("assembly_intent") or "").strip()
    current_intent = str(assembly_intent or "")
    if current_intent and intent and current_intent != intent:
        raise ValueError(
            f"candidate assembly_intent={intent} does not match current assembly={current_intent}"
        )
    parts = dict(part_inputs or {})
    if set(parts) - {"box_body", "head", "tail"}:
        raise ValueError("candidate validation received unknown physical part")
    if "box_body" not in parts:
        raise ValueError("candidate-specific 3D validation requires box_body")

    def physical(part_key):
        render_data, x_profile, y_profile = parts[part_key]
        if render_data is None or getattr(render_data, "material", None) is None:
            raise ValueError(f"candidate validation render data unavailable: {part_key}")
        return (render_data, tuple(dict(s) for s in x_profile), tuple(dict(s) for s in y_profile))

    body_render, body_x, _ = physical("box_body")
    solutions = {}
    validated_parts = []
    for part_key in ("head", "tail"):
        if part_key not in parts:
            continue
        end_render, end_x, end_y = physical(part_key)
        ephemeral = evaluate_editable_endcap_rule_record(
            raw,
            endcap_render_data=end_render,
            box_body_x_profile=body_x,
            endcap_x_profile=end_x,
            endcap_y_profile=end_y,
            sheet_thickness=sheet_thickness,
            box_body_structure_state=box_body_structure_state,
        )
        if ephemeral is None:
            raise ValueError(f"candidate formula does not apply to {part_key}")
        solution = solve_world_backprojected_endcap_relief(
            box_body_render_data=body_render,
            endcap_render_data=end_render,
            box_body_x_profile=body_x,
            endcap_x_profile=end_x,
            endcap_y_profile=end_y,
            finished_dimensions=finished_dimensions,
            endcap_placement=SCENE_ASSEMBLY_PLACEMENTS.get(
                part_key, "top" if part_key == "head" else "bottom"
            ),
            sheet_thickness=sheet_thickness,
            clearance=clearance,
            assembly_intent=intent,
            cabinet_family=cabinet_family,
            allow_3d_fallback=False,
            certified_result_override=ephemeral,
        )
        validated_parts.append(part_key)
        solutions[part_key] = {
            "verified": bool(getattr(solution, "verified", False)),
            "trust_level": str(getattr(solution, "trust_level", "") or ""),
            "rule_id": getattr(solution, "rule_id", None),
            "rule_revision": getattr(solution, "rule_revision", None),
            "residual_pair_count": int(
                getattr(getattr(solution, "residual_projection", None), "pair_count", 0) or 0
            ),
        }

    zero = bool(validated_parts) and all(row["verified"] for row in solutions.values())
    return {
        "candidate_specific": True,
        "candidate_id": candidate_id,
        "zero_penetration": zero,
        "validated_parts": validated_parts,
        "solutions": solutions,
    }
