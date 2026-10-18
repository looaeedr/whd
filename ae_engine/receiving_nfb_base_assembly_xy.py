# -*- coding: utf-8 -*-
"""#1502: CENTER-to-CENTER NFB opening-group and per-tier Base Plate placement.

User product rule: each NFB tier within the UPPER outer-door compartment
has ONE independently installed Base Plate with left/right fixing plates;
the plate centre follows the tier's NFB opening-group centre. This
placement DOES NOT change the plate's physical finished W/H. The OUTER
door's lower compartment has no NFB Base Plate.

The actual welded fixing-plate side-sheet MARKING remains non-certified.
Unknown/unconfirmed NFB X never becomes verified manufacturing evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class ReceivingNfbBaseAssemblyXY:
    world_y_mm: float
    verified_world_x_mm: float | None
    source_hole_count: int
    inner_door_id: str


def receiving_source_nfb_base_assembly_xy(snapshot, inner_door_id):
    """Legacy one-row convenience projection; per-tier ownership below.

    For one tier, the NFB opening group's XY also anchors the installed
    Base Plate's centre (CENTER-to-CENTER), not its finished height. Multiple
    tiers each require their own Base Plate; never mix rows into one result.
    """
    from .receiving_nfb_depth_surface_policy import (
        committed_receiving_nfb_depth_pair_mm,
        committed_receiving_flat_nfb_depth_mm,
    )
    from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    if not isinstance(snapshot,Mapping):
        raise TypeError("NFB assembly XY requires physical Receiving snapshot")
    pair=committed_receiving_nfb_depth_pair_mm(snapshot)
    flat_depth=(
        committed_receiving_flat_nfb_depth_mm(snapshot)
        if pair is None else None
    )
    if pair is None and flat_depth is None:
        return None
    config = snapshot.get("nfb_config")
    if not isinstance(config, Mapping):
        layout=snapshot.get("receiving_layout")
        sets=layout.get("sets") if isinstance(layout,Mapping) else None
        chosen=None
        if isinstance(sets,(tuple,list)) and sets:
            selected=snapshot.get("_receiving_runtime_selection")
            if isinstance(selected,Mapping):
                si,bi=selected.get("set_index"),selected.get("bay_index")
                if (type(si) is int and 0<=si<len(sets)
                        and isinstance(sets[si],Mapping)
                        and sets[si].get("stable_id")==selected.get("set_id")):
                    bays=sets[si].get("bays")
                    if (isinstance(bays,(tuple,list)) and type(bi) is int
                            and 0<=bi<len(bays) and isinstance(bays[bi],Mapping)
                            and bays[bi].get("stable_id")==selected.get("bay_id")):
                        chosen=bays[bi]
            elif (len(sets)==1 and isinstance(sets[0],Mapping)
                  and isinstance(sets[0].get("bays"),(tuple,list))
                  and len(sets[0]["bays"])==1):
                chosen=sets[0]["bays"][0]
        if not isinstance(chosen,Mapping):
            raise ValueError("NFB_BASE_XY_ACTIVE_BAY_UNRESOLVED")
        config=chosen.get("nfb_config")
    if not isinstance(config,Mapping):
        raise ValueError("NFB_BASE_XY_CONFIG_MISSING")
    rows=config.get("holes")
    if (not isinstance(rows,(tuple,list)) or not 1<=len(rows)<=2
            or (pair is not None and len(rows)!=2)):
        raise ValueError("NFB_BASE_XY_REQUIRES_ONE_OR_TWO_SAME_ROW_HOLES")
    y_values=[]
    x_values=[]
    projections={}
    for row in rows:
        if not isinstance(row,Mapping):
            raise ValueError("NFB_BASE_XY_HOLE_INVALID")
        count=row.get("layer_count",config.get("layer_count"))
        slot=row.get("slot_index",0)
        # Both same-row models share ONE geometry solve. Do not rebuild the
        # full inner-door FinalScene for every hole on a normal two-NFB row.
        key=(count,slot)
        if key not in projections:
            projections[key]=project_nfb_inner_door_nominal_y(
                snapshot,inner_door_id,layer_count=count,slot_index=slot,
            )
        y_values.append(float(projections[key].box_world_y_mm))
        x=row.get("manual_x_mm")
        confirmed=(
            row.get("manual_x_state")=="CONFIRMED"
            and type(x) in (int,float) and isfinite(float(x))
            and isinstance(row.get("datum_revision"),str) and bool(row.get("datum_revision"))
            and isinstance(row.get("datum_snapshot"),Mapping) and bool(row.get("datum_snapshot"))
        )
        if confirmed:
            x_values.append(float(x))
    if abs(y_values[0]-y_values[1])>1e-6:
        raise ValueError("NFB_BASE_XY_DISTINCT_ROWS_REQUIRE_DISTINCT_PHYSICAL_PLATES")
    x_center=(min(x_values)+max(x_values))/2 if len(x_values)==len(rows) else None
    return ReceivingNfbBaseAssemblyXY(
        world_y_mm=y_values[0],verified_world_x_mm=x_center,
        source_hole_count=len(rows),inner_door_id=str(inner_door_id),
    )



@dataclass(frozen=True)
class ReceivingNfbLayerCenter:
    """Source geometry target for one physical NFB tier's Base Plate."""

    layer_index: int
    layer_part_id: str
    world_y_mm: float
    verified_world_x_mm: float | None
    source_hole_count: int
    inner_door_id: str


