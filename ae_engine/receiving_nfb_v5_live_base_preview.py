# -*- coding: utf-8 -*-
"""Actual Receiving base PartSpec -> current V5 operator screw trial.

The original #1502 physical base owner and fold-pattern contract determines
the sheet, real EAR cutouts, flat work face and Y installation envelope.
Never create a second base, infer ear Z, or authorize manufacturing.
"""
from __future__ import annotations

from dataclasses import replace
from math import isfinite
from typing import Mapping, Sequence

from .contracts import BasePlatePartSpec
from .manufacturing_api import build_part_render_data
from .manufacturing_render_data import PartRenderData
from .receiving_nfb_base_process_projection import NfbActualBaseWorkFace
from .receiving_nfb_v5_actual_base_screws import (
    NfbV5ActualBaseScrewTrial, trial_v5_screws_on_existing_receiving_base,
)
from .receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole, NfbV5ConfiguredInnerDoorTrial,
)
from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from .sheetmetal_drawing import PolylinePrimitive
from .sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_CENTER, RECEIVING_BASE_PATTERNS,
    derive_door_layout_cells, door_layout_part_key,
)
from .assembly_placement import resolve_outer_door_placement

_TOL = 1e-6


def preview_v5_on_existing_receiving_base(
    snapshot: Mapping[str, object], inner_door_id: str,
    *, door: NfbV5ConfiguredInnerDoorTrial,
    configured_holes: Sequence[NfbV5ConfiguredInnerDoorHole],
    base_spec: BasePlatePartSpec,
    tier_slot_index: int | None = None,
    existing_render_data: PartRenderData | None = None,
) -> NfbV5ActualBaseScrewTrial:
    """Use current application's existing base PartSpec, not a test fixture.

    One real plate = one installation Y row. The physical base width,
    thickness, receiving bend pattern, physical ID, EAR slots and upper-cell
    fit all come from the same current owner as existing #1502 MFG-2.
    """
    if not isinstance(base_spec, BasePlatePartSpec):
        raise ValueError("NFB V5 尚未取得目前連的原始實體底板 PartSpec")
    if str(base_spec.model_name or "").strip() not in ("受電箱", "RECEIVING"):
        raise ValueError("NFB V5 底板不是目前的受電箱實體板件")
    if base_spec.receiving_bend_pattern not in RECEIVING_BASE_PATTERNS:
        raise ValueError("NFB V5 底板未設定實際折彎型式")
    physical_id = str(base_spec.physical_id or "").strip()
    if not physical_id or physical_id.startswith("base_plate_c"):
        raise ValueError("NFB V5 不可拿舊內門格子的虛構底板當實體底板")
    if tier_slot_index is not None:
        if type(tier_slot_index) is not int or tier_slot_index < 0:
            raise ValueError("NFB V5 實體層索引不合法")
        if physical_id != f"base_plate:nfb_layer:{tier_slot_index}":
            raise ValueError("NFB V5 實體底板不是本層原始 BasePlatePartSpec")
    if (abs(float(snapshot.get("w", 0)) - float(base_spec.width)) > _TOL
            or abs(float(snapshot.get("t", 0)) - float(base_spec.thickness)) > _TOL):
        raise ValueError("NFB V5 底板寬／板厚與目前受電箱不符")
    inner = next((
        row for row in snapshot.get("inner_doors", ())
        if isinstance(row, Mapping)
        and row.get("stable_id") == inner_door_id
    ), None)
    if inner is None:
        raise ValueError("NFB V5 原內門不屬於目前實體箱")
    try:
        col, row = (int(v) for v in str(inner.get("cell_key", "")).split(":"))
    except ValueError as exc:
        raise ValueError("NFB V5 原內門缺少所屬實體格") from exc
    cells = derive_door_layout_cells(snapshot.get("door_layout_columns") or ())
    cell = next((v for v in cells
                 if (v.column_index, v.row_index) == (col, row)), None)
    if cell is None or row != 0 or abs(float(cell.start_height) - 1100) > _TOL:
        raise ValueError("NFB V5 尚未核對上方 1100 實體作用區")
    if not (0 < float(base_spec.height) <= float(cell.start_height)):
        raise ValueError("NFB V5 原始底板高度超出上方實體作用區")
    entries = tuple(configured_holes)
    if (not entries or len(entries) != len(door.hole_ids)
            or tuple(e.physical_hole_id for e in entries) != door.hole_ids):
        raise ValueError("NFB V5 未取得完整的已配置螺絲孔所屬開關")
    selected = tuple(
        e for e in entries
        if tier_slot_index is None or e.slot_index == tier_slot_index
    )
    if not selected:
        raise ValueError("NFB V5 本層沒有對應的已配置開關")
    world_centres = []
    for entry in selected:
        if not isinstance(entry, NfbV5ConfiguredInnerDoorHole):
            raise ValueError("NFB V5 缺少已配置孔位識別")
        if (type(entry.world_x_mm) not in (int, float)
                or not isfinite(float(entry.world_x_mm))):
            raise ValueError("NFB V5 實體世界 X 不合法")
        yy = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id,
            layer_count=entry.layer_count, slot_index=entry.slot_index,
        )
        world_centres.append((float(entry.world_x_mm), float(yy.box_world_y_mm)))
    if max(v for _, v in world_centres) - min(v for _, v in world_centres) > _TOL:
        raise ValueError("NFB V5 不同層高必須各有原始實體底板，不可共用")
    # Receiving Base Plate and its four EAR mounting slots are fixed at
    # cabinet X=0. Each NFB's world X shifts ONLY its own screw circles.
    # Averaging the NFB centres here used to move the entire plate and
    # falsely rejected every legitimately offset NFB row.
    center_world = (0.0, world_centres[0][1])
    # Punch the already-built physical AssemblyScenePart, not a parallel
    # rendering; compare with the current canonical PartSpec before overlay.
    canonical = build_part_render_data(base_spec)
    if existing_render_data is None:
        original = canonical
    else:
        original = existing_render_data
        if (not isinstance(original, PartRenderData)
                or original.unfolded_topology != canonical.unfolded_topology
                or tuple(original.scene.primitives) != tuple(canonical.scene.primitives)
                or original.material is None
                or original.material.symmetric_difference(canonical.material).area > _TOL
                or tuple(original.fold_guides or ()) != tuple(canonical.fold_guides or ())
                or original.metadata.get("stable_id") != physical_id
                or original.metadata.get("receiving_bend_pattern")
                   != base_spec.receiving_bend_pattern):
            raise ValueError("NFB V5 實際組合體底板與目前來源 PartSpec 不一致")
    topo = original.unfolded_topology
    if (topo is None or topo.piece_id != physical_id
            or original.metadata.get("stable_id") != physical_id):
        raise ValueError("NFB V5 底板 PartSpec 與 FinalScene 實體身份不符")
    w, h = float(topo.width), float(topo.height)
    outer = resolve_outer_door_placement(snapshot, door_layout_part_key(cell))
    lower = float(outer.world_offset[1])-float(cell.start_height)/2
    upper = float(outer.world_offset[1])+float(cell.start_height)/2
    if (center_world[1]-h/2 < lower-_TOL
            or center_world[1]+h/2 > upper+_TOL):
        raise ValueError("NFB V5 底板裝配位置超出上方作用區")
    if abs(center_world[0])+float(base_spec.width)/2 > float(snapshot["w"])/2+_TOL:
        raise ValueError("NFB V5 底板整片超出箱體寬度")
    # Resolve the real source-generated BEND stations, not the old 71-mm
    # nominal or a second hardcoded unfolded face width.
    if base_spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_CENTER:
        x_guides = sorted({
            float(g.position) for g in tuple(original.fold_guides or ())
            if str(g.axis) == "x"
        })
        if len(x_guides) != 4:
            raise ValueError("NFB V5 原底板缺少四條真實側折 BEND")
        x0 = x_guides[1] + float(base_spec.thickness)/2.0
        x1 = x_guides[2] - float(base_spec.thickness)/2.0
    else:
        x0, x1 = 0.0, w
    y0, y1 = float(base_spec.bend), h-float(base_spec.bend)
    if x0 >= x1 or y0 >= y1:
        raise ValueError("NFB V5 原底板沒有有效平面工作區")
    original_ears = tuple(p for p in original.scene.primitives
                          if isinstance(p, PolylinePrimitive)
                          and p.layer == "CUTTING" and p.closed)
    if len(original_ears) != 5:
        raise ValueError("NFB V5 原底板不含一個外形及四處 EAR 固定孔")
    target = NfbActualBaseWorkFace(
        physical_part_id=physical_id,
        actual_render=original,
        world_face_center_xy_mm=center_world,
        unfolded_face_center_uv_mm=((x0+x1)/2, (y0+y1)/2),
        face_outline_uv_mm=((x0,y0), (x1,y0), (x1,y1), (x0,y1)),
    )
    return trial_v5_screws_on_existing_receiving_base(
        snapshot, inner_door_id,
        door=door, configured_holes=entries, target=target,
        tier_slot_index=tier_slot_index,
    )


