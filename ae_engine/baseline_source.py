# -*- coding: utf-8 -*-
"""Baseline DXF parsed-source and cache lifecycle owner.

This module owns source fingerprinting, parsed-document caching, last-known-good
source fallback, and operation-layer classification of baseline DXF entities.
It is intentionally independent from manufacturing geometry and DXF output
serialization.
"""
from __future__ import annotations

import os
from pathlib import Path

import ezdxf

_BASELINE_DXF_SOURCE_CACHE = {}
_BASELINE_DXF_LAST_GOOD = {}
_BASELINE_DXF_RELOAD_GENERATION = 0
_BASELINE_DXF_PARSER_VERSION = 1
_BASELINE_DXF_SCHEMA_VERSION = 1
BASELINE_SOURCE_VERIFIED = "VERIFIED"
BASELINE_SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"


def clear_baseline_dxf_source_cache():
    """Clear parsed-source and last-known-good baseline DXF caches."""
    _BASELINE_DXF_SOURCE_CACHE.clear()
    _BASELINE_DXF_LAST_GOOD.clear()


def force_reload_baseline_dxf_sources():
    """Advance cache generation so the next access reparses every baseline source."""
    global _BASELINE_DXF_RELOAD_GENERATION
    _BASELINE_DXF_RELOAD_GENERATION += 1
    return _BASELINE_DXF_RELOAD_GENERATION


def _baseline_dxf_fingerprint(path):
    resolved = Path(path).expanduser().resolve(strict=False)
    stat = resolved.stat()
    return (
        str(resolved),
        int(stat.st_size),
        int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))),
        _BASELINE_DXF_PARSER_VERSION,
        _BASELINE_DXF_SCHEMA_VERSION,
        _BASELINE_DXF_RELOAD_GENERATION,
    )


def baseline_source_fingerprint(path):
    """Return the immutable parsed-source fingerprint for a baseline path."""
    return _baseline_dxf_fingerprint(path)


def load_baseline_dxf_source_with_status(path, *, allow_unverified_source=False):
    """Return ``(doc, status)`` while keeping preview LKG distinct from fresh truth."""
    normalized = os.path.abspath(os.fspath(path))
    try:
        key = _baseline_dxf_fingerprint(normalized)
    except OSError:
        if allow_unverified_source and normalized in _BASELINE_DXF_LAST_GOOD:
            return _BASELINE_DXF_LAST_GOOD[normalized], BASELINE_SOURCE_UNVERIFIED
        raise
    cached = _BASELINE_DXF_SOURCE_CACHE.get(key)
    if cached is not None:
        return cached, BASELINE_SOURCE_VERIFIED
    try:
        doc = ezdxf.readfile(normalized)
    except OSError:
        if allow_unverified_source and normalized in _BASELINE_DXF_LAST_GOOD:
            return _BASELINE_DXF_LAST_GOOD[normalized], BASELINE_SOURCE_UNVERIFIED
        raise
    _BASELINE_DXF_SOURCE_CACHE[key] = doc
    _BASELINE_DXF_LAST_GOOD[normalized] = doc
    for old_key in tuple(_BASELINE_DXF_SOURCE_CACHE):
        if old_key != key and old_key[0] == key[0]:
            _BASELINE_DXF_SOURCE_CACHE.pop(old_key, None)
    return doc, BASELINE_SOURCE_VERIFIED


def load_baseline_dxf_source(path, *, allow_unverified_source=False):
    """Backward-compatible document-only view of baseline source loading."""
    doc, _status = load_baseline_dxf_source_with_status(
        path, allow_unverified_source=allow_unverified_source
    )
    return doc


def iter_baseline_entities(entities):
    """Yield baseline geometry with INSERT blocks expanded in world coordinates."""
    for ent in entities:
        if ent.dxftype() != "INSERT":
            yield ent
            continue
        try:
            virtual = list(ent.virtual_entities())
        except Exception:
            continue
        yield from iter_baseline_entities(virtual)


def baseline_entity_layer(ent):
    """Resolve baseline DXF operation ownership; explicit layers beat legacy colors."""
    raw = str(getattr(ent.dxf, "layer", "") or "").strip().upper()
    if raw in {"CUTTING", "BEND", "MARKING", "DATUM", "BLIND_HOLE"}:
        return raw
    if raw in {"CHECK", "STOCK"}:
        return raw
    color = int(getattr(ent.dxf, "color", 0) or 0) if ent.dxf.hasattr("color") else 0
    # Legacy layer-0 DXF identifies operation by its ACI subcategory color.
    # 30/150 are CUTTING holes; 211/212/213 are MARKING lines.
    return "MARKING" if color in {211, 212, 213} else "CUTTING"


def baseline_cutting_bounds(msp):
    """Bounds of real CUTTING entities, never mixing halves of corrupt points.

    One damaged structural entity invalidates the entire source's bounds
    instead of constructing a plausible envelope from unrelated X/Y values.
    MARKING, DATUM and BLIND_HOLE cannot enlarge material bounds.
    """
    import math

    xs, ys = [], []

    def add_points(points):
        try:
            coords = tuple((float(x), float(y)) for x, y in points)
        except (TypeError, ValueError, OverflowError):
            return False
        if not coords or not all(
            math.isfinite(x) and math.isfinite(y) for x, y in coords
        ):
            return False
        xs.extend(x for x, _ in coords)
        ys.extend(y for _, y in coords)
        return True

    for ent in iter_baseline_entities(msp):
        if baseline_entity_layer(ent) != "CUTTING" or ent.dxftype() == "REGION":
            continue
        kind = ent.dxftype()
        try:
            if kind == "LWPOLYLINE":
                points = ((pt[0], pt[1]) for pt in ent.get_points())
                if not add_points(points):
                    return None
            elif kind == "LINE":
                if not add_points((
                    (ent.dxf.start.x, ent.dxf.start.y),
                    (ent.dxf.end.x, ent.dxf.end.y),
                )):
                    return None
            elif kind in {"CIRCLE", "ARC"}:
                cx = float(ent.dxf.center.x)
                cy = float(ent.dxf.center.y)
                # Some old DXF tools encode signed radii; a circle's
                # geometric envelope uses the magnitude, not its sign.
                radius = abs(float(ent.dxf.radius))
                if not all(math.isfinite(v) for v in (cx, cy, radius)) or radius <= 0:
                    return None
                if kind == "CIRCLE":
                    if not add_points(((cx-radius, cy-radius), (cx+radius, cy+radius))):
                        return None
                else:
                    raw_start = float(ent.dxf.start_angle)
                    raw_end = float(ent.dxf.end_angle)
                    if not (math.isfinite(raw_start) and math.isfinite(raw_end)):
                        return None
                    start_a = raw_start % 360.0
                    end_a = raw_end % 360.0
                    span = (end_a - start_a) % 360.0
                    sample_angles = [start_a, end_a]
                    for cardinal in (0.0, 90.0, 180.0, 270.0):
                        if abs(span) <= 1e-9 or ((cardinal - start_a) % 360.0) <= span + 1e-9:
                            sample_angles.append(cardinal)
                    if not add_points(
                        (cx + radius * math.cos(math.radians(angle)),
                         cy + radius * math.sin(math.radians(angle)))
                        for angle in sample_angles
                    ):
                        return None
        except (AttributeError, TypeError, ValueError, OverflowError, IndexError):
            return None

    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)
