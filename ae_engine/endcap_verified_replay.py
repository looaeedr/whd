# -*- coding: utf-8 -*-
"""Engine-owned replay of verified EndCap relief through canonical PartSpec."""
from __future__ import annotations

from dataclasses import replace

from .assembly_collision import serialize_joint_relief_polygons


def replay_resolved_endcap_render(part_input, solution):
    """Replay authoritative EndCap cuts and verify 2D/3D material equivalence.

    Reuse the existing certified solver polygon and canonical PartSpec render;
    never use the private 3D shadow as manufacturing material. Match the
    historical Phase6 physical-difference tolerance without a second policy.
    """
    cuts = tuple(
        tuple((float(x), float(y)) for x, y in polygon)
        for polygon in serialize_joint_relief_polygons(
            getattr(solution, "cut_polygon_2d", None)
        )
    )
    if part_input.part_spec is not None:
        from . import manufacturing_api
        replay_spec = replace(
            part_input.part_spec,
            resolved_assembly_relief_cuts=cuts,
        )
        canonical_render = manufacturing_api.build_part_render_data(
            replay_spec, part_input.manufacturing_context,
        )
    else:
        # Preserve existing lightweight/headless replay compatibility only
        # where the solver actually supplies the previously resolved render.
        canonical_render = getattr(solution, "solved_render_data", None)

    part_key = part_input.part_key
    canonical_material = getattr(canonical_render, "material", None)
    if canonical_render is None or canonical_material is None:
        raise ValueError(
            f"authoritative relief replay unavailable: {part_key}"
        )
    solver_material = getattr(
        getattr(solution, "solved_render_data", None), "material", None,
    )
    if solver_material is not None:
        mismatch = float(
            canonical_material.symmetric_difference(solver_material).area
        )
        if mismatch > 1e-5:
            raise ValueError(
                f"2D/3D relief replay mismatch: {part_key} area={mismatch:.6f}"
            )
    return canonical_render
