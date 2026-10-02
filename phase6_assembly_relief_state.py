"""Persisted assembly-relief save/replay contract.

This module owns the *persisted state* contract only.  It intentionally does not
solve relief geometry, own Certified Registry formulas, or compute manufacturing
placement.  Callers collect current mechanical context and already-resolved
solutions, then delegate deterministic identity/replay decisions here.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Mapping, Sequence

from ae_engine.certified_relief_registry import (
    RELIEF_CONTRACT_VERSION,
    certified_rule_revision_exists,
)

_CERTIFIED_TRUST_LEVELS = frozenset({"CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"})
_NUMERIC_SOURCE_KEYS = (
    "w", "h", "d", "t", "fw", "zl1", "zl2", "zr1", "zr2",
    "yl1", "yr1", "ytop1", "ybottom1",
)


def relief_profile_fingerprint(profile):
    """Return the stable mechanical Fold-profile identity used by persistence."""
    rows = []
    for raw in list(profile or ()):
        row = dict(raw or {})
        try:
            length = round(float(row.get("len", row.get("length", 0.0)) or 0.0), 6)
        except (TypeError, ValueError):
            length = 0.0
        angle = row.get("angle")
        try:
            angle = None if angle is None else round(float(angle), 6)
        except (TypeError, ValueError):
            angle = None
        rows.append((
            str(row.get("phase6_key") or ""),
            length,
            angle,
            str(row.get("core") or ""),
        ))
    return tuple(rows)


def structure_fingerprint(structure_state) -> str:
    payload = json.dumps(
        structure_state or {}, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_current_source_signature(
    *,
    scalar_source,
    joint_graph_fingerprint: str,
    structure_state,
    cabinet_family: str,
    formed_left,
    formed_right,
    box_body_profile,
    part_profiles: Mapping[str, object],
):
    """Build the persisted/replay mechanical source identity from caller-collected context.

    Callers own live application/workspace reads.  This neutral owner owns the
    deterministic persisted contract shape so save and reload cannot drift.
    """
    source = dict(scalar_source or {})
    scalar_keys = (
        "w", "h", "d", "t", "fw", "zl1", "zl2", "zr1", "zr2",
        "yl1", "yr1", "ytop1", "ybottom1", "assembly_type",
    )
    result = {key: deepcopy(source.get(key)) for key in scalar_keys if key in source}
    result.update({
        "relief_contract_version": RELIEF_CONTRACT_VERSION,
        "joint_graph_fingerprint": str(joint_graph_fingerprint or ""),
        "family_structure_fingerprint": structure_fingerprint(structure_state),
        "cabinet_family": str(cabinet_family or ""),
        "box_body_formed_fw": {
            "left": None if formed_left is None else float(formed_left),
            "right": None if formed_right is None else float(formed_right),
        },
        "box_body_profile": deepcopy(list(box_body_profile or ())),
        "part_profiles": {
            str(key): deepcopy(value or {})
            for key, value in dict(part_profiles or {}).items()
        },
    })
    return result


def _same_number(left, right, *, tolerance: float = 1e-6) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def _active_rule_revision(rule_id, revision) -> bool:
    rule_id = str(rule_id or "")
    if not rule_id:
        return True
    try:
        revision = int(revision or 0)
    except (TypeError, ValueError):
        return False
    return revision > 0 and certified_rule_revision_exists(rule_id, revision)


def source_matches_current(
    saved_source, current_source, required_parts: Sequence[str], *, require_formed_fw: bool = True
) -> bool:
    """Validate persisted relief source identity against current mechanics.

    ``assembly_type`` is intentionally not compared.  Joint graph/family/structure
    identity is the mechanical authority; the high-level mirror may differ while
    representing the same accepted mechanics.
    """
    saved = dict(saved_source or {})
    current = dict(current_source or {})
    if not saved:
        return False
    try:
        if int(saved.get("relief_contract_version", 0) or 0) != RELIEF_CONTRACT_VERSION:
            return False
        if int(current.get("relief_contract_version", 0) or 0) != RELIEF_CONTRACT_VERSION:
            return False
    except (TypeError, ValueError):
        return False

    saved_formed = dict(saved.get("box_body_formed_fw") or {})
    current_formed = dict(current.get("box_body_formed_fw") or {})
    if saved_formed:
        for side in ("left", "right"):
            if side not in saved_formed or side not in current_formed:
                return False
            if not _same_number(saved_formed[side], current_formed[side]):
                return False
    elif require_formed_fw:
        return False

    saved_parts = dict(saved.get("part_profiles") or {})
    for key in _NUMERIC_SOURCE_KEYS:
        if key not in saved or key not in current:
            continue
        # Once a saved Y Fold profile exists, that topology/length fingerprint
        # is authoritative.  The legacy aggregate ytop1 may legitimately be
        # reported as zero after structural top-fold removal.
        if key == "ytop1" and any(
            "Y" in dict(saved_parts.get(str(part_key)) or {})
            for part_key in required_parts
        ):
            continue
        if not _same_number(saved[key], current[key]):
            return False

    for key in ("joint_graph_fingerprint", "family_structure_fingerprint"):
        saved_value = str(saved.get(key) or "")
        current_value = str(current.get(key) or "")
        if not saved_value or not current_value or saved_value != current_value:
            return False
    if str(saved.get("cabinet_family") or "") != str(current.get("cabinet_family") or ""):
        return False

    saved_rules = dict(saved.get("registry_rules") or {})
    for part_key in required_parts:
        rule = dict(saved_rules.get(str(part_key)) or {})
        if not _active_rule_revision(rule.get("rule_id"), rule.get("revision")):
            return False

    if "box_body_profile" in saved:
        if relief_profile_fingerprint(saved.get("box_body_profile")) != relief_profile_fingerprint(
            current.get("box_body_profile")
        ):
            return False

    current_parts = dict(current.get("part_profiles") or {})
    for part_key in required_parts:
        saved_axes = dict(saved_parts.get(str(part_key)) or {})
        current_axes = dict(current_parts.get(str(part_key)) or {})
        for axis in ("X", "Y"):
            if axis not in saved_axes:
                continue
            if relief_profile_fingerprint(saved_axes.get(axis)) != relief_profile_fingerprint(
                current_axes.get(axis)
            ):
                return False
    return True


def committed_relief_cuts(state, part_key: str, current_source):
    """Return persisted cut polygons only when the replay contract is still valid."""
    state = deepcopy(dict(state or {}))
    if not bool(state.get("enabled")):
        return ()
    part_key = str(part_key)
    part = dict((state.get("parts") or {}).get(part_key, {}) or {})
    if not bool(part.get("verified")) and not bool(part.get("canonical_accepted")):
        return ()

    trust_level = str(part.get("trust_level") or "")
    rule_id = part.get("rule_id")
    rule_revision = part.get("rule_revision")
    if trust_level in _CERTIFIED_TRUST_LEVELS and rule_id:
        if not _active_rule_revision(rule_id, rule_revision):
            return ()

    source = dict(state.get("source") or {})
    if not source_matches_current(
        source, current_source, [part_key], require_formed_fw=False
    ):
        return ()

    if trust_level in _CERTIFIED_TRUST_LEVELS and rule_id:
        saved_rule = dict((source.get("registry_rules") or {}).get(part_key) or {})
        try:
            if str(saved_rule.get("rule_id") or "") != str(rule_id):
                return ()
            if int(saved_rule.get("revision", 0) or 0) != int(rule_revision):
                return ()
        except (TypeError, ValueError):
            return ()

    cuts = []
    for polygon in list(part.get("cuts") or ()):
        coords = tuple((float(point[0]), float(point[1])) for point in polygon if len(point) >= 2)
        if len(coords) >= 3:
            cuts.append(coords)
    return tuple(cuts)


def _polygon_coords(geometry):
    if geometry is None or getattr(geometry, "is_empty", True):
        return []
    polygons = [geometry] if getattr(geometry, "geom_type", "") == "Polygon" else [
        item for item in getattr(geometry, "geoms", ())
        if getattr(item, "geom_type", "") == "Polygon" and float(item.area) > 1e-9
    ]
    out = []
    for polygon in polygons:
        coords = list(polygon.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) >= 3:
            out.append([[float(x), float(y)] for x, y in coords])
    return out


def _solution_is_committable(solution) -> bool:
    if bool(getattr(solution, "verified", False)):
        return True
    trust = str(getattr(solution, "trust_level", "") or "")
    return bool(getattr(solution, "rule_id", None)) and trust in _CERTIFIED_TRUST_LEVELS


def build_persisted_relief_state(
    *,
    required_parts: Sequence[str],
    solutions: Mapping[str, object],
    source_signature,
    prior_state=None,
    fallback_enabled: bool,
    clearance: float,
):
    """Build the atomic Head/Tail persisted transaction from resolved solutions.

    Geometry solving is out of scope; this function only serializes already
    resolved candidates and preserves a still-current prior atomic transaction
    when the latest solve is incomplete.
    """
    required = [str(key) for key in required_parts]
    solutions = dict(solutions or {})
    source_signature = deepcopy(dict(source_signature or {}))
    atomic_committable = bool(required) and all(
        key in solutions and _solution_is_committable(solutions[key]) for key in required
    )
    if not atomic_committable:
        prior = deepcopy(dict(prior_state or {}))
        if prior and source_matches_current(prior.get("source"), source_signature, required):
            return prior
        return {
            "enabled": False,
            "fallback_enabled": bool(fallback_enabled),
            "clearance": float(clearance),
            "source": {},
            "parts": {},
        }

    source_signature["registry_rules"] = {
        key: {
            "rule_id": str(getattr(solutions[key], "rule_id", "") or ""),
            "revision": int(getattr(solutions[key], "rule_revision", 0) or 0),
        }
        for key in required
    }
    parts = {}
    for key in required:
        solution = solutions[key]
        measurements = []
        for item in tuple(getattr(solution, "corner_reliefs", ()) or ()):
            measurement = getattr(item, "measurement", None)
            if measurement is None:
                continue
            measurements.append({
                "corner_name": str(getattr(measurement, "corner_name", getattr(item, "corner_name", ""))),
                "primary_u": float(measurement.primary_u),
                "primary_v": float(measurement.primary_v),
                "secondary_u": None if measurement.secondary_u is None else float(measurement.secondary_u),
                "secondary_depth": None if measurement.secondary_depth is None else float(measurement.secondary_depth),
                "clearance_a": float(getattr(measurement, "clearance_a", 0.0)),
            })
        parts[key] = {
            "verified": bool(getattr(solution, "verified", False)),
            "canonical_accepted": True,
            "trust_level": str(getattr(solution, "trust_level", "PROVISIONAL_3D") or "PROVISIONAL_3D"),
            "rule_id": getattr(solution, "rule_id", None),
            "rule_revision": getattr(solution, "rule_revision", None),
            "joint_signature": [dict(item) for item in tuple(getattr(solution, "joint_signature", ()) or ())],
            "shadow_validation": deepcopy(getattr(solution, "shadow_validation", None)),
            "cuts": _polygon_coords(getattr(solution, "cut_polygon_2d", None)),
            "measurements": measurements,
        }
    return {
        "enabled": True,
        "fallback_enabled": bool(fallback_enabled),
        "clearance": float(clearance),
        "source": source_signature,
        "parts": parts,
    }
