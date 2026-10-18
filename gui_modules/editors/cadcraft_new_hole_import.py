"""#1959: strict conversion of newly drawn CADCraft isolated DXF holes to WHD.

Only use after the WHD-issued exchange provenance has been checked. Every
admitted entity is a new CUTTING Feature in WHD finished-face millimetres.
Neither a CADCraft layer nor a DXF file can acquire manufacturing authority.
"""
from __future__ import annotations

from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor, Vec2,
)
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, _near, _number, _ring,
)

_EXCHANGE_LAYER = "0"
_MAX_VERTEX_COUNT = 100


def new_hole_from_cadcraft_entity(entity):
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

    if len(points) == 4 and _is_axis_aligned_rectangle(points):
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


def _is_axis_aligned_rectangle(points) -> bool:
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
