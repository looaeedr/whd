# -*- coding: utf-8 -*-
"""Canonical already-resolved physical part projection, owned by Engine.

This is a move of Phase6 manufacturing-service's existing result mapping:
no formulas, Fold solver, inferred physical identity, or DXF generation.
"""
from .contracts import ResolvedManufacturingPart


def materialize_resolved_manufacturing_parts(parts):
    """Materialize the final physical parts in source order without UI policy.

    Detach each Fold-segment mapping exactly as the legacy materialization did.
    Keep the authoritative render/placement identity; the immutable canonical
    geometry contract remains responsible for rejecting duplicate part keys.
    """
    return tuple(
        ResolvedManufacturingPart(
            part_key=part.part_key,
            render_data=part.render_data,
            x_profile=tuple(dict(seg) for seg in tuple(part.x_profile or ())),
            y_profile=tuple(dict(seg) for seg in tuple(part.y_profile or ())),
            placement=part.placement,
            offset=tuple(part.offset),
        )
        for part in parts
    )
