# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""#1502 native Shihlin upper source processing: reconstruct closed Color30.

This is SOURCE geometry only. No board position, UV, DXF emission or
manufacturing approval is inferred from a color. Upper Color212 is distinct
from the deferred 23 lower-region Color212 entities. Four source LINEs may
form one real closed CUTTING contour; missing/branching/crossing segments
are rejected rather than patched with fabricated cutting edges.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Sequence

from shapely.geometry import Polygon

from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_dxf_source import (
    NfbSourceEntity, inspect_nfb_dxf_source,
    resolve_upper_color150_reference,
)
from .receiving_nfb_source_regions import (
    UPPER, LOWER, inspect_nfb_original_source_regions,
)

OBSERVED = "NFB_UPPER_BASE_NATIVE_PROCESS_SOURCE_ONLY"
TOL = 1e-6


@dataclass(frozen=True)
class NfbNativeBaseCircle:
    source_handle: str
    center_xy_mm: tuple[float, float]
    radius_mm: float
    source_color_aci: int = 30


@dataclass(frozen=True)
class NfbNativeBaseClosedLoop:
    source_handles: tuple[str, ...]
    vertices_xy_mm: tuple[tuple[float, float], ...]
    source_color_aci: int = 30


@dataclass(frozen=True)
class NfbNativeBaseMark:
    source_handle: str
    dxf_type: str
    vertices_xy_mm: tuple[tuple[float, float], ...]
    bulges: tuple[float, ...]
    source_color_aci: int = 212
    source_closed: bool = False


@dataclass(frozen=True)
class NfbUpperBaseSourceProcess:
    source_sha256: str
    indexed_filename: str
    upper_color150_handle: str
    upper_color150_center_xy_mm: tuple[float, float]
    base_cutting_circles: tuple[NfbNativeBaseCircle, ...]
    base_cutting_closed_loops: tuple[NfbNativeBaseClosedLoop, ...]
    base_marking_entities: tuple[NfbNativeBaseMark, ...]
    lower_deferred_handles: tuple[str, ...]
    status: str = OBSERVED
    manufacturing_ready: bool = False


def _key(point):
    if len(point) != 2 or not all(isfinite(float(v)) for v in point):
        raise ValueError("NFB Color30 line has nonfinite source coordinates")
    return tuple(round(float(v) / TOL) for v in point)


def _closed_color30_lines(lines: Sequence[NfbSourceEntity]):
    """Trace native line graph; require exact closed simple contours."""
    if not lines:
        return ()
    vertex = {}
    adjacency = {}
    edges = []
    seen_edges = set()
    for row in lines:
        if row.dxf_type != "LINE" or len(row.vertices_xy) != 2:
            raise ValueError("NFB Color30 segment must be a real LINE")
        points = tuple(tuple(map(float, pt)) for pt in row.vertices_xy)
        a, b = _key(points[0]), _key(points[1])
        if a == b:
            raise ValueError("NFB Color30 zero-length cutting line")
        for key, point in zip((a,b),points):
            if key in vertex and max(abs(x-y) for x,y in zip(vertex[key],point)) > TOL:
                raise ValueError("NFB Color30 endpoints differ beyond closing tolerance")
            vertex.setdefault(key, point)
            adjacency.setdefault(key,[])
        edge_key = frozenset((a,b))
        if edge_key in seen_edges:
            raise ValueError("NFB Color30 duplicate cutting segment")
        seen_edges.add(edge_key)
        index = len(edges)
        edges.append((a,b,row.handle_path))
        adjacency[a].append(index)
        adjacency[b].append(index)
    if any(len(indices)!=2 for indices in adjacency.values()):
        raise ValueError("NFB Color30 LINE topology is open or branched; cannot cut")
    result=[]
    visited=set()
    for start_index, (start_a,start_b,handle) in enumerate(edges):
        if start_index in visited:
            continue
        keys=[start_a]
        handles=[]
        current=start_a
        edge_index=start_index
        while True:
            if edge_index in visited:
                raise ValueError("NFB Color30 source loop reuses a cutting edge")
            visited.add(edge_index)
            a,b,edge_handle=edges[edge_index]
            next_key=b if current==a else a if current==b else None
            if next_key is None:
                raise ValueError("NFB Color30 source graph has inconsistent connectivity")
            handles.append(edge_handle)
            if next_key==start_a:
                break
            if next_key in keys:
                raise ValueError("NFB Color30 LINE contour crosses itself")
            keys.append(next_key)
            next_edges=[idx for idx in adjacency[next_key] if idx!=edge_index]
            if len(next_edges)!=1:
                raise ValueError("NFB Color30 LINE contour cannot close")
            current=next_key
            edge_index=next_edges[0]
        if len(keys)<3:
            raise ValueError("NFB Color30 LINE contour has fewer than 3 corners")
        vertices=tuple(vertex[key] for key in keys)
        polygon=Polygon(vertices)
        if not polygon.is_valid or polygon.area<=TOL:
            raise ValueError("NFB Color30 LINE contour is not a valid closed cutting polygon")
        result.append(NfbNativeBaseClosedLoop(tuple(handles),vertices))
    if len(visited)!=len(edges):
        raise ValueError("NFB Color30 source cutting lines were not all consumed")
    return tuple(result)


