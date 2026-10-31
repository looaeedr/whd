# -*- coding: utf-8 -*-
"""Engine-owned physical material -> assembly mesh Fold profile normalization.

This is a move of the pre-existing Phase6 request-time policy. It introduces
no new 2D/DXF manufacturing authority or formula and has no GUI/Tk imports.
"""
from __future__ import annotations

def resolve_material_mesh_profiles(part_input, material):
    """Resolve immutable request profiles for physical single-material assembly meshes.

    Only canonical whole-body and one-axis physical frame/divider branches
    may derive the missing flat span from already-resolved material bounds.
    Preserve lazy bounds checks so unrelated valid parts are not blocked.
    """
    key = str(part_input.part_key or "")
    x_prof = [dict(seg) for seg in tuple(part_input.x_profile or ())]
    y_prof = [dict(seg) for seg in tuple(part_input.y_profile or ())]

    def material_span(axis):
        # Only the whole Box Body and a one-axis frame/divider need this
        # geometric fallback. Other physical pieces already own both fold
        # profiles; inspecting unrelated bounds could abort valid assembly.
        from math import isfinite
        try:
            raw = tuple(material.bounds)
            if len(raw) != 4 or any(isinstance(v, bool) for v in raw):
                raise ValueError("material bounds must have four real values")
            minx, miny, maxx, maxy = (float(value) for value in raw)
            if not all(isfinite(value) for value in (minx, miny, maxx, maxy)):
                raise ValueError("material bounds must be finite")
            span = (maxx - minx) if axis == "x" else (maxy - miny)
            if not isfinite(span) or span <= 0.0:
                raise ValueError("derived material span must be positive")
            return span
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("physical material bounds unavailable for mesh profile") from exc

    if key == "box_body":
        return x_prof, [{"len": material_span("y")}]
    if key.startswith("box_body:divider:") or (
        key.startswith("inner_door:") and key.endswith("_frame")
    ):
        if x_prof and not y_prof:
            y_prof = [{"len": material_span("y")}]
        elif y_prof and not x_prof:
            x_prof = [{"len": material_span("x")}]
    return x_prof, y_prof
