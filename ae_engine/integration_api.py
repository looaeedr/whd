# -*- coding: utf-8 -*-
"""Stable in-process Engine integration entry for GUI and CADSplit source adapters.

This is NOT the retired installed Worker/CLI transport and it NEVER promotes a
source DXF, family registration, or importable exporter into manufacturing
authorization. It accepts source identities only; canonical physical-part
identities and manufacturing geometry remain owned by WHD Engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from .contracts import ResolvedManufacturingGeometry

from .cabinet_types import registered_cabinet_types, resolve_cabinet_type


IntegrationOperation = Literal["capabilities", "prepare", "export"]


@dataclass(frozen=True)
class ManufacturingSourceIdentity:
    """CADSplit-owned source reference. NOT a manufacturing physical-part ID."""

    panel_key: str
    source_revision: str
    set_id: str | None = None
    bay_id: str | None = None


@dataclass(frozen=True)
class ManufacturingIntegrationRequest:
    """Immutable one-operation request; no geometry or GUI state is accepted."""

    operation: IntegrationOperation
    family: str | None = None
    source: ManufacturingSourceIdentity | None = None


@dataclass(frozen=True)
class ManufacturingIntegrationResponse:
    operation: str
    status: str
    family: str | None = None
    source: ManufacturingSourceIdentity | None = None
    reason: str | None = None
    family_implemented: bool | None = None
    python_api_available: bool = True
    manufacturing_authorized: bool = False
    dxf_roundtrip_verified: bool = False
    external_export_available: bool = False
    known_families: tuple[str, ...] = ()


def _valid_source(source: object) -> bool:
    if not isinstance(source, ManufacturingSourceIdentity):
        return False
    if not all(
        isinstance(value, str) and bool(value.strip())
        for value in (source.panel_key, source.source_revision)
    ):
        return False
    for value in (source.set_id, source.bay_id):
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            return False
    # A Bay without its Set, or a Set without its Bay, cannot be mapped reliably.
    return (source.set_id is None) == (source.bay_id is None)


def dispatch_manufacturing_integration(
    request: ManufacturingIntegrationRequest,
) -> ManufacturingIntegrationResponse:
    """Return deterministic capability/preparation results, never manufacturing.

    Python consumers may use this entry before building an authoritative
    PartSpec/FinalScene through the *existing* Engine manufacturing APIs.
    No operation here writes a DXF, infers a physical part from source labels,
    or exposes the retired source-only CLI as a manufacturing service.
    """
    if not isinstance(request, ManufacturingIntegrationRequest):
        raise TypeError("ManufacturingIntegrationRequest required")

    operation = request.operation
    if operation not in ("capabilities", "prepare", "export"):
        return ManufacturingIntegrationResponse(
            operation=str(operation), status="UNSUPPORTED_OPERATION",
            reason="WHD_INTEGRATION_OPERATION_UNSUPPORTED",
        )

    family = request.family
    family_reg = None
    if family is not None:
        if not isinstance(family, str) or not family.strip():
            return ManufacturingIntegrationResponse(
                operation=operation, status="INVALID_FAMILY",
                reason="WHD_INTEGRATION_FAMILY_REQUIRED",
            )
        try:
            family_reg = resolve_cabinet_type(family)
        except KeyError:
            return ManufacturingIntegrationResponse(
                operation=operation, status="UNSUPPORTED_FAMILY",
                reason="WHD_INTEGRATION_FAMILY_UNKNOWN",
            )

    if operation == "capabilities":
        return ManufacturingIntegrationResponse(
            operation=operation, status="SOURCE_API_AVAILABLE",
            family=family_reg.canonical_name if family_reg else None,
            family_implemented=family_reg.implemented if family_reg else None,
            known_families=tuple(
                item.canonical_name for item in registered_cabinet_types()
            ),
        )

    if family_reg is None:
        return ManufacturingIntegrationResponse(
            operation=operation, status="INVALID_FAMILY",
            reason="WHD_INTEGRATION_FAMILY_REQUIRED",
        )

    if not family_reg.implemented:
        return ManufacturingIntegrationResponse(
            operation=operation, family=family_reg.canonical_name,
            family_implemented=False, status="UNSUPPORTED_FAMILY",
            reason="WHD_INTEGRATION_FAMILY_NOT_IMPLEMENTED",
        )

    if not _valid_source(request.source):
        return ManufacturingIntegrationResponse(
            operation=operation, family=family_reg.canonical_name,
            family_implemented=True, status="SOURCE_REQUIRED",
            reason="WHD_INTEGRATION_SOURCE_IDENTITY_REQUIRED",
        )

    if operation == "export":
        # Scope of this refusal: source-identity-only integration, NOT an
        # authorization check for the established in-process generate_part /
        # verified resolved-part manufacturing APIs. A trusted typed request
        # must call those APIs directly and obey their own physical/Registry
        # checks; never use this source-only status as a global Family veto.
        return ManufacturingIntegrationResponse(
            operation=operation, family=family_reg.canonical_name,
            source=request.source, family_implemented=True,
            status="EXTERNAL_EXPORT_NOT_CERTIFIED",
            reason="WHD_INTEGRATION_MANUFACTURING_NOT_CERTIFIED",
        )

    return ManufacturingIntegrationResponse(
        operation=operation, family=family_reg.canonical_name,
        source=request.source, family_implemented=True,
        status="SOURCE_ACCEPTED_NOT_MANUFACTURING_READY",
        reason="WHD_INTEGRATION_ENGINE_RESOLUTION_REQUIRED",
    )


@dataclass(frozen=True)
class ManufacturingResolvedBayInput:
    """Source identity + already-authoritative Engine physical geometry.

    CADSplit supplies the original source key. It must NOT manufacture the
    geometry or derive physical part keys from Set/Bay source labels.
    """

    family: str
    source: ManufacturingSourceIdentity
    resolved_geometry: ResolvedManufacturingGeometry


@dataclass(frozen=True)
class VerifiedIntegrationBatchExport:
    """Only the exact staged physical DXFs were reopened and verified."""

    output_files: Mapping[str, str]
    physical_dxf_roundtrip_verified: bool = True
    complete_assembly_certified: bool = False
    external_cli_enabled: bool = False


def export_verified_resolved_integration_bays(
    bays: Sequence[ManufacturingResolvedBayInput],
    output_dir: str | Path,
    *,
    pre_commit_guard,
    overwrite: bool = False,
) -> VerifiedIntegrationBatchExport:
    """Commit already-resolved Receiving parts after WHD staged DXF verification.

    The guard is supplied by the trusted in-process project state owner and
    invoked before staging AND after independent DXF reopen. No raw source DXF,
    JSON, preview, or "prepare" response can be promoted to manufacturing here.
    The old source-only CLI remains disabled.
    """
    if not callable(pre_commit_guard):
        raise ValueError("WHD_PRECOMMIT_GUARD_REQUIRED")
    selected = tuple(bays)
    if not selected or len(selected) > 20:
        raise ValueError("WHD_VERIFIED_BAY_COUNT_INVALID")

    # Import at call time to preserve the public ae_engine import direction.
    from . import manufacturing_api

    seen: set[str] = set()
    instances: list[tuple[str, ResolvedManufacturingGeometry]] = []
    for item in selected:
        if not isinstance(item, ManufacturingResolvedBayInput):
            raise TypeError("ManufacturingResolvedBayInput required")
        try:
            registration = resolve_cabinet_type(item.family)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("WHD_INTEGRATION_FAMILY_UNKNOWN") from exc
        if registration.canonical_name != "受電箱" or not registration.implemented:
            raise ValueError("WHD_VERIFIED_BAY_RECEIVING_ONLY")
        source = item.source
        if not _valid_source(source) or source.set_id is None or source.bay_id is None:
            raise ValueError("RECEIVING_STABLE_SOURCE_SET_BAY_REQUIRED")
        if (not isinstance(item.resolved_geometry, ResolvedManufacturingGeometry)
                or not item.resolved_geometry.parts):
            raise ValueError("RECEIVING_ENGINE_RESOLVED_GEOMETRY_REQUIRED")
        namespace = manufacturing_api.receiving_manufacturing_instance_namespace(
            set_id=source.set_id, bay_id=source.bay_id,
        )
        if namespace.casefold() in seen:
            raise ValueError("RECEIVING_DUPLICATE_OUTPUT_NAMESPACE")
        seen.add(namespace.casefold())
        instances.append((namespace, item.resolved_geometry))

    files = manufacturing_api.save_verified_resolved_manufacturing_geometry_batch_dxf(
        tuple(instances), output_dir,
        pre_commit_guard=pre_commit_guard,
        overwrite=overwrite,
    )
    return VerifiedIntegrationBatchExport(output_files=MappingProxyType(dict(files)))
