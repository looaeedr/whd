# -*- coding: utf-8 -*-
"""Engine-owned CADCraft disposable exchange geometry proof, never manufacturing.

The CLI and GUI retain compatibility aliases; Engine owns exact units, entity
shape and source-prefix checks. Neither raw DXF nor preview is canonical CUTTING.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import ezdxf
from shapely.geometry import Polygon

from .sheetmetal_features import (ResolvedCircle, ResolvedProfile, ResolvedRect, resolve_surface_features)


class CadcraftCommandProofError(ValueError):
    """WHD / CADCraft independent geometry check failed; do not use output."""


@dataclass(frozen=True)
class DrawInstruction:
    kind: str
    points: tuple[tuple[float, float], ...] = ()
    radius: float = 0.0


MAX_ENTITY_COUNT = 100
MAX_COORD = 1_000_000.0
TOLERANCE_MM = 0.00001


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise CadcraftCommandProofError("NON_NUMERIC_COORDINATE")
    f = float(value)
    if not math.isfinite(f) or abs(f) > MAX_COORD:
        raise CadcraftCommandProofError("OUT_OF_RANGE_COORDINATE")
    return f


def _point(point: object) -> tuple[float, float]:
    return (_number(point.x), _number(point.y))


def _ring(points: tuple[tuple[float, float], ...]) -> None:
    if not 3 <= len(points) <= 100:
        raise CadcraftCommandProofError("INVALID_CLOSED_PROFILE_VERTEX_COUNT")
    if len(set(points)) != len(points):
        raise CadcraftCommandProofError("DUPLICATE_OR_ZERO_LENGTH_VERTEX")
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 1e-8:
        raise CadcraftCommandProofError("SELF_INTERSECTING_OR_ZERO_AREA_PROFILE")
    if not polygon.exterior.is_simple:
        raise CadcraftCommandProofError("INVALID_PROFILE_BOUNDARY")


def from_whd_resolved(features: tuple[object, ...]) -> tuple[DrawInstruction, ...]:
    """Only accept already-validated WHD resolved geometry, never raw DXF tags."""
    if not features or len(features) > MAX_ENTITY_COUNT:
        raise CadcraftCommandProofError("INVALID_WHD_FEATURE_COUNT")
    result: list[DrawInstruction] = []
    for feature in features:
        if isinstance(feature, ResolvedCircle):
            radius = _number(feature.radius)
            if radius <= 0:
                raise CadcraftCommandProofError("NON_POSITIVE_RADIUS")
            result.append(DrawInstruction("circle", (_point(feature.center),), radius))
        elif isinstance(feature, ResolvedRect):
            width, height = _number(feature.width), _number(feature.height)
            if width <= 0 or height <= 0:
                raise CadcraftCommandProofError("NON_POSITIVE_RECTANGLE_DIMENSION")
            points = tuple(_point(p) for p in feature.points)
            _ring(points)
            result.append(DrawInstruction("rectangle", points))
        elif isinstance(feature, ResolvedProfile):
            if feature.layered_profiles:
                raise CadcraftCommandProofError("COMPLEX_LAYERED_PROFILE_NOT_SUPPORTED")
            points = tuple(_point(p) for p in feature.points)
            _ring(points)
            result.append(DrawInstruction("profile", points))
        else:
            raise CadcraftCommandProofError("UNSUPPORTED_WHD_FEATURE")
    return tuple(result)



def project_whd_cadcraft_command_instructions(
    *, surface, features, width, height,
) -> tuple[DrawInstruction, ...]:
    """Isolated WHD finished-face holes -> CADCraft commands; not production.

    Both surface resolution and geometry eligibility stay on the Engine side.
    An empty, valid source means CADCraft may draw its first *candidate* hole,
    not that WHD has approved a manufacturing feature.
    """
    if isinstance(width, bool) or isinstance(height, bool):
        raise CadcraftCommandProofError("INVALID_WHD_FINISHED_FACE_DIMENSIONS")
    try:
        w, h = float(width), float(height)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CadcraftCommandProofError("INVALID_WHD_FINISHED_FACE_DIMENSIONS") from exc
    if not all(math.isfinite(value) and value > 0 for value in (w, h)):
        raise CadcraftCommandProofError("INVALID_WHD_FINISHED_FACE_DIMENSIONS")
    originals = tuple(features)
    if len(originals) > MAX_ENTITY_COUNT:
        raise CadcraftCommandProofError("INVALID_WHD_CUTTING_FEATURE_COUNT")
    if any(getattr(feature, "layer", None) != "CUTTING" for feature in originals):
        raise CadcraftCommandProofError("CADCRAFT_TRIAL_SUPPORTS_CUTTING_HOLES_ONLY")
    try:
        resolved = tuple(resolve_surface_features(surface, originals, w, h))
    except (ValueError, TypeError, AttributeError) as exc:
        raise CadcraftCommandProofError("WHD_FEATURE_SURFACE_REJECTED") from exc
    return from_whd_resolved(resolved) if resolved else ()


def save_blank_cadcraft_exchange_drawing(output_dxf, preview_png) -> dict:
    """Create only an empty mm exchange and PNG, exclusively, never overwrite.

    This is a disposable CADCraft editing seed. It contains zero manufacturing
    entities and cannot act as a CUTTING/BEND export or approved source.
    """
    import struct
    import zlib

    target, preview = Path(output_dxf), Path(preview_png)
    if target.suffix.lower() != ".dxf" or preview.suffix.lower() != ".png":
        raise CadcraftCommandProofError("INVALID_CADCRAFT_EXCHANGE_DESTINATION")
    if target == preview or target.exists() or preview.exists():
        raise CadcraftCommandProofError("REFUSE_TO_OVERWRITE_EXISTING_FILE")

    document = ezdxf.new("R2010", units=ezdxf.units.MM)
    created_dxf = False
    created_png = False
    try:
        # 'x' reserves each new path atomically. A previously written drawing
        # or concurrently created user file is never silently replaced.
        try:
            with target.open("xt", encoding="utf-8", newline="") as stream:
                created_dxf = True
                document.write(stream)
        except FileExistsError as exc:
            raise CadcraftCommandProofError("REFUSE_TO_OVERWRITE_EXISTING_FILE") from exc

        def chunk(kind, payload):
            return (struct.pack(">I", len(payload)) + kind + payload
                    + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))

        width_px, height_px = 320, 200
        pixels = (bytes([0]) + bytes([255, 255, 255]) * width_px) * height_px
        image = (
            bytes([137, 80, 78, 71, 13, 10, 26, 10])
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width_px, height_px, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels))
            + chunk(b"IEND", b"")
        )
        try:
            with preview.open("xb") as stream:
                created_png = True
                stream.write(image)
        except FileExistsError as exc:
            raise CadcraftCommandProofError("REFUSE_TO_OVERWRITE_EXISTING_FILE") from exc
    except Exception:
        if created_png:
            preview.unlink(missing_ok=True)
        if created_dxf:
            target.unlink(missing_ok=True)
        raise
    return {"status": "PASS", "scope": "EMPTY_WHD_ISSUED_EXCHANGE"}


def _near(a: object, b: object) -> bool:
    return math.isclose(float(a), float(b), abs_tol=TOLERANCE_MM, rel_tol=0)


def verify_dxf(path: Path, expected: tuple[DrawInstruction, ...]) -> dict:
    if not path.is_file() or not expected:
        raise CadcraftCommandProofError("NO_OUTPUT_OR_NO_EXPECTED_GEOMETRY")
    doc = ezdxf.readfile(path)
    units = doc.header.get("$INSUNITS")
    if units != 4 or doc.header.get("$MEASUREMENT") != 1:
        raise CadcraftCommandProofError("MILLIMETRE_HEADER_MISMATCH")
    entities = list(doc.modelspace())
    if len(entities) != len(expected):
        raise CadcraftCommandProofError("ENTITY_COUNT_MISMATCH")
    observations = []
    for index, (e, item) in enumerate(zip(entities, expected)):
        if e.dxf.layer != "0" or not all(_near(a, b) for a, b in zip(e.dxf.get("extrusion", (0, 0, 1)), (0, 0, 1))):
            raise CadcraftCommandProofError("UNEXPECTED_LAYER_OR_EXTRUSION")
        if item.kind == "circle":
            if e.dxftype() != "CIRCLE":
                raise CadcraftCommandProofError("MISSING_CIRCLE")
            center = e.dxf.center
            if not (_near(center.x, item.points[0][0]) and _near(center.y, item.points[0][1])
                    and _near(center.z, 0) and _near(e.dxf.radius, item.radius)):
                raise CadcraftCommandProofError("CIRCLE_COORDINATE_OR_RADIUS_MISMATCH")
        else:
            if e.dxftype() != "LWPOLYLINE" or not e.closed:
                raise CadcraftCommandProofError("OPEN_OR_WRONG_ENTITY_PROFILE")
            if not _near(e.dxf.get("const_width", 0), 0):
                raise CadcraftCommandProofError("NONZERO_POLYLINE_WIDTH")
            verts = list(e.get_points("xyseb"))
            if len(verts) != len(item.points):
                raise CadcraftCommandProofError("VERTEX_COUNT_MISMATCH")
            for (x, y, sw, ew, bulge), (ex, ey) in zip(verts, item.points):
                if not (_near(x, ex) and _near(y, ey)
                        and _near(sw, 0) and _near(ew, 0) and _near(bulge, 0)):
                    raise CadcraftCommandProofError("POLYGON_COORDINATE_OR_BULGE_MISMATCH")
            if not _near(e.dxf.get("elevation", 0), 0):
                raise CadcraftCommandProofError("UNEXPECTED_ELEVATION")
        observations.append({"index": index, "kind": item.kind, "check": "PASS"})
    return {
        "status": "PASS",
        "scope": "new blank metric CADCraft drawing, isolated CHECK, not WHD manufacturing",
        "units": "millimetre",
        "entity_count": len(entities),
        "geometry": observations,
    }


