# -*- coding: utf-8 -*-
"""Engine-owned Quantity version request replay and physical-demand orchestration.

All selected-version NFB/Head/Tail sources, PartSpec render replay, immutable
request fingerprints and PAD physical BOM duplication checks stay in Engine.
No GUI/Phase6 import, Tk ownership, DXF certification or extra exporter.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from .cabinet_types.policy import canonical_family_name
from .contracts import EndCapPartSpec
from .manufacturing_contracts import manufacturing_request_fingerprint, thaw_manufacturing_value
from .manufacturing_quantity import ResolvedQuantityVersion
from .quantity_manufacturing_groups import QuantityManufacturingBatch
from .receiving_quantity_box import project_common_box, require_valid_quantity_features
from .receiving_quantity_versions import QuantityModel
from .receiving_layout import project_receiving_bay_legacy_aliases
from .receiving_nfb_pad_delivery import pad_bom_demands_from_committed_snapshot


def build_operator_quantity_manufacturing_requests(base_request, workspace_snapshot):
    """Materialize versions from immutable request data and a workspace snapshot."""
    from .manufacturing_api import build_part_render_data
    live = deepcopy(workspace_snapshot)
    if live.get("active_mode") != "quantity" or not live.get("quantity"):
        raise ValueError("quantity manufacturing requires active quantity mode")
    source = thaw_manufacturing_value(base_request.input_snapshot)
    source.update(live)
    source.update(thaw_manufacturing_value(base_request.settings))
    source.update(thaw_manufacturing_value(base_request.box_dimensions))
    source["model"] = base_request.cabinet_model
    require_valid_quantity_features(source)
    owner = QuantityModel.from_payload(live["quantity"])
    if canonical_family_name(source) == "受電箱":
        source = project_common_box(source)
    base = base_request
    requests = []
    for row in owner.snapshot()["versions"]:
        version_id = row["version_id"]
        selected = QuantityModel.from_payload(owner.snapshot())
        selected.select(version_id)
        snapshot = deepcopy(source)
        snapshot["quantity"] = selected.snapshot()
        if canonical_family_name(snapshot) == "受電箱":
            # Rebuild the SOURCE-owned singleton Bay for THIS version.
            # Previously only the initial selected version was projected
            # before the loop, and all later versions could borrow its NFB
            # model/holes when manufacturing the same common box.
            snapshot = project_common_box(snapshot)
            snapshot = project_receiving_bay_legacy_aliases(
                snapshot, set_index=0, bay_index=0,
            )
        snapshot["part_features"] = deepcopy(snapshot.get("part_features") or {})
        parts = []
        for part in base.parts:
            if part.part_key not in {"head", "tail"}:
                parts.append(part)
                continue
            features = tuple(selected.features_for(part.part_key))
            if not isinstance(part.part_spec, EndCapPartSpec):
                raise ValueError(f"canonical EndCap PartSpec unavailable: {part.part_key}")
            # Keep every shared Fold/policy/relief input; only typed holes vary.
            spec = replace(part.part_spec, holes=features)
            render = build_part_render_data(spec, part.manufacturing_context)
            values = thaw_manufacturing_value(part.scene_values)
            values["features"] = features
            values["quantity"] = selected.snapshot()
            snapshot["part_features"][part.part_key] = list(features)
            parts.append(replace(
                part, scene_values=values, features=features, part_spec=spec,
                render_data=render, committed_render_data=render,
            ))
        request = replace(
            base, input_snapshot=snapshot, parts=tuple(parts),
            source_fingerprint="", cache_key_fingerprint="",
        )
        request = replace(request, source_fingerprint=manufacturing_request_fingerprint(request))
        requests.append((version_id, row["piece_count"], request))
    return tuple(requests)


def resolve_operator_quantity_manufacturing_batch(base_request, workspace_snapshot, *, resolve_request):
    """Produce demand for export/BOM consumers without applying resolver effects."""
    if not callable(resolve_request):
        raise TypeError("resolve_request must be callable")
    from .manufacturing_api import resolved_quantity_physical_demands
    requests = build_operator_quantity_manufacturing_requests(base_request, workspace_snapshot)
    versions = tuple(
        ResolvedQuantityVersion(version_id, count, resolve_request(request).geometry)
        for version_id, count, request in requests
    )
    # Stable identity and multiplicity come from the persisted custom catalog.
    # Removed/disabled metadata cannot create an inventory row on its own.
    counts = {
        key: row["per_box_count"]
        for key, row in (workspace_snapshot.get("custom_parts") or {}).get("items", {}).items()
    }
    demands = resolved_quantity_physical_demands(
        versions, per_box_counts=counts
    )
    if canonical_family_name(base_request.cabinet_model) == "受電箱":
        # PAD is a physical sheet, not an ephemeral 3D preview. Preserve one
        # genuine per-owner item in each version's BOM with the version box
        # multiplicity. Never manufacture it here: the canonical DXF PAD gate
        # still rejects trial-only parts until full T2 contact is certified.
        pad_demands=[]
        for version_id, piece_count, request in requests:
            # build_quantity_manufacturing_requests already supplies a
            # detached version-specific dict. Thawing it would coerce source
            # integer Set/Bay indices to floats (e.g. 0 -> 0.0), which
            # violates canonical receiving scope identity.
            payload=request.input_snapshot
            source=(deepcopy(payload) if isinstance(payload,dict)
                    else thaw_manufacturing_value(payload))
            pad_demands.extend(pad_bom_demands_from_committed_snapshot(
                version_id,source,piece_count=piece_count))
        seen={(row.version_id,row.physical_id) for row in demands}
        if any((row.version_id,row.physical_id) in seen for row in pad_demands):
            raise ValueError("PAD_QUANTITY_BOM_DUPLICATE_PHYSICAL_SOURCE")
        demands=tuple(demands)+tuple(pad_demands)
    return QuantityManufacturingBatch(versions, demands, requests)
