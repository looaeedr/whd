# -*- coding: utf-8 -*-
"""#1504 AC51/SWT30: ephemeral evidence for an EXACT successful CSV V5 pair export.

A model shown in the catalogue is always preview-only.  A positive label is
only a description of a previously successful, operator-requested, physically
validated and reopened current pair output.  It is not a manufacturing gate,
stored approval, substitute exporter, or permission for the next click.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from ae_engine.receiving_nfb_model_identity import parse_numeric_model_ref
from ae_engine.receiving_nfb_numeric_catalog import brand_csv_path
from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
from .receiving_nfb_pair_partial_export_action import (
    NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
    NfbCsvVerifiedExportScope, _verified_csv_v5_export_scope,
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


def _output_paths(receipt):
    if type(receipt) is NfbCsvPairedPartOnlyDxf:
        return (receipt.inner_door_path, receipt.base_plate_path)
    if type(receipt) is NfbCsvTwoTierPartOnlyDxf:
        return (receipt.inner_door_path, *receipt.base_plate_paths)
    return ()


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
    """In-memory receipt only; never store in .p6fold or reuse for export."""
    scope: NfbCsvVerifiedExportScope
    snapshot_sha256: str
    source_shas: tuple[tuple[str, str], ...]
    generated_output_shas: tuple[tuple[str, str], ...]


def capture_verified_v5_pair_display(snapshot, receipt):
    """Accept only real typed post-export receipts with physical output files."""
    if not isinstance(snapshot, Mapping) or type(receipt) not in (
        NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
    ):
        return None
    scope = receipt.verified_v5_scope
    if type(scope) is not NfbCsvVerifiedExportScope:
        return None
    digest = _snapshot_digest(snapshot)
    source_hashes = _source_hashes(scope)
    paths = _output_paths(receipt)
    output_hashes = _output_hashes(paths)
    if (digest is None or source_hashes is None or output_hashes is None
            or len(paths) != len(output_hashes)):
        return None
    try:
        original = _submitted_csv_holes(snapshot)
        if not original or _verified_csv_v5_export_scope(
            snapshot, *original
        ) != scope:
            return None
        if tuple(site.physical_hole_id for site in scope.sites) != (
            receipt.source_hole_ids
        ):
            return None
    except (ValueError, KeyError, TypeError, IndexError):
        return None
    return NfbCsvVerifiedSelectorProof(
        scope, digest, source_hashes, output_hashes,
    )


def verified_v5_model_operator_label(proof, snapshot, brand, model_ref):
    """Return a positive *historic scope disclosure* only if still exact.

    Always fail to preview-only on source, project, Bay, X/Y, rotation,
    model, material/settings, actual DXF output or editor identity drift.
    This is not current manufacturing approval and cannot authorize exports.
    """
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
    try:
        current = _submitted_csv_holes(snapshot)
        if not current or _verified_csv_v5_export_scope(
            snapshot, *current
        ) != proof.scope:
            return None
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    return proof.scope.operator_label
