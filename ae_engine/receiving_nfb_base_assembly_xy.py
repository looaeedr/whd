# -*- coding: utf-8 -*-
"""#1502: legacy NFB HOLE-group X/Y preview from current committed Bay.

WARNING: the returned X/Y are NFB OPENING coordinates on the inner door,
NOT the world position of an entire Receiving Base Plate. The Base Plate is
secured to the left/right side-sheet welded fixing plates; its assembly XY
must be derived from the ear contact and its 670-mm support holes, never from
an operator-edited hole height or a mean NFB opening X.

Kept for hole projection compatibility until callers migrate to a per-layer
NFB Feature owner. DO NOT reconnect this helper to resolve_base_plate_placement.
One NFB layer needs one independently installed Base Plate / ear pair.
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
    """Return NFB *hole row* Y and optional confirmed hole X (not plate XY).

    Kept under its existing public function name for compatibility; consumers
    may project switch holes/bolts but may NEVER move the whole welded-ear
    Base Plate to this Y. A per-layer Base Plate is a separate physical part.
    Do not mix two distinct NFB rows in this single-row preview result.
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
