# -*- coding: utf-8 -*-
"""Engine-owned physical quantity equivalence and source-verified NFB CHECK/Q.

Moved unchanged from Phase6's old manufacturing presentation/orchestration
module. The old Phase6 imports are compatible read-only facades. This module
does not open Tk, infer a manufacturer rule, or relax NFB source verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from .manufacturing_value_thaw import thaw_manufacturing_value

@dataclass(frozen=True)
class QuantityManufacturingBatch:
    versions: tuple
    demands: tuple
    requests: tuple

def quantity_manufacturing_groups(batch, *, demands=None):
    """Project the existing typed request parameters into physical equivalence."""
    from .manufacturing_equivalence import ManufacturingParameters, group_quantity_physical_demands
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
    return group_quantity_physical_demands(
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
    from .manufacturing_quantity import PhysicalPartDemand
    from .receiving_nfb_export_manifest import NfbPartialExportManifest
    from .receiving_nfb_quantity_gate import (
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

