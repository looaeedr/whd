# -*- coding: utf-8 -*-
"""Engine-owned replay of verified EndCap relief through canonical PartSpec."""
from __future__ import annotations

from dataclasses import replace

from .assembly_collision import serialize_joint_relief_polygons


def replay_resolved_endcap_render(part_input, solution):
    """Replay physical relief cuts through canonical manufacturing render path.

    This relocates the previous Phase6 replay behavior without changing source
    geometry, verification, existing lightweight-test compatibility, or DXF
    manufacturing certification.
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
        return manufacturing_api.build_part_render_data(
            replay_spec, part_input.manufacturing_context,
        )

    # Preserve the existing headless, pre-resolved render compatibility.
    solved = getattr(solution, "solved_render_data", None)
    if solved is None:
        raise ValueError(
            f"authoritative relief replay unavailable: {part_input.part_key}"
        )
    return solved
