# -*- coding: utf-8 -*-
"""#1502 true middle base circular holes are NFB LOWER-region fixing holes.

Explicit owner rule from the user: the 16 middle-drawing circles on
受電箱底板(1).dxf represent NFB fixing-hole SOURCE geometry, corresponding
to *circles only* in the earlier Shihlin NFB lower source group. Its OTHER
lower entities are not imported as base CUTTING or MARKING.

No new switch-X, no per-floor BasePlate, no automatic assignment of all
four quartets to one configured NFB. In particular, the leftmost two
quartets are ALTERNATIVE 30x132 and 35x126 patterns, not duplicate holes.

Also verifies a converted DXF's circular LWPOLYLINE geometry without
trusting generated BENDING layers. The user confirms only the CENTER
plate bends: any BENDING entities in LEFT/RIGHT require correction.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from math import isclose, isfinite, sqrt
from pathlib import Path

import ezdxf

from .receiving_nfb_actual_base_source import (
    inspect_receiving_nfb_actual_base,
)

ROLE = "NFB_LOWER_REGION_CIRCLES_ONLY_FIXING_HOLES"
SOURCE_ONLY = "MFG2_NFB_MIDDLE_FIXED_HOLE_SOURCE_LINK_NOT_UV_RELEASE"
DIAG_FLAT_BEND = "LEFT_OR_RIGHT_BENDING_LAYER_CONFLICTS_WITH_USER_FLAT_RULE"


@dataclass(frozen=True)
class NfbMiddleFixingQuartet:
    original_handles: tuple[str, str, str, str]
    source_centers_xy: tuple[tuple[float, float], ...]
    center_xy: tuple[float, float]
    horizontal_pitch: float
    vertical_pitch: float
    circle_radius: float
    role: str = ROLE
    manufacturing_ready: bool = False


@dataclass(frozen=True)
class NfbMiddleFixingEvidence:
    original_source_sha256: str
    quartets: tuple[NfbMiddleFixingQuartet, ...]
    raw_circle_count: int
    converted_source_sha256: str | None
    converted_circle_match: bool
    fold_layer_conflicts: tuple[str, ...]
    status: str = SOURCE_ONLY
    manufacturing_ready: bool = False


def _sample_quartets(rows):
    """Pair actual native circles by X columns and their identical Y pair.

    Each x coordinate has precisely two Y coordinates, defining one left or
    right column of a 4-hole rectangle. Pair adjacent X columns *within the
    same Y pair*, never by closeness alone, as two alternative quartets
    overlap the same leftmost NFB source center.
    """
    columns = defaultdict(list)
    seen = set()
    for handle, x, y, radius in rows:
        key = (round(x, 5), round(y, 5))
        if key in seen:
            raise ValueError("NFB middle fixing source has duplicate circle center")
        seen.add(key)
        if radius <= 0 or not isfinite(radius):
            raise ValueError("NFB fixing-hole radius unavailable")
        columns[round(x, 5)].append((handle, x, y, radius))
    by_ys = defaultdict(list)
    for x, samples in columns.items():
        samples = sorted(samples, key=lambda item: item[2])
        if len(samples) != 2:
            raise ValueError("NFB middle fixing-holes must form two-row columns")
        ypair = tuple(round(s[2], 5) for s in samples)
        by_ys[ypair].append((x, samples))
    quartets = []
    for ypair, cols in by_ys.items():
        cols.sort(key=lambda c: c[0])
        if len(cols) % 2 != 0:
            raise ValueError("NFB middle fixing-hole source has unpaired columns")
        for i in range(0, len(cols), 2):
            left, right = cols[i:i+2]
            pitch = right[0] - left[0]
            if not (0 < pitch <= 40.001):
                raise ValueError("NFB fixing-hole rectangle columns not source-verified")
            pts = tuple(left[1] + right[1])
            rr = [p[3] for p in pts]
            if any(abs(r-rr[0])>1e-5 for r in rr):
                raise ValueError("NFB fixing-hole quartet mixes circle diameters")
            quartets.append(NfbMiddleFixingQuartet(
                original_handles=tuple(p[0] for p in pts),
                source_centers_xy=tuple((p[1], p[2]) for p in pts),
                center_xy=((left[0] + right[0])/2,(ypair[0]+ypair[1])/2),
                horizontal_pitch=pitch,
                vertical_pitch=ypair[1]-ypair[0],
                circle_radius=rr[0],
            ))
    quartets.sort(key=lambda q: (q.center_xy[0],q.horizontal_pitch))
    if len(quartets) != 4 or len(rows) != 16 or (
        sum(len(x.original_handles) for x in quartets) != 16
    ):
        raise ValueError("NFB Shihlin middle base expected 16 native fixing circles")
    return tuple(quartets)


def _converted_circles(modelspace, bounds):
    left, right = bounds
    circles = []
    for entity in modelspace:
        if entity.dxftype() != "LWPOLYLINE" or entity.dxf.layer != "CUTTING":
            continue
        pts = tuple(entity.get_points("xyb"))
        if len(pts) != 4 or not entity.closed:
            continue
        if any(abs(float(p[2]) - (sqrt(2) - 1)) > 1e-5 for p in pts):
            continue
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        width = max(xs)-min(xs)
        height = max(ys)-min(ys)
        if not (left <= min(xs) and max(xs) <= right
                and abs(width - height) < 1e-5 and width <= 4.0):
            continue
        circles.append((
            round((min(xs) + max(xs))/2, 5),
            round((min(ys) + max(ys))/2, 5),
            round(width/2, 5),
        ))
    return circles


def inspect_middle_base_nfb_fixing_holes(
    original_source_path: str | Path, *,
    converted_dxf_path: str | Path | None = None,
    index_path: str | Path | None = None,
) -> NfbMiddleFixingEvidence:
    """Record the actual NFB fixing quartet alternatives, not a machining plan.

    Original native circle identity is mandatory. A provided derived file
    must reproduce every center and radius, even if its new handles differ.
    Its BENDING lines are audited separately: LEFT/RIGHT BENDING is invalid
    under the owner's explicit flat-plate rule, but cannot erase source
    circles or be silently accepted as a valid bend.
    """
    source = Path(original_source_path)
    opts = {} if index_path is None else {"index_path": index_path}
    catalog = inspect_receiving_nfb_actual_base(source, **opts)
    if catalog.sha256 != sha256(source.read_bytes()).hexdigest():
        raise ValueError("NFB actual base source SHA changed during fixing inspection")
    middle = next(p for p in catalog.patterns if p.key == "CENTER_BENT")
    original_doc = ezdxf.readfile(source)
    entities = {str(e.dxf.handle).upper():e for e in original_doc.modelspace()}
    rows = []
    for handle in middle.native_circle_handles:
        e = entities.get(handle)
        if e is None or e.dxftype() != "CIRCLE":
            raise ValueError("NFB fixing source requires original native CIRCLE")
        x, y, r = (
            float(e.dxf.center.x),float(e.dxf.center.y),float(e.dxf.radius)
        )
        if not all(isfinite(v) for v in (x,y,r)):
            raise ValueError("NFB native fixing hole has nonfinite geometry")
        rows.append((handle,x,y,r))
    quartets = _sample_quartets(rows)
    if any(abs(q.circle_radius - 1.6) > 1e-5 for q in quartets):
        raise ValueError("NFB original Shihlin middle fixed holes are not Ø3.2")
    derived_sha = None
    converted_match = False
    conflicts = ()
    if converted_dxf_path is not None:
        derived = Path(converted_dxf_path)
        derived_sha = sha256(derived.read_bytes()).hexdigest()
        d = ezdxf.readfile(derived)
        if int(d.header.get("$INSUNITS",0)) != 4:
            raise ValueError("NFB converted DXF units are not millimetres")
        observed = _converted_circles(d.modelspace(),middle.x_bounds_native)
        expected = sorted((
            round(x,5),round(y,5),round(r,5)
        ) for _h,x,y,r in rows)
        if sorted(observed) != expected:
            raise ValueError("NFB converted middle fixing-hole circles differ from original")
        converted_match = True
        bad = []
        for e in d.modelspace():
            if e.dxftype() != "LINE" or e.dxf.layer != "BENDING":
                continue
            lo = min(float(e.dxf.start.x),float(e.dxf.end.x))
            hi = max(float(e.dxf.start.x),float(e.dxf.end.x))
            for p in catalog.patterns:
                if (p.key != "CENTER_BENT"
                        and p.x_bounds_native[0] - 1e-4 <= lo
                        and hi <= p.x_bounds_native[1] + 1e-4):
                    bad.append(f"{DIAG_FLAT_BEND}:{p.key}:{e.dxf.handle}")
        conflicts = tuple(sorted(bad))
    return NfbMiddleFixingEvidence(
        original_source_sha256=catalog.sha256,
        quartets=quartets,
        raw_circle_count=len(rows),
        converted_source_sha256=derived_sha,
        converted_circle_match=converted_match,
        fold_layer_conflicts=conflicts,
    )
