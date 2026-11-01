# -*- coding: utf-8 -*-
"""#2517 read-only authority boundary for NFB physical manifest disclosure.

A live physical report is evidence, not a manufacturing capability. This
validation rejects contradictory counts, fake whole-ready and stale scope
identities before any GUI paints a 'ready' claim. Actual DXF authorization
remains exclusively with the typed NfbPartialExportManifest/Engine writers.
"""
from __future__ import annotations

from collections.abc import Mapping


def validate_receiving_nfb_manifest_view(view):
    """Validate one current physical report; do NOT manufacture/approve it."""
    if not isinstance(view, dict) or "status" not in view:
        raise TypeError("NFB manufacturing status must be a live view")
    state = view["status"]
    if state in ("LEGACY", "BLOCKED"):
        return view
    if state == "CSV_V5_SCOPED_DIAGNOSTIC":
        if (view.get("actual_export_count") is not None or view.get("rows")
                or view.get("manufacturing_ready") is not False
                or view.get("whole_ready") is not False):
            raise ValueError("CSV V5 status must not claim manufactured parts")
        for unit in view.get("unit_rows", ()):
            if unit.get("manufacturing_verified") is not False:
                raise ValueError("CSV V5 unit cannot fake manufacturing approval")
            errors = tuple(unit.get("reasons") or ())
            configured = unit.get("configuration_verified")
            if type(configured) is not bool or configured is bool(errors):
                raise ValueError("NFB unit configuration verification/reasons mismatch")
        for part in view.get("part_rows", ()):
            affected = part.get("nfb_affected")
            if affected is True:
                if not tuple(part.get("reasons") or ()):
                    raise ValueError("NFB affected physical part needs reasons")
            elif affected is not False:
                raise ValueError("CSV V5 part evidence invalid")
        return view
    if state == "CSV_SOURCE_RECHECK_ONLY":
        if view.get("actual_export_count") is not None or view.get("rows"):
            raise ValueError("CSV recheck-only display cannot claim manufactured parts")
        return view
    if state not in ("PARTIAL_ONLY", "WHOLE_READY"):
        raise ValueError("NFB manufacturing view status unsupported")
    rows = tuple(view.get("rows", ()))
    allowed = view.get("actual_export_count", 0)
    if type(allowed) is not int or allowed < 0:
        raise ValueError("NFB manifest display count must be a nonnegative integer")
    actual_ready = 0
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("NFB manifest row must be a mapping")
        count = item.get("actual_count")
        status = item.get("status")
        may_export = item.get("may_export")
        if type(count) is not int or count <= 0:
            raise ValueError("NFB manifest row count must be positive")
        if type(may_export) is not bool:
            raise ValueError("NFB manifest row export decision must be boolean")
        if status not in ("READY", "UNAFFECTED", "BLOCKED"):
            raise ValueError("NFB manifest row status not recognized")
        if may_export is not (status in ("READY", "UNAFFECTED")):
            raise ValueError("NFB manifest row status/export mismatch")
        if may_export:
            actual_ready += count
    if allowed != actual_ready:
        raise ValueError("NFB manifest displayed count differs from physical rows")
    if state == "WHOLE_READY" and (
            any(not row["may_export"] for row in rows)
            or view.get("unresolved_dependencies")):
        raise ValueError("NFB manifest full-ready display has blocked dependencies")
    return view


def validate_receiving_nfb_highlighted_manifest(ports, set_index, highlighted_bays):
    """Read each live Set/Bay once, reject ambiguous scope/status, return views.

    The returned report is still only DISPLAY evidence. The live DXF writer
    must recheck source and manufacturing capability at export time.
    """
    if not isinstance(ports, Mapping) or not callable(ports.get("manifest")):
        raise TypeError("NFB live manifest port required")
    if type(set_index) is not int or set_index < 0:
        raise ValueError("NFB Set index invalid")
    bays = tuple(highlighted_bays)
    if (not bays or len(set(bays)) != len(bays)
            or any(type(bi) is not int or bi < 0 for bi in bays)):
        raise ValueError("NFB highlighted Bay selection invalid")
    selected = []
    for bay_index in bays:
        current = ports["manifest"](set_index, bay_index)
        if not isinstance(current, Mapping):
            raise TypeError("NFB live manifest must be a mapping")
        view = validate_receiving_nfb_manifest_view(dict(current))
        state = view["status"]
        if state == "CSV_V5_SCOPED_DIAGNOSTIC":
            set_id, bay_id = view.get("set_id"), view.get("bay_id")
            if (not isinstance(set_id, str) or not set_id.strip()
                    or not isinstance(bay_id, str) or not bay_id.strip()):
                raise ValueError("NFB CSV V5 scoped identity is missing")
            version = view.get("version_id")
            if version is not None and not isinstance(version, str):
                raise ValueError("NFB CSV V5 version identity invalid")
        elif state not in ("LEGACY", "BLOCKED", "CSV_SOURCE_RECHECK_ONLY"):
            ids = tuple(view.get(key) for key in ("set_id", "bay_id", "version_id"))
            if any(not isinstance(value, str) or not value.strip() for value in ids):
                raise ValueError("NFB live manifest missing Set/Bay/version stable IDs")
        selected.append((bay_index, view))
    return tuple(selected)
