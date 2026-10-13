# -*- coding: utf-8 -*-
"""#1497 NFB upper-opening preflight: never manufacture an unverified hole.

Receives authoritative part/fold geometry and a Color-150 UPPER source
profile. X/Y owners are intentionally separate (#1494 / #1495); no default
center, model name, or source-attachment suffix can substitute for approval.

This is a pure, read-only *preflight* that returns preview coordinates and
blocking diagnostics. It NEVER writes a CUTTING primitive or edits the
original Hole Editor / CSV / DXF. FinalScene integration is a later, explicit
manufacturing capability that must consume certified geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from .inner_door_panels import InnerDoorPanelPart

UPPER_SOURCE_ROLE = "UPPER"
SOURCE_COLOR_150 = 150
APPROVED_ROTATIONS = (0, 90, 180, 270)
PREVIEW_ONLY = "PREVIEW_ONLY"
BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class NfbUpperOpeningRequest:
    physical_hole_id: str
    target_part_id: str
    source_sha256: str
    source_handle: str
    source_region: str
    source_aci: int
    source_outline_xy: tuple[tuple[float, float], ...]
    source_center_xy: tuple[float, float]
    source_profile_closed: bool
    source_bulges: tuple[float, ...]
    rotation_deg: int = 0
    # Actual manufactured-inner-Door UV coordinates, never nominal box X/Y.
    uv_center_x: float | None = None
    uv_center_y: float | None = None
    # These revisions cannot be inferred from geometry/CSV alone.
    x_rule_revision: str | None = None
    y_rule_revision: str | None = None
    model_filename: str | None = None


@dataclass(frozen=True)
class NfbExistingCuttingClaim:
    physical_hole_id: str
    part_id: str
    # Actual CUTTING footprint in the *same* material UV coordinate system.
    outline_uv_xy: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class NfbUpperOpeningPreflight:
    physical_hole_id: str
    part_id: str
    status: str
    diagnostics: tuple[str, ...]
    preview_outline_uv_xy: tuple[tuple[float, float], ...] = ()
    source_sha256: str = ""
    source_handle: str = ""

    @property
    def manufacturing_ready(self) -> bool:
        # Even fully populated source X/Y evidence does not equal a signed,
        # explicitly registered, model-specific manufacturing capability.
        return False


@dataclass(frozen=True)
class NfbUpperOpeningBatchPreflight:
    """Atomic Q16-style change gate: all proposals or none, never partial CUTTING."""
    status: str
    diagnostics: tuple[str, ...]
    items: tuple[NfbUpperOpeningPreflight, ...]

    @property
    def manufacturing_ready(self) -> bool:
        return False


def _finite_xy(values: Sequence[float], label: str) -> tuple[float, float]:
    if len(values) != 2:
        raise ValueError(f"{label} must be exactly two coordinates")
    x, y = float(values[0]), float(values[1])
    if not all(isfinite(v) for v in (x, y)):
        raise ValueError(f"{label} must contain finite numbers")
    return x, y


def _upper_rectangle_relative_vertices(request: NfbUpperOpeningRequest):
    """Validate actual source upper Color150 contour without guessing a pivot."""
    if request.source_region != UPPER_SOURCE_ROLE or request.source_aci != SOURCE_COLOR_150:
        raise ValueError("NFB source must be upper Color 150; lower spacer is out of scope")
    if not request.source_handle or not request.source_handle.strip():
        raise ValueError("NFB source handle required")
    digest = str(request.source_sha256).lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("NFB original source SHA256 is required")
    pts = tuple(_finite_xy(p, "NFB source point") for p in request.source_outline_xy)
    if not request.source_profile_closed or len(pts) != 4 or len(set(pts)) != 4:
        raise ValueError("NFB upper Color150 profile must be a closed four-corner rectangle")
    bulges = tuple(float(v) for v in request.source_bulges)
    if len(bulges) != 4 or any(not isfinite(v) or abs(v) > 1e-9 for v in bulges):
        raise ValueError("NFB upper Color150 must have four straight edges without bulges")
    xs = sorted({p[0] for p in pts})
    ys = sorted({p[1] for p in pts})
    if (
        len(xs) != 2 or len(ys) != 2
        or xs[1] <= xs[0] or ys[1] <= ys[0]
        or set(pts) != {(x, y) for x in xs for y in ys}
    ):
        raise ValueError("NFB upper Color150 must be an axis-aligned rectangle")
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        horizontal = abs(p[1] - q[1]) <= 1e-8 and abs(p[0] - q[0]) > 1e-8
        vertical = abs(p[0] - q[0]) <= 1e-8 and abs(p[1] - q[1]) > 1e-8
        if not (horizontal or vertical):
            raise ValueError("NFB upper Color150 source outline has broken/crossed edge order")
    center = _finite_xy(request.source_center_xy, "NFB Color150 source center")
    computed = (sum(xs) / 2.0, sum(ys) / 2.0)
    if max(abs(center[0]-computed[0]), abs(center[1]-computed[1])) > 1e-5:
        raise ValueError("NFB source pivot differs from upper Color150 rectangle center")
    if isinstance(request.rotation_deg, bool) or request.rotation_deg not in APPROVED_ROTATIONS:
        raise ValueError("NFB source rotation must be 0/90/180/270")
    delta = tuple((x-center[0], y-center[1]) for x, y in pts)
    turn = request.rotation_deg // 90
    if turn == 1:
        delta = tuple((-y, x) for x, y in delta)
    elif turn == 2:
        delta = tuple((-x, -y) for x, y in delta)
    elif turn == 3:
        delta = tuple((y, -x) for x, y in delta)
    return delta


def _bbox(outline: Sequence[tuple[float, float]]):
    xs = [x for x, _ in outline]
    ys = [y for _, y in outline]
    if not xs:
        raise ValueError("empty CUTTING outline is unsupported")
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_overlaps(left, right, *, epsilon=1e-7):
    # Conservative contact guard. A bbox overlap can be a false positive
    # for curved legacy holes, which is deliberately fail-closed.
    a = _bbox(left); b = _bbox(right)
    return min(a[2], b[2])-max(a[0], b[0]) > epsilon and min(a[3], b[3])-max(a[1], b[1]) > epsilon


def preflight_nfb_inner_door_opening(
    panel: InnerDoorPanelPart,
    request: NfbUpperOpeningRequest,
    *,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
) -> NfbUpperOpeningPreflight:
    """Build a safe preview from the UPPER Color150 source, never manufacture.

    Source provenance is validated independently from target part and
    projection. Missing approvals block; a verified shape and a filename
    cannot become approved X or Y by implication.
    """
    if not isinstance(panel, InnerDoorPanelPart):
        raise TypeError("NFB target must be an InnerDoorPanelPart")
    if not isinstance(request, NfbUpperOpeningRequest):
        raise TypeError("NFB request must be NfbUpperOpeningRequest")
    delta = _upper_rectangle_relative_vertices(request)
    diagnostics: list[str] = []
    if not request.physical_hole_id or not request.physical_hole_id.strip():
        diagnostics.append("MISSING_PHYSICAL_HOLE_ID")
    if request.target_part_id != panel.stable_id:
        diagnostics.append("TARGET_PART_MISMATCH")
    if request.uv_center_x is None or request.x_rule_revision is None:
        diagnostics.append("OPEN_X_NOT_CERTIFIED")
    if request.uv_center_y is None or request.y_rule_revision is None:
        diagnostics.append("OPEN_Y_NOT_CERTIFIED")
    if not request.model_filename or not str(request.model_filename).lower().endswith(".dxf"):
        diagnostics.append("INDEXED_MODEL_FILENAME_UNRESOLVED")

    preview: tuple[tuple[float, float], ...] = ()
    if request.uv_center_x is not None and request.uv_center_y is not None:
        cx, cy = _finite_xy((request.uv_center_x, request.uv_center_y), "NFB target UV center")
        preview = tuple((cx + x, cy + y) for x, y in delta)
        left = panel.fold_left
        right = panel.unfolded_width - panel.fold_right
        bottom = panel.fold_bottom
        top = panel.unfolded_height - panel.fold_top
        tol = 1e-7
        # Inner-door flat CORE is smaller than the outer unfolded CUTTING.
        if any(not (left + tol < x < right - tol and bottom + tol < y < top - tol)
               for x, y in preview):
            diagnostics.append("OPENING_OUTSIDE_FINISHED_DOOR_CORE")

    for claim in tuple(existing_claims):
        if not isinstance(claim, NfbExistingCuttingClaim):
            raise TypeError("legacy claims must be NfbExistingCuttingClaim instances")
        if claim.part_id != panel.stable_id:
            # Existing holes on another physical part are not conflicts.
            continue
        if (claim.physical_hole_id == request.physical_hole_id
                and bool(request.physical_hole_id)):
            diagnostics.append("LEGACY_PHYSICAL_HOLE_ALREADY_OWNED")
        if preview and _bbox_overlaps(preview, tuple(
                _finite_xy(v, "legacy CUTTING point") for v in claim.outline_uv_xy)):
            diagnostics.append("LEGACY_CUTTING_FOOTPRINT_COLLISION")

    if diagnostics:
        return NfbUpperOpeningPreflight(
            physical_hole_id=request.physical_hole_id,
            part_id=panel.stable_id,
            status=BLOCKED,
            diagnostics=tuple(dict.fromkeys(diagnostics)),
            preview_outline_uv_xy=preview,
            source_sha256=request.source_sha256,
            source_handle=request.source_handle,
        )
    return NfbUpperOpeningPreflight(
        physical_hole_id=request.physical_hole_id,
        part_id=panel.stable_id,
        status=PREVIEW_ONLY,
        diagnostics=("MANUFACTURING_CAPABILITY_NOT_REGISTERED",),
        preview_outline_uv_xy=preview,
        source_sha256=request.source_sha256,
        source_handle=request.source_handle,
    )


def preflight_nfb_inner_door_batch(
    panel: InnerDoorPanelPart,
    requests: Sequence[NfbUpperOpeningRequest],
    *,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
) -> NfbUpperOpeningBatchPreflight:
    """Plan a whole proposed edit atomically, without mutating owner/Feature data.

    Duplicate IDs or colliding NFB units block the entire batch. An invalid
    switch-model change must NOT silently move a neighbor or remove legacy.
    All-success is still PREVIEW_ONLY until an authorized capability is added.
    """
    proposals = tuple(requests)
    if not proposals:
        return NfbUpperOpeningBatchPreflight(
            status=PREVIEW_ONLY, diagnostics=("NO_NEW_NFB_CUTTING",), items=(),
        )
    items = tuple(preflight_nfb_inner_door_opening(
        panel, request, existing_claims=existing_claims,
    ) for request in proposals)
    problems: list[str] = []
    if any(item.status == BLOCKED for item in items):
        problems.extend(code for item in items for code in item.diagnostics)
    for idx, first in enumerate(items):
        for second in items[idx+1:]:
            if (first.physical_hole_id and
                    first.physical_hole_id == second.physical_hole_id):
                problems.append("DUPLICATE_NEW_NFB_PHYSICAL_HOLE_OWNER")
            if first.preview_outline_uv_xy and second.preview_outline_uv_xy and (
                    _bbox_overlaps(
                        first.preview_outline_uv_xy, second.preview_outline_uv_xy
                    )):
                problems.append("NEW_NFB_CUTTING_FOOTPRINT_COLLISION")
    if problems:
        return NfbUpperOpeningBatchPreflight(
            status=BLOCKED, diagnostics=tuple(dict.fromkeys(problems)), items=items,
        )
    return NfbUpperOpeningBatchPreflight(
        status=PREVIEW_ONLY,
        diagnostics=("MANUFACTURING_CAPABILITY_NOT_REGISTERED",),
        items=items,
    )
