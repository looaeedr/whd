# -*- coding: utf-8 -*-
"""#2379: read-only verification of a Worker-trusted original DXF CIRCLE.

The public Worker is disabled. W-06 must supply *trusted* source file custody.
Only direct modelspace CIRCLE and planar zero-width, zero-bulge closed
LWPOLYLINE rectangles or bounded simple polygon profiles in explicit DXF-header
mm/inch sources are supported. No arbitrary curved/INSERT/POLYLINE source
conversion or undefined per-entity source-geometry hash canonicalization.
"""
from __future__ import annotations

import hashlib
import io
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

import ezdxf

from integration_cli.prepare_evidence import PrepareEvidenceError

_HASH = re.compile(r"^[0-9a-f]{64}$")
_MAX_SOURCE_BYTES = 32 * 1024 * 1024
_TOL = 1e-6


def _fail(detail: str) -> None:
    raise PrepareEvidenceError("WHD_SOURCE_UNVERIFIED", detail)


def _finite(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail("original DXF entity contains nonfinite geometry")
    return float(value)


def _source_snapshot(path: Path, expected_sha256: str):
    """Open a bounded immutable byte snapshot, not cached/preview DXF state."""
    if not isinstance(path, Path) or not isinstance(expected_sha256, str) or not _HASH.fullmatch(expected_sha256):
        _fail("missing trusted original DXF path or source SHA-256")
    current = path
    while True:
        if current.is_symlink():
            _fail("source path or ancestor is symlinked")
        if current == current.parent:
            break
        current = current.parent
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= _MAX_SOURCE_BYTES:
                _fail("source is not a supported regular bounded DXF file")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(_MAX_SOURCE_BYTES + 1)
            if len(raw) != info.st_size:
                _fail("source changed during snapshot read")
        finally:
            os.close(descriptor)
    except (OSError, ValueError) as exc:
        _fail("trusted original DXF cannot be opened")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("original DXF bytes differ from prepared source_document_sha256")
    try:
        # Python StringIO's default newline="\\n" preserves CRLF from
        # Windows-authored DXFs. The DXF tag reader expects universal-newline
        # text; otherwise entity HANDLE values can retain a stray CR and fail
        # identity lookup despite the file's correct pinned SHA-256.
        # Normalize newline *only in the in-memory view of the SAME bytes*.
        # Do NOT reopen a mutable customer file or skip the source hash.
        document = ezdxf.read(io.StringIO(raw.decode("utf-8-sig"), newline=None))
    except (UnicodeError, ValueError, ezdxf.DXFError, OSError) as exc:
        raise PrepareEvidenceError("WHD_SOURCE_UNVERIFIED", "original DXF cannot be parsed from its pinned bytes") from exc
    return document


def _finite_dxf_number(value):
    """Normalize only ezdxf-parsed entity numbers (may be NumPy scalar).

    Untrusted wire JSON still uses strict _finite. Reject text, booleans,
    missing numbers and non-finite CAD geometry, never coerce raw JSON here.
    """
    if value is None or isinstance(value, (bool, str, bytes)):
        _fail("invalid original DXF numeric geometry")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        _fail("original DXF entity number cannot be interpreted")
    if not math.isfinite(number):
        _fail("original DXF contains nonfinite geometry")
    return number


def _require_planar_dxf_thickness(entity):
    """A nonzero DXF extrusion thickness is not a planar CUTTING shape."""
    if _finite_dxf_number(entity.dxf.get("thickness", 0.0)) != 0.0:
        _fail("original DXF source has unverified extrusion thickness")


def _verified_rect_from_source(entity, feature, transform):
    """Verify all four *actual* DXF corners before returning a WHD RectFeature.

    Only exact orthogonal, axis-aligned four-corner modelspace polylines
    without bulges are admitted. The preflight already validated quarter-turn
    rotation/mirror flags; this owner checks the original physical geometry.
    """
    from ae_engine.sheetmetal_features import RectFeature, FeatureAnchor, Vec2

    if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
        _fail("source RECT requires a closed original modelspace LWPOLYLINE")
    normal = tuple(_finite(x) for x in entity.dxf.get("extrusion", (0, 0, 1)))
    elevation = _finite(entity.dxf.get("elevation", 0.0))
    if normal != (0.0, 0.0, 1.0) or abs(elevation) > _TOL:
        _fail("source RECT requires the original positive-XY modelspace plane")
    _require_planar_dxf_thickness(entity)
    # A DXF LWPOLYLINE has *two* distinct shape modifiers: segment bulge
    # and stroke width. Both affect the physical contour, so matching only
    # the centreline's four corners would incorrectly certify manufacturing.
    # Read x, y, start_width, end_width, bulge from the actual DXF entity.
    raw = tuple(entity.get_points("xyseb"))
    if len(raw) != 4:
        _fail("source RECT must have exactly four source vertices")
    if entity.dxf.hasattr("const_width") and _finite_dxf_number(entity.dxf.const_width) != 0.0:
        _fail("source RECT has unverified DXF constant-width contour")
    if any(
        value is not None and _finite_dxf_number(value) != 0.0
        for p in raw for value in (p[2], p[3])
    ):
        _fail("source RECT has unverified DXF per-segment width")
    if any(p[4] is not None and _finite_dxf_number(p[4]) != 0.0 for p in raw):
        _fail("source RECT contains unverified DXF arc/bulge geometry")
    scale = _finite(transform.get("source_to_mm_scale"))
    matrix = transform.get("matrix_2x2")
    trans = transform.get("translation_mm")
    if not isinstance(matrix, (list, tuple)) or len(matrix) != 2 or not isinstance(trans, (list, tuple)) or len(trans) != 2:
        _fail("source RECT transform malformed")
    corners = []
    for p in raw:
        x, y = _finite_dxf_number(p[0]) * scale, _finite_dxf_number(p[1]) * scale
        coords = []
        for i in range(2):
            row = matrix[i]
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                _fail("source RECT matrix malformed")
            coords.append(_finite(row[0]) * x + _finite(row[1]) * y + _finite(trans[i]))
        corners.append(tuple(coords))
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    width, height = x1 - x0, y1 - y0
    if width <= _TOL or height <= _TOL:
        _fail("source RECT has no positive-area bounds")
    expected_corners = ((x0,y0),(x1,y0),(x1,y1),(x0,y1))
    # Distinct physical vertices must form the four envelope corners, not
    # merely have matching bbox (bow-tie and slanted shapes must never pass).
    remaining = list(expected_corners)
    for corner in corners:
        found = [v for v in remaining if
                 math.isclose(corner[0], v[0], rel_tol=0, abs_tol=_TOL)
                 and math.isclose(corner[1], v[1], rel_tol=0, abs_tol=_TOL)]
        if len(found) != 1:
            _fail("source RECT is not an orthogonal four-corner rectangle")
        remaining.remove(found[0])
    # Reject bow-tie winding and repeated crossing, even if its vertices
    # happen to be the same four rectangle corners.
    from shapely.geometry import Polygon
    polygon = Polygon(corners)
    if not polygon.is_valid or polygon.area <= 0:
        _fail("source RECT has crossed or degenerate contour")
    center = ((x0 + x1) / 2, (y0 + y1) / 2)
    claim = feature.get("center_mm")
    if not isinstance(claim, (list, tuple)) or len(claim) != 2:
        _fail("source RECT claim missing target center")
    if any(not math.isclose(center[i], _finite(claim[i]), rel_tol=0, abs_tol=_TOL)
           for i in range(2)):
        _fail("source RECT target center differs from the original DXF")
    rotation = feature.get("rotation_deg")
    if type(rotation) is not int or rotation not in (0,90,180,270):
        _fail("source RECT orientation is unsupported")
    claim_width = _finite(feature.get("width_mm"))
    claim_height = _finite(feature.get("height_mm"))
    expected_dims = ((claim_height, claim_width) if rotation in (90,270)
                     else (claim_width, claim_height))
    if not (math.isclose(width, expected_dims[0], rel_tol=0, abs_tol=_TOL)
            and math.isclose(height, expected_dims[1], rel_tol=0, abs_tol=_TOL)):
        _fail("source RECT dimensions differ from the original DXF")
    return RectFeature(
        width=width, height=height, rotation_deg=0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(*center), layer="CUTTING",
    )



def _verified_profile_from_source(entity, feature, transform):
    """Attest a source polygon's complete transformed edge cycle, not its bbox."""
    from shapely.geometry import Polygon
    from ae_engine.sheetmetal_features import ProfileFeature, FeatureAnchor, Vec2

    if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
        _fail("source PROFILE requires a closed direct modelspace LWPOLYLINE")
    normal = tuple(_finite_dxf_number(v) for v in entity.dxf.get("extrusion", (0, 0, 1)))
    elevation = _finite_dxf_number(entity.dxf.get("elevation", 0.0))
    if normal != (0.0, 0.0, 1.0) or abs(elevation) > _TOL:
        _fail("source PROFILE is not in the original positive XY plane")
    _require_planar_dxf_thickness(entity)
    raw = tuple(entity.get_points("xyseb"))
    if not 3 <= len(raw) <= 256:
        _fail("source PROFILE vertex count unsupported")
    if (entity.dxf.hasattr("const_width")
            and _finite_dxf_number(entity.dxf.const_width) != 0.0):
        _fail("source PROFILE contains unverified constant-width contour")
    for p in raw:
        if any(value is not None and _finite_dxf_number(value) != 0.0
               for value in (p[2], p[3], p[4])):
            _fail("source PROFILE contains unverified stroke width or curved segment")

    scale = _finite(transform.get("source_to_mm_scale"))
    matrix = transform.get("matrix_2x2")
    translation = transform.get("translation_mm")
    if (not isinstance(matrix, (list, tuple)) or len(matrix) != 2
            or not isinstance(translation, (list, tuple)) or len(translation) != 2):
        _fail("source PROFILE transform malformed")
    rows = []
    for row in matrix:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            _fail("source PROFILE transform matrix malformed")
        rows.append((_finite(row[0]), _finite(row[1])))
    dx, dy = _finite(translation[0]), _finite(translation[1])
    points = tuple((
        rows[0][0] * _finite_dxf_number(p[0]) * scale
        + rows[0][1] * _finite_dxf_number(p[1]) * scale + dx,
        rows[1][0] * _finite_dxf_number(p[0]) * scale
        + rows[1][1] * _finite_dxf_number(p[1]) * scale + dy,
    ) for p in raw)
    if any(not math.isfinite(v) for point in points for v in point):
        _fail("source PROFILE transformed geometry is nonfinite")
    polygon = Polygon(points)
    if (len(set(points)) != len(points)
            or not polygon.is_valid or polygon.is_empty or polygon.area <= 0):
        _fail("source PROFILE has repeated, crossed or degenerate edges")

    claimed = feature.get("points_mm")
    if (feature.get("closed") is not True
            or not isinstance(claimed, (list, tuple)) or len(claimed) != len(points)):
        _fail("source PROFILE claimed closed contour does not match original")
    wire = []
    for point in claimed:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            _fail("source PROFILE wire vertex malformed")
        wire.append((_finite(point[0]), _finite(point[1])))

    def same_point(a, b):
        return (math.isclose(a[0], b[0], abs_tol=_TOL, rel_tol=0)
                and math.isclose(a[1], b[1], abs_tol=_TOL, rel_tol=0))

    # A closed contour may start at another point or reverse its winding;
    # arbitrary reordering changes physical CUTTING edges and is forbidden.
    n = len(points)
    if not any(
        all(same_point(wire[(start + direction * i) % n], points[i])
            for i in range(n))
        for start in range(n) for direction in (1, -1)
    ):
        _fail("source PROFILE wire point sequence changes original cutting edges")
    return ProfileFeature(
        points=tuple(Vec2(x, y) for x, y in points),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(0, 0), layer="CUTTING",
    )


def verify_trusted_original_dxf_features(
    features: Sequence[Mapping[str, Any]],
    *,
    source_path: Path,
    expected_document_sha256: str,
) -> tuple:
    """Compare wire claims to real modelspace entity handles and transformed geometry.

    Call *after* W-03 authenticated prepare/Frame and Feature-envelope checks.
    Returns WHD-owned Feature values derived from a verified source-byte
    snapshot, never built by blindly trusting wire values. Downstream WHD
    PartSpec retains the finished-face -> unfolded authority. This does NOT
    certify source_geometry_sha256, full PartSpec manufacturing or W-06 custody.
    """
    if not isinstance(features, (list, tuple)):
        _fail("missing source feature inventory")
    if not features:
        return ()
    document = _source_snapshot(source_path, expected_document_sha256)
    # The only supported *manufacturing* mapping uses the real WHD Feature
    # contract. Finished-face -> unfolded translation remains WHD-owned.
    from ae_engine.sheetmetal_features import CircleFeature, Feature, FeatureAnchor, Vec2
    built: list[Feature] = []
    modelspace = {
        str(e.dxf.handle).upper(): e for e in document.modelspace()
        if e.dxf.hasattr("handle")
    }
    used_handles: set[str] = set()
    for feature in features:
        if not isinstance(feature, Mapping) or feature.get("type") not in ("circle", "rect", "profile"):
            _fail("only original DXF CIRCLE or planar closed LWPOLYLINE are verified")
        if feature.get("process") != "THROUGH_CUT":
            _fail("only certified THROUGH_CUT source Feature mapping is supported")
        t = feature.get("source_transform")
        if not isinstance(t, Mapping):
            _fail("source transform evidence missing")
        refs = t.get("source_entity_refs")
        if not isinstance(refs, list) or len(refs) != 1 or not isinstance(refs[0], str):
            _fail("Feature must bind one original DXF entity handle")
        handle = refs[0].upper()
        if handle in used_handles:
            _fail("one original DXF handle cannot be claimed by multiple features")
        used_handles.add(handle)
        entity = modelspace.get(handle)
        kind = feature["type"]
        expected_type = "CIRCLE" if kind == "circle" else "LWPOLYLINE"
        if entity is None or entity.dxftype() != expected_type:
            _fail("source handle does not identify an original supported modelspace entity")
        if t.get("unit_authority") != "DXF-HEADER":
            _fail("source units require explicit DXF header evidence")
        expected_units = 4 if t.get("source_units") == "mm" else 1 if t.get("source_units") == "inch" else None
        if expected_units is None or document.header.get("$INSUNITS") != expected_units:
            _fail("source DXF units disagree with declared source transform")
        if kind == "rect":
            built.append(_verified_rect_from_source(entity, feature, t))
            continue
        if kind == "profile":
            built.append(_verified_profile_from_source(entity, feature, t))
            continue
        center = tuple(_finite(v) for v in entity.dxf.center)
        normal = tuple(_finite(v) for v in entity.dxf.get("extrusion", (0, 0, 1)))
        if len(center) != 3 or len(normal) != 3 or abs(center[2]) > _TOL or any(
            abs(a - b) > _TOL for a, b in zip(normal, (0.0, 0.0, 1.0))
        ):
            _fail("only planar XY modelspace CIRCLE evidence is supported")
        radius = _finite(entity.dxf.radius)
        if radius <= 0:
            _fail("source circle radius must be positive")
        _require_planar_dxf_thickness(entity)

        scale = _finite(t.get("source_to_mm_scale"))
        matrix = t.get("matrix_2x2")
        translation = t.get("translation_mm")
        if (not isinstance(matrix, (list, tuple)) or len(matrix) != 2
                or not isinstance(translation, (list, tuple)) or len(translation) != 2):
            _fail("source transform is malformed")
        transformed = []
        for i in range(2):
            row = matrix[i]
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                _fail("source matrix is malformed")
            transformed.append(
                _finite(row[0]) * center[0] * scale
                + _finite(row[1]) * center[1] * scale + _finite(translation[i])
            )
        claim_center = feature.get("center_mm")
        if not isinstance(claim_center, (list, tuple)) or len(claim_center) != 2:
            _fail("wire circle center is malformed")
        if any(not math.isclose(actual, _finite(claim_center[i]), rel_tol=0, abs_tol=_TOL)
               for i, actual in enumerate(transformed)):
            _fail("wire circle does not match transformed original DXF handle")
        if not math.isclose(radius * scale, _finite(feature.get("radius_mm")),
                            rel_tol=0, abs_tol=_TOL):
            _fail("wire radius differs from actual original DXF source circle")
        built.append(CircleFeature(
            diameter=2.0 * radius * scale,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(transformed[0], transformed[1]),
            layer="CUTTING",
        ))
    return tuple(built)


# Existing callers/tests keep the old name while the strict source-verified
# Feature output expands from CIRCLE to direct LWPOLYLINE RECT/PROFILE.
verify_trusted_original_dxf_circles = verify_trusted_original_dxf_features
