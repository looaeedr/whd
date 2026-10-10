"""Read-only quantity manufacturing boundary around the existing resolver."""
from copy import deepcopy
from dataclasses import dataclass, replace

from ae_engine import manufacturing_api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.manufacturing_quantity import ResolvedQuantityVersion
from ae_engine.receiving_quantity_box import require_valid_quantity_features
from phase6_manufacturing_contracts import (
    manufacturing_request_fingerprint, thaw_manufacturing_value,
)
from phase6_quantity_model import QuantityModel


@dataclass(frozen=True)
class QuantityManufacturingBatch:
    versions: tuple
    demands: tuple
    requests: tuple


def build_quantity_manufacturing_requests(base_request, workspace_snapshot):
    """Materialize versions from immutable request data and a workspace snapshot."""
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
    if source["model"] == "受電箱":
        from ae_engine.receiving_quantity_box import project_common_box
        source = project_common_box(source)
    base = base_request
    requests = []
    for row in owner.snapshot()["versions"]:
        version_id = row["version_id"]
        selected = QuantityModel.from_payload(owner.snapshot())
        selected.select(version_id)
        snapshot = deepcopy(source)
        snapshot["quantity"] = selected.snapshot()
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
            render = manufacturing_api.build_part_render_data(spec, part.manufacturing_context)
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


def resolve_quantity_manufacturing(base_request, workspace_snapshot):
    """Produce demand for export/BOM consumers without applying resolver effects."""
    import phase6_manufacturing_service as service
    requests = build_quantity_manufacturing_requests(base_request, workspace_snapshot)
    versions = tuple(
        ResolvedQuantityVersion(version_id, count, service.resolve(request).geometry)
        for version_id, count, request in requests
    )
    # Stable identity and multiplicity come from the persisted custom catalog.
    # Removed/disabled metadata cannot create an inventory row on its own.
    counts = {
        key: row["per_box_count"]
        for key, row in (workspace_snapshot.get("custom_parts") or {}).get("items", {}).items()
    }
    demands = manufacturing_api.resolved_quantity_physical_demands(
        versions, per_box_counts=counts
    )
    return QuantityManufacturingBatch(versions, demands, requests)
