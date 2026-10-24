# -*- coding: utf-8 -*-
"""Source-verified per-version physical demands for the existing CHECK writer."""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path
from typing import Mapping

from ae_engine.cabinet_types import policy
from ae_engine.receiving_nfb_cutting_manufacturing import read_nfb_runtime_source_profiles_csv
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole, NfbValidatedInnerDoorRender, X_REVISION, configured_nfb_inner_door_render_data,
)
from ae_engine.receiving_nfb_persistence import normalize_nfb_saved_fields
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_2d_preview import resolve_indexed_dxf_path
from ae_engine.receiving_switch_model_catalog import INDEX_PATH
from phase6_manufacturing_contracts import thaw_manufacturing_value
from phase6_quantity_model import QuantityModel


@dataclass(frozen=True)
class QuantityNfbPartialSelection:
    demands: tuple
    rows: tuple
    deferred_assembly: tuple = ("PAD", "EAR_ATTACHMENT")

    @property
    def held_piece_count(self):
        return sum(row["actual_count"] for row in self.rows if not row["may_export"])

    @property
    def exported_piece_count(self):
        return sum(d.quantity for d in self.demands)

    def report(self):
        return {
            "kind": "NFB_QUANTITY_PARTIAL_MANUFACTURING",
            "whole_cabinet_complete": False,
            "actual_export_count": self.exported_piece_count,
            "held_actual_count": self.held_piece_count,
            "deferred_assembly": list(self.deferred_assembly),
            "rows": list(self.rows),
        }


def verify_quantity_nfb_inner_door(version, snapshot, *, index_path=INDEX_PATH,
                                   profile_path=None):
    """Rebuild from current original bytes and operator datum, never saved READY."""
    saved = normalize_nfb_saved_fields(version)
    holes = saved["nfb_config"]["holes"]
    panels = tuple(policy.derive_inner_door_panels(snapshot))
    referenced = {hole["datum_snapshot"].get("part_id") for hole in holes}
    matched = tuple(panel for panel in panels if panel.stable_id in referenced)
    if len(referenced) != 1 or len(matched) != 1:
        raise ValueError("NFB version has no unique current physical inner-door datum")
    panel = matched[0]
    keys = {(hole.get("source_brand"), hole["model_filename"]) for hole in holes}
    if len(keys) != 1:
        raise ValueError("NFB version needs one verified source brand/model")
    brand, filename = next(iter(keys))
    if not brand:
        raise ValueError("NFB version source brand missing")
    index = Path(index_path)
    profiles = read_nfb_runtime_source_profiles_csv(
        Path(profile_path) if profile_path else index.parent / "來源輪廓索引.csv"
    )
    matches = tuple(p for p in profiles if
                    (p.brand, p.indexed_filename.casefold()) == (brand, filename.casefold()))
    if len(matches) != 1:
        raise ValueError("NFB version source profile missing or ambiguous")
    profile = matches[0]
    for hole in holes:
        datum = hole["datum_snapshot"]
        if (hole["manual_x_state"] != "CONFIRMED"
                or hole["datum_revision"] != X_REVISION
                or datum.get("part_id") != panel.stable_id
                or datum.get("inner_door_id") != panel.inner_door_id
                or datum.get("cell_key") != panel.cell_key
                or datum.get("profile_revision") != profile.revision
                or any(
                    isinstance(datum.get(k), bool)
                    or not isinstance(datum.get(k), (int, float))
                    or isinstance(snapshot.get(k), bool)
                    or not isinstance(snapshot.get(k), (int, float))
                    or not isfinite(float(datum[k]))
                    or not isfinite(float(snapshot[k]))
                    or abs(float(datum[k]) - float(snapshot[k])) > 1e-6
                    for k in ("w", "h", "t")
                )):
            raise ValueError("NFB version datum changed; source/coordinates need revalidation")
    ready = configured_nfb_inner_door_render_data(
        snapshot, panel.inner_door_id,
        holes=tuple(NfbConfiguredInnerDoorHole(
            hole["physical_hole_id"], hole["manual_x_mm"],
            hole["layer_count"], hole["slot_index"], hole["rotation_deg"],
        ) for hole in holes),
        index_path=index,
        source_path=resolve_indexed_dxf_path(brand, filename, index_path=index),
        profile=profile,
    )
    return ready


def _independent(source_id):
    # Only existing physical Receiving roles whose machining does not consume
    # NFB inner-door/base profiles. Custom/unrecognized sheets remain held.
    return (source_id in {"head", "tail", "box_body:left_side",
                          "box_body:right_side", "box_body:back"}
            or source_id == "indicator_box" or source_id == "indicator_door"
            or source_id.startswith(("indicator_box_", "indicator_door_")))