def inspect_nfb_upper_base_native_process(
    source_path: str | Path,
    *,
    profile: NfbUpperSourceProfile,
    lower_reference_handle: str,
) -> NfbUpperBaseSourceProcess:
    """Resolve source Color30 circles/closed lines, Color212 marks and shared
    Color150 pivot without changing any customer source or releasing a part.
    """
    if not isinstance(profile,NfbUpperSourceProfile):
        raise TypeError("NFB original source needs verified model profile")
    groups=inspect_nfb_original_source_regions(
        source_path,indexed_filename=profile.indexed_filename,
        expected_sha256=profile.source_sha256,
        upper_reference_handle=profile.upper_handle,
        lower_reference_handle=lower_reference_handle,
        expected_upper_width_mm=profile.upper_size_mm[0],
        expected_upper_height_mm=profile.upper_size_mm[1],
    )
    if groups.upper.region!=UPPER or groups.lower.region!=LOWER:
        raise ValueError("NFB native upper/lower group identity changed")
    inventory=inspect_nfb_dxf_source(source_path)
    if inventory.diagnostics or inventory.source_sha256!=groups.source_sha256:
        raise ValueError("NFB original group/source processing unresolved")
    members={row.handle_path:row for row in inventory.entities}
    if len(members)!=len(inventory.entities):
        raise ValueError("NFB duplicate source handles")
    upper=tuple(members[handle] for handle in groups.upper.entity_handles)
    if any(e.effective_color_aci not in (30,150,212) for e in upper):
        raise ValueError("NFB upper contains unassigned native process color")
    source_reference=resolve_upper_color150_reference(
        inventory,upper_source_entity_ids=(
            f"{inventory.source_sha256}:{profile.upper_handle}",
        ),
    )
    if any(abs(a-b) > 1e-5 for a, b in
           zip(source_reference.size_mm, profile.upper_size_mm)):
        raise ValueError("NFB source Color150 pivot geometry changed")
    color30=tuple(e for e in upper if e.effective_color_aci==30)
    circles=[]
    lines=[]
    loops=[]
    for row in color30:
        if row.dxf_type=="CIRCLE":
            if row.center_xy is None or row.radius is None or row.radius<=0:
                raise ValueError("NFB Color30 source cutting circle invalid")
            circles.append(NfbNativeBaseCircle(
                row.handle_path,row.center_xy,float(row.radius),
            ))
        elif row.dxf_type=="LINE":
            lines.append(row)
        elif row.dxf_type in ("LWPOLYLINE","POLYLINE"):
            if (not row.closed or len(row.vertices_xy)<3
                    or any(abs(float(b))>TOL for b in row.bulges)):
                raise ValueError("NFB Color30 polyline cutting contour unclosed/curved")
            polygon=Polygon(row.vertices_xy)
            if not polygon.is_valid or polygon.area<=TOL:
                raise ValueError("NFB Color30 source polyline cutting is invalid")
            loops.append(NfbNativeBaseClosedLoop(
                (row.handle_path,),tuple(row.vertices_xy),
            ))
        else:
            raise ValueError("NFB Color30 native cutting geometry unsupported: "+row.dxf_type)
    loops.extend(_closed_color30_lines(lines))
    marks=[]
    for row in upper:
        if row.effective_color_aci!=212:
            continue
        if row.dxf_type not in ("LINE","LWPOLYLINE","POLYLINE"):
            raise ValueError("NFB upper Color212 native MARKING geometry unsupported")
        marks.append(NfbNativeBaseMark(
            row.handle_path,row.dxf_type,tuple(row.vertices_xy),tuple(row.bulges),
            source_closed=bool(row.closed),
        ))
    if not color30 or not marks or not (circles or loops):
        raise ValueError("NFB upper base CUTTING/MARKING source not fully identified")
    consumed=(
        {profile.upper_handle}
        | {x.source_handle for x in circles}
        | {h for x in loops for h in x.source_handles}
        | {x.source_handle for x in marks}
    )
    if consumed!=set(groups.upper.entity_handles):
        raise ValueError("NFB source upper native handles not all accounted for")
    return NfbUpperBaseSourceProcess(
        source_sha256=groups.source_sha256,
        indexed_filename=profile.indexed_filename,
        upper_color150_handle=profile.upper_handle,
        upper_color150_center_xy_mm=source_reference.center_xy,
        base_cutting_circles=tuple(circles),
        base_cutting_closed_loops=tuple(loops),
        base_marking_entities=tuple(marks),
        lower_deferred_handles=groups.lower.entity_handles,
    )
