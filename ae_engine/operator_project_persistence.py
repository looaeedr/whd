"""Engine authority for persisted Phase6 project schema and Receiving NFB scope.

The GUI file codec owns only JSON / filesystem / operator file selection.
Successful Save/Reload does not certify cutting, assembly or external export.
"""
from __future__ import annotations

from .cabinet_types.receiving import is_receiving_snapshot
from .project_snapshot_state import normalize_project_snapshot_authority
from .receiving_layout import (
    strip_legacy_receiving_aliases,
    project_primary_bay_legacy_aliases,
)
from .receiving_nfb_persistence import contains_submitted_nfb
from .receiving_quantity_versions import normalize_quantity_snapshot


PROJECT_SCHEMA_V1 = "phase6-fold-project-v1"
PROJECT_SCHEMA_V2 = "phase6-fold-project-v2"
PROJECT_SCHEMA_V3 = "phase6-fold-project-v3"


def validate_operator_project_payload(payload, *, for_read=False):
    """Validate persisted project schema against its actual Family/NFB source."""
    if not isinstance(payload, dict):
        raise ValueError("Phase6 專案必須是 JSON 物件")
    schema = payload.get("schema")
    if schema not in {PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3}:
        raise ValueError(f"不支援的 Phase6 專案格式：{schema!r}")
    if not isinstance(payload.get("snapshot"), dict):
        raise ValueError("Phase6 專案缺少 snapshot")
    if schema in {PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3}:
        if not is_receiving_snapshot(payload["snapshot"]):
            raise ValueError("Receiving project v2/v3 requires Receiving family")
    if for_read:
        submitted = contains_submitted_nfb(payload["snapshot"])
        if submitted and schema != PROJECT_SCHEMA_V3:
            raise ValueError("submitted NFB project cannot be loaded through an old schema")
        if schema == PROJECT_SCHEMA_V3 and not submitted:
            raise ValueError("NFB project v3 has no committed NFBConfig")
    return payload


def project_operator_project_for_write(payload):
    """Plan schema/authority before the GUI encodes and atomically opens a file."""
    validate_operator_project_payload(payload)
    materialized = dict(payload)
    snapshot = normalize_project_snapshot_authority(payload.get("snapshot") or {})
    if is_receiving_snapshot(snapshot):
        materialized["schema"] = (
            PROJECT_SCHEMA_V3 if contains_submitted_nfb(snapshot) else PROJECT_SCHEMA_V2
        )
        snapshot = strip_legacy_receiving_aliases(snapshot)
    elif materialized.get("schema") in {PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3}:
        raise ValueError("Receiving project v2/v3 requires Receiving family")
    else:
        materialized["schema"] = PROJECT_SCHEMA_V1
    materialized["snapshot"] = normalize_quantity_snapshot(snapshot, for_save=True)
    # FinalScene is derived from real physical sources after Reload, never saved truth.
    materialized["final_geometry"] = {}
    return materialized


def project_operator_project_for_read(payload):
    """Revalidate source, then project current in-memory legacy UI aliases."""
    validate_operator_project_payload(payload, for_read=True)
    decoded = dict(payload)
    decoded["snapshot"] = normalize_project_snapshot_authority(decoded["snapshot"])
    if is_receiving_snapshot(decoded["snapshot"]):
        decoded["schema"] = (
            PROJECT_SCHEMA_V3 if contains_submitted_nfb(decoded["snapshot"]) else PROJECT_SCHEMA_V2
        )
        # Only for an existing GUI view: resave strips these non-authoritative aliases.
        decoded["snapshot"] = project_primary_bay_legacy_aliases(decoded["snapshot"])
    decoded["final_geometry"] = {}
    return decoded
