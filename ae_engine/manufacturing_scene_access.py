"""Single domain-neutral manufacturing FinalScene render-data access owner.

Both Joint Placement and Receiving pairing use this immutable scene seam.
No machining policy, tolerance, contact logic, or world-to-flat projection lives
here.  Composite pieces remain keyed by ``box_body:<role>``.
"""
from __future__ import annotations

from dataclasses import replace

from .contracts import ResolvedManufacturingGeometry
from .manufacturing_render_data import build_exploded_box_body_preview


def owner_render_data(geometry: ResolvedManufacturingGeometry, owner_key: str):
    """Read direct-part or Box Body piece render data; absent keys return None."""
    key = str(owner_key)
    parts = {str(part.part_key): part for part in tuple(geometry.parts or ())}
    direct = parts.get(key)
    if direct is not None:
        return direct.render_data
    if key.startswith("box_body:"):
        body = parts.get("box_body")
        if body is not None:
            role = key.split(":", 1)[1].strip().lower()
            for piece in tuple(getattr(body.render_data, "pieces", ()) or ()):
                if str(getattr(piece, "role", "") or "").strip().lower() == role:
                    return piece.render_data
    return None


def replace_owner_render_data(
    geometry: ResolvedManufacturingGeometry, owner_key: str, render_data,
) -> ResolvedManufacturingGeometry:
    """Return a new scene with only the named manufacturing owner replaced.

    Preserve geometry diagnostics, part order, piece order, Box Body canonical
    strip, and all policy metadata; rederive the composite exploded preview.
    """
    key = str(owner_key)
    parts = tuple(geometry.parts or ())
    if any(str(part.part_key) == key for part in parts):
        return replace(
            geometry,
            parts=tuple(
                replace(part, render_data=render_data)
                if str(part.part_key) == key else part
                for part in parts
            ),
        )
    if not key.startswith("box_body:"):
        raise KeyError(key)
    body = next((part for part in parts if str(part.part_key) == "box_body"), None)
    if body is None:
        raise KeyError(key)
    role = key.split(":", 1)[1].strip().lower()
    pieces = []
    found = False
    for piece in tuple(getattr(body.render_data, "pieces", ()) or ()):
        if str(getattr(piece, "role", "") or "").strip().lower() == role:
            pieces.append(replace(piece, render_data=render_data))
            found = True
        else:
            pieces.append(piece)
    if not found:
        raise KeyError(key)
    pieces = tuple(pieces)
    structure = replace(
        body.render_data,
        pieces=pieces,
        preview_render_data=build_exploded_box_body_preview(pieces),
    )
    return replace(
        geometry,
        parts=tuple(
            replace(part, render_data=structure)
            if str(part.part_key) == "box_body" else part
            for part in parts
        ),
    )
