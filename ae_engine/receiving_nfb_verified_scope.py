# -*- coding: utf-8 -*-
"""#2517: Engine-owned exact Receiving V5 pair evidence and transient display scope.

A real saved-and-reopened part-only DXF pair is a required input witness from
the existing exporter. The returned label is ONLY disclosure for that historical
output, never a source of further CUTTING, DXF, welding or whole-cabinet approval.
Engine recomputes the original submitted Set/Bay/physical-site identity and
rechecks source CSV and output bytes on every label read; no GUI reverse import.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Mapping

from .receiving_nfb_model_identity import parse_numeric_model_ref
from .receiving_nfb_numeric_catalog import brand_csv_path


@dataclass(frozen=True)
class NfbCsvVerifiedPhysicalSite:
    physical_hole_id: str
    model_ref: str
    world_x_mm: float
    world_y_mm: float
    rotation_deg: int
    tier_index: int


@dataclass(frozen=True)
class NfbCsvVerifiedExportScope:
    """Returned only after the exact real part-only pair output passes."""
    set_id: str
    bay_id: str
    width_mm: float
    inner_door_id: str
    sites: tuple[NfbCsvVerifiedPhysicalSite, ...]

    @property
    def operator_label(self):
        rows = "；".join(
            f"{site.model_ref} X={site.world_x_mm:g} Y={site.world_y_mm:g}"
            f" R={site.rotation_deg}°"
            for site in self.sites
        )
        return (
            f"可製造（內門）｜僅本次真實出圖已驗證 "
            f"Set={self.set_id} Bay={self.bay_id} "
            f"W={self.width_mm:g} N={len(self.sites)}：{rows}。"
            "其他版本／位置／型號及 PAD／整箱未放行。"
        )


def resolve_verified_csv_v5_export_scope(snapshot, inner_door_id, holes):
    """Exact current Set/Bay/NFBConfig source scope, not model-wide approval."""
    from math import isfinite
    from ae_engine.receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    from ae_engine.receiving_nfb_model_identity import selected_numeric_spec

    selector = snapshot.get("_receiving_runtime_selection")
    if not isinstance(selector, Mapping):
        raise ValueError("CSV_EXPORT_EXACT_SET_BAY_REQUIRED")
    set_id, bay_id = selector.get("set_id"), selector.get("bay_id")
    if not all(isinstance(x, str) and x for x in (set_id, bay_id)):
        raise ValueError("CSV_EXPORT_EXACT_SET_BAY_REQUIRED")
    raw_w = snapshot.get("w")
    if type(raw_w) not in (int, float) or not isfinite(raw_w) or raw_w <= 0:
        raise ValueError("CSV_EXPORT_WIDTH_SOURCE_REQUIRED")
    if not holes:
        raise ValueError("CSV_EXPORT_HOLE_SOURCE_REQUIRED")
    sites = []
    for hole in holes:
        spec = selected_numeric_spec(hole.brand, hole.model_ref)
        if spec is None or not spec.dimensionally_complete:
            raise ValueError("CSV_EXPORT_NUMERIC_MODEL_SOURCE_REQUIRED")
        if not isfinite(hole.world_x_mm):
            raise ValueError("CSV_EXPORT_CONFIRMED_WORLD_X_REQUIRED")
        projected = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id,
            layer_count=hole.layer_count, slot_index=hole.slot_index,
        )
        if not isfinite(projected.box_world_y_mm):
            raise ValueError("CSV_EXPORT_CONFIRMED_WORLD_Y_REQUIRED")
        sites.append(NfbCsvVerifiedPhysicalSite(
            physical_hole_id=hole.physical_hole_id,
            model_ref=hole.model_ref,
            world_x_mm=float(hole.world_x_mm),
            world_y_mm=float(projected.box_world_y_mm),
            rotation_deg=hole.rotation_deg, tier_index=hole.slot_index,
        ))
    if len({r.physical_hole_id for r in sites}) != len(sites):
        raise ValueError("CSV_EXPORT_DUPLICATE_PHYSICAL_HOLE")
    return NfbCsvVerifiedExportScope(
        set_id=set_id, bay_id=bay_id, width_mm=float(raw_w),
        inner_door_id=inner_door_id, sites=tuple(sites),
    )



def _snapshot_digest(snapshot):
    # A change ANYWHERE in the current authority invalidates the UI label.
    # Non-JSON snapshots intentionally fail closed rather than inventing a
    # less-complete derived NFBConfig/signoff token.
    try:
        serialized = json.dumps(
            snapshot, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError):
        return None
    return sha256(serialized.encode("utf-8")).hexdigest()


def _source_hashes(scope):
    refs = {parse_numeric_model_ref(site.model_ref) for site in scope.sites}
    if None in refs:
        return None
    try:
        return tuple(
            (brand, sha256(brand_csv_path(brand).read_bytes()).hexdigest())
            for brand in sorted({brand for brand, _ in refs})
        )
    except (OSError, ValueError):
        return None


def _output_hashes(paths):
    if not paths or len(paths) != len(set(paths)):
        return None
    try:
        return tuple(
            (str(Path(path).resolve(strict=True)),
             sha256(Path(path).read_bytes()).hexdigest())
            for path in paths
            if Path(path).is_file()
        )
    except (OSError, ValueError, TypeError):
        return None



@dataclass(frozen=True)
class NfbCsvVerifiedSelectorProof:
    """Ephemeral original-pair proof; never serialize in a .p6fold project."""
    scope: NfbCsvVerifiedExportScope
    snapshot_sha256: str
    source_shas: tuple[tuple[str, str], ...]
    generated_output_shas: tuple[tuple[str, str], ...]


def capture_verified_csv_v5_pair_display_proof(
    snapshot, scope, output_paths, source_hole_ids,
) -> NfbCsvVerifiedSelectorProof | None:
    """Validate a typed export's actual paths/scope against *current* Engine source.

    The GUI exporter must first verify receipt TYPE and supply the exact real
    part-only paths; no ad-hoc caller can use this display DTO to authorize MFG.
    """
    if not isinstance(snapshot, Mapping) or type(scope) is not NfbCsvVerifiedExportScope:
        return None
    paths = tuple(output_paths or ())
    if len(paths) not in (2, 3) or any(not isinstance(p, (str, Path)) for p in paths):
        return None
    digest = _snapshot_digest(snapshot)
    source_hashes = _source_hashes(scope)
    output_hashes = _output_hashes(paths)
    if (digest is None or source_hashes is None or output_hashes is None
            or len(paths) != len(output_hashes)):
        return None
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes
    try:
        original = _submitted_csv_holes(snapshot)
        if not original or resolve_verified_csv_v5_export_scope(
            snapshot, *original,
        ) != scope:
            return None
        if tuple(site.physical_hole_id for site in scope.sites) != tuple(source_hole_ids):
            return None
    except (ValueError, KeyError, TypeError, IndexError):
        return None
    return NfbCsvVerifiedSelectorProof(scope, digest, source_hashes, output_hashes)


def verified_csv_v5_operator_label(proof, snapshot, brand, model_ref):
    """Return the historical scope label ONLY while every exact witness survives."""
    if type(proof) is not NfbCsvVerifiedSelectorProof:
        return None
    if not isinstance(snapshot, Mapping) or not isinstance(model_ref, str):
        return None
    model = parse_numeric_model_ref(model_ref)
    if model is None or model[0] != brand:
        return None
    if not any(site.model_ref == model_ref for site in proof.scope.sites):
        return None
    if _snapshot_digest(snapshot) != proof.snapshot_sha256:
        return None
    if _source_hashes(proof.scope) != proof.source_shas:
        return None
    paths = tuple(path for path, _ in proof.generated_output_shas)
    if _output_hashes(paths) != proof.generated_output_shas:
        return None
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes
    try:
        current = _submitted_csv_holes(snapshot)
        if not current or resolve_verified_csv_v5_export_scope(
            snapshot, *current,
        ) != proof.scope:
            return None
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    return proof.scope.operator_label