def preview_v5_on_existing_receiving_tier_bases(
    snapshot: Mapping[str, object], inner_door_id: str,
    *, door: NfbV5ConfiguredInnerDoorTrial,
    configured_holes: Sequence[NfbV5ConfiguredInnerDoorHole],
    base_specs: Mapping[int, BasePlatePartSpec],
) -> tuple[NfbV5ActualBaseScrewTrial, ...]:
    """One unchanged CSV source/geometry algorithm for ONE or MANY real NFB tiers.

    The FULL inner-door trial is passed unmodified to each tier, not split
    into forged independent certifications. Each existing BasePlatePartSpec
    owns exactly one tier and its four fixed EAR mount holes. This is still
    an unapproved FinalScene *trial*, never a whole-box MFG-2 export.
    """
    entries = tuple(configured_holes)
    if (not isinstance(door, NfbV5ConfiguredInnerDoorTrial)
            or not entries or not isinstance(base_specs, Mapping)
            or len(entries) != len(door.hole_ids)
            or tuple(e.physical_hole_id for e in entries) != door.hole_ids):
        raise ValueError("NFB V5 每層須提供完整原內門孔位試作與實體板件")
    counts = {e.layer_count for e in entries}
    if len(counts) != 1 or type(next(iter(counts))) is not int or next(iter(counts)) < 1:
        raise ValueError("NFB V5 必須提供一致且至少一層的實際層數")
    count = next(iter(counts))
    if (any(type(e.slot_index) is not int
            or not 0 <= e.slot_index < count for e in entries)):
        raise ValueError("NFB V5 各顆所屬層索引不合法")
    active = {e.slot_index for e in entries}
    if set(base_specs) != active:
        raise ValueError("NFB V5 實體底板集合與已有開關的層數不一致")
    results = tuple(
        preview_v5_on_existing_receiving_base(
            snapshot, inner_door_id,
            door=door, configured_holes=entries,
            base_spec=base_specs[tier], tier_slot_index=tier,
        )
        for tier in sorted(active)
    )
    if len({part.part_id for part in results}) != len(results):
        raise ValueError("NFB V5 各層底板實體 ID 重複")
    assert all(not part.manufacturing_ready for part in results)
    return results


