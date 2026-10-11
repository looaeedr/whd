# -*- coding: utf-8 -*-
"""#1502 trace *native* actual base DXF LINE+ARC loops without manufacturing.

An original white LINE or ARC is not automatically a CUTTING instruction.
Preserve exact source handles/radii/angles and report closed graphs versus
dangling/branched auxiliary geometry. Never add bridge edges, straighten arcs
or rewrite customer geometry. Color211 marks and CIRCLEs are distinct.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians, sin
from pathlib import Path
from typing import Iterable

import ezdxf

from .receiving_nfb_actual_base_source import (
    NfbActualBaseSource, inspect_receiving_nfb_actual_base,
)

_TOL = 1e-3
_STATUS = "NFB_ACTUAL_BASE_NATIVE_CLOSED_LOOP_AUDIT_NOT_CUTTING_APPROVAL"


@dataclass(frozen=True)
class NfbActualBaseContourAudit:
    pattern_key: str
    source_sha256: str
    fold_policy: str
    native_outer_loop_handles: tuple[str, ...]
    closed_loop_handle_groups: tuple[tuple[str, ...], ...]
    unresolved_white_source_handles: tuple[str, ...]
    original_circle_handles: tuple[str, ...]
    original_mark211_handles: tuple[str, ...]
    status: str = _STATUS
    manufacturing_ready: bool = False


def _pt(x,y):
    x,y=float(x),float(y)
    if not all(isfinite(v) for v in (x,y)):
        raise ValueError("NFB original DXF has nonfinite LINE/ARC endpoints")
    return int(round(x/_TOL)),int(round(y/_TOL))


def _native_endpoints(entity):
    kind=entity.dxftype()
    if kind=="LINE":
        return (_pt(entity.dxf.start.x,entity.dxf.start.y),
                _pt(entity.dxf.end.x,entity.dxf.end.y))
    if kind=="ARC":
        r=float(entity.dxf.radius)
        theta=(float(entity.dxf.start_angle),float(entity.dxf.end_angle))
        if r<=0 or not isfinite(r) or not all(isfinite(v) for v in theta):
            raise ValueError("NFB actual base original ARC geometry invalid")
        xy=[]
        for a in theta:
            rad=radians(a)
            xy.append(_pt(
                float(entity.dxf.center.x)+r*cos(rad),
                float(entity.dxf.center.y)+r*sin(rad),
            ))
        return tuple(xy)
    raise TypeError("NFB native outline candidate must be a LINE or ARC")


def _audit_one(pattern, entities):
    graph={}
    incident={}
    ids=tuple(
        h for h in (*pattern.native_line_handles,*pattern.native_arc_handles)
        if h not in set(pattern.native_mark211_handles)
    )
    for handle in ids:
        e=entities.get(handle)
        if e is None or e.dxftype() not in ("LINE","ARC"):
            raise ValueError("NFB source original LINE/ARC handle unavailable")
        a,b=_native_endpoints(e)
        graph[handle]=(a,b)
        incident.setdefault(a,[]).append(handle)
        incident.setdefault(b,[]).append(handle)
    visited=set()
    complete=[]
    unresolved=[]
    outer=None
    for first in ids:
        if first in visited:
            continue
        pending=[first]
        visited.add(first)
        component=[]
        vertices=set()
        while pending:
            item=pending.pop()
            component.append(item)
            for vertex in graph[item]:
                vertices.add(vertex)
                for adjacent in incident[vertex]:
                    if adjacent not in visited:
                        visited.add(adjacent)
                        pending.append(adjacent)
        # A simple closed contour has degree two at every graph vertex,
        # no degenerate edge and at least two distinct native entities.
        valid=(len(component)>=2
               and all(graph[item][0]!=graph[item][1] for item in component)
               and all(len(incident[point])==2 for point in vertices))
        ordered=tuple(sorted(component,key=lambda h:int(h,16)))
        if valid:
            complete.append(ordered)
            if pattern.source_anchor_handle in ordered:
                if outer is not None:
                    raise ValueError("NFB source pattern outer contour ambiguous")
                outer=ordered
        else:
            unresolved.extend(ordered)
    if len(visited)!=len(graph):
        raise ValueError("NFB original source audit dropped LINE/ARC entities")
    if outer is None:
        raise ValueError("NFB actual base outer contour is not a true closed native loop")
    return NfbActualBaseContourAudit(
        pattern_key=pattern.key,
        source_sha256=pattern.original_source_sha256,
        fold_policy=pattern.fold_policy,
        native_outer_loop_handles=outer,
        closed_loop_handle_groups=tuple(complete),
        unresolved_white_source_handles=tuple(
            sorted(unresolved,key=lambda h:int(h,16))
        ),
        original_circle_handles=pattern.native_circle_handles,
        original_mark211_handles=pattern.native_mark211_handles,
    )


def audit_receiving_nfb_actual_base_contours(
    source_path: str | Path, *,
    source: NfbActualBaseSource | None=None,
    index_path: str | Path | None=None,
) -> tuple[NfbActualBaseContourAudit, ...]:
    """Audit all three actual drawings as independent source candidates."""
    kwargs={} if index_path is None else {"index_path":index_path}
    current=inspect_receiving_nfb_actual_base(source_path,**kwargs)
    if source is not None and (source != current or not isinstance(source,NfbActualBaseSource)):
        raise ValueError("NFB candidate source proof is stale or differs from current DXF")
    doc=ezdxf.readfile(source_path)
    original={}
    for entity in doc.modelspace():
        handle=str(entity.dxf.get("handle","")).strip().upper()
        if handle:
            if handle in original:
                raise ValueError("NFB original DXF source handle duplicate")
            original[handle]=entity
    return tuple(_audit_one(p,original) for p in current.patterns)
