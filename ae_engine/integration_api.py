# -*- coding: utf-8 -*-
"""Stable in-process Engine integration entry for GUI and CADSplit source adapters.

This is NOT the retired installed Worker/CLI transport and it NEVER promotes a
source DXF, family registration, or importable exporter into manufacturing
authorization. It accepts source identities only; canonical physical-part
identities and manufacturing geometry remain owned by WHD Engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from .contracts import (
    BoxBodyPartSpec, DoorPartSpec, EndCapPartSpec, ManufacturingContext,
    ResolvedManufacturingGeometry, ResolvedManufacturingPart, PartSpec,
)

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
    resolved_geometry: ResolvedManufacturingGeometry | None = None
    # Already-confirmed Engine PartSpecs, NOT raw DXF, CSV or source-view labels.
    # Exclusive with resolved_geometry; the same Engine renderer resolves them.
    confirmed_parts: tuple[tuple[str, PartSpec], ...] = ()
    door_layout_columns: tuple[tuple[float, tuple[float, ...]], ...] = ()


def _confirmed_door_layout_projections(
    parts: tuple[tuple[str, PartSpec], ...],
    columns: tuple[tuple[float, tuple[float, ...]], ...],
    *,
    family_name: str,
):
    """Require exact authored Door-grid ownership before manufacturing.

    Use the existing Engine physical cell projector; source DXF labels never
    become physical identities, and incomplete grids cannot stage DXFs.
    """
    from . import manufacturing_api
    from .sheetmetal_part_adapters import validate_door_layout_dimensions

    cell_keys = {
        key for key, _ in parts
        if isinstance(key, str) and re.fullmatch(r"door_c[1-9]\\d*_r[1-9]\\d*", key)
    }
    if not columns:
        if cell_keys:
            raise ValueError("RECEIVING_DOOR_LAYOUT_REQUIRED")
        return {}

    doors = [(key, spec) for key, spec in parts if key == "door" or key in cell_keys]
    if not doors or any(type(spec) is not DoorPartSpec for _, spec in doors):
        raise ValueError("RECEIVING_DOOR_TOPOLOGY_INCOMPLETE")
    first = doors[0][1]
    try:
        boxes = [spec for key, spec in parts
                 if key == "box_body" and type(spec) is BoxBodyPartSpec]
        if boxes:
            validate_door_layout_dimensions(
                columns, total_width=boxes[0].width, total_height=boxes[0].height,
            )
        projected = manufacturing_api.door_part_projections({
            "model": family_name, "multi_door_enabled": True,
            "door_layout_columns": columns,
            "t": first.thickness, "fw": first.frame_width,
            "door_gap_w": first.gap_w, "door_gap_h": first.gap_h,
        })
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("RECEIVING_DOOR_LAYOUT_INVALID") from exc
    expected = {cell.part_key: cell for cell in projected}
    if not expected or {key for key, _ in doors} != set(expected):
        raise ValueError("RECEIVING_DOOR_TOPOLOGY_INCOMPLETE")
    for key, spec in doors:
        cell = expected[key]
        try:
            common = all(math.isclose(
                float(getattr(spec, attr)), float(getattr(first, attr)),
                rel_tol=0.0, abs_tol=1e-6,
            ) for attr in ("thickness", "frame_width", "gap_w", "gap_h"))
            dimensions = (
                math.isclose(float(spec.width), cell.start_width, rel_tol=0.0, abs_tol=1e-6)
                and math.isclose(float(spec.height), cell.start_height, rel_tol=0.0, abs_tol=1e-6)
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("RECEIVING_DOOR_TOPOLOGY_MISMATCH") from exc
        if not common or not dimensions or spec.frame_edges != cell.frame_edges:
            raise ValueError("RECEIVING_DOOR_TOPOLOGY_MISMATCH")
    return expected


def _resolve_confirmed_integration_parts(
    confirmed_parts: Sequence[tuple[str, PartSpec]],
    *,
    family_name: str,
    context: ManufacturingContext,
    door_layout_columns: tuple[tuple[float, tuple[float, ...]], ...] = (),
) -> ResolvedManufacturingGeometry:
    """Resolve typed, independently authored physical parts through Engine.

    This is the existing FinalScene renderer, not an alternate manufacturing
    exporter. Three-piece BoxBody can only enter via the original Engine
    physical-piece solver; partial Cabinet/NFB cannot be inferred from a
    source-view drawing.
    """
    from . import manufacturing_api

    parts = tuple(confirmed_parts)
    projections = _confirmed_door_layout_projections(
        parts, tuple(door_layout_columns), family_name=family_name,
    )
    if not parts:
        raise ValueError("RECEIVING_CONFIRMED_PARTS_REQUIRED")
    resolved: list[ResolvedManufacturingPart] = []
    seen: set[str] = set()
    for entry in parts:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError("RECEIVING_CONFIRMED_PART_INVALID")
        part_key, spec = entry
        if part_key in seen:
            raise ValueError("RECEIVING_CONFIRMED_PART_DUPLICATE")
        # Exact physical role, never a manufacturing identity guessed from
        # CADSplit's displayed source-panel name or an NFB preview key.
        if (part_key == "door" or part_key in projections) and type(spec) is DoorPartSpec:
            if (spec.feature_space != "finished_face"
                    or any(getattr(spec, key) is None for key in (
                        "gap_w", "gap_h", "fold_left", "fold_right",
                        "fold_top", "fold_bottom",
                    ))):
                raise ValueError("RECEIVING_DOOR_AUTHORED_VALUES_REQUIRED")
        elif part_key in ("head", "tail") and type(spec) is EndCapPartSpec:
            if (spec.is_tail != (part_key == "tail")
                    or not spec.fold_profile_x or not spec.fold_profile_y
                    or spec.corner_policy is None):
                raise ValueError("RECEIVING_ENDCAP_AUTHORED_FOLD_REQUIRED")
        elif part_key == "box_body" and type(spec) is BoxBodyPartSpec:
            if (not spec.fold_profile or not spec.back_panel_contract
                    or spec.structure_state.get("active_type")
                        != "three_piece_side_back_split"):
                raise ValueError("RECEIVING_BOX_BODY_AUTHORED_FOLD_REQUIRED")
        else:
            raise ValueError("RECEIVING_CONFIRMED_PART_SCOPE_UNSUPPORTED")
        try:
            if resolve_cabinet_type(spec.model_name).canonical_name != family_name:
                raise ValueError("RECEIVING_CONFIRMED_PART_FAMILY_MISMATCH")
        except (KeyError, TypeError):
            raise ValueError("RECEIVING_CONFIRMED_PART_FAMILY_MISMATCH") from None
        seen.add(part_key)
        if part_key == "box_body":
            # The existing Engine-only structural FinalScene resolves exactly
            # three physical sheets; never serialize a combined preview blank.
            render_data = manufacturing_api.build_box_body_structure_render_data(
                spec, context,
            )
            roles = tuple(piece.role for piece in render_data.pieces)
            if (len(roles) != 3
                    or set(roles) != {"left_side", "back", "right_side"}):
                raise ValueError("RECEIVING_BOX_BODY_PHYSICAL_ROLES_INVALID")
        else:
            render_data = manufacturing_api.build_part_render_data(spec, context)
        resolved.append(ResolvedManufacturingPart(
            part_key=part_key, render_data=render_data,
        ))
    return ResolvedManufacturingGeometry(parts=tuple(resolved))


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
    context: ManufacturingContext | None = None,
) -> VerifiedIntegrationBatchExport:
    """Commit trusted Receiving parts after WHD staged DXF verification.

    Either supply already Engine-resolved geometry or complete, confirmed
    physical PartSpecs for Door/Head/Tail and confirmed three-piece BoxBody;
    the latter are resolved through the existing physical-piece FinalScene
    solver, never an exploded layout preview. Raw DXF,
    JSON, source-only prepare or guessed Factory parameters remain rejected.
    The trusted project owner guards pre-stage and post-reopen commit; the
    retired source-only CLI remains disabled.
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
        if item.confirmed_parts:
            if item.resolved_geometry is not None:
                raise ValueError("RECEIVING_AMBIGUOUS_MANUFACTURING_INPUT")
            if context is not None and not isinstance(context, ManufacturingContext):
                raise TypeError("ManufacturingContext required")
            resolved_geometry = _resolve_confirmed_integration_parts(
                item.confirmed_parts,
                family_name=registration.canonical_name,
                context=context or ManufacturingContext(),
                door_layout_columns=item.door_layout_columns,
            )
        else:
            if item.door_layout_columns:
                raise ValueError("RECEIVING_DOOR_LAYOUT_REQUIRES_CONFIRMED_PARTS")
            resolved_geometry = item.resolved_geometry
        if (not isinstance(resolved_geometry, ResolvedManufacturingGeometry)
                or not resolved_geometry.parts):
            raise ValueError("RECEIVING_ENGINE_RESOLVED_GEOMETRY_REQUIRED")
        namespace = manufacturing_api.receiving_manufacturing_instance_namespace(
            set_id=source.set_id, bay_id=source.bay_id,
        )
        if namespace.casefold() in seen:
            raise ValueError("RECEIVING_DUPLICATE_OUTPUT_NAMESPACE")
        seen.add(namespace.casefold())
        instances.append((namespace, resolved_geometry))

    files = manufacturing_api.save_verified_resolved_manufacturing_geometry_batch_dxf(
        tuple(instances), output_dir,
        pre_commit_guard=pre_commit_guard,
        overwrite=overwrite,
    )
    return VerifiedIntegrationBatchExport(output_files=MappingProxyType(dict(files)))
