# -*- coding: utf-8 -*-
"""Engine-owned material BEND world-line projections for FinalScene.

These read ONLY the canonical DrawingScene/BEND/Fold and resolved BoxBody
pieces, then call the SAME canonical assembly placement utilities used by
collision and 3D solids. The GUI paints results, never derives geometry.
"""
from __future__ import annotations

from .assembly_geometry_folded_mesh import (
    _profile_geometry, _prepare_profile_mapper, place_box_body_structure_points,
)
from .assembly_geometry_primitives import place_assembly_points
from .sheetmetal_drawing import LinePrimitive


def contract_fold_profile_rows(profile):
    """Serialize resolved FoldSegment rows exactly as old FinalScene adapter."""
    rows = []
    for seg in profile or ():
        row = {"len": float(getattr(seg, "length", 0.0))}
        angle = getattr(seg, "angle", None)
        if angle is not None:
            row["angle"] = float(angle)
        core = getattr(seg, "core", None)
        if core:
            row["core"] = str(core)
        key = getattr(seg, "phase6_key", None)
        if key:
            row["phase6_key"] = str(key)
        rows.append(row)
    return rows


def _physical_bend_lines(scene):
    for primitive in getattr(scene, "primitives", ()):
        if isinstance(primitive, LinePrimitive) and str(primitive.layer).upper() == "BEND":
            yield primitive


def _mappers(x_profile, y_profile, fold_guides):
    xp = tuple(x_profile or ())
    yp = tuple(y_profile or ())
    guides = tuple(fold_guides or ())
    return (
        _prepare_profile_mapper(
            xp, axis="x", fold_guides=guides, geometry=_profile_geometry(xp),
        ),
        _prepare_profile_mapper(
            yp, axis="y", fold_guides=guides, geometry=_profile_geometry(yp),
        ),
    )


def _map_point(point, map_x, map_y):
    x, y = float(point.x), float(point.y)
    ux, zx = map_x(x, y)
    uy, zy = map_y(y, x)
    return (ux, uy, zx + zy)


def project_assembly_box_body_bend_segments(
    scene, x_profile, y_profile, fold_guides, local_reference,
    placement, dimensions, offset,
):
    """Return immutable BEND world lines for one resolved Box Body sheet."""
    if not callable(getattr(scene, "primitives", None)) and not tuple(getattr(scene, "primitives", ()) or ()):
        return ()
    bends = tuple(_physical_bend_lines(scene))
    if not bends:
        return ()
    map_x, map_y = _mappers(x_profile, y_profile, fold_guides)
    segments = []
    for primitive in bends:
        local = (
            _map_point(primitive.p1, map_x, map_y),
            _map_point(primitive.p2, map_x, map_y),
        )
        world = place_assembly_points(
            local, local_reference, placement, dimensions, offset,
        )
        if len(world) == 2:
            segments.append((world[0], world[1]))
    return tuple(segments)


def project_box_body_structure_bend_segments(
    render_data, *, thickness, local_reference=None, placement="box_body",
    dimensions=None, offset=(0.0, 0.0, 0.0), visible_piece_keys=None,
):
    """Return physical piece BEND lines in canonical side/back world space.

    Back BEND overlays remain intentionally suppressed only for display.
    The visible set limits strokes, never changes the material or topology.
    """
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if not pieces:
        return ()
    total_w = max(float(getattr(piece, "formed_w_end", 0.0)) for piece in pieces)
    visible_set = None if visible_piece_keys is None else set(visible_piece_keys)
    segments = []
    for piece in pieces:
        role = str(getattr(piece, "role", "") or "").strip()
        if visible_set is not None and f"box_body:{role}" not in visible_set:
            continue
        if role == "back":
            continue
        data = piece.render_data
        bends = tuple(_physical_bend_lines(data.scene))
        if not bends:
            continue
        x_profile = contract_fold_profile_rows(piece.fold_profile)
        minx, miny, maxx, maxy = map(float, data.material.bounds)
        y_profile = [{"len": maxy - miny}]
        fold_guides = tuple(getattr(data, "fold_guides", ()) or ())
        map_x, map_y = _mappers(x_profile, y_profile, fold_guides)
        for primitive in bends:
            local = (
                _map_point(primitive.p1, map_x, map_y),
                _map_point(primitive.p2, map_x, map_y),
            )
            points = place_box_body_structure_points(
                local, piece, total_w=total_w, thickness=thickness,
                x_profile=x_profile,
            )
            if local_reference is not None:
                points = place_assembly_points(
                    points, local_reference, placement, dimensions, offset,
                )
            if len(points) == 2:
                segments.append((points[0], points[1]))
    return tuple(segments)
