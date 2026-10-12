# -*- coding: utf-8 -*-
"""#1497 one real NFB upper source -> inner-door CUTTING trial.

One data-driven adapter, not one code path per NFB filename. The trusted
operator-owned CSV selects (brand, filename); a source profile names the
original DXF SHA and UPPER Color150 entity. Only a matching parsed source may
supply its geometry. A trial scene contains real, closed CUTTING polylines,
but is NEVER routed into the production exporter without the independently
certified OPEN-X / OPEN-Y / part-owner capability (#1494/#1498).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from math import isfinite
import json
from typing import Sequence

from .inner_door_panels import InnerDoorPanelPart
from .manufacturing_api import build_inner_door_panel_render_data
from .manufacturing_render_data import PartRenderData, material_polygon_from_final_scene
from .receiving_nfb_cutting_preflight import (
    BLOCKED, NfbExistingCuttingClaim, NfbUpperOpeningRequest,
    preflight_nfb_inner_door_batch,
)
from .receiving_nfb_dxf_source import (
    NfbSourceInventory, resolve_upper_color150_reference,
)
from .receiving_nfb_index_sources import NfbIndexSourceCatalog
from .sheetmetal_drawing import (
    DrawingScene, CirclePrimitive, PolylinePrimitive,
)

TRIAL_ONLY = "NFB_CUTTING_TRIAL_NOT_PRODUCTION_APPROVED"
SOURCE_ALIAS_UNCERTIFIED = "SOURCE_ALIAS_UNCERTIFIED"


@dataclass(frozen=True)
class NfbUpperSourceProfile:
    brand: str
    indexed_filename: str
    source_sha256: str
    upper_handle: str
    upper_size_mm: tuple[float, float]
    source_alias_status: str
    revision: str


@dataclass(frozen=True)
class NfbInnerDoorCuttingTrial:
    part_id: str
    model_key: tuple[str, str]
    status: str
    render_data: object
    physical_hole_ids: tuple[str, ...]
    source_sha256: str
    source_handle: str
    manufacturing_ready: bool = False


def read_nfb_upper_source_profiles(path: str | Path) -> tuple[NfbUpperSourceProfile, ...]:
    """New DXF models add verified *data records*, never new geometry code."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema") != "WHD_NFB_UPPER_SOURCE_PROFILE_V1":
        raise ValueError("NFB source profile schema unsupported")
    rows = []
    keys = set()
    for item in raw["profiles"]:
        brand = str(item["brand"]).strip()
        filename = str(item["indexed_filename"]).strip()
        key = (brand, filename.casefold())
        if not brand or not filename.lower().endswith(".dxf") or key in keys:
            raise ValueError("NFB profile has duplicate/invalid (brand, filename)")
        if "/" in filename or "\\" in filename or filename in (".", ".."):
            raise ValueError("NFB profile must use an index basename")
        keys.add(key)
        digest = str(item["source_sha256"]).lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("NFB profile requires original DXF sha256")
        size = tuple(float(v) for v in item["upper_size_mm"])
        if len(size) != 2 or min(size) <= 0:
            raise ValueError("NFB upper Color150 dimensions invalid")
        rows.append(NfbUpperSourceProfile(
            brand=brand, indexed_filename=filename, source_sha256=digest,
            upper_handle=str(item["upper_handle"]).strip(),
            upper_size_mm=size,
            source_alias_status=str(item["source_alias_status"]),
            revision=str(item["revision"]),
        ))
    return tuple(rows)



def read_nfb_runtime_source_profiles_csv(path: str | Path) -> tuple[NfbUpperSourceProfile, ...]:
    """Read source fingerprints from operator-editable CSV, never as approval."""
    import csv
    keys=("brand","indexed_filename","source_sha256","upper_handle",
          "upper_width_mm","upper_height_mm","source_alias_status","revision")
    results=[]; seen=set()
    with Path(path).open("r",encoding="utf-8-sig",newline="") as stream:
        reader=csv.DictReader(stream)
        if tuple(reader.fieldnames or ())!=keys:
            raise ValueError("NFB source-profile CSV header invalid")
        for number,row in enumerate(reader,start=2):
            if not row or any(row.get(key) is None for key in keys):
                raise ValueError(f"NFB source-profile CSV row {number} incomplete")
            brand=row["brand"].strip()
            filename=row["indexed_filename"].strip()
            digest=row["source_sha256"].strip().lower()
            handle=row["upper_handle"].strip()
            if (not brand or not filename.lower().endswith(".dxf")
                    or filename in (".dxf",".DXF") or
                    "/" in filename or chr(92) in filename):
                raise ValueError("NFB source-profile CSV name invalid")
            key=(brand,filename.casefold())
            if key in seen:
                raise ValueError("NFB source-profile CSV duplicate model")
            seen.add(key)
            if (len(digest)!=64 or
                    any(char not in "0123456789abcdef" for char in digest)):
                raise ValueError("NFB source-profile CSV SHA256 invalid")
            try:
                width,height=float(row["upper_width_mm"]),float(row["upper_height_mm"])
            except (ValueError,TypeError) as exc:
                raise ValueError("NFB source-profile CSV dimensions invalid") from exc
            if (not isfinite(width) or not isfinite(height) or
                    width<=0 or height<=0 or not handle):
                raise ValueError("NFB source-profile CSV geometry invalid")
            results.append(NfbUpperSourceProfile(
                brand=brand,indexed_filename=filename,source_sha256=digest,
                upper_handle=handle,upper_size_mm=(width,height),
                source_alias_status=row["source_alias_status"],
                revision=row["revision"],
            ))
    return tuple(results)


