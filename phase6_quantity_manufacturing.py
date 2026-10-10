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



def quantity_manufacturing_groups(batch, *, demands=None):
    """Project the existing typed request parameters into physical equivalence."""
    from ae_engine.manufacturing_equivalence import ManufacturingParameters
    parameters = {}
    parameter_keys = ("material", "material_name", "material_grade", "process",
                      "process_parameters", "manufacturing_process")
    for version_id, _, request in batch.requests:
        source = thaw_manufacturing_value(request.input_snapshot)
        settings = thaw_manufacturing_value(request.settings)
        parts = {part.part_key: part for part in request.parts}
        for row in batch.demands:
            if row.version_id != version_id:
                continue
            part = parts.get(row.source_part_id)
            spec = part.part_spec if part is not None else None
            values = thaw_manufacturing_value(part.scene_values) if part is not None else {}
            metadata = dict(getattr(row.render_data, "metadata", {}) or {})
            supplied = {
                owner: {key: value[key] for key in parameter_keys if key in value}
                for owner, value in (("input", source), ("settings", settings),
                                     ("part", values), ("resolved", metadata))
            }
            thickness = getattr(spec, "thickness", None)
            if thickness is None:
                thickness = settings.get("t", source.get("t"))
            if thickness is None:
                raise ValueError(f"canonical thickness unavailable: {row.source_part_id}")
            context = part.manufacturing_context if part is not None else None
            profile = tuple(getattr(spec, "fold_profile", ()) or ())
            # Core/editor keys are transport anchors, not machining commands.
            fold_commands = tuple((segment.length, segment.angle, segment.formed_length)
                                  for segment in profile)
            parameters[(version_id, row.source_part_id)] = ManufacturingParameters(
                material=supplied,
                thickness=thickness,
                process=dict(
                    settings=settings, policy=getattr(context, "policy", None),
                    fold_commands=fold_commands, fold_axis=getattr(spec, "fold_axis", None),
                    x_profile=part.x_profile if part is not None else (),
                    y_profile=part.y_profile if part is not None else (),
                ),
            )
    return manufacturing_api.group_quantity_physical_demands(
        batch.demands if demands is None else demands, parameters)
