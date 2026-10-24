# -*- coding: utf-8 -*-
"""#1499 single saved NFBConfig contract for Receiving Bay/quantity versions.

Persist ONLY the explicit fact of submission plus operator-entered values.
Preview/readiness/collision/certification are derived live by #1497/#1498 and
MUST NOT be serialized. A saved NFB is not automatic manufacturing permission.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from collections.abc import Mapping

MANUAL_X_STATES = frozenset({
    "NONE", "UNVERIFIED_BASIS", "RECONFIRM_REQUIRED", "CONFIRMED",
})
DERIVED_KEYS = frozenset({
    "status", "readiness", "manufacturing_ready", "can_submit",
    "collision", "collisions", "preview", "preview_only", "approved",
    "certified_x_revision", "nfb_trial_export_approved",
    "physical_part_readiness", "diagnostics",
    # #1504 AC-24 live verification is a READ-ONLY projection; it is not
    # an operator-entered field, and must never become another saved truth.
    "configuration_verified", "manufacturing_verified", "source_status",
    "unit_rows", "part_rows", "derived_state", "unresolved_dependencies",
    "actual_export_count", "whole_ready",
})
NFB_FIELDS = frozenset({"nfb_config_submitted", "nfb_config"})


def _json_value(value, *, location: str):
    """Persist only JSON-compatible user values; reject cache / private types."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if type(value) in (int, float):
        if not isfinite(float(value)):
            raise ValueError(f"{location} must be finite")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(v, location=location) for v in value]
    if isinstance(value, Mapping):
        result = {}
        for k, v in value.items():
            if not isinstance(k, str) or not k or k.startswith("_") or k in DERIVED_KEYS:
                raise ValueError(f"{location} contains derived or invalid key: {k!r}")
            result[k] = _json_value(v, location=f"{location}.{k}")
        return result
    raise ValueError(f"{location} has nonpersistent value {type(value).__name__}")


def normalize_nfb_config(config):
    """Validate stable per-hole owner and operator X state without inferring X."""
    if not isinstance(config, Mapping):
        raise ValueError("submitted NFBConfig must be a mapping")
    value = _json_value(config, location="NFBConfig")
    if "brand" in value or "switch_brand" in value:
        raise ValueError("NFB brand has one existing Set owner; no duplicate brand")
    holes = value.get("holes")
    if not isinstance(holes, list) or not holes:
        raise ValueError("submitted NFBConfig requires explicit hole list")
    seen = set()
    for hole in holes:
        if not isinstance(hole, dict):
            raise ValueError("NFBConfig hole must be an object")
        owner = hole.get("physical_hole_id")
        if not isinstance(owner, str) or not owner.strip() or owner in seen:
            raise ValueError("NFB physical_hole_id missing/duplicate")
        seen.add(owner)
        model = hole.get("model_filename")
        # CURRENT CSV V5 persists a source-owned brand/model identity, not a
        # fake .dxf basename. Reuse the existing typed identity validator:
        # it accepts historical DXF names, rejects malformed V5 identities,
        # and does not invent a missing CSV row when reading saved projects.
        from .receiving_nfb_model_identity import (
            parse_numeric_model_ref, validate_stored_model_ref,
        )
        try:
            model = validate_stored_model_ref(model)
        except ValueError as exc:
            raise ValueError("NFB model must be a valid V5 identity or legacy DXF basename") from exc
        parsed = parse_numeric_model_ref(model)
        if parsed is not None:
            source_brand = hole.get("source_brand")
            if source_brand is not None and source_brand != parsed[0]:
                raise ValueError("NFB V5 model and saved hole source_brand mismatch")
        state = hole.get("manual_x_state", "NONE")
        if state not in MANUAL_X_STATES:
            raise ValueError("NFB manual_x_state unsupported")
        hole["manual_x_state"] = state
        x = hole.get("manual_x_mm")
        if x is not None and (type(x) not in (int, float) or not isfinite(float(x))):
            raise ValueError("NFB manual_x_mm must be a finite number or None")
        if state == "CONFIRMED":
            if x is None:
                raise ValueError("NFB CONFIRMED X requires explicit numeric coordinate")
            if (not isinstance(hole.get("datum_revision"), str)
                    or not hole["datum_revision"].strip()
                    or not isinstance(hole.get("datum_snapshot"), dict)
                    or not hole["datum_snapshot"]):
                raise ValueError("NFB CONFIRMED X requires datum revision and snapshot")
        angle = hole.get("rotation_deg", 0)
        if type(angle) is not int or angle not in (0, 90, 180, 270):
            raise ValueError("NFB rotation must be 0/90/180/270")
        hole["rotation_deg"] = angle
    return value


