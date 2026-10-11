# -*- coding: utf-8 -*-
"""#1502 actual Receiving NFB base-plate DXF: three independent source drawings.

User-confirmed:
  left drawing:  flat; middle drawing: bent; right drawing: flat.
These are three *variants*, not three parts of one sheet, and NOT the legacy
Receiving base_plate / base_plate_cN_rN. No base plate exists in the lower
cell of this product request. A pattern follows the SAME already verified
inner-door NFB configuration; it never creates independent switch positions.

Source-only until an original-world -> physical flat/bent plate map, exact
CUTTING/MARKING contours, units and quantity are certified. The original
customer DXF is never rewritten or copied into the repository.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
import csv
from typing import Mapping

import ezdxf
from ezdxf import bbox

from .receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)

_INDEX = (
    Path(__file__).resolve().parents[1] / "基準檔" / "開孔" / "NFB"
    / "受電箱底板圖樣索引.csv"
)
_PATTERN_ROLES = {
    "LEFT_FLAT": "NO_BEND_USER_CONFIRMED",
    "CENTER_BENT": "BEND_PRESENT_USER_CONFIRMED_FOLD_AXIS_UNRESOLVED",
    "RIGHT_FLAT": "NO_BEND_USER_CONFIRMED",
}
_SOURCE_ONLY = "RECEIVING_NFB_BASE_THREE_PATTERN_SOURCE_ONLY_NOT_CUTTING"
_NFB_LINK_ONLY = "RECEIVING_NFB_BASE_PATTERN_BOUND_TO_INNER_DOOR_NO_UV_RELEASE"
_TOL = 1e-4


@dataclass(frozen=True)
class NfbActualBasePattern:
    key: str
    fold_policy: str
    original_source_sha256: str
    source_index_filename: str
    x_bounds_native: tuple[float, float]
    source_anchor_handle: str
    native_line_handles: tuple[str, ...]
    native_arc_handles: tuple[str, ...]
    native_circle_handles: tuple[str, ...]
    native_mark211_handles: tuple[str, ...]
    original_units: str = "DXF_INSUNITS_0_UNSPECIFIED"
    status: str = _SOURCE_ONLY
    manufacturing_ready: bool = False


@dataclass(frozen=True)
class NfbActualBaseSource:
    sha256: str
    indexed_filename: str
    patterns: tuple[NfbActualBasePattern, ...]
    status: str = _SOURCE_ONLY
    manufacturing_ready: bool = False


@dataclass(frozen=True)
class NfbActualBasePatternBinding:
    """Explicit source *candidate* linked to original verified inner-door NFB.

    Selection of a base template is not silently inferred from its x position,
    number of circles or the historical top/lower BasePlate layout. Actual
    slot/hole positions stay in the existing verified NFB door configuration.
    """
    base_pattern_key: str
    base_source_sha256: str
    fold_policy: str
    inner_door_part_id: str
    nfb_indexed_model_key: tuple[str, str]
    nfb_source_sha256: str
    verified_physical_hole_ids: tuple[str, ...]
    status: str = _NFB_LINK_ONLY
    manufacturing_ready: bool = False


def _index_rows(index_path: Path, expected_sha256: str):
    if not index_path.is_file():
        raise ValueError("NFB real base-plate source index is unavailable")
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 3 or {r["pattern_key"] for r in rows} != set(_PATTERN_ROLES):
        raise ValueError("NFB base-plate source requires exactly three distinct patterns")
    if len({r["source_filename"] for r in rows}) != 1:
        raise ValueError("NFB base patterns must all be from the same original DXF")
    decoded = []
    for row in rows:
        digest = str(row["sha256"]).strip().lower()
        key = str(row["pattern_key"])
        if digest != expected_sha256:
            raise ValueError("NFB base-plate DXF bytes do not match the source index SHA")
        if row["fold_policy"] != _PATTERN_ROLES[key]:
            raise ValueError("NFB base-plate flat/bent role is not the user-approved role")
        if (row["units_contract"] != "DXF_INSUNITS_0_UNSPECIFIED"
                or row["manufacturing_status"] != "SOURCE_ONLY"):
            raise ValueError("NFB unitless source cannot become production READY by index edit")
        low, high = float(row["min_x"]), float(row["max_x"])
        if not all(isfinite(v) for v in (low, high)) or high <= low:
            raise ValueError("NFB base-plate source drawing x bounds are invalid")
        counts = tuple(int(row[k]) for k in (
            "line_count","arc_count","circle_count","marking_211_lines"
        ))
        if min(counts) < 0 or counts[3] > counts[0]:
            raise ValueError("NFB base-plate native entity counts are invalid")
        anchor = str(row["anchor_handle"]).strip().upper()
        if not anchor:
            raise ValueError("NFB real base-plate outer outline anchor absent")
        decoded.append((row, low, high, counts, anchor))
    ordered = sorted(decoded, key=lambda item: item[1])
    if any(ordered[i][2] + _TOL >= ordered[i + 1][1] for i in (0, 1)):
        raise ValueError("NFB source patterns overlap or touch; physical source split ambiguous")
    if [item[0]["pattern_key"] for item in ordered] != [
        "LEFT_FLAT", "CENTER_BENT", "RIGHT_FLAT",
    ]:
        raise ValueError("NFB source drawing order conflicts with real user-confirmed layout")
    return ordered


def inspect_receiving_nfb_actual_base(
    source_path: str | Path, *, index_path: str | Path = _INDEX,
) -> NfbActualBaseSource:
    """Byte-verify, classify exact native entity handles, preserve the variants.

    Color 7 is still **unclassified** source geometry; no assumption that all
    white ARC/LINE segments are toolpaths. Color 211 remains only marking
    candidate. DIMENSION/TEXT/POINT are annotations, never cut geometry.
    """
    path = Path(source_path)
    digest = sha256(path.read_bytes()).hexdigest()
    ordered = _index_rows(Path(index_path), digest)
    doc = ezdxf.readfile(path)
    if doc.dxfversion != "AC1032" or int(doc.header.get("$INSUNITS", 0)) != 0:
        raise ValueError("NFB actual base source version/units changed, scale unapproved")
    msp = doc.modelspace()
    graphic_types = {"LINE", "ARC", "CIRCLE"}
    allowed_annotations = {"DIMENSION", "TEXT", "POINT"}
    by_key = {
        row["pattern_key"]: {"LINE": [], "ARC": [], "CIRCLE": [], "MARK211": []}
        for row, _lo, _hi, _counts, _anchor in ordered
    }
    anchors = {key: anchor for (row, _lo, _hi, _counts, anchor) in ordered
               for key in (row["pattern_key"],)}
    seen_handles = set()
    for entity in msp:
        kind = entity.dxftype()
        if kind in allowed_annotations:
            continue
        if kind not in graphic_types:
            raise ValueError(f"NFB base contains unsupported source object: {kind}")
        handle = str(entity.dxf.get("handle","")).strip().upper()
        if not handle or handle in seen_handles:
            raise ValueError("NFB base source entity handle absent or repeated")
        seen_handles.add(handle)
        bounds = bbox.extents([entity])
        if not bounds.has_data:
            raise ValueError("NFB base native entity has no geometric extent")
        x0, x1 = float(bounds.extmin.x), float(bounds.extmax.x)
        if not all(isfinite(v) for v in (x0, x1)):
            raise ValueError("NFB base native geometry nonfinite")
        matching = [
            row["pattern_key"] for row, low, high, _counts, _anchor in ordered
            if low - _TOL <= x0 <= x1 <= high + _TOL
        ]
        if len(matching) != 1:
            raise ValueError("NFB base geometry crosses/escapes original source pattern")
        key = matching[0]
        color = int(entity.dxf.get("color",256))
        if kind in ("CIRCLE","ARC") and color != 7:
            raise ValueError("NFB base native round geometry color unexpectedly changed")
        if kind == "LINE" and color not in (7,211):
            raise ValueError("NFB base source line color unexpectedly changed")
        by_key[key][kind].append(handle)
        if color == 211:
            by_key[key]["MARK211"].append(handle)

    patterns = []
    for row, low, high, counts, anchor in ordered:
        key = row["pattern_key"]
        part = by_key[key]
        actual = (
            len(part["LINE"]),len(part["ARC"]),len(part["CIRCLE"]),
            len(part["MARK211"]),
        )
        if actual != counts:
            raise ValueError(f"NFB {key} source entity inventory has changed: {actual}")
        if anchor not in part["LINE"]:
            raise ValueError(f"NFB {key} outer-source anchor missing")
        patterns.append(NfbActualBasePattern(
            key=key,fold_policy=_PATTERN_ROLES[key],
            original_source_sha256=digest,
            source_index_filename=str(row["source_filename"]),
            x_bounds_native=(low,high),
            source_anchor_handle=anchor,
            native_line_handles=tuple(part["LINE"]),
            native_arc_handles=tuple(part["ARC"]),
            native_circle_handles=tuple(part["CIRCLE"]),
            native_mark211_handles=tuple(part["MARK211"]),
        ))
    return NfbActualBaseSource(
        sha256=digest,indexed_filename=patterns[0].source_index_filename,
        patterns=tuple(patterns),
    )


def link_actual_base_to_verified_inner_door_nfb(
    source: NfbActualBaseSource,
    pattern_key: str,
    *,
    verified_inner_door: NfbValidatedInnerDoorRender,
) -> NfbActualBasePatternBinding:
    """Link source option to the already-verified inner-door NFB, NOT a lower base.

    Still requires source-to-real-plate UV mapping / fold lines / metric units
    before actual CUTTING. No NEW positioning input is accepted.
    """
    if not isinstance(source,NfbActualBaseSource) or source.manufacturing_ready:
        raise ValueError("NFB source pattern evidence missing or already tainted")
    options = tuple(p for p in source.patterns if p.key == pattern_key)
    if len(options) != 1:
        raise ValueError("NFB selected real base pattern missing/ambiguous")
    if not isinstance(verified_inner_door,NfbValidatedInnerDoorRender):
        raise TypeError("NFB real base follows actual verified inner door")
    meta = getattr(verified_inner_door.render_data,"metadata",{})
    if (verified_inner_door.manufacturing_ready is not True
            or meta.get("nfb_trial_status") != VALIDATED
            or meta.get("nfb_trial_export_approved") is not True):
        raise ValueError("NFB actual base requires live verified inner-door CUTTING proof")
    physical = tuple(verified_inner_door.physical_hole_ids)
    entries = tuple(verified_inner_door.verified_hole_locations)
    if (not physical or len(physical) != len(set(physical))
            or len(entries) != len(physical)
            or {row[0] for row in entries} != set(physical)):
        raise ValueError("NFB original configured hole identities inconsistent")
    if (not verified_inner_door.part_id
            or not all(verified_inner_door.indexed_model_key)
            or not verified_inner_door.source_sha256):
        raise ValueError("NFB original indexed inner-door source identity missing")
    return NfbActualBasePatternBinding(
        base_pattern_key=pattern_key,
        base_source_sha256=source.sha256,
        fold_policy=options[0].fold_policy,
        inner_door_part_id=verified_inner_door.part_id,
        nfb_indexed_model_key=verified_inner_door.indexed_model_key,
        nfb_source_sha256=verified_inner_door.source_sha256,
        verified_physical_hole_ids=physical,
    )
