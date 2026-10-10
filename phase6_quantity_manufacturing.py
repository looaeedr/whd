"""Read-only quantity manufacturing boundary around the existing resolver."""
from copy import deepcopy
from dataclasses import dataclass, replace

from ae_engine import manufacturing_api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.manufacturing_quantity import ResolvedQuantityVersion
from ae_engine.receiving_quantity_box import require_valid_quantity_features
from phase6_manufacturing_adapter import (
    build_manufacturing_request, build_scene_payload_for_app,
    operator_finished_dimensions_for_app,
)
from phase6_manufacturing_contracts import (
    manufacturing_request_fingerprint, thaw_manufacturing_value,
)
from phase6_quantity_model import QuantityModel


@dataclass(frozen=True)
class QuantityManufacturingBatch:
    versions: tuple
    demands: tuple
    requests: tuple


def build_quantity_manufacturing_requests(app):
    """Materialize every version without changing selection or GUI/cache state."""
    workspace = app.designer_workspace
    live = workspace.snapshot()
    if live.get("active_mode") != "quantity" or workspace.quantity_model is None:
        raise ValueError("quantity manufacturing requires active quantity mode")
    source = deepcopy(app._phase6_input_snapshot)
    source.update(live)
    source.update(deepcopy(app._settings_values))
    source.update(deepcopy(app._phase6_box_whd))
    source["model"] = app.baseline_model_var.get()
    require_valid_quantity_features(source)
    owner = QuantityModel.from_payload(live["quantity"])
    if source["model"] == "受電箱":
        from ae_engine.receiving_quantity_box import project_common_box
        source = project_common_box(source)
        # The official quantity projection is an independent 1 Set / 1 Bay.
        # Historical Receiving topology is never an input to this batch.
    render_provider = getattr(app, "_scene_query_callback", None)
    spec_provider = getattr(app, "_part_spec_query_callback", None)
    if not callable(render_provider) or not callable(spec_provider):
        raise RuntimeError("quantity manufacturing providers are not connected")
    base = build_manufacturing_request(
        app,
        scene_payload_builder=lambda key: build_scene_payload_for_app(app, key),
        render_data_provider=render_provider,
        part_spec_provider=spec_provider,
        finished_dimensions_provider=lambda key=None: operator_finished_dimensions_for_app(app, key),
    )
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


def resolve_quantity_manufacturing_for_app(app):
    """Produce demand for export/BOM consumers without applying resolver effects."""
    import phase6_manufacturing_service as service
    requests = build_quantity_manufacturing_requests(app)
    versions = tuple(
        ResolvedQuantityVersion(version_id, count, service.resolve(request).geometry)
        for version_id, count, request in requests
    )
    workspace = app.designer_workspace
    # Stable identity and multiplicity come from the persisted custom catalog.
    # Removed/disabled metadata cannot create an inventory row on its own.
    counts = {
        key: row["per_box_count"]
        for key, row in (workspace.snapshot().get("custom_parts") or {}).get("items", {}).items()
    }
    demands = manufacturing_api.resolved_quantity_physical_demands(
        versions, per_box_counts=counts
    )
    return QuantityManufacturingBatch(versions, demands, requests)
