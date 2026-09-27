"""Bounded generic planar collision and relief backprojection primitives."""
from __future__ import annotations


def detect_planar_collision(
    *,
    box_body_material,
    endcap_material,
    collision_region_factory,
    source_role,
    target_role,
):
    overlap = box_body_material.intersection(endcap_material)
    if overlap.is_empty or float(overlap.area) <= 1e-9:
        return None
    return collision_region_factory(
        region=overlap,
        source_role=source_role,
        target_role=target_role,
    )


def project_collision_to_endcap_relief(
    collision,
    policy,
    *,
    endcap_role,
    cut_action,
    relief_candidate_factory,
    clearance: float = 0.0,
    min_area: float = 1e-6,
):
    if collision is None:
        return None
    if collision.target_role is not endcap_role:
        return None
    if policy.endcap is not cut_action:
        return None

    source_area = float(collision.region.area)
    if source_area <= min_area:
        return None

    cut_polygon = collision.region
    if clearance > 0.0:
        cut_polygon = cut_polygon.buffer(float(clearance))
    if cut_polygon.is_empty:
        return None

    return relief_candidate_factory(
        cut_polygon_2d=cut_polygon,
        clearance=float(clearance),
        source_collision_area=source_area,
    )
