# -*- coding: utf-8 -*-
"""Engine-owned EndCap World-relief solver and physical diagnostics boundary."""
from __future__ import annotations

from .relief_commit_policy import endcap_relief_solution_committable


def solve_endcap_assembly_relief(
    body_part, endcap_part, *, finished_dimensions, sheet_thickness,
    clearance, assembly_intent, assembly_graph, cabinet_family,
    allow_3d_fallback,
):
    """Route already-resolved physical parts to the existing Engine solver.

    Duck typing avoids an Engine import of Phase6 AssemblyScenePart / Tk.
    Never derive manufacturing geometry from GUI presentation state.
    """
    from .assembly_collision import solve_world_backprojected_endcap_relief

    return solve_world_backprojected_endcap_relief(
        box_body_render_data=body_part.render_data,
        endcap_render_data=endcap_part.render_data,
        box_body_x_profile=body_part.x_profile,
        endcap_x_profile=endcap_part.x_profile,
        endcap_y_profile=endcap_part.y_profile,
        finished_dimensions=finished_dimensions,
        endcap_placement=endcap_part.placement,
        sheet_thickness=sheet_thickness,
        clearance=clearance,
        assembly_intent=assembly_intent,
        assembly_graph=assembly_graph,
        endcap_part=endcap_part.part_key,
        cabinet_family=cabinet_family,
        allow_3d_fallback=allow_3d_fallback,
        assembly_joint=None,
    )


def endcap_relief_solution_diagnostic(solution) -> str | None:
    """Keep the previous verified, certified and unverified error semantics."""
    if bool(getattr(solution, "verified", False)):
        return None
    if endcap_relief_solution_committable(solution):
        return "已認證公式與立體影子驗證衝突；正式結果仍採已認證公式"
    reason = dict(getattr(solution, "shadow_validation", {}) or {}).get("reason")
    return str(reason or "3D 回折驗證仍有材料穿透")