def normalize_nfb_saved_fields(row):
    """Canonicalize persistence: no submission => no stored NFBConfig."""
    if not isinstance(row, Mapping):
        raise ValueError("NFB record must be mapping")
    has_config = "nfb_config" in row
    submitted = row.get("nfb_config_submitted", False)
    if type(submitted) is not bool:
        raise ValueError("NFB submission fact must be explicit boolean")
    if not submitted:
        # DRAFT editor data is never a saved manufacturing fact.
        return {}
    if not has_config or row["nfb_config"] is None:
        raise ValueError("submitted NFB must preserve its actual NFBConfig")
    config = normalize_nfb_config(row["nfb_config"])
    physical_width = row.get("width")
    if physical_width is not None:
        # Every persisted ReceivingLayout Bay carries its own actual width.
        # Importing an old CONFIRMED datum from W800 into a W750 Bay must
        # never silently re-authorize the previous hole X. Check established
        # operator datum key variants, without fabricating a missing datum.
        # The existing Receiving Bay _number adapter also accepts numeric
        # strings from older projects. Match that compatibility while still
        # rejecting boolean, nonnumeric and nonfinite manufacturing widths.
        if type(physical_width) is bool:
            raise ValueError("NFB saved Bay physical width invalid")
        try:
            bay_width = float(physical_width)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("NFB saved Bay physical width invalid") from exc
        if not isfinite(bay_width) or bay_width <= 0:
            raise ValueError("NFB saved Bay physical width invalid")
        for hole in config["holes"]:
            if hole["manual_x_state"] != "CONFIRMED":
                continue
            snapshot = hole.get("datum_snapshot") or {}
            known_widths = tuple(
                snapshot[key] for key in (
                    "width", "w", "box_width_mm", "bay_width_mm",
                    "outer_width_mm",
                ) if key in snapshot
            )
            # The current numeric CSV V5 is a model/geometry identity,
            # NOT an implicit permission to reuse an old world-X datum.
            # A legacy DXF row may have no structured width evidence, but a
            # V5 CONFIRMED hole must explicitly bind its manual X to this Bay.
            # Missing width, conflicting aliases, boolean or nonfinite input
            # may not silently preserve manufacturing confidence. Retain
            # the authored coordinate and source for operator reconfirmation.
            from .receiving_nfb_model_identity import parse_numeric_model_ref
            missing_v5_width_proof = (
                parse_numeric_model_ref(hole.get("model_filename")) is not None
                and not known_widths
            )
            if missing_v5_width_proof or any(
                type(value) not in (int, float)
                or not isfinite(float(value))
                or abs(float(value) - bay_width) > 1e-7
                for value in known_widths
            ):
                hole["manual_x_state"] = "RECONFIRM_REQUIRED"
    return {
        "nfb_config_submitted": True,
        "nfb_config": config,
    }


def reconfirm_copied_nfb_config(config):
    """An independent new physical version/Bay must recheck its X datum."""
    copied = normalize_nfb_config(config)
    for hole in copied["holes"]:
        if hole["manual_x_state"] == "CONFIRMED":
            hole["manual_x_state"] = "RECONFIRM_REQUIRED"
    return copied


def contains_submitted_nfb(scope):
    """Facts only; never claim manufacturing READY here."""
    if not isinstance(scope, Mapping):
        return False
    if scope.get("nfb_config_submitted") is True:
        return True
    receiving = scope.get("receiving_layout")
    if isinstance(receiving, Mapping):
        for selected in receiving.get("sets", ()) or ():
            for bay in selected.get("bays", ()) or ():
                if isinstance(bay, Mapping) and bay.get("nfb_config_submitted") is True:
                    return True
    quantity = scope.get("quantity")
    if isinstance(quantity, Mapping):
        for version in quantity.get("versions", ()) or ():
            if isinstance(version, Mapping) and version.get("nfb_config_submitted") is True:
                return True
    return False
