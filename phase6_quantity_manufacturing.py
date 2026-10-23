# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

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
    if source["model"] in ("受電箱", "RECEIVING"):
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
        if snapshot["model"] in ("受電箱", "RECEIVING"):
            # Rebuild the SOURCE-owned singleton Bay for THIS version.
            # Previously only the initial selected version was projected
            # before the loop, and all later versions could borrow its NFB
            # model/holes when manufacturing the same common box.
            from ae_engine.receiving_quantity_box import project_common_box
            from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
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
    if base_request.cabinet_model in ("受電箱", "RECEIVING"):
        # PAD is a physical sheet, not an ephemeral 3D preview. Preserve one
        # genuine per-owner item in each version's BOM with the version box
        # multiplicity. Never manufacture it here: the canonical DXF PAD gate
        # still rejects trial-only parts until full T2 contact is certified.
        from ae_engine.receiving_nfb_pad_delivery import (
            pad_bom_demands_from_committed_snapshot,
        )
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


def quantity_nfb_checked_manufacturing_groups(
    batch, *, live_manifest_provider, partial,
):
    """Join live NFB Set/Bay/version proof to CANONICAL quantity CHECK/Q.

    Each QuantityModel version is supplied with the *CURRENT* NFB per-part
    manifest(s) by the caller's source/geometry-verifying provider. No cached
    UI report or saved 'READY' flag is accepted as a manufacturing grant.
    Every resolved physical demand, including held parts, must have exactly
    one matching real manifest row before any grouping. The ordinary legacy
    `quantity_manufacturing_groups` path remains unchanged.

    Returns (canonical_groups, actual_gate). Callers must not serialize a
    complete-box delivery claim when gate.partial_only is true.
    """
    from ae_engine.manufacturing_quantity import PhysicalPartDemand
    from ae_engine.receiving_nfb_export_manifest import NfbPartialExportManifest
    from ae_engine.receiving_nfb_quantity_gate import (
        gate_nfb_quantity_physical_demands,
    )

    if not isinstance(batch, QuantityManufacturingBatch):
        raise TypeError("NFB CHECK requires canonical QuantityManufacturingBatch")
    if not callable(live_manifest_provider):
        raise TypeError("NFB CHECK requires a live verified manifest provider")
    if type(partial) is not bool:
        raise TypeError("NFB CHECK partial selection must be boolean")
    versions = tuple(batch.versions)
    requests = tuple(batch.requests)
    demands = tuple(batch.demands)
    if not versions or len(versions) != len(requests) or not demands:
        raise ValueError("NFB CHECK requires complete resolved quantity versions")

    counts = {}
    for version in versions:
        version_id = getattr(version, "version_id", None)
        pieces = getattr(version, "piece_count", None)
        if (not isinstance(version_id, str) or not version_id.strip()
                or version_id in counts
                or type(pieces) is not int or pieces < 1):
            raise ValueError("NFB CHECK quantity version identity/count invalid")
        counts[version_id] = pieces
    request_ids = set()
    manifests = []
    for version_id, piece_count, request in requests:
        if (version_id not in counts or version_id in request_ids
                or type(piece_count) is not int
                or piece_count != counts[version_id]):
            raise ValueError("NFB CHECK request version or quantity mismatch")
        request_ids.add(version_id)
        current = live_manifest_provider(version_id, request)
        if not isinstance(current, (tuple, list)) or not current:
            raise ValueError("NFB CHECK missing live per-Bay manifest for version")
        for manifest in current:
            if (not isinstance(manifest, NfbPartialExportManifest)
                    or manifest.scope.version_id != version_id):
                raise ValueError("NFB CHECK source manifest belongs to wrong version")
            manifests.append(manifest)
    if request_ids != set(counts):
        raise ValueError("NFB CHECK quantity versions are not fully represented")
    expected = []
    for manifest in manifests:
        expected.extend((manifest.scope.version_id, row.part_id)
                        for row in manifest.rows)
    observed = []
    for demand in demands:
        if (not isinstance(demand, PhysicalPartDemand)
                or demand.version_id not in counts
                or type(demand.piece_count) is not int
                or demand.piece_count != counts[demand.version_id]):
            raise ValueError("NFB CHECK resolved demand version/count mismatch")
        observed.append((demand.version_id, demand.physical_id))
    if (len(set(expected)) != len(expected)
            or len(set(observed)) != len(observed)
            or set(expected) != set(observed)):
        raise ValueError(
            "NFB CHECK physical inventory does not match full live manifest"
        )

    gate = gate_nfb_quantity_physical_demands(
        demands, manifests=tuple(manifests), partial=partial,
    )
    groups = quantity_manufacturing_groups(batch, demands=gate.permitted)
    if sum(group.quantity for group in groups) != gate.permitted_total_pieces:
        raise ValueError("NFB CHECK grouped Q not equal to verified physical Q")
    return groups, gate
