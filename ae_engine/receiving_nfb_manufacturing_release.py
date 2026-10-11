# -*- coding: utf-8 -*-
"""#1497 optional verified NFB INNER-DOOR manufacturing entrypoint.

The #1609 trial is NOT a production capability. Production input must be
re-parsed from the exact indexed DXF; an owner-reviewed repository registry
must approve the *individual* model/source, physical panel and X/Y
placements. One source profile and one generic renderer serve all brands.

No implicit W/2 X, filename-suffix alias, inferred lower PAD, or DEFAULT
permission. Absence of an approved registry entry is a hard stop BEFORE
writing a DXF. This module owns no GUI transaction.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from math import isfinite
from pathlib import Path
from typing import Mapping, Sequence

from .inner_door_panels import InnerDoorPanelPart
from .receiving_nfb_cutting_manufacturing import (
    NfbUpperSourceProfile, trial_nfb_upper_cutting_on_inner_door,
)
from .receiving_nfb_cutting_preflight import (
    NfbExistingCuttingClaim, NfbUpperOpeningRequest,
)
from .receiving_nfb_dxf_source import inspect_nfb_dxf_source
from .receiving_nfb_index_sources import (
    NfbIndexSourceCatalog, unique_nfb_dxfs_from_switch_index,
)

RELEASE_SCHEMA = "WHD_NFB_PHYSICAL_MANUFACTURING_APPROVAL_V1"
RELEASE_STATUS = "APPROVED_INNER_DOOR_CUTTING"
SOURCE_PROVEN = "INDEX_FILENAME_AND_SHA_VERIFIED"
APPROVAL_REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "docs/receiving_nfb_manufacturing_approvals.json"
)


@dataclass(frozen=True)
class NfbCertifiedInnerDoorRender:
    render_data: object
    approval_ids: tuple[str, ...]
    source_sha256: str
    part_id: str
    manufacturing_ready: bool = True


def _xy(value: object) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("certified NFB X/Y must contain exactly two coordinates")
    if any(type(v) not in (int, float) for v in value):
        raise ValueError("certified NFB X/Y must contain real numbers")
    result = (float(value[0]), float(value[1]))
    if not all(isfinite(v) for v in result):
        raise ValueError("certified NFB X/Y must be finite")
    return result


def _same_xy(a: object, b: object) -> bool:
    left, right = _xy(a), _xy(b)
    return max(abs(left[0] - right[0]), abs(left[1] - right[1])) <= 1e-6


def _approved_row(
    row: Mapping[str, object],
    *,
    panel: InnerDoorPanelPart,
    request: NfbUpperOpeningRequest,
    profile: NfbUpperSourceProfile,
    catalog: NfbIndexSourceCatalog,
) -> str:
    """Each physical hole must match *all* independently approved owners."""
    if row.get("status") != RELEASE_STATUS:
        raise ValueError("NFB manufacturing approval PENDING or absent")
    if row.get("brand") != profile.brand or row.get("indexed_filename") != profile.indexed_filename:
        raise ValueError("NFB approval model identity mismatch")
    if row.get("source_sha256") != profile.source_sha256 or row.get("source_handle") != profile.upper_handle:
        raise ValueError("NFB approval original DXF fingerprint mismatch")
    if row.get("index_sha256") != catalog.index_sha256:
        raise ValueError("NFB approval indexed CSV revision mismatch")
    if row.get("part_id") != panel.stable_id or row.get("cell_key") != panel.cell_key:
        raise ValueError("NFB approval physical part/cell mismatch")
    if row.get("physical_hole_id") != request.physical_hole_id:
        raise ValueError("NFB approval physical hole owner mismatch")
    if row.get("door_geometry_mm") != [
        float(panel.width), float(panel.height), float(panel.thickness),
        float(panel.unfolded_width), float(panel.unfolded_height),
    ]:
        raise ValueError("NFB approval physical door CUTTING dimensions changed")
    if not (_same_xy(row.get("uv_center_xy"), (request.uv_center_x, request.uv_center_y))
            and _same_xy(row.get("world_center_xy"), row.get("verified_world_center_xy"))):
        raise ValueError("NFB approved UV / physical world X/Y mismatch")
    if row.get("rotation_deg") != request.rotation_deg:
        raise ValueError("NFB approval rotation mismatch")
    if (row.get("x_rule_revision") != request.x_rule_revision
            or row.get("y_rule_revision") != request.y_rule_revision):
        raise ValueError("NFB approval X/Y rule revision mismatch")
    for key in ("x_rule_revision", "y_rule_revision"):
        value = str(row.get(key) or "").upper()
        if not value or any(token in value for token in ("SHADOW", "PREVIEW", "HYP", "UNKNOWN")):
            raise ValueError("NFB manufacturing cannot accept shadow/preview coordinates")
    if row.get("physical_source_to_blank_x_approved") is not True:
        raise ValueError("NFB physical source-to-blank X identity not approved")
    if row.get("blank_to_box_world_x_approved") is not True:
        raise ValueError("NFB blank-to-box-world X projection not approved")
    if row.get("upper_color150_to_inner_door_y_approved") is not True:
        raise ValueError("NFB upper Color150-to-inner-door Y not approved")
    if row.get("legacy_hole_owner_verified") is not True:
        raise ValueError("NFB legacy CUTTING owner not verified")
    approval_id = str(row.get("approval_id") or "").strip()
    authority = str(row.get("approval_owner") or "").strip()
    physical_evidence = str(row.get("physical_evidence_reference") or "").strip()
    if not (approval_id and authority and physical_evidence):
        raise ValueError("NFB approval has no traceable manufacturing owner/evidence")
    return approval_id


def _build_with_approved_registry(
    panel: InnerDoorPanelPart,
    requests: Sequence[NfbUpperOpeningRequest],
    *,
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
    approval_registry: Mapping[str, object],
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
) -> NfbCertifiedInnerDoorRender:
    """Internal testable gate. The public manufacturing API uses ONLY repo registry."""
    if not isinstance(panel, InnerDoorPanelPart):
        raise TypeError("NFB target must be inner-door physical part")
    if approval_registry.get("schema") != RELEASE_SCHEMA:
        raise ValueError("NFB manufacturing authority registry schema mismatch")
    # Reading a real original DXF is mandatory. Neither a mocked inventory
    # nor a JSON fixture may be substituted at the public manufacturing API.
    source = Path(source_path)
    if source.name != profile.indexed_filename:
        raise ValueError("NFB indexed DXF basename differs from real source: alias unverified")
    if profile.source_alias_status != SOURCE_PROVEN:
        raise ValueError("NFB source alias/name has not been independently certified")
    catalog = unique_nfb_dxfs_from_switch_index(index_path)
    inventory = inspect_nfb_dxf_source(source)
    if inventory.source_sha256 != profile.source_sha256:
        raise ValueError("NFB real DXF content changed since source evidence")
    rows = tuple(approval_registry.get("approvals") or ())
    proposed = tuple(requests)
    if not proposed:
        raise ValueError("NFB manufacturing batch requires explicit configured holes")
    if len({r.physical_hole_id for r in proposed}) != len(proposed):
        raise ValueError("NFB duplicate physical-hole owner")
    approvals = []
    for request in proposed:
        matching = [row for row in rows if
                    row.get("physical_hole_id") == request.physical_hole_id and
                    row.get("brand") == profile.brand and
                    row.get("indexed_filename") == profile.indexed_filename]
        if len(matching) != 1:
            raise ValueError("NFB manufacturing approval missing or duplicate")
        approvals.append(_approved_row(
            matching[0], panel=panel, request=request,
            profile=profile, catalog=catalog,
        ))
    if len(set(approvals)) != len(approvals):
        raise ValueError("NFB reused manufacturing approval")
    trial = trial_nfb_upper_cutting_on_inner_door(
        panel, proposed, catalog=catalog, inventory=inventory,
        profile=profile, existing_claims=existing_claims,
    )
    if trial.manufacturing_ready:
        raise ValueError("NFB trial bypassed manufacturing approval")
    data = replace(
        trial.render_data,
        metadata={
            **dict(trial.render_data.metadata),
            "nfb_trial_status": "PRODUCTION_APPROVED_BY_INDEPENDENT_REGISTRY",
            "nfb_trial_export_approved": True,
            "nfb_manufacturing_approval_ids": tuple(approvals),
            "nfb_original_index_sha256": catalog.index_sha256,
        },
    )
    return NfbCertifiedInnerDoorRender(
        render_data=data, approval_ids=tuple(approvals),
        source_sha256=inventory.source_sha256, part_id=panel.stable_id,
    )


def build_verified_nfb_inner_door_render_data(
    panel: InnerDoorPanelPart,
    requests: Sequence[NfbUpperOpeningRequest],
    *,
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
) -> NfbCertifiedInnerDoorRender:
    """Canonical product entrypoint: only repository-pinned owner approvals."""
    registry = json.loads(APPROVAL_REGISTRY.read_text(encoding="utf-8"))
    return _build_with_approved_registry(
        panel, requests, index_path=index_path, source_path=source_path,
        profile=profile, approval_registry=registry,
        existing_claims=existing_claims,
    )


def save_verified_nfb_inner_door_dxf(
    panel: InnerDoorPanelPart,
    requests: Sequence[NfbUpperOpeningRequest],
    output_path: str | Path,
    *,
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
    overwrite: bool = False,
) -> str:
    """Production DXF path; no output file if any source/owner/geometry gate fails."""
    approved = build_verified_nfb_inner_door_render_data(
        panel, requests, index_path=index_path, source_path=source_path,
        profile=profile, existing_claims=existing_claims,
    )
    from .manufacturing_api import save_part_render_data_dxf
    return save_part_render_data_dxf(
        approved.render_data, output_path, overwrite=overwrite,
    )
