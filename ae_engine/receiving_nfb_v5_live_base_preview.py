# -*- coding: utf-8 -*-
"""Actual Receiving base PartSpec -> current V5 operator screw trial.

The original #1502 physical base owner and fold-pattern contract determines
the sheet, real EAR cutouts, flat work face and Y installation envelope.
Never create a second base, infer ear Z, or authorize manufacturing.
"""
from __future__ import annotations

from math import isfinite
from typing import Mapping, Sequence

from .contracts import BasePlatePartSpec
from .manufacturing_api import build_part_render_data
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
    if not entries or len(entries) != len(door.hole_ids):
        raise ValueError("NFB V5 未取得完整的已配置螺絲孔所屬開關")
    world_centres = []
    for entry in entries:
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
    center_world = (
        (min(x for x, _ in world_centres)+max(x for x, _ in world_centres))/2,
        world_centres[0][1],
    )
    original = build_part_render_data(base_spec)
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
    margin_x = (71.0 if base_spec.receiving_bend_pattern
                == RECEIVING_BASE_PATTERN_CENTER else 0.0)
    x0, x1 = margin_x, w-margin_x
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
    )
