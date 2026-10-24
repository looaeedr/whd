# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""OPEN-Y-PROJECTION: box-top nominal NFB Y -> physical inner-door flat Y.

This is a geometric source contract, NOT NFB model/CUTTING certification.
It consumes the existing Receiving panel manufacturing, folded-core topology
and assembly placement; it neither inserts holes nor upgrades preview status.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .assembly_placement import resolve_inner_door_panel_placement
from .cabinet_types import policy as cabinet_family_policy
from .manufacturing_api import build_inner_door_panel_render_data
from .sheetmetal_part_adapters import derive_door_layout_cells

RULE_ID = "OPEN-Y-PROJECTION"
REVISION = "WHD-RECEIVING-NFB-Y-1100-V1"
OPERATOR_HEIGHT_REVISION = "WHD-RECEIVING-NFB-Y-OPERATOR-HEIGHT-V1"
_STATUS = "GEOMETRY_ONLY_NOT_NFB_CUTTING_CERTIFIED"
_NOMINAL_TOP_Y_MM = {
    1: (550.0,),
    2: (290.0, 790.0),
}


@dataclass(frozen=True)
class NfbInnerDoorYProjection:
    rule_id: str
    revision: str
    status: str
    part_id: str
    cell_key: str
    layer_count: int
    slot_index: int
    nominal_y_from_box_top_mm: float
    box_world_y_mm: float
    finished_face_y_from_bottom_mm: float
    unfolded_uv_y_mm: float
    unfolded_uv_y_from_top_mm: float
    unfolded_blank_height_mm: float
    finished_panel_height_mm: float


def approved_nominal_y_mm(layer_count: int) -> tuple[float, ...]:
    """Only the explicitly specified 1100-mm upper-cell one/two-layer cases."""
    if isinstance(layer_count, bool) or layer_count not in _NOMINAL_TOP_Y_MM:
        raise ValueError("OPEN-Y-PROJECTION unsupported NFB layer count")
    return _NOMINAL_TOP_Y_MM[layer_count]


