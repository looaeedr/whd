# -*- coding: utf-8 -*-
"""WHD Engine-only validation of CADCraft manual isolated DXF returns.

No Phase6, Tk, GUI, Worker, external manufacturing or CLI authority.
The result is a candidate tuple for the existing reversible hole-editor Session.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import ezdxf
from shapely.geometry import Point, Polygon

from .cadcraft_exchange_proof import (
    CadcraftCommandProofError, from_whd_resolved, verify_dxf,
    _near, _number, _ring,
)
from .sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor, Vec2,
    feature_is_strictly_within_surface, resolve_surface_features,
)


def cadcraft_feature_footprint_polygon(feature, width: float, height: float) -> Polygon:
    """Build finished-face physical footprints, never from DXF render hints."""
    from .sheetmetal_features import feature_finished_point
    from .sheetmetal_feature_core import _rotate_local_point
    center = feature_finished_point(feature, width, height)
    if isinstance(feature, CircleFeature):
        return Point(center.x, center.y).buffer(float(feature.diameter) / 2, quad_segs=64)
    if isinstance(feature, RectFeature):
        half_width, half_height = float(feature.width) / 2, float(feature.height) / 2
        local = (
            type(center)(-half_width, -half_height),
            type(center)(half_width, -half_height),
            type(center)(half_width, half_height),
            type(center)(-half_width, half_height),
        )
        points = [center + _rotate_local_point(p, feature.rotation_deg) for p in local]
    elif isinstance(feature, ProfileFeature) and not feature.layered_profiles:
        points = [center + _rotate_local_point(p, feature.rotation_deg)
                  for p in feature.points]
    else:
        raise CadcraftCommandProofError("UNSUPPORTED_EXISTING_FEATURE_GEOMETRY")
    polygon = Polygon([(p.x, p.y) for p in points])
    if not polygon.is_valid or polygon.area <= 1e-8:
        raise CadcraftCommandProofError("INVALID_WHD_FEATURE_FOOTPRINT")
    return polygon


_EXCHANGE_LAYER = "0"
_MAX_VERTEX_COUNT = 100


def cadcraft_new_hole_from_entity(entity):
    """Convert a single new circle/closed straight contour; fail on all others."""
    if entity.dxf.layer != _EXCHANGE_LAYER:
        raise CadcraftCommandProofError("NEW_HOLE_NOT_ON_EXCHANGE_LAYER")
    extrusion = tuple(entity.dxf.get("extrusion", (0, 0, 1)))
    if len(extrusion) != 3 or not all(
        _near(_number(a), b) for a, b in zip(extrusion, (0, 0, 1))
    ):
        raise CadcraftCommandProofError("NEW_HOLE_WRONG_EXTRUSION")
    if not _near(_number(entity.dxf.get("thickness", 0)), 0):
        raise CadcraftCommandProofError("NEW_HOLE_NONZERO_THICKNESS")

    if entity.dxftype() == "CIRCLE":
        center = entity.dxf.center
        x, y, z, radius = map(
            _number, (center.x, center.y, center.z, entity.dxf.radius)
        )
        if not _near(z, 0) or radius <= 0:
            raise CadcraftCommandProofError("INVALID_NEW_CIRCLE")
        return CircleFeature(
            diameter=2 * radius, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(x, y),
        )

    if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
        raise CadcraftCommandProofError("ENTITY_COUNT_MISMATCH")
    if not _near(_number(entity.dxf.get("const_width", 0)), 0):
        raise CadcraftCommandProofError("NEW_HOLE_POLYLINE_WIDTH")
    if not _near(_number(entity.dxf.get("elevation", 0)), 0):
        raise CadcraftCommandProofError("NEW_HOLE_POLYLINE_ELEVATION")
    vertices = list(entity.get_points("xyseb"))
    if not 3 <= len(vertices) <= _MAX_VERTEX_COUNT:
        raise CadcraftCommandProofError("INVALID_CLOSED_PROFILE_VERTEX_COUNT")
    if any(
        not (_near(_number(sw), 0) and _near(_number(ew), 0)
             and _near(_number(bulge), 0))
        for _, _, sw, ew, bulge in vertices
    ):
        raise CadcraftCommandProofError("NEW_HOLE_BULGE_OR_WIDTH_NOT_SUPPORTED")
    points = tuple((_number(x), _number(y)) for x, y, *_ in vertices)
    _ring(points)

    if len(points) == 4 and cadcraft_is_axis_aligned_rectangle(points):
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        return RectFeature(
            width=max_x - min_x, height=max_y - min_y,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2((max_x + min_x) / 2, (max_y + min_y) / 2),
        )
    # Rotated rectangles are represented as WHD ProfileFeature to preserve
    # arbitrary angles; WHD RectFeature only accepts 90-degree rotations.
    return ProfileFeature(
        points=tuple(Vec2(x, y) for x, y in points),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(0, 0),
    )


def cadcraft_is_axis_aligned_rectangle(points) -> bool:
    # Corner order may start anywhere or be clockwise. For an axis-aligned
    # rectangle all consecutive edges must alternate horizontal/vertical.
    if len(points) != 4:
        return False
    axis = []
    for i, (x, y) in enumerate(points):
        nx, ny = points[(i + 1) % 4]
        dx, dy = nx - x, ny - y
        if _near(dx, 0) and not _near(dy, 0):
            axis.append("v")
        elif _near(dy, 0) and not _near(dx, 0):
            axis.append("h")
        else:
            return False
    return axis in (["h", "v", "h", "v"], ["v", "h", "v", "h"])

def cadcraft_manual_feature_eligible(feature) -> bool:
    # An approved NFB CSV hole or an authored manufacturing source must not be
    # silently de-linked from its governing source by this prototype.
    return (
        isinstance(feature, (CircleFeature, RectFeature, ProfileFeature))
        and feature.layer == "CUTTING"
        and not feature.source_type
        and not feature.source_params
        and not getattr(feature, "layered_profiles", ())
        and not getattr(feature, "add_centerline", False)
    )



def cadcraft_manual_finite_positive(value) -> bool:
    """Preserve the original strict finite finished-face dimension precheck."""
    import math
    return math.isfinite(value) and value > 0


def verify_cadcraft_manual_ticket_seed(path: Path, originals: tuple, surface, width: float, height: float) -> None:
    """Verify original WHD-issued exchange geometry before GUI ticket issuance."""
    expected = (from_whd_resolved(tuple(
        resolve_surface_features(surface, originals, width, height)
    )) if originals else ())
    if expected:
        verify_dxf(path, expected)
    else:
        # An empty face can only issue a truly empty, explicit millimetre DXF.
        try:
            document = ezdxf.readfile(path)
        except (OSError, ValueError, ezdxf.DXFError) as exc:
            raise CadcraftCommandProofError("INVALID_BLANK_EXCHANGE_DXF") from exc
        if (document.header.get("$INSUNITS") != 4
                or document.header.get("$MEASUREMENT") != 1
                or any(document.modelspace())):
            raise CadcraftCommandProofError("INVALID_BLANK_EXCHANGE_DXF")


def project_cadcraft_manual_return_changes(output: Path, original: tuple, surface, width, height):
    """Allow existing-hole translations and strictly append new holes, not deletes/resizes."""
    expected = (from_whd_resolved(tuple(
        resolve_surface_features(surface, original, width, height)
    )) if original else ())
    try:
        doc = ezdxf.readfile(output)
    except (OSError, ValueError, TypeError, ezdxf.DXFError) as exc:
        raise CadcraftCommandProofError("CADCRAFT_DXF_PARSE_FAILED") from exc
    if doc.header.get("$INSUNITS") != 4 or doc.header.get("$MEASUREMENT") != 1:
        raise CadcraftCommandProofError("MILLIMETRE_HEADER_MISMATCH")
    entities = list(doc.modelspace())
    # Source holes must remain the original ordered prefix. Extra circles and
    # contours are the *only* admissible additions, on this isolated drawing.
    if len(entities) < len(original) or len(entities) > 100:
        raise CadcraftCommandProofError("ENTITY_COUNT_MISMATCH")
    moves = []
    updated = []
    for index, (entity, instruction, feature) in enumerate(zip(entities, expected, original)):
        if entity.dxf.layer != "0":
            raise CadcraftCommandProofError("UNEXPECTED_LAYER")
        extrusion = tuple(entity.dxf.get("extrusion", (0, 0, 1)))
        if len(extrusion) != 3 or not all(
            _near(_number(a), b) for a, b in zip(extrusion, (0, 0, 1))
        ):
            raise CadcraftCommandProofError("UNEXPECTED_EXTRUSION")
        if instruction.kind == "circle":
            if entity.dxftype() != "CIRCLE":
                raise CadcraftCommandProofError("CHANGED_ENTITY_TYPE")
            center = entity.dxf.center
            x, y, z, radius = map(_number, (center.x, center.y, center.z, entity.dxf.radius))
            if not _near(z, 0) or not _near(radius, instruction.radius):
                raise CadcraftCommandProofError("CIRCLE_SIZE_OR_PLANE_CHANGED")
            dx, dy = x-instruction.points[0][0], y-instruction.points[0][1]
        else:
            if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
                raise CadcraftCommandProofError("OPEN_OR_CHANGED_PROFILE")
            if not _near(_number(entity.dxf.get("const_width", 0)), 0):
                raise CadcraftCommandProofError("POLYLINE_WIDTH_CHANGED")
            if not _near(_number(entity.dxf.get("elevation", 0)), 0):
                raise CadcraftCommandProofError("POLYLINE_ELEVATION_CHANGED")
            vertices = list(entity.get_points("xyseb"))
            if len(vertices) != len(instruction.points):
                raise CadcraftCommandProofError("VERTEX_COUNT_MISMATCH")
            points = tuple((_number(x), _number(y)) for x, y, *_ in vertices)
            _ring(points)
            dx = points[0][0]-instruction.points[0][0]
            dy = points[0][1]-instruction.points[0][1]
            for (x, y, start, end, bulge), (ex, ey) in zip(vertices, instruction.points):
                if (not all(_near(_number(v), 0) for v in (start, end, bulge))
                        or not _near(_number(x), ex+dx)
                        or not _near(_number(y), ey+dy)):
                    raise CadcraftCommandProofError("SHAPE_OR_ROTATION_CHANGED")
        if abs(dx) > 1_000_000 or abs(dy) > 1_000_000:
            raise CadcraftCommandProofError("OUT_OF_RANGE_TRANSLATION")
        candidate = replace(feature, offset=Vec2(
            _number(feature.offset.x+dx), _number(feature.offset.y+dy)
        ))
        if not feature_is_strictly_within_surface(surface, candidate, width, height):
            raise CadcraftCommandProofError("OUTSIDE_WHD_PHYSICAL_SURFACE")
        updated.append(candidate)
        if not _near(dx, 0) or not _near(dy, 0):
            moves.append((index, dx, dy))
    additions = tuple(cadcraft_new_hole_from_entity(entity)
                      for entity in entities[len(original):])
    for feature in additions:
        if not feature_is_strictly_within_surface(surface, feature, width, height):
            raise CadcraftCommandProofError("OUTSIDE_WHD_PHYSICAL_SURFACE")
    if not moves and not additions:
        raise CadcraftCommandProofError("NO_MANUAL_HOLE_POSITION_CHANGE")
    updated.extend(additions)
    footprints = [cadcraft_feature_footprint_polygon(feature, width, height) for feature in updated]
    for index, footprint in enumerate(footprints):
        for preceding in footprints[:index]:
            if footprint.intersects(preceding):
                raise CadcraftCommandProofError("WHD_FEATURE_COLLISION")
    return tuple(updated), tuple(moves), additions


