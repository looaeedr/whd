"""CADCraft new-hole conversion compatibility: geometry authority is Engine."""
from __future__ import annotations

from ae_engine import manufacturing_api


def new_hole_from_cadcraft_entity(entity):
    return manufacturing_api.cadcraft_new_hole_from_entity(entity)


def _is_axis_aligned_rectangle(points) -> bool:
    return manufacturing_api.cadcraft_is_axis_aligned_rectangle(points)