def _validated_legacy_inner_door_scene(
    panel: InnerDoorPanelPart,
    current: PartRenderData | None,
) -> tuple[PartRenderData, tuple[NfbExistingCuttingClaim, ...]]:
    """Keep native legacy-hole geometry and detect physical CUTTING collisions.

    An existing FinalScene is accepted ONLY for the same real sheet and after
    its entire canonical outer CUTTING/BEND prefix matches WHD's fresh part.
    The extra physical holes preserve their own primitives/IDs, while the
    common manufacturing UV becomes the single owner for collisions.
    Unsupported/open CUTTING is not silently ignored.
    """
    baseline = build_inner_door_panel_render_data(panel)
    if current is None:
        return baseline, ()
    if not isinstance(current, PartRenderData):
        raise TypeError("NFB existing physical FinalScene must be PartRenderData")
    meta = dict(current.metadata)
    if (meta.get("stable_id") != panel.stable_id
            or meta.get("inner_door_id") != panel.inner_door_id
            or meta.get("cell_key") != panel.cell_key
            or current.unfolded_topology != baseline.unfolded_topology
            or current.fold_guides != baseline.fold_guides):
        raise ValueError("NFB legacy inner-door FinalScene physical identity/topology mismatch")
    before = tuple(baseline.scene.primitives)
    actual = tuple(current.scene.primitives)
    if len(actual) < len(before) or actual[:len(before)] != before:
        raise ValueError("NFB legacy FinalScene must preserve exact original panel CUTTING/BEND")
    claims = []
    for index, primitive in enumerate(actual[len(before):], start=1):
        if str(getattr(primitive, "layer", "")).upper() != "CUTTING":
            # MARKING/BEND/etc stay in the final scene unmodified.
            continue
        hole_id = f"legacy:{panel.stable_id}:{index}"
        if isinstance(primitive, PolylinePrimitive):
            vertices = tuple((float(p.x), float(p.y)) for p in primitive.points)
            if not primitive.closed or len(vertices) < 3 or len(set(vertices)) < 3:
                raise ValueError("NFB existing legacy CUTTING contour is not closed")
            outline = vertices
        elif isinstance(primitive, CirclePrimitive):
            center = primitive.center
            x, y, radius = float(center.x), float(center.y), float(primitive.radius)
            from math import isfinite
            if not all(isfinite(t) for t in (x, y, radius)) or radius <= 0:
                raise ValueError("NFB existing legacy CIRCLE has invalid CUTTING radius")
            # Bounding polygon is intentionally conservative for round holes:
            # bbox intersection may hold a noncolliding hole, never duplicate it.
            outline = (
                (x-radius, y-radius), (x+radius, y-radius),
                (x+radius, y+radius), (x-radius, y+radius),
            )
            if primitive.source_id:
                hole_id = primitive.source_id
        else:
            raise ValueError("NFB existing legacy CUTTING type cannot be safely owned")
        if (any(not all(__import__("math").isfinite(v) for v in pair) for pair in outline)):
            raise ValueError("NFB existing legacy CUTTING contains nonfinite XY")
        claims.append(NfbExistingCuttingClaim(
            physical_hole_id=hole_id,
            part_id=panel.stable_id,
            outline_uv_xy=outline,
        ))
    return current, tuple(claims)


