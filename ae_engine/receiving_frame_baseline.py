# -*- coding: utf-8 -*-
"""Separate Receiving 框.dxf source roles A/B/C/D, without drawing labels.

A = left frame, B = right frame, C = shared divider (not an inner-door
frame), D = top frame. The file contains four independent sample parts.
Keep sample widths and local cut reliefs; parameterize the longitudinal
span from the actual resolved part rather than freezing sample H=1098/696.
"""
from __future__ import annotations

from hashlib import sha256
import math
from pathlib import Path

from ezdxf import bbox

from .baseline_source import BASELINE_SOURCE_VERIFIED, load_baseline_dxf_source_with_status
from .sheetmetal_geometry import Vec2


SOURCE_ROLES = {
    "left": ("A", (90.0, 1098.0), (0.0, 0.0), False),
    "right": ("B", (110.0, 1098.0), (250.0, 0.0), False),
    "divider": ("C", (158.0, 796.0), (550.0, 650.0), True),
    "top": ("D", (90.0, 696.0), (550.0, 150.0), True),
}
TOL = 0.04


def frame_source_file() -> Path:
    return Path(__file__).resolve().parent.parent / "基準檔" / "受電箱" / "框.dxf"


def _reference_record(msp, *, role):
    tag, (width, length), (origin_x, origin_y), rotate = SOURCE_ROLES[role]
    # The source uses a horizontal orientation for C/D and a vertical
    # orientation for A/B. Only closed green CUTTING material contours qualify.
    candidates = []
    for entity in msp.query("LWPOLYLINE"):
        if str(entity.dxf.layer).upper() != "CUTTING" or not entity.closed:
            continue
        size = bbox.extents([entity])
        if not size.has_data:
            continue
        sx, sy = float(size.size.x), float(size.size.y)
        x0, y0 = float(size.extmin.x), float(size.extmin.y)
        ew, eh = ((length, width) if rotate else (width, length))
        if (abs(sx-ew) < TOL and abs(sy-eh) < TOL
                and abs(x0-origin_x) < TOL and abs(y0-origin_y) < TOL):
            candidates.append(entity)
    if len(candidates) != 1:
        raise ValueError(f"RECEIVING_FRAME_SOURCE_{tag}_OUTLINE_NOT_UNIQUE")
    return tag, (width, length), (origin_x, origin_y), rotate, candidates[0]


def _y_by_edge(local_y: float, sample_span: float, target_span: float) -> float:
    # Preserve each original end notch/hole distance to the same physical
    # edge; sample part dimensions are not a fixed manufacturing span.
    if local_y < sample_span/2:
        return local_y
    return target_span - (sample_span-local_y)


def receiving_frame_source(role: str, *, material_width: float, span: float,
                           source_path: Path | None = None):
    if role not in ("left", "right", "top"):
        raise ValueError("RECEIVING_FRAME_SOURCE_IS_NOT_AN_INNER_FRAME")
    # Physical requested dimensions must be valid before opening DXF source.
    if (isinstance(material_width, bool) or isinstance(span, bool)):
        raise ValueError("RECEIVING_FRAME_SOURCE_DIMENSIONS_INVALID")
    try:
        width, target_span = float(material_width), float(span)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("RECEIVING_FRAME_SOURCE_DIMENSIONS_INVALID") from exc
    if not math.isfinite(width) or not math.isfinite(target_span) or width <= 0 or target_span <= 0:
        raise ValueError("RECEIVING_FRAME_SOURCE_DIMENSIONS_INVALID")
    path = Path(source_path or frame_source_file())
    if not path.is_file():
        raise FileNotFoundError(f"受電箱框專用基準檔不存在：{path}")
    doc, status = load_baseline_dxf_source_with_status(path, allow_unverified_source=False)
    if status != BASELINE_SOURCE_VERIFIED:
        raise ValueError("RECEIVING_FRAME_SOURCE_UNVERIFIED")
    msp = doc.modelspace()
    tag, (sample_width, sample_span), (x0, y0), rotate, outline = _reference_record(msp, role=role)
    width, span = width, target_span
    if abs(width-sample_width) > TOL:
        raise ValueError(f"RECEIVING_FRAME_SOURCE_{tag}_WIDTH_MISMATCH")
    if span <= 110.0:
        raise ValueError(f"RECEIVING_FRAME_SOURCE_{tag}_SPAN_TOO_SHORT")

    def point(source_x, source_y):
        if rotate:
            local_x, local_y = float(source_y)-y0, float(source_x)-x0
        else:
            local_x, local_y = float(source_x)-x0, float(source_y)-y0
        return Vec2(local_x, _y_by_edge(local_y, sample_span, span))

    vertices = tuple(point(row[0], row[1]) for row in outline.get_points())
    if not vertices:
        raise ValueError(f"RECEIVING_FRAME_SOURCE_{tag}_EMPTY")
    contour = vertices + (vertices[0],)
    from .sheetmetal_drawing import CirclePrimitive
    holes = []
    for entity in msp.query("CIRCLE"):
        if str(entity.dxf.layer).upper() != "CUTTING":
            continue
        c = entity.dxf.center
        # Keep only this part's source holes, not the independent C divider.
        if not (x0-TOL <= c.x <= x0 + (sample_span if rotate else sample_width) + TOL
                and y0-TOL <= c.y <= y0 + (sample_width if rotate else sample_span) + TOL):
            continue
        target = point(c.x, c.y)
        radius = float(entity.dxf.radius)
        if target.x-radius < -TOL or target.x+radius > width+TOL or target.y-radius < -TOL or target.y+radius > span+TOL:
            raise ValueError(f"RECEIVING_FRAME_SOURCE_{tag}_HOLE_OUTSIDE_BLANK")
        holes.append(CirclePrimitive(target, radius, "CUTTING", color=7,
                        source_type="receiving_frame_baseline", source_id=f"{tag}:{entity.dxf.handle}"))
    if role in ("left", "right") and holes:
        raise ValueError("RECEIVING_FRAME_SIDE_UNEXPECTED_HOLES")
    if role == "top" and len(holes) != 2:
        raise ValueError("RECEIVING_FRAME_TOP_SOURCE_TWO_HOLES_REQUIRED")
    metadata = {
        "receiving_frame_source_path": str(path),
        "receiving_frame_source_tag": tag,
        "receiving_frame_source_sha256": sha256(path.read_bytes()).hexdigest(),
        "receiving_frame_source_reference_width": sample_width,
        "receiving_frame_source_reference_span": sample_span,
        "receiving_frame_source_holes": len(holes),
    }
    return contour, tuple(holes), metadata


def certified_source_catalog(source_path: Path | None = None):
    """Audit A/B/C/D as separate source parts, including C divider identity."""
    path = Path(source_path or frame_source_file())
    doc, status = load_baseline_dxf_source_with_status(path, allow_unverified_source=False)
    if status != BASELINE_SOURCE_VERIFIED:
        raise ValueError("RECEIVING_FRAME_SOURCE_UNVERIFIED")
    msp = doc.modelspace()
    return {tag: {
        "role": role,
        "blank_width": width,
        "sample_span": length,
        "source_path": str(path),
    } for role in SOURCE_ROLES
        for tag, (width, length), _origin, _rot, _poly in [_reference_record(msp, role=role)]}