def select_quantity_nfb_partial(batch, workspace_snapshot, *,
                                verifier=None):
    """Keep unconfigured versions intact; hold only submitted dependent pieces.

    Actual physical inventory, stable IDs and multiplicities come exclusively
    from the canonical quantity batch. The existing equivalence engine owns Q.
    """
    verifier = verifier or verify_quantity_nfb_inner_door
    versions = QuantityModel.from_payload(workspace_snapshot["quantity"]).snapshot()["versions"]
    versions = {row["version_id"]: row for row in versions}
    requests = {vid: request for vid, _count, request in batch.requests}
    if set(versions) != set(requests):
        raise ValueError("NFB quantity batch/version owner mismatch")
    proof = {}
    reasons = {}
    for vid, version in versions.items():
        if version.get("nfb_config_submitted") is not True:
            continue
        try:
            snapshot = thaw_manufacturing_value(requests[vid].input_snapshot)
            ready = verifier(version, snapshot)
            if not isinstance(ready, NfbValidatedInnerDoorRender) or ready.manufacturing_ready is not True:
                raise ValueError("NFB version requires typed live manufacturing proof")
            proof[vid] = ready
        except (ValueError, TypeError, KeyError, IndexError, OSError) as exc:
            reasons[vid] = str(exc)
    selected = []
    reports = []
    seen = set()
    for demand in batch.demands:
        vid = demand.version_id
        version = versions.get(vid)
        if (version is None or (vid, demand.physical_id) in seen
                or type(demand.piece_count) is not int
                or demand.piece_count != version["piece_count"]
                or type(demand.per_box_count) is not int or demand.per_box_count < 1):
            raise ValueError("NFB quantity physical identity/count invalid")
        seen.add((vid, demand.physical_id))
        submitted = version.get("nfb_config_submitted") is True
        ready = proof.get(vid)
        topology = getattr(demand.render_data, "unfolded_topology", None)
        actual_id = getattr(topology, "piece_id", None) or demand.physical_id
        part_proof = ready is not None and ready.part_id == actual_id
        if part_proof:
            snapshot = thaw_manufacturing_value(requests[vid].input_snapshot)
            panels = tuple(p for p in policy.derive_inner_door_panels(snapshot)
                           if p.stable_id == actual_id)
            if len(panels) != 1:
                raise ValueError("NFB canonical panel identity is not unique")
            baseline = build_inner_door_panel_render_data(panels[0])
            if tuple(demand.render_data.scene.primitives) != tuple(baseline.scene.primitives):
                part_proof = False
                reasons[vid] = "Existing physical machining needs explicit NFB ownership reconciliation"
        allowed = not submitted or _independent(demand.source_part_id) or part_proof
        reason = ""
        status = "UNCONFIGURED_LEGACY" if not submitted else "UNAFFECTED"
        if part_proof:
            demand = replace(demand, render_data=ready.render_data)
            status = "READY"
        elif not allowed:
            status = "BLOCKED"
            reason = reasons.get(vid, "NFB dependent physical sheet not manufacturing-verified")
        if allowed:
            selected.append(demand)
        reports.append({
            "version_id": vid, "part_id": demand.physical_id,
            "physical_part_id": actual_id,
            "source_part_id": demand.source_part_id,
            "source_dependencies": [
                {key: hole.get(key) for key in (
                    "physical_hole_id", "source_brand", "model_filename",
                    "manual_x_state", "datum_revision",
                )}
                for hole in ((version.get("nfb_config") or {}).get("holes") or ())
                if isinstance(hole, Mapping)
            ] if submitted and not _independent(demand.source_part_id) else [],
            "status": status, "may_export": allowed, "reason": reason,
            "per_box_count": demand.per_box_count,
            "piece_count": demand.piece_count, "actual_count": demand.quantity,
        })
    # A source proof must match an ACTUAL canonical sheet. Never turn an
    # unrelated/absent panel into a manufactured inventory row.
    for vid, ready in proof.items():
        matches = [row for row in reports if row["version_id"] == vid
                   and row["physical_part_id"] == ready.part_id]
        if len(matches) != 1:
            raise ValueError("NFB verified part absent/ambiguous in canonical inventory")
    return QuantityNfbPartialSelection(tuple(selected), tuple(reports))


def quantity_partial_live_manifests(selection, workspace_snapshot, selected_rows):
    """Adapt freshly verified machining facts to the shared #1501 CHECK gate.

    These rows originate only from select_quantity_nfb_partial in this action,
    not from persisted/UI reports. Quantity has no synthetic Set/Bay IDs.
    """
    from ae_engine.receiving_nfb_export_manifest import (
        NfbPartialExportManifest, NfbManifestRow, INNER_DOOR, BASE_PLATE, OTHER,
    )
    from ae_engine.receiving_nfb_part_readiness import NfbQuantityPhysicalScope
    versions = {v["version_id"]: v for v in
                QuantityModel.from_payload(workspace_snapshot["quantity"]).snapshot()["versions"]}
    result = {}
    for vid, version in versions.items():
        rows = tuple(row for row in selected_rows if row["version_id"] == vid)
        if not rows:
            continue
        submitted = version.get("nfb_config_submitted") is True
        inner_ids = tuple(row["part_id"] for row in selection.rows
                          if row["version_id"] == vid
                          and row["source_part_id"].startswith("inner_door:"))
        bases = tuple(row["part_id"] for row in rows
                      if row["source_part_id"] == "base_plate"
                      or row["source_part_id"].startswith(("base_plate_", "base_plate:")))
        datum_ids = {
            hole["datum_snapshot"].get("part_id")
            for hole in ((version.get("nfb_config") or {}).get("holes") or ())
            if isinstance(hole, Mapping) and isinstance(hole.get("datum_snapshot"), Mapping)
        }
        targets = tuple(row["part_id"] for row in selection.rows
                        if row["version_id"] == vid
                        and row["physical_part_id"] in datum_ids
                        and row["part_id"] in inner_ids)
        scope = NfbQuantityPhysicalScope(None, None, vid, submitted,
                                        targets[0] if len(targets) == 1 else None,
                                        base_plate_part_ids=bases)
        typed_rows = tuple(NfbManifestRow(
            *scope.identity, row["part_id"],
            INNER_DOOR if row["source_part_id"].startswith("inner_door:") else
            BASE_PLATE if row["part_id"] in bases else OTHER,
            row["status"], (row["reason"],) if row["reason"] else (),
            row["per_box_count"], row["may_export"],
        ) for row in rows)
        result[vid] = (NfbPartialExportManifest(
            scope, typed_rows,
            ("NFB_FULL_ASSEMBLY_NOT_RELEASED",) if submitted else (),
            submitted, not submitted,
        ),)
    return result
