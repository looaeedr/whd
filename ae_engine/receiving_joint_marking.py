# -*- coding: utf-8 -*-
"""Receiving Joint Placement MARKING production activation.

Current Receiving product authority: every physical inner-door top/left/right
frame owns one upper-horizontal manufacturing MARKING in its own canonical
FinalScene. The superseded V1 left/right -> shared Divider SIDE_BOUNDARY_PAIR
implementation is retained only in history, not in this production path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from shapely.geometry import LineString

from .cabinet_types import policy as cabinet_family_policy
from .contracts import (
    JointMarkingFailurePolicy,
    JointMarkingPolicy,
    JointMarkingProductionStatus,
    ResolvedJointMarkingResult,
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
)
from .inner_door_frames import derive_all_inner_door_frames, inner_door_frame_stable_id
from .joint_marking_policy import stable_joint_mark_id
from .sheetmetal_drawing import DrawingScene, LinePrimitive


RECEIVING_POLICY_ID = "RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_V2"
GATE_B_STATE = "JOINT_PLACEMENT_MARKING_PRODUCTION_ENABLED"
ALLOW_EXPORT_WITH_DIAGNOSTIC = "ALLOW_EXPORT_WITH_DIAGNOSTIC"

PRODUCTION_JOINT_MARKING_FAILURE_POLICY = JointMarkingFailurePolicy(
    disposition=ALLOW_EXPORT_WITH_DIAGNOSTIC,
)

RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY = JointMarkingPolicy(
    policy_id=RECEIVING_POLICY_ID,
    revision=2,
    enabled=True,
    locator_selector="RECEIVING_INNER_DOOR_FRAME",
    attached_selector="RECEIVING_INNER_DOOR_ASSEMBLY",
    locator_contact_region="FINAL_MATERIAL",
    attached_contact_region="UPPER_REGISTRATION",
    footprint_mode="UPPER_HORIZONTAL",
    boundary_frame_contract={
        "frame_version": "FRAME_FLAT_OWNER_V1",
        "basis_part": "LOCATOR",
        "longitudinal_flat_axis": "+X",
        "cross_flat_axis": "+Y",
        "boundary_role": "UPPER_HORIZONTAL",
        "boundary_source": "FRAME_SPAN_MAX",
    },
    contact_span_contract="FULL_FRAME_MATERIAL_WIDTH",
    allowed_overlap_contract="NONE",
)

# Compatibility export for callers that imported the old V1 symbol name.
# It intentionally points to the V2 user-authoritative policy.
RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY = (
    RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY
)


@dataclass(frozen=True)
class ReceivingJointMarkingResolution:
    geometry: ResolvedManufacturingGeometry
    results: tuple[ResolvedJointMarkingResult, ...]
    status: JointMarkingProductionStatus


def resolve_joint_marking_production_status() -> JointMarkingProductionStatus:
    return JointMarkingProductionStatus(
        gate_state=GATE_B_STATE,
        activation_enabled=True,
        export_disposition=PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition,
        production_policy_count=1,
    )


def joint_marking_export_summary(results) -> tuple[dict[str, object], ...]:
    """Return the machine-readable export/manufacturing summary."""
    rows = []
    for item in tuple(results or ()):
        if not isinstance(item, ResolvedJointMarkingResult):
            raise TypeError(
                "joint marking summary requires ResolvedJointMarkingResult values"
            )
        rows.append(
            {
                "policy_id": str(item.policy_id),
                "policy_revision": int(item.policy_revision),
                "locator_part_id": str(item.locator_part_id),
                "attached_part_id": str(item.attached_part_id),
                "status": str(item.status),
                "diagnostic_code": item.diagnostic_code,
                "export_disposition": str(item.export_disposition),
            }
        )
    return tuple(rows)


def _inner_door_items(snapshot) -> tuple[dict[str, object], ...]:
    rows = []
    for raw in tuple(dict(snapshot or {}).get("inner_doors") or ()):
        if isinstance(raw, Mapping):
            item = dict(raw)
            if str(item.get("stable_id") or "").strip():
                rows.append(item)
    return tuple(rows)


def _derived_receiving_frames(snapshot):
    frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(
        dict(snapshot or {})
    )
    return tuple(derive_all_inner_door_frames(frame_sets))


def _part_map(
    geometry: ResolvedManufacturingGeometry,
) -> dict[str, ResolvedManufacturingPart]:
    return {
        str(part.part_key): part
        for part in tuple(geometry.parts or ())
    }


def _marking_line_signature(p1, p2):
    a = (
        round(float(p1[0]), 9),
        round(float(p1[1]), 9),
    )
    b = (
        round(float(p2[0]), 9),
        round(float(p2[1]), 9),
    )
    return tuple(sorted((a, b)))


def _clean_prior_joint_markings(render_data):
    metadata = dict(
        getattr(render_data, "metadata", {}) or {}
    )
    prior = tuple(metadata.get("joint_markings") or ())
    owned = {
        _marking_line_signature(row["p1"], row["p2"])
        for row in prior
        if isinstance(row, Mapping)
        and str(row.get("source") or "") == "JOINT_PLACEMENT_MARKING"
        and row.get("p1") is not None
        and row.get("p2") is not None
    }
    scene = DrawingScene()
    for primitive in tuple(
        getattr(render_data.scene, "primitives", ()) or ()
    ):
        if (
            isinstance(primitive, LinePrimitive)
            and str(primitive.layer) == "MARKING"
            and _marking_line_signature(
                (primitive.p1.x, primitive.p1.y),
                (primitive.p2.x, primitive.p2.y),
            )
            in owned
        ):
            continue
        scene.add(primitive)
    metadata["joint_markings"] = tuple(
        row
        for row in prior
        if not (
            isinstance(row, Mapping)
            and str(row.get("source") or "") == "JOINT_PLACEMENT_MARKING"
        )
    )
    return scene, metadata


def _clean_geometry_prior_joint_markings(
    geometry: ResolvedManufacturingGeometry,
) -> ResolvedManufacturingGeometry:
    parts = []
    for part in tuple(geometry.parts or ()):
        # Composite owners expose scene/material as read-only projections but
        # do not own PartRenderData metadata. Leave those aggregate owners alone.
        if not hasattr(part.render_data, "metadata"):
            parts.append(part)
            continue
        scene, metadata = _clean_prior_joint_markings(
            part.render_data
        )
        if (
            scene.primitives
            == list(
                getattr(part.render_data.scene, "primitives", ())
                or ()
            )
            and metadata
            == dict(
                getattr(part.render_data, "metadata", {})
                or {}
            )
        ):
            parts.append(part)
            continue
        parts.append(
            replace(
                part,
                render_data=replace(
                    part.render_data,
                    scene=scene,
                    metadata=metadata,
                ),
            )
        )
    diagnostics = tuple(
        item
        for item in tuple(geometry.diagnostics or ())
        if not isinstance(item, ResolvedJointMarkingResult)
    )
    return replace(
        geometry,
        parts=tuple(parts),
        diagnostics=diagnostics,
    )


def _replace_part(
    geometry: ResolvedManufacturingGeometry,
    part_key: str,
    render_data,
) -> ResolvedManufacturingGeometry:
    return replace(
        geometry,
        parts=tuple(
            replace(part, render_data=render_data)
            if str(part.part_key) == str(part_key)
            else part
            for part in tuple(geometry.parts or ())
        ),
    )


def _assembly_semantic_id(frame) -> str:
    return f"inner_door:{str(frame.inner_door_id)}:assembly"


def _fail(
    *,
    locator_part_id: str,
    attached_part_id: str,
    diagnostic_code: str,
    detail: str,
    evidence: Mapping[str, object] | None = None,
) -> ResolvedJointMarkingResult:
    policy = RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY
    return ResolvedJointMarkingResult(
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        locator_part_id=str(locator_part_id or ""),
        attached_part_id=str(attached_part_id or ""),
        status="SKIPPED_FAIL_CLOSED",
        mark_ids=(),
        diagnostic_code=str(diagnostic_code),
        diagnostic_detail=str(detail or ""),
        export_disposition=(
            PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition
        ),
        evidence=dict(evidence or {}),
    )


def _solve_frame_upper_horizontal(
    *,
    geometry: ResolvedManufacturingGeometry,
    frame,
):
    """Build one frame-owned upper-horizontal MARKING in canonical flat space.

    InnerDoorFramePart owns both axes used here: Fold material owns the full
    X width and the explicit frame span owns Y. No Canvas coordinate, renderer
    bbox, test fixture, or visual measurement becomes manufacturing authority.
    """
    policy = RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY
    locator_id = str(frame.stable_id)
    attached_id = _assembly_semantic_id(frame)
    locator_part = _part_map(geometry).get(locator_id)
    if locator_part is None:
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code="LOCATOR_MISSING",
                detail=(
                    "authoritative inner-door frame physical part "
                    "is absent"
                ),
            ),
            (),
        )

    if str(frame.side) not in {"top", "left", "right"}:
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code="MATING_REGION_UNRESOLVED",
                detail=(
                    "Receiving upper-horizontal marking only "
                    "applies to top/left/right frames"
                ),
            ),
            (),
        )

    width = float(frame.blank_width)
    upper_y = float(frame.span)
    p1 = (0.0, upper_y)
    p2 = (width, upper_y)
    line = LineString((p1, p2))
    material = locator_part.render_data.material
    if (
        width <= 0.0
        or upper_y <= 0.0
        or line.is_empty
        or float(line.length) <= 0.0
        or not material.covers(line)
    ):
        return (
            _fail(
                locator_part_id=locator_id,
                attached_part_id=attached_id,
                diagnostic_code="MARK_OUTSIDE_FINAL_MATERIAL",
                detail=(
                    "upper-horizontal mark is not covered by "
                    "frame Final Material"
                ),
                evidence={
                    "frame_side": str(frame.side),
                    "blank_width": width,
                    "frame_span": upper_y,
                },
            ),
            (),
        )

    role = "UPPER_HORIZONTAL"
    mark_id = stable_joint_mark_id(
        policy.policy_id,
        locator_id,
        attached_id,
        role,
    )
    row = {
        "mark_id": mark_id,
        "boundary_role": role,
        "locator_part_id": locator_id,
        "attached_part_id": attached_id,
        "p1": p1,
        "p2": p2,
        "source": "JOINT_PLACEMENT_MARKING",
    }
    result = ResolvedJointMarkingResult(
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        locator_part_id=locator_id,
        attached_part_id=attached_id,
        status="EMITTED",
        mark_ids=(mark_id,),
        diagnostic_code=None,
        diagnostic_detail="",
        export_disposition=(
            PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition
        ),
        evidence={
            "frame_side": str(frame.side),
            "locator_region": policy.locator_contact_region,
            "attached_region": policy.attached_contact_region,
            "footprint_mode": policy.footprint_mode,
            "boundary_frame_contract": dict(
                policy.boundary_frame_contract
            ),
            "geometry_owner": "INNER_DOOR_FRAME_FLAT_CONTRACT",
        },
    )
    return result, (row,)


def resolve_receiving_joint_markings(
    snapshot,
    geometry: ResolvedManufacturingGeometry,
    *,
    dimensions,
    sheet_thickness: float,
    cabinet_family="受電箱",
) -> ReceivingJointMarkingResolution:
    """Enrich Receiving top/left/right frames with upper-horizontal MARKING."""
    if not isinstance(
        geometry,
        ResolvedManufacturingGeometry,
    ):
        raise TypeError(
            "geometry must be ResolvedManufacturingGeometry"
        )

    # Kept for orchestration/API compatibility. V2 is a frame-flat rule and
    # does not need the superseded world-space Divider contact solve.
    _ = dimensions, sheet_thickness

    status = resolve_joint_marking_production_status()
    geometry = _clean_geometry_prior_joint_markings(
        geometry
    )
    family = str(
        cabinet_family
        or dict(snapshot or {}).get("model")
        or ""
    ).strip()
    if family != "受電箱":
        return ReceivingJointMarkingResolution(
            geometry=geometry,
            results=(),
            status=status,
        )

    items = _inner_door_items(snapshot)
    if not items:
        return ReceivingJointMarkingResolution(
            geometry=geometry,
            results=(),
            status=status,
        )

    try:
        frames = _derived_receiving_frames(snapshot)
    except (TypeError, ValueError) as exc:
        results = []
        for item in items:
            door_id = str(item["stable_id"])
            included = {
                str(side).strip().lower()
                for side in tuple(
                    item.get("included_frame_sides")
                    or ("top", "left", "right")
                )
            }
            for side in ("top", "left", "right"):
                if side not in included:
                    continue
                results.append(
                    _fail(
                        locator_part_id=(
                            inner_door_frame_stable_id(
                                door_id,
                                side,
                            )
                        ),
                        attached_part_id=(
                            f"inner_door:{door_id}:assembly"
                        ),
                        diagnostic_code="STALE_STABLE_ID",
                        detail=str(exc),
                    )
                )
        return ReceivingJointMarkingResolution(
            geometry=replace(
                geometry,
                diagnostics=(
                    tuple(geometry.diagnostics or ())
                    + tuple(results)
                ),
            ),
            results=tuple(results),
            status=status,
        )

    frame_by_id = {
        str(frame.stable_id): frame
        for frame in frames
    }
    all_results = []
    lines_by_locator = {}

    for item in items:
        door_id = str(item["stable_id"])
        included = {
            str(side).strip().lower()
            for side in tuple(
                item.get("included_frame_sides")
                or ("top", "left", "right")
            )
        }
        for side in ("top", "left", "right"):
            if side not in included:
                continue
            locator_id = inner_door_frame_stable_id(
                door_id,
                side,
            )
            frame = frame_by_id.get(locator_id)
            if frame is None:
                all_results.append(
                    _fail(
                        locator_part_id=locator_id,
                        attached_part_id=(
                            f"inner_door:{door_id}:assembly"
                        ),
                        diagnostic_code="LOCATOR_MISSING",
                        detail=(
                            "requested Receiving inner-door "
                            "frame semantic owner is absent"
                        ),
                    )
                )
                continue
            result, line_rows = _solve_frame_upper_horizontal(
                geometry=geometry,
                frame=frame,
            )
            all_results.append(result)
            if line_rows:
                lines_by_locator.setdefault(
                    locator_id,
                    [],
                ).extend(line_rows)

    enriched = geometry
    for locator_id, rows in sorted(
        lines_by_locator.items()
    ):
        locator_part = _part_map(enriched).get(
            locator_id
        )
        if locator_part is None:
            continue
        scene, metadata = _clean_prior_joint_markings(
            locator_part.render_data
        )
        ordered = tuple(
            sorted(
                rows,
                key=lambda row: (
                    str(row["boundary_role"]),
                    str(row["mark_id"]),
                ),
            )
        )
        for row in ordered:
            scene.add_line(
                row["p1"],
                row["p2"],
                layer="MARKING",
            )
        metadata["joint_markings"] = (
            tuple(
                metadata.get("joint_markings")
                or ()
            )
            + ordered
        )
        enriched = _replace_part(
            enriched,
            locator_id,
            replace(
                locator_part.render_data,
                scene=scene,
                metadata=metadata,
            ),
        )

    enriched = replace(
        enriched,
        diagnostics=(
            tuple(enriched.diagnostics or ())
            + tuple(all_results)
        ),
    )
    return ReceivingJointMarkingResolution(
        geometry=enriched,
        results=tuple(all_results),
        status=status,
    )


__all__ = [
    "ALLOW_EXPORT_WITH_DIAGNOSTIC",
    "GATE_B_STATE",
    "PRODUCTION_JOINT_MARKING_FAILURE_POLICY",
    "RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY",
    "RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY",
    "ReceivingJointMarkingResolution",
    "joint_marking_export_summary",
    "resolve_joint_marking_production_status",
    "resolve_receiving_joint_markings",
]