def project_csv_v5_onto_existing_assembly_parts(
    snapshot: Mapping[str, object], inner_door_id: str,
    *, door: NfbV5ConfiguredInnerDoorTrial,
    configured_holes: Sequence[NfbV5ConfiguredInnerDoorHole],
    base_specs: Mapping[int, BasePlatePartSpec],
    assembly_parts: Sequence[object],
) -> tuple[object, ...]:
    """Cut CSV screws into the actual physical 2D/3D AssemblyScenePart renders.

    Preserve physical identity, installed offsets, fold profiles and the
    other assembly pieces. This is not DXF permission or a new blank.
    """
    entries = tuple(configured_holes)
    parts = tuple(assembly_parts)
    if (not isinstance(door, NfbV5ConfiguredInnerDoorTrial)
            or not entries or not isinstance(base_specs, Mapping)
            or tuple(e.physical_hole_id for e in entries) != door.hole_ids
            or not parts):
        raise ValueError("NFB V5 組合體缺少完整內門來源或實體底板")
    if any(not isinstance(e, NfbV5ConfiguredInnerDoorHole) for e in entries):
        raise TypeError("NFB V5 組合體含非實體孔位")
    counts = {e.layer_count for e in entries}
    if len(counts) != 1 or next(iter(counts)) not in (1, 2):
        raise ValueError("NFB V5 組合體 NFB 層數不一致")
    count = next(iter(counts))
    active = {e.slot_index for e in entries}
    if (any(type(e.slot_index) is not int or not 0 <= e.slot_index < count
            for e in entries) or set(base_specs) != active):
        raise ValueError("NFB V5 組合體每層缺少獨立原始底板來源")

    by_key = {}
    for part in parts:
        key = str(getattr(part, "part_key", ""))
        if key in by_key:
            raise ValueError("NFB V5 組合體重複的實體板件身份")
        by_key[key] = part
    output = {}
    for tier in sorted(active):
        spec = base_specs[tier]
        if not isinstance(spec, BasePlatePartSpec):
            raise TypeError("NFB V5 每層必須使用實體 BasePlatePartSpec")
        expected = ("base_plate" if count == 1 and spec.physical_id == "base_plate"
                    else f"base_plate:nfb_layer:{tier}")
        if spec.physical_id != expected or expected not in by_key:
            raise ValueError("NFB V5 組合體不存在本層原始實體底板")
        owner = by_key[expected]
        if not isinstance(getattr(owner, "render_data", None), PartRenderData):
            raise ValueError("NFB V5 組合體缺少本層原始 PartRenderData")
        projected = preview_v5_on_existing_receiving_base(
            snapshot, inner_door_id, door=door,
            configured_holes=entries, base_spec=spec,
            tier_slot_index=(None if expected == "base_plate" else tier),
            existing_render_data=owner.render_data,
        )
        if projected.part_id != expected or expected in output:
            raise ValueError("NFB V5 底板 FinalScene 所屬實體漂移")
        output[expected] = projected.render_data

    return tuple(replace(part, render_data=output[part.part_key])
                 if part.part_key in output else part for part in parts)