def _inner_door_y_basis(snapshot: Mapping[str, object], inner_door_id: str):
    """Resolve real part/placement/core-band; reject unsupported datum changes."""
    data = dict(snapshot or {})
    if str(data.get("model", "")).strip() not in {"受電箱", "RECEIVING"}:
        raise ValueError("OPEN-Y-PROJECTION requires Receiving family")
    if not bool(data.get("multi_door_enabled")):
        raise ValueError("OPEN-Y-PROJECTION requires enabled Door topology")
    columns = list(data.get("door_layout_columns") or ())
    if not columns:
        raise ValueError("OPEN-Y-PROJECTION requires authoritative Door cells")
    try:
        # Original physical W/H/T must remain typed until validation.
        # bool is not a millimetre; malformed saved huge ints cannot overflow.
        raw_whd = (data["w"], data["h"], data["t"])
        if any(isinstance(value, bool) for value in raw_whd):
            raise ValueError("boolean physical dimension")
        cells = derive_door_layout_cells(columns)
        full_h = float(data["h"])
        full_w = float(data["w"])
        t = float(data["t"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("OPEN-Y-PROJECTION invalid box dimensional authority") from exc
    if (not all(isfinite(v) for v in (full_h, full_w, t))
            or full_h <= 0 or full_w <= 0 or t <= 0
            or abs(sum(float(col[0]) for col in columns) - full_w) > 1e-6
            or any(abs(sum(float(v) for v in col[1]) - full_h) > 1e-6
                   for col in columns)):
        # Diagnostics preserve strict dimensional refusal while exposing the
        # exact *input authority* that drifted after a real Set/Bay edit.
        raise ValueError(
            "OPEN-Y-PROJECTION inconsistent box and Door partitions: "
            f"box=({full_w:g},{full_h:g}); "
            f"columns={tuple((row[0], tuple(row[1])) for row in columns)!r}; "
            f"selection={data.get('_receiving_runtime_selection')!r}"
        )
    wanted = str(inner_door_id or "").strip()
    owners = [row for row in data.get("inner_doors", ())
              if isinstance(row, dict) and str(row.get("stable_id", "")).strip() == wanted]
    if len(owners) != 1:
        raise ValueError("OPEN-Y-PROJECTION unresolved or duplicate inner-door owner")
    cell_key = str(owners[0].get("cell_key", "")).strip()
    cell = next((row for row in cells if f"{row.column_index}:{row.row_index}" == cell_key), None)
    if cell is None:
        raise ValueError("OPEN-Y-PROJECTION inner-door owner has no valid cell")
    if cell.row_index != 0 or abs(float(cell.start_height) - 1100.0) > 1e-6:
        # Y=550/290/790 are box-TOP datums for H1100 upper cells only.
        raise ValueError("OPEN-Y-PROJECTION unapproved cell height / box-top Y datum")
    panels = [p for p in cabinet_family_policy.derive_inner_door_panels(data)
              if p.inner_door_id == wanted and p.cell_key == cell_key]
    if len(panels) != 1:
        raise ValueError("OPEN-Y-PROJECTION ambiguous manufactured inner-door part")
    part = panels[0]
    placement = resolve_inner_door_panel_placement(data, wanted)
    if placement.stable_id != part.stable_id:
        raise ValueError("OPEN-Y-PROJECTION assembly and manufacture part ID mismatch")
    render = build_inner_door_panel_render_data(part)
    topology = render.unfolded_topology
    if topology is None or topology.piece_id != part.stable_id:
        raise ValueError("OPEN-Y-PROJECTION missing canonical unfolded part topology")
    segments = tuple(topology.y_segments)
    if tuple(item.name for item in segments) != (
        "inner_door_fold_bottom", "inner_door_face_height", "inner_door_fold_top",
    ):
        raise ValueError("OPEN-Y-PROJECTION unsupported folded Y core owner")
    lower_fold, core, upper_fold = (float(s.length) for s in segments)
    blank_h = float(topology.height)
    if (
        min(lower_fold, core, upper_fold) <= 0.0
        or abs(blank_h - part.unfolded_height) > 1e-6
        or abs(core - (part.height - 2.0 * t)) > 1e-6
        or abs(render.metadata["finished_height"] - part.height) > 1e-6
    ):
        raise ValueError("OPEN-Y-PROJECTION folded core / finished face mismatch")
    return part, placement, cell_key, full_h, t, lower_fold, core, blank_h


def project_nfb_inner_door_nominal_y(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    *,
    layer_count: int,
    slot_index: int,
) -> NfbInnerDoorYProjection:
    """Project the approved nominal box-top Y onto one real inner Door blank.

    Box top is +H/2 in existing assembly Y. The Y core midplane is the
    centered manufacturing face segment, NOT the outer blank's bottom edge.
    Translation is physical assembly placement; fold lengths come from the
    actual manufacturing topology, without a new 36.5/50/80-mm offset.
    """
    approved = approved_nominal_y_mm(layer_count)  # keep the 1/2-layer hard gate
    heights = snapshot.get("receiving_inner_door_layer_heights_mm")
    if heights is not None:
        from .receiving_shared_settings import validate_setting
        checked = validate_setting("inner_door_layer_heights_mm", heights)
        nominal = tuple(checked[:layer_count])
        revision = OPERATOR_HEIGHT_REVISION
    else:
        nominal = approved
        revision = REVISION
    if isinstance(slot_index, bool) or not isinstance(slot_index, int) or not 0 <= slot_index < len(nominal):
        raise ValueError("OPEN-Y-PROJECTION invalid NFB layer slot")
    part, placement, cell_key, full_h, t, lower_fold, core, blank_h = (
        _inner_door_y_basis(snapshot, inner_door_id)
    )
    from_top = nominal[slot_index]
    world_y = full_h / 2.0 - from_top
    core_local_y = world_y - float(placement.world_offset[1])
    if not -core / 2.0 < core_local_y < core / 2.0:
        raise ValueError("OPEN-Y-PROJECTION nominal center outside physical flat face")
    flat_uv_y = lower_fold + core / 2.0 + core_local_y
    finished_y_from_bottom = float(part.height) / 2.0 + core_local_y
    return NfbInnerDoorYProjection(
        rule_id=RULE_ID, revision=revision, status=_STATUS,
        part_id=part.stable_id, cell_key=cell_key,
        layer_count=layer_count, slot_index=slot_index,
        nominal_y_from_box_top_mm=from_top,
        box_world_y_mm=world_y,
        finished_face_y_from_bottom_mm=finished_y_from_bottom,
        unfolded_uv_y_mm=flat_uv_y,
        unfolded_uv_y_from_top_mm=blank_h - flat_uv_y,
        unfolded_blank_height_mm=blank_h,
        finished_panel_height_mm=float(part.height),
    )


def invert_nfb_inner_door_unfolded_y(
    snapshot: Mapping[str, object], inner_door_id: str, *, unfolded_uv_y_mm: float,
) -> float:
    """Recover the nominal box-top Y from the same true folded core.

    Inverse coordinates are geometric evidence only; they do not license
    unapproved slot counts/heights or manufacturing holes.
    """
    part, placement, _cell_key, full_h, _t, lower_fold, core, _blank_h = (
        _inner_door_y_basis(snapshot, inner_door_id)
    )
    v = float(unfolded_uv_y_mm)
    if not isfinite(v) or not lower_fold < v < lower_fold + core:
        raise ValueError("OPEN-Y-PROJECTION unfolded Y outside inner-door face core")
    world_y = float(placement.world_offset[1]) + v - lower_fold - core / 2.0
    from_top = full_h / 2.0 - world_y
    if not isfinite(from_top):
        raise ValueError("OPEN-Y-PROJECTION nonfinite reconstructed nominal Y")
    return from_top
