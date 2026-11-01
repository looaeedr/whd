# -*- coding: utf-8 -*-
"""Legacy operator Door blank dimension readback; not a manufacturing release.

Keep the baseline/standalone display precedence inside the public Engine.
Real Door manufacturing remains owned by typed DoorPartSpec/FinalScene policy.
"""
from __future__ import annotations

from collections.abc import Mapping

from . import ae


def project_operator_door_blank_dimensions(
    values: Mapping[str, object],
    *,
    material_frame_width: float,
    baseline_model: str = "",
    selected_cell_size: tuple[float, float] | None = None,
    frame_edges=None,
) -> tuple[float, float]:
    """Mirror the approved main-window Door summary without GUI formulas.

    For selected multi-Door cells, use the exact live cell starting size/edges
    and the canonical AE blank calculator. For single Doors, preserve existing
    baseline-first display and its legacy formula fallback; fallback is never
    a verified source for manufacturing/export or a new DXF capability.
    """
    v = values
    if selected_cell_size is not None:
        if (not isinstance(selected_cell_size, (list, tuple))
                or len(selected_cell_size) != 2):
            raise ValueError("DOOR_CELL_OPERATOR_SIZE_INVALID")
        w, h = selected_cell_size
    else:
        w, h = v["w"], v["h"]
    params = (
        w, h, v["t"], material_frame_width,
        v["door_gap_w"], v["door_gap_h"],
        v["door_fold_l"], v["door_fold_r"],
        v["door_fold_t"], v["door_fold_b"],
    )
    if selected_cell_size is not None:
        return ae.calculate_door_blank_size(*params, frame_edges=frame_edges)
    if baseline_model:
        try:
            resolved = ae.get_stretched_door_data(baseline_model, *params)
            return resolved.params["total_width"], resolved.params["total_depth"]
        except Exception:
            # Historical display-only fallback, not source certification.
            pass
    return ae.calculate_door_blank_size(*params)