def receiving_nfb_layer_centers(
    snapshot: Mapping[str, object], inner_door_id: str,
) -> tuple[ReceivingNfbLayerCenter, ...]:
    """Return independent CENTER-to-CENTER positions for every submitted tier.

    The caller must instantiate ONE separately-owned physical Base Plate and
    one left/right fixing-plate pair per result. A legacy root 'base_plate'
    may consume this only when exactly one tier is configured; never collapse
    a two-tier layout into one root plate.

    Y is from the approved NFB inner-door opening projection; X is the
    opening group's bounding-box centre only when every hole has a confirmed
    source X. Without X provenance, zero is a *preview* fallback at the
    callsite, not manufacturing-authorized positioning.
    """
    from .receiving_layout import RECEIVING_RUNTIME_SELECTION_KEY
    from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y

    if not isinstance(snapshot, Mapping):
        raise TypeError("RECEIVING_NFB_LAYER_CENTER_REQUIRES_SNAPSHOT")
    if snapshot.get("nfb_config_submitted") is False:
        return ()
    layout = snapshot.get("receiving_layout")
    sets = layout.get("sets") if isinstance(layout, Mapping) else None
    if not isinstance(sets, (list, tuple)) or not sets:
        return ()
    selection = snapshot.get(RECEIVING_RUNTIME_SELECTION_KEY)
    if isinstance(selection, Mapping):
        si, bi = selection.get("set_index"), selection.get("bay_index")
        if (type(si) is not int or not 0 <= si < len(sets)
                or not isinstance(sets[si], Mapping)
                or sets[si].get("stable_id") != selection.get("set_id")):
            raise ValueError("RECEIVING_NFB_LAYER_SET_IDENTITY_DRIFT")
        bays = sets[si].get("bays")
        if (not isinstance(bays, (list, tuple))
                or type(bi) is not int or not 0 <= bi < len(bays)
                or not isinstance(bays[bi], Mapping)
                or bays[bi].get("stable_id") != selection.get("bay_id")):
            raise ValueError("RECEIVING_NFB_LAYER_BAY_IDENTITY_DRIFT")
        bay = bays[bi]
    elif (len(sets) == 1 and isinstance(sets[0], Mapping)
          and isinstance(sets[0].get("bays"), (list, tuple))
          and len(sets[0]["bays"]) == 1):
        bay = sets[0]["bays"][0]
    else:
        # Do not use a random Bay or overwrite a nonselected tier.
        return ()
    if not isinstance(bay, Mapping) or bay.get("nfb_config_submitted") is not True:
        return ()
    config = bay.get("nfb_config")
    if not isinstance(config, Mapping):
        raise ValueError("RECEIVING_NFB_LAYER_SUBMITTED_CONFIG_MISSING")
    if ("nfb_config" in snapshot and snapshot["nfb_config"] != config):
        raise ValueError("RECEIVING_NFB_LAYER_CONFIG_IDENTITY_DRIFT")
    count = config.get("layer_count")
    if type(count) is not int or count not in (1, 2):
        raise ValueError("RECEIVING_NFB_LAYER_COUNT_UNSUPPORTED")
    holes = config.get("holes")
    if not isinstance(holes, (list, tuple)) or not holes:
        raise ValueError("RECEIVING_NFB_LAYER_HOLES_MISSING")
    by_tier: dict[int, list[Mapping[str, object]]] = {}
    for row in holes:
        if not isinstance(row, Mapping):
            raise ValueError("RECEIVING_NFB_LAYER_HOLE_INVALID")
        if row.get("layer_count", count) != count:
            raise ValueError("RECEIVING_NFB_LAYER_HOLE_COUNT_DRIFT")
        slot = row.get("slot_index", 0)
        if type(slot) is not int or not 0 <= slot < count:
            raise ValueError("RECEIVING_NFB_LAYER_SLOT_OUTSIDE_CURRENT_LAYOUT")
        if not isinstance(row.get("physical_hole_id"), str):
            raise ValueError("RECEIVING_NFB_LAYER_HOLE_ID_MISSING")
        by_tier.setdefault(slot, []).append(row)

    projected: list[ReceivingNfbLayerCenter] = []
    for slot in sorted(by_tier):
        hole_rows = by_tier[slot]
        hole = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id, layer_count=count, slot_index=slot,
        )
        confirmed_x: list[float] = []
        for row in hole_rows:
            x = row.get("manual_x_mm")
            if (row.get("manual_x_state") != "CONFIRMED"
                    or type(x) not in (int, float) or not isfinite(float(x))
                    or not isinstance(row.get("datum_revision"), str)
                    or not row.get("datum_revision")
                    or not isinstance(row.get("datum_snapshot"), Mapping)
                    or not row.get("datum_snapshot")):
                break
            confirmed_x.append(float(x))
        x_center = (
            (min(confirmed_x) + max(confirmed_x)) / 2.0
            if len(confirmed_x) == len(hole_rows) else None
        )
        projected.append(ReceivingNfbLayerCenter(
            layer_index=slot,
            layer_part_id=f"base_plate:nfb_layer:{slot}",
            world_y_mm=float(hole.box_world_y_mm),
            verified_world_x_mm=x_center,
            source_hole_count=len(hole_rows),
            inner_door_id=str(inner_door_id),
        ))
    return tuple(projected)
