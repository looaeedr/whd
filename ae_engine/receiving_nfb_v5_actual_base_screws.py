# -*- coding: utf-8 -*-
"""V5 screw CUTTING on a supplied actual Receiving Base Plate work face.

The verified *geometry-only* V5 inner-door trial owns each switch installation
centre. Existing #1502 NfbActualBaseWorkFace owns the corresponding real base
sheet, EAR openings, UV face, and assembly group centre. There is no invented
second base, automatic PAD, model-derived Z, or manufacturing authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from math import isfinite
from typing import Mapping, Sequence

from shapely.geometry import Point
from shapely.ops import unary_union

from .manufacturing_render_data import (
    PartRenderData, material_polygon_from_final_scene,
)
from .receiving_nfb_base_process_projection import NfbActualBaseWorkFace, _work_face
from .receiving_nfb_numeric_catalog import brand_csv_path
from .receiving_nfb_numeric_panel_projection import (
    NfbPanelDatum, NfbV5PanelPattern, project_nfb_v5_to_panel,
)
from .receiving_nfb_v5_configured_inner_door import (
    AXES, STATUS as DOOR_TRIAL_STATUS,
    NfbV5ConfiguredInnerDoorHole, NfbV5ConfiguredInnerDoorTrial,
)
from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from .receiving_nfb_manufacturing_release import _resolve_physical_panel
from .receiving_nfb_model_identity import parse_numeric_model_ref
from .sheetmetal_drawing import CirclePrimitive, DrawingScene, PolylinePrimitive

STATUS = "NFB_V5_ACTUAL_BASE_SCREW_TRIAL_UNVERIFIED"
_TOL = 1e-6


@dataclass(frozen=True)
class NfbV5ActualBaseScrewTrial:
    part_id: str
    hole_ids: tuple[str, ...]
    patterns: tuple[NfbV5PanelPattern, ...]
    render_data: PartRenderData
    status: str = STATUS
    manufacturing_ready: bool = False


def trial_v5_screws_on_existing_receiving_base(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    *,
    door: NfbV5ConfiguredInnerDoorTrial,
    configured_holes: Sequence[NfbV5ConfiguredInnerDoorHole],
    target: NfbActualBaseWorkFace,
    tier_slot_index: int | None = None,
) -> NfbV5ActualBaseScrewTrial:
    """Physically subtract 4 V5 mounting circles per switch from ONE base.

    All switch installation centres must be on this existing plate's Y row.
    A separate physical base identity is required for a second vertical row;
    callers cannot silently create two EAR groups on one part. Collision with
    an EAR slot, native hole, another switch or a fold is an atomic failure.
    """
    if (not isinstance(door, NfbV5ConfiguredInnerDoorTrial)
            or door.status != DOOR_TRIAL_STATUS or door.manufacturing_ready
            or door.render_data.metadata.get("nfb_trial_export_approved") is not False):
        raise ValueError("NFB V5 底板孔須對應真實但尚未核准的內門開孔")
    panel, placement = _resolve_physical_panel(snapshot, inner_door_id)
    if door.part_id != panel.stable_id:
        raise ValueError("NFB V5 底板與內門實體來源不一致")
    if (not isinstance(target, NfbActualBaseWorkFace)
            or not isinstance(target.actual_render, PartRenderData)):
        raise TypeError("NFB V5 螺絲孔需要現有實體底板工作面")
    face_poly, face_world, face_uv = _work_face(target)
    baseline = target.actual_render
    metadata = dict(baseline.metadata or {})
    if (metadata.get("receiving_bend_pattern") not in (
            "LEFT_FLAT_SIDE", "RIGHT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD")
            or metadata.get("nfb_v5_trial_status") is not None
            or metadata.get("nfb_trial_export_approved") is True
            or baseline.material is None or baseline.material.is_empty):
        raise ValueError("NFB V5 須使用原始已配置折邊／EAR 的實際底板")
    native = tuple(p for p in baseline.scene.primitives
                   if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
                   and p.closed)
    if len(native) != 5:
        raise ValueError("NFB V5 原底板必須已有一片外形與四處 EAR 固定開孔")
    current = material_polygon_from_final_scene(baseline.scene)
    if current.symmetric_difference(baseline.material).area > _TOL:
        raise ValueError("NFB V5 底板 FinalScene 與實際材料不一致")

    entries = tuple(configured_holes)
    if (not entries or len(entries) != len(door.patterns)
            or tuple(e.physical_hole_id for e in entries) != door.hole_ids
            or len(set(door.hole_ids)) != len(door.hole_ids)):
        raise ValueError("NFB V5 底板必須對應相同的完整內門孔位群")
    if tier_slot_index is not None and (
        type(tier_slot_index) is not int or tier_slot_index < 0
    ):
        raise ValueError("NFB V5 實體層索引不合法")
    selected_entries = tuple(
        e for e in entries
        if tier_slot_index is None or e.slot_index == tier_slot_index
    )
    if not selected_entries:
        raise ValueError("NFB V5 實體底板對應層沒有開關")
    footprints = []
    patterns = []
    source_brands = {entry.brand for entry in entries}
    # Bind this current geometry trial to the exact CSV source bytes; later
    # CHECK Q must reject a stale trial rather than silently reuse old holes.
    def source_hashes():
        try:
            return tuple(sorted(
                (brand, sha256(brand_csv_path(brand).read_bytes()).hexdigest())
                for brand in source_brands
            ))
        except OSError as exc:
            raise ValueError("NFB V5 原始 CSV 來源不可讀") from exc

    csv_sha = source_hashes()
    for entry, prior in zip(entries, door.patterns):
        if not isinstance(entry, NfbV5ConfiguredInnerDoorHole):
            raise TypeError("NFB V5 原始孔位識別格式不符")
        parsed = parse_numeric_model_ref(entry.model_ref)
        if (parsed is None or parsed != (entry.brand, prior.model)
                or prior.brand != entry.brand or prior.datum.part_id != door.part_id
                or type(entry.rotation_deg) is not int
                or entry.rotation_deg not in AXES
                or type(entry.world_x_mm) not in (int, float)
                or not isfinite(float(entry.world_x_mm))):
            raise ValueError("NFB V5 底板來源型號、旋轉或世界 X 已改變")
        x = float(entry.world_x_mm)
        y = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id,
            layer_count=entry.layer_count, slot_index=entry.slot_index,
        )
        if y.part_id != door.part_id:
            raise ValueError("NFB V5 底板與內門層高所屬實體不符")
        expected_door_uv_x = (
            panel.fold_left
            + (panel.unfolded_width - panel.fold_left - panel.fold_right) / 2
            + x - float(placement.world_offset[0])
        )
        if (abs(prior.datum.uv_centre_mm[0] - expected_door_uv_x) > _TOL
                or abs(prior.datum.uv_centre_mm[1] - y.unfolded_uv_y_mm) > _TOL
                or (prior.datum.uv_axis_x, prior.datum.uv_axis_y) != AXES[entry.rotation_deg]):
            raise ValueError("NFB V5 內門已驗證孔位與目前裝配座標不一致")
        # Check the entire current Door proof before selecting this tier:
        # an unselected tier's changed model/X/Y/rotation cannot borrow the
        # saved full-door trial. The actual machining below is tier-local.
        if tier_slot_index is not None and entry.slot_index != tier_slot_index:
            continue
        world_y = float(y.box_world_y_mm)
        if abs(world_y - face_world[1]) > _TOL:
            raise ValueError("NFB V5 不同層高不可共用一片底板 EAR 工作面")
        # Existing #1502 contracts express face UV and its world XY centre
        # on the same axes. No paper DXF origin or W/2 inference.
        datum = NfbPanelDatum(
            target.physical_part_id, "base-plate",
            (face_uv[0] + x - face_world[0],
             face_uv[1] + world_y - face_world[1]),
            *AXES[entry.rotation_deg],
        )
        pattern = project_nfb_v5_to_panel(
            entry.brand, parsed[1], datum, feature="screws",
        )
        if pattern.screw_centres_uv_mm is None or len(pattern.screw_centres_uv_mm) != 4:
            raise ValueError("NFB V5 底板缺少四孔完整螺絲規格")
        radius = pattern.screw_diameter_mm / 2.0
        for position in pattern.screw_centres_uv_mm:
            circ = Point(position).buffer(radius, quad_segs=32)
            if (not face_poly.contains(circ)
                    or not baseline.material.contains(circ)):
                raise ValueError("NFB V5 螺絲孔碰到 EAR／原孔／折邊或超出實體底板")
            if any(circ.intersects(earlier) for earlier in footprints):
                raise ValueError("NFB V5 底板新增螺絲孔互相碰撞")
            footprints.append(circ)
        patterns.append(pattern)

    if source_hashes() != csv_sha:
        raise ValueError("NFB V5 CSV 驗算期間來源資料已變更")
    scene = DrawingScene(list(baseline.scene.primitives))
    for entry, pattern in zip(selected_entries, patterns):
        for index, centre in enumerate(pattern.screw_centres_uv_mm, start=1):
            scene.add_circle(
                centre, pattern.screw_diameter_mm / 2.0,
                layer="CUTTING", color=30,
                source_type="NFB_V5_NUMERIC_BASE_TRIAL",
                source_id=f"{entry.physical_hole_id}:screw:{index}",
            )
    material = material_polygon_from_final_scene(scene)
    expected = baseline.material.difference(unary_union(footprints))
    if (material.is_empty or not material.is_valid
            or material.symmetric_difference(expected).area > 1e-4
            or baseline.material.area <= material.area):
        raise ValueError("NFB V5 底板真實 FinalScene 螺絲孔驗算失敗")
    patched = replace(
        baseline, scene=scene, material=material,
        metadata={
            **metadata,
            "nfb_v5_trial_status": STATUS,
            "nfb_v5_hole_ids": tuple(e.physical_hole_id for e in selected_entries),
            "nfb_v5_tier_slot_index": tier_slot_index,
            "nfb_v5_source_models": tuple((x.brand, x.model) for x in patterns),
            "nfb_v5_source_csv_sha256": csv_sha,
            "nfb_v5_target_role": "base-plate",
            "nfb_base_mfg2_release_approved": False,
            "nfb_trial_export_approved": False,
        },
    )
    return NfbV5ActualBaseScrewTrial(
        part_id=target.physical_part_id,
        hole_ids=tuple(e.physical_hole_id for e in selected_entries),
        patterns=tuple(patterns),
        render_data=patched,
    )
