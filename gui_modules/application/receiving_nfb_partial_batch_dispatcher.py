# -*- coding: utf-8 -*-
"""#1501 Receiving highlighted-Bay -> REAL partial inner-door DXF dispatch.

The existing session-scoped Receiving ports and #1635 per-Bay writer remain
the only manufacturing authority. This action never feeds cached preview
geometry into the canonical CHECK/Q grouping or claims full-box delivery.
Every selected Bay must have current source proof; nothing is published
until ALL selected real DXFs have been written in an isolated stage.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

from ae_engine.receiving_nfb_export_manifest import (
    INNER_DOOR, NfbPartialExportManifest,
)


def _selection(set_index, bay_indices):
    if type(set_index) is not int or set_index < 0:
        raise ValueError("NFB partial export requires a real Set index")
    selected = tuple(bay_indices)
    if (not selected or any(type(bi) is not int or bi < 0 for bi in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("NFB partial export requires unique highlighted Bays")
    return selected


def require_highlighted_nfb_inner_doors(ports, set_index, bay_indices, *, allow_held=False):
    """Display-only preflight; real writer MUST revalidate before any DXF.

    No unconfigured, stale, wrong-scope or mixed blocked selection gets a
    partial-export button. A whole-box export flag cannot authorize this.
    """
    selected = _selection(set_index, bay_indices)
    if type(allow_held) is not bool:
        raise TypeError("NFB partial selection must be boolean")
    if allow_held:
        ready = []
        for bi in selected:
            try:
                require_highlighted_nfb_inner_doors(ports, set_index, (bi,))
            except (ValueError, TypeError, KeyError, IndexError, OSError):
                continue
            ready.append(bi)
        if not ready:
            raise ValueError("NFB highlighted selection has no READY inner-door parts")
        return tuple(ready)
    if not isinstance(ports, Mapping):
        raise TypeError("NFB operator ports required")
    report = ports.get("manifest")
    if not callable(report) or not callable(ports.get("partial_export")):
        raise ValueError("NFB live partial manufacturing ports unavailable")
    for bay_index in selected:
        view = report(set_index, bay_index)
        if not isinstance(view, Mapping) or view.get("status") not in (
            "PARTIAL_ONLY", "WHOLE_READY",
        ) or view.get("nfb_config_submitted") is not True:
            raise ValueError("NFB highlighted Bay needs fresh submitted DXF proof")
        rows = tuple(view.get("rows") or ())
        inner = tuple(row for row in rows if isinstance(row, Mapping)
                      and row.get("role") == INNER_DOOR)
        if (len(inner) != 1 or inner[0].get("may_export") is not True
                or inner[0].get("status") != "READY"
                or type(inner[0].get("actual_count")) is not int
                or inner[0]["actual_count"] != 1):
            raise ValueError("NFB highlighted inner-door part is not READY")
        if (view.get("set_id") is None or view.get("bay_id") is None
                or view.get("version_id") is None):
            raise ValueError("NFB Set/Bay/version stable identity unavailable")
    return selected


def export_highlighted_nfb_inner_doors(ports, *, set_index, bay_indices,
                                       output_directory, allow_held=False):
    """All-or-none NFB-only partial DXF batch for real selected Set/Bays.

    The output names are operator locations, NOT substitute physical IDs.
    Returned typed manifests retain their true Set/Bay/version/part owner.
    Never silently skip a held Bay or count it toward CHECK Q. No overwrites.
    """
    requested = _selection(set_index, bay_indices)
    selected = require_highlighted_nfb_inner_doors(
        ports, set_index, requested, allow_held=allow_held,
    )
    current_views = {bi: ports["manifest"](set_index, bi) for bi in requested}
    root = Path(output_directory)
    if not root.is_dir():
        raise ValueError("NFB partial export destination must already exist")
    export = ports["partial_export"]
    staged = []
    with TemporaryDirectory(prefix=".whd-nfb-partial-stage-", dir=root) as temp:
        stage = Path(temp)
        # Detect destination collisions BEFORE writing any manufactured DXF.
        destinations = tuple(
            root / f"nfb_set{set_index + 1}_bay{bi + 1}_inner_partial.dxf"
            for bi in selected
        )
        report_destination = root / f"nfb_set{set_index + 1}_partial_manifest.json"
        publication_targets = (*destinations, report_destination) if allow_held else destinations
        if any(path.exists() or path.is_symlink() for path in publication_targets):
            raise FileExistsError("NFB partial DXF destination already exists")
        for bi, destination in zip(selected, destinations):
            source = stage / destination.name
            written, manifest = export(set_index, bi, source)
            if not isinstance(manifest, NfbPartialExportManifest):
                raise ValueError("NFB partial DXF needs a live typed manifest")
            expected = current_views[bi]
            if manifest.scope.identity != (
                    expected.get("set_id"), expected.get("bay_id"), expected.get("version_id")):
                raise ValueError("NFB writer Set/Bay/version ownership changed")
            manifest.require_export((manifest.scope.inner_door_part_id,), partial=True)
            if (manifest.scope.submitted is not True
                    or manifest.scope.inner_door_part_id not in
                    manifest.authorized_part_ids
                    or any(row.actual_count != 1 for row in manifest.rows
                           if row.part_id == manifest.scope.inner_door_part_id)
                    or manifest.actual_export_count != 1):
                raise ValueError("NFB partial DXF manufactured part count invalid")
            if (Path(written) != source or source.is_symlink()
                    or not source.is_file()):
                raise ValueError("NFB writer did not create expected staged DXF")
            staged.append((source, destination, manifest))
        report_source = None
        if allow_held:
            held = []
            for bi in requested:
                if bi in selected:
                    continue
                view = current_views[bi]
                held.append({
                    "set_index": set_index, "bay_index": bi,
                    "set_id": view.get("set_id"), "bay_id": view.get("bay_id"),
                    "version_id": view.get("version_id"),
                    "status": "NOT_EXPORTED",
                    "reason": view.get("reason") or "Inner-door manufacturing proof not READY",
                    "physical_rows": view.get("rows", ()),
                    "unresolved_dependencies": view.get("unresolved_dependencies", ()),
                })
            report_source = stage / report_destination.name
            report_source.write_text(json.dumps({
                "whole_cabinet_complete": False,
                "actual_export_count": len(staged),
                "exported": [manifest.report() for _, _, manifest in staged],
                "not_exported_bays": held,
                "deferred_assembly": ["PAD", "EAR_ATTACHMENT"],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        # Hard links in the same directory/filesystem provide exclusive,
        # no-overwrite publication. Roll back on a collision or IO failure.
        published = []
        try:
            for source, destination, _ in staged:
                os.link(source, destination)
                published.append(destination)
            if report_source is not None:
                os.link(report_source, report_destination)
                published.append(report_destination)
        except OSError:
            for destination in reversed(published):
                destination.unlink()
            raise
        return tuple((str(dest), manifest) for _, dest, manifest in staged)
