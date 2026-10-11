# -*- coding: utf-8 -*-
"""#1502 physical middle-plate Color150 CUTTING shadow, NOT production export.

Use the one source Color150 upper contour/pivot verified for the inner door,
but resolve the MIDDLE plate as its actual Box Body horizontal divider with
its OWN unfolded material and world placement. The operator's world X is
never treated as a flat-pattern coordinate. A signed span-axis orientation
and a physical fold-core depth datum are still independent assembly
evidence, so this returns a trial FinalScene and NEVER manufacturing READY.

Source Color30, Color212 and the entire LOWER group are deliberately not
ported to this middle plate. They need separate real part/process evidence;
a color or original source region alone is not a part owner.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path
from typing import Mapping

from shapely.geometry import Polygon

from .assembly_geometry import place_assembly_points
from .assembly_placement import resolve_divider_placement
from .door_dividers import BoxBodyDividerPart
from .manufacturing_api import material_polygon_from_final_scene
from .manufacturing_render_data import PartRenderData
from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_dxf_source import (
    inspect_nfb_dxf_source, place_upper_color150_opening_outline,
    resolve_upper_color150_reference,
)
from .receiving_nfb_source_regions import (
    inspect_nfb_original_source_regions, UPPER, LOWER,
)
from .sheetmetal_drawing import DrawingScene

MIDDLE_SHADOW = "MFG2_MIDDLE_PLATE_COLOR150_PHYSICAL_SHADOW_ONLY"


@dataclass(frozen=True)
class NfbMiddlePlateUnfoldDatum:
    """Uncertified until the physical width/depth axis is witnessed.

    Flat strip Y is the horizontal divider's real column span. Its positive
    direction in WORLD X must come from physical assembly evidence, not from
    a DXF filename or nominal switch pitch. Core depth UV X is explicitly
    supplied pending world Z -> folded divider face registration.
    """
    part_id: str
    span_world_x_sign: int
    core_depth_uv_x_mm: float
    revision: str


@dataclass(frozen=True)
class NfbMiddlePlateShadow:
    part_id: str
    source_sha256: str
    source_handle: str
    original_region: str
    world_x_mm: float
    uv_center_xy: tuple[float, float]
    uv_outline_xy: tuple[tuple[float, float], ...]
    render_data: PartRenderData
    status: str = MIDDLE_SHADOW
    manufacturing_ready: bool = False


def shadow_nfb_middle_plate_color150(
    snapshot: Mapping[str, object],
    divider: BoxBodyDividerPart,
    baseline: PartRenderData,
    *, source_path: str | Path,
    profile: NfbUpperSourceProfile,
    lower_reference_handle: str,
    world_x_mm: float,
    physical_datum: NfbMiddlePlateUnfoldDatum,
    rotation_deg: int = 0,
) -> NfbMiddlePlateShadow:
    """Transfer only the native upper Color150 main aperture into a real
    horizontal divider FinalScene. NOT a permission to manufacture.
    """
    if not isinstance(divider, BoxBodyDividerPart) or divider.axis != "HORIZONTAL":
        raise ValueError("NFB middle plate requires actual horizontal Box Body divider")
    if not isinstance(baseline, PartRenderData):
        raise TypeError("NFB middle plate requires canonical PartRenderData")
    if not isinstance(physical_datum, NfbMiddlePlateUnfoldDatum):
        raise TypeError("NFB middle plate requires typed physical unfolding datum")
    if (physical_datum.part_id != divider.stable_id
            or type(physical_datum.span_world_x_sign) is not int
            or physical_datum.span_world_x_sign not in (-1, 1)
            or not isinstance(physical_datum.revision, str)
            or not physical_datum.revision.strip()):
        raise ValueError("NFB middle plate physical UV axis/datum is unresolved")
    if (type(world_x_mm) not in (int, float) or not isfinite(float(world_x_mm))
            or type(physical_datum.core_depth_uv_x_mm) not in (int, float)
            or not isfinite(float(physical_datum.core_depth_uv_x_mm))):
        raise ValueError("NFB middle plate WORLD-X/core UV must be finite physical coordinates")
    meta = dict(baseline.metadata or {})
    topology = baseline.unfolded_topology
    if (topology is None or topology.piece_id != divider.stable_id
            or abs(float(topology.width) - divider.blank_width) > 1e-5
            or abs(float(topology.height) - divider.blank_height) > 1e-5
            or meta.get("stable_id") != divider.stable_id
            or meta.get("axis") != "HORIZONTAL"
            or dict(meta.get("physical_geometry_contract") or {})
               != dict(divider.physical_geometry_contract)):
        raise ValueError("NFB middle part's actual resolved unfold topology differs")
    placement = resolve_divider_placement(snapshot, divider.stable_id)
    if (placement.stable_id != divider.stable_id
            or placement.parent_assembly_node != "box_body"
            or not placement.placement_kind.startswith("divider_horizontal")
            or tuple(placement.rotation) != (0.0, 0.0, 0.0)):
        raise ValueError("NFB middle plate actual placement contract mismatch")
    # Verify the proposed flat-span orientation against the SAME physical
    # folded-mesh placement transform used by 3D/assembly. Both ordinary and
    # inward horizontal divider placements must preserve native UV +Y -> X.
    # A wrong sign is not a harmless visual mirror: the hole would be cut on
    # the opposite side of the actual middle sheet.
    span = float(divider.span)
    endpoints = place_assembly_points(
        ((0., 0., 0.), (0., span, 0.)),
        (((0., 0., 0.), (0., span, 0.), (1., 0., 0.)),),
        placement.placement_kind,
        (float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
        offset=placement.world_offset,
    )
    if (len(endpoints) != 2
            or abs((endpoints[1][0] - endpoints[0][0])
                   - span * physical_datum.span_world_x_sign) > 1e-6):
        raise ValueError("NFB middle flat span orientation contradicts physical assembly")
    core = divider.physical_geometry_contract["core_physical_segment"]
    band = tuple(core.get("flat_band") or ())
    if len(band) != 2 or not (float(band[0]) < float(band[1])):
        raise ValueError("NFB middle plate physical fold core unavailable")

    source = Path(source_path)
    regions = inspect_nfb_original_source_regions(
        source, indexed_filename=profile.indexed_filename,
        expected_sha256=profile.source_sha256,
        upper_reference_handle=profile.upper_handle,
        lower_reference_handle=lower_reference_handle,
        expected_upper_width_mm=profile.upper_size_mm[0],
        expected_upper_height_mm=profile.upper_size_mm[1],
    )
    if (regions.upper.region != UPPER or regions.lower.region != LOWER
            or profile.upper_handle not in regions.upper.entity_handles):
        raise ValueError("NFB upper Color150 source owner not established")
    inventory = inspect_nfb_dxf_source(source)
    ref = resolve_upper_color150_reference(
        inventory, upper_source_entity_ids=(
            f"{inventory.source_sha256}:{profile.upper_handle}",
        ),
    )
    if (ref.size_mm != tuple(profile.upper_size_mm)
            or ref.source_sha256 != regions.source_sha256):
        raise ValueError("NFB main Color150 source has changed")

    # The physical horizontal divider's unfolded strip X is folded depth;
    # unfolded strip Y is the TRUE column span. World X=column center maps
    # to the middle of that span, not to source DXF world coordinates.
    uv_x = float(physical_datum.core_depth_uv_x_mm)
    uv_y = divider.span / 2.0 + physical_datum.span_world_x_sign * (
        float(world_x_mm) - float(placement.world_offset[0])
    )
    recovered_world_x = float(placement.world_offset[0]) + (
        uv_y - divider.span / 2.0
    ) / physical_datum.span_world_x_sign
    if abs(recovered_world_x - float(world_x_mm)) > 1e-7:
        raise ValueError("NFB middle plate WORLD X / unfolded span not reversible")
    outline = place_upper_color150_opening_outline(
        reference=ref, target_center_xy=(uv_x, uv_y),
        rotation_deg=rotation_deg, consumer="MIDDLE_PLATE",
    )
    hole = Polygon(outline)
    if not hole.is_valid or hole.area <= 0:
        raise ValueError("NFB middle plate native opening invalid")
    epsilon = 1e-6
    if any(
        not (float(band[0]) + epsilon < x < float(band[1]) - epsilon
             and epsilon < y < divider.span - epsilon)
        for x, y in outline
    ):
        raise ValueError("NFB middle opening outside actual flat fold core/span")
    # Existing baseline holes, relief and perimeter own the original material.
    # A candidate that overlaps any of them must not silently duplicate CUTTING.
    if baseline.material is None or not baseline.material.covers(hole.buffer(epsilon)):
        raise ValueError("NFB middle aperture collides with existing real CUTTING/material")
    scene = DrawingScene(primitives=list(baseline.scene.primitives))
    scene.add_polyline(outline, layer="CUTTING", closed=True, color=150)
    trial = replace(
        baseline, scene=scene,
        material=material_polygon_from_final_scene(scene),
        metadata={
            **meta,
            "nfb_mfg2_status": MIDDLE_SHADOW,
            "nfb_mfg2_manufacturing_ready": False,
            "nfb_source_sha256": regions.source_sha256,
            "nfb_source_region": UPPER,
            "nfb_source_handle": profile.upper_handle,
            "nfb_middle_physical_part_id": divider.stable_id,
            "nfb_middle_world_x_mm": float(world_x_mm),
            "nfb_middle_unfold_datum_revision": physical_datum.revision,
            "nfb_middle_uv_center": (uv_x, uv_y),
        },
    )
    if abs(float(trial.material.area) -
           (float(baseline.material.area) - float(hole.area))) > 1e-4:
        raise ValueError("NFB middle plate CUTTING shadow did not remove exact source aperture")
    return NfbMiddlePlateShadow(
        part_id=divider.stable_id, source_sha256=regions.source_sha256,
        source_handle=profile.upper_handle, original_region=UPPER,
        world_x_mm=float(world_x_mm), uv_center_xy=(uv_x, uv_y),
        uv_outline_xy=outline, render_data=trial,
    )