def trial_nfb_upper_cutting_on_inner_door(
    panel: InnerDoorPanelPart,
    requests: Sequence[NfbUpperOpeningRequest],
    *,
    catalog: NfbIndexSourceCatalog,
    inventory: NfbSourceInventory,
    profile: NfbUpperSourceProfile,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
    existing_render_data: PartRenderData | None = None,
) -> NfbInnerDoorCuttingTrial:
    """Render actual closed NFB CUTTING contours without releasing manufacturing.

    The caller supplies the real source inventory from inspect_nfb_dxf_source;
    source SHA, handle, shape and the operator CSV must all agree. Requests
    supply independent panel UV X/Y projections, never guessed from the DXF
    bounding box or the center of a nominal W. All requests are atomic.
    """
    if not isinstance(panel, InnerDoorPanelPart):
        raise TypeError("NFB cutting target must be a physical inner-door panel")
    if not isinstance(catalog, NfbIndexSourceCatalog):
        raise TypeError("NFB model catalog must come from 開關索引.csv")
    if not isinstance(inventory, NfbSourceInventory):
        raise TypeError("NFB original DXF source inventory required")
    matches = [s for s in catalog.sources if
               s.brand == profile.brand and
               s.filename.casefold() == profile.indexed_filename.casefold()]
    if len(matches) != 1:
        raise ValueError("NFB source not present exactly once in current operator CSV")
    if inventory.source_sha256 != profile.source_sha256:
        raise ValueError("NFB source SHA differs from sample / approved profile")
    if not profile.upper_handle:
        raise ValueError("NFB upper Color150 source handle required")
    ref = resolve_upper_color150_reference(
        inventory,
        upper_source_entity_ids=(f"{inventory.source_sha256}:{profile.upper_handle}",),
    )
    if (abs(ref.size_mm[0] - profile.upper_size_mm[0]) > 1e-5
            or abs(ref.size_mm[1] - profile.upper_size_mm[1]) > 1e-5):
        raise ValueError("NFB upper Color150 contour differs from profile")
    proposed = tuple(requests)
    if not proposed:
        raise ValueError("NFB trial requires at least one physical hole")
    # Never trust arbitrary request contour or identity in preference to the
    # actual SHA-bound source entity. Lower spacer and Color30/212 are omitted.
    normalized = tuple(replace(
        request,
        model_filename=profile.indexed_filename,
        source_sha256=ref.source_sha256,
        source_handle=profile.upper_handle,
        source_region="UPPER",
        source_aci=150,
        source_outline_xy=ref.source_outline_vertices_xy,
        source_center_xy=ref.center_xy,
        source_profile_closed=True,
        source_bulges=(0.0,) * len(ref.source_outline_vertices_xy),
    ) for request in proposed)
    # Reject spoofed model/source details instead of silently remapping them.
    for orig in proposed:
        if (orig.model_filename != profile.indexed_filename
                or orig.source_sha256 != profile.source_sha256
                or orig.source_handle != profile.upper_handle
                or orig.source_aci != 150 or orig.source_region != "UPPER"):
            raise ValueError("NFB request/model/source identity mismatch")
    baseline, native_legacy_claims = _validated_legacy_inner_door_scene(
        panel, existing_render_data,
    )
    preflight = preflight_nfb_inner_door_batch(
        panel, normalized,
        existing_claims=(*tuple(existing_claims), *native_legacy_claims),
    )
    if preflight.status == BLOCKED:
        raise ValueError("NFB cutting trial blocked: " + ",".join(preflight.diagnostics))
    if any(not item.preview_outline_uv_xy for item in preflight.items):
        raise ValueError("NFB cutting trial cannot infer unapproved X/Y centers")

    scene = DrawingScene()
    scene.extend(tuple(baseline.scene.primitives))
    for item in preflight.items:
        scene.add_polyline(item.preview_outline_uv_xy, layer="CUTTING", closed=True, color=3)
    # Recompute material from the exact same candidate FinalScene and preserve
    # the canonical door fold topology; the stock/legacy data is not mutated.
    trial_render = replace(
        baseline, scene=scene,
        material=material_polygon_from_final_scene(scene),
        metadata={
            **dict(baseline.metadata),
            "nfb_trial_status": TRIAL_ONLY,
            "nfb_trial_export_approved": False,
            "nfb_source_brand": profile.brand,
            "nfb_indexed_model": profile.indexed_filename,
            "nfb_source_sha256": profile.source_sha256,
            "nfb_profile_revision": profile.revision,
        },
    )
    return NfbInnerDoorCuttingTrial(
        part_id=panel.stable_id,
        model_key=(profile.brand, profile.indexed_filename),
        status=TRIAL_ONLY, render_data=trial_render,
        physical_hole_ids=tuple(r.physical_hole_id for r in normalized),
        source_sha256=ref.source_sha256, source_handle=profile.upper_handle,
    )
