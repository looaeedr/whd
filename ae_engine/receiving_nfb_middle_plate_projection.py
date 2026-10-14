# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

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
from .cabinet_types import policy as cabinet_family_policy
from .door_dividers import BoxBodyDividerPart
from .manufacturing_api import material_polygon_from_final_scene
from .manufacturing_render_data import PartRenderData
from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)
from .receiving_nfb_middle_3d_witness import (
    witness_middle_plate_uv_on_folded_assembly,
)
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
    verified_inner_door: NfbValidatedInnerDoorRender,
    physical_hole_id: str,
    physical_datum: NfbMiddlePlateUnfoldDatum,
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
    if (type(physical_datum.core_depth_uv_x_mm) not in (int, float)
            or not isfinite(float(physical_datum.core_depth_uv_x_mm))):
        raise ValueError("NFB middle plate core UV must be finite physical coordinate")
    # Reuse existing #1497 verified NFBConfig; never ask for a second X.
    if (not isinstance(verified_inner_door, NfbValidatedInnerDoorRender)
            or not verified_inner_door.manufacturing_ready
            or not isinstance(physical_hole_id, str) or not physical_hole_id):
        raise ValueError("NFB middle plate needs an existing verified inner-door hole")
    hole_rows = tuple(row for row in verified_inner_door.verified_hole_locations
                      if row[0] == physical_hole_id)
    if len(hole_rows) != 1 or verified_inner_door.physical_hole_ids.count(physical_hole_id) != 1:
        raise ValueError("NFB middle plate physical hole identity is missing/ambiguous")
    _id, world_x_mm, _layers, _slot, rotation_deg = hole_rows[0]
    if type(world_x_mm) not in (int, float) or not isfinite(float(world_x_mm)):
        raise ValueError("NFB existing verified hole position is invalid")
    inner = tuple(p for p in cabinet_family_policy.derive_inner_door_panels(snapshot)
                  if p.stable_id == verified_inner_door.part_id)
    if (len(inner) != 1 or inner[0].cell_key not in divider.adjacent_cells
            or not str(inner[0].cell_key).endswith(":0")):
        raise ValueError("NFB middle plate and verified inner door do not share an upper cell")
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
            or ref.source_sha256 != regions.source_sha256
            or verified_inner_door.source_sha256 != regions.source_sha256
            or verified_inner_door.indexed_model_key
               != (profile.brand, profile.indexed_filename)):
        raise ValueError("NFB middle/inner original Color150 identity differs")
    proof_meta = getattr(verified_inner_door.render_data, "metadata", {})
    if (proof_meta.get("nfb_trial_status") != VALIDATED
            or proof_meta.get("nfb_trial_export_approved") is not True
            or proof_meta.get("nfb_source_handle") != ref.source_entity_id
            or proof_meta.get("nfb_profile_revision") != profile.revision):
        raise ValueError("NFB middle Color150 differs from verified inner-door source proof")

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
    # Verify the *same* flat UV against the canonical physically folded 3D
    # material before drawing. This proves the candidate's assembled XYZ
    # and WORLD X consistency, but NOT the final NFB depth datum.
    witness = witness_middle_plate_uv_on_folded_assembly(
        snapshot, divider, baseline,
        uv_xy=(uv_x, uv_y), expected_world_x_mm=float(world_x_mm),
    )
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
            "nfb_middle_assembled_world_xyz": witness.world_xyz,
            "nfb_middle_3d_witness_status": witness.status,
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
