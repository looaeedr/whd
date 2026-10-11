# -*- coding: utf-8 -*-
"""#1492: read-only, true-source NFB 2D viewport, NOT manufacturing geometry.

This maps actual DXF ARC/CIRCLE/LINE/LWPOLYLINE/POLYLINE/INSERT virtual
geometry to display strokes; polyline bulges remain curved. It deliberately
does not select a machining pivot or publish source-to-blank CUTTING.
Every viewport zoom/pan works on cached strokes, never reopens a DXF.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from math import atan, atan2, cos, hypot, isfinite, pi, sin
from pathlib import Path

from .receiving_nfb_dxf_source import inspect_nfb_dxf_source, NfbSourceEntity
from .receiving_switch_model_catalog import INDEX_PATH, model_filenames

PREVIEW_ONLY = "SOURCE_OBSERVED_PREVIEW_ONLY_MAIN_CUTTING_UNCERTIFIED"
MISSING = "SOURCE_MISSING_UNKNOWN"
UNREADABLE = "SOURCE_UNREADABLE_UNKNOWN"
MAX_STROKES = 12000
MAX_POINTS = 250000


@dataclass(frozen=True)
class NfbDxfPreview:
    brand: str
    indexed_filename: str
    source_path: str
    source_sha256: str | None
    status: str
    reason: str
    entity_count: int
    strokes: tuple[tuple[int | None, tuple[tuple[float, float], ...]], ...]
    bounds: tuple[float, float, float, float] | None
    diagnostics: tuple[str, ...] = ()
    manufacturing_ready: bool = False
    approved_source_pivot: None = None


def resolve_indexed_dxf_path(brand: str, filename: str, *,
                             index_path: str | Path = INDEX_PATH) -> Path:
    """Prevent arbitrary file access; brand + exact CSV filename are authority.

    A specific brand directory wins over a flat shared source directory.
    If neither exists, the first expected path is returned for diagnostics.
    """
    indexed = Path(index_path)
    if filename not in model_filenames(brand, path=indexed):
        raise ValueError("NFB filename is not indexed for the selected brand")
    if (Path(filename).name != filename or filename in (".", "..")
            or "/" in filename or chr(92) in filename):
        raise ValueError("NFB DXF filename is not a safe basename")
    parent = indexed.parent
    branded = parent / brand / filename
    flat = parent / filename
    return branded if branded.is_file() or not flat.is_file() else flat


def _arc_points(center, radius, start, sweep):
    if not radius or not isfinite(radius) or radius <= 0:
        raise ValueError("NFB display ARC has invalid radius")
    n = max(8, min(240, int(abs(sweep) / (pi / 36)) + 1))
    return tuple((center[0] + radius * cos(start + sweep * i / n),
                  center[1] + radius * sin(start + sweep * i / n))
                 for i in range(n + 1))


def _bulge_segment(start, end, bulge):
    """True circular-bulge display, never the misleading straight chord."""
    if not isfinite(bulge):
        raise ValueError("NFB display polyline bulge non-finite")
    if abs(bulge) <= 1e-12:
        return (start, end)
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    chord = hypot(dx, dy)
    if chord <= 0:
        raise ValueError("NFB display polyline curved edge zero length")
    theta = 4 * atan(bulge)
    offset = chord * (1 - bulge * bulge) / (4 * bulge)
    center = ((x0+x1)*0.5 - dy / chord * offset,
              (y0+y1)*0.5 + dx / chord * offset)
    radius = hypot(x0-center[0], y0-center[1])
    return _arc_points(center,radius,atan2(y0-center[1],x0-center[0]),theta)


def sampled_source_strokes(entity: NfbSourceEntity):
    kind=entity.dxf_type
    if kind == "CIRCLE":
        if entity.center_xy is None or entity.radius is None:
            raise ValueError("NFB display circle data missing")
        points = _arc_points(entity.center_xy, entity.radius, 0, 2*pi)
    elif kind == "ARC":
        if entity.center_xy is None or entity.radius is None or entity.arc_angles is None:
            raise ValueError("NFB display arc data missing")
        s,e = entity.arc_angles
        sweep = (e-s)%360
        if abs(sweep)<1e-12:
            sweep=360.
        points=_arc_points(entity.center_xy,entity.radius,s*pi/180,sweep*pi/180)
    elif kind=="LINE":
        points=entity.vertices_xy
    elif kind in ("LWPOLYLINE","POLYLINE"):
        pts=entity.vertices_xy
        if len(pts)<2:
            raise ValueError("NFB display polyline fewer than 2 vertices")
        segments=len(pts) if entity.closed else len(pts)-1
        built=[]
        for i in range(segments):
            a,b=pts[i],pts[(i+1)%len(pts)]
            bulge=entity.bulges[i] if i<len(entity.bulges) else 0.0
            section=_bulge_segment(a,b,bulge)
            built.extend(section if not built else section[1:])
        points=tuple(built)
    else:
        return ()
    if (len(points)<2 or len(points)>MAX_POINTS
            or any(not all(isfinite(v) for v in p) for p in points)):
        raise ValueError("NFB display stroke invalid or too complex")
    return tuple((float(p[0]),float(p[1])) for p in points)


def inspect_indexed_nfb_preview(brand,filename,*,index_path=INDEX_PATH):
    path=resolve_indexed_dxf_path(brand,filename,index_path=index_path)
    if not path.is_file():
        return NfbDxfPreview(brand,filename,str(path),None,MISSING,
                             "未找到索引對應原始 DXF；沒有可確認的真圖",0,(),None)
    try:
        inventory=inspect_nfb_dxf_source(path)
        strokes=[]
        for ent in inventory.entities:
            pts=sampled_source_strokes(ent)
            if pts:
                strokes.append((ent.effective_color_aci,pts))
                if len(strokes)>MAX_STROKES or sum(len(x[1]) for x in strokes)>MAX_POINTS:
                    raise ValueError("DXF preview geometry exceeds safe display budget")
        if not strokes:
            raise ValueError("DXF has no supported visible source geometry")
        xx=[p[0] for _,points in strokes for p in points]
        yy=[p[1] for _,points in strokes for p in points]
        bounds=(min(xx),min(yy),max(xx),max(yy))
        reason=("讀取真實來源圖元；主 CUTTING 中心／物理定位未據此認證。"
                if not inventory.diagnostics else
                "部分來源圖元無法解析：只顯示已讀部分；不得製造。")
        return NfbDxfPreview(
            brand,filename,str(path),inventory.source_sha256,PREVIEW_ONLY,
            reason,len(inventory.entities),tuple(strokes),bounds,
            inventory.diagnostics)
    except (ValueError,OSError,TypeError,RuntimeError,ImportError,EOFError) as exc:
        return NfbDxfPreview(brand,filename,str(path),None,UNREADABLE,
                             f"無法讀取真實 DXF：{exc}",0,(),None)


class NfbDxfPreviewCache:
    """Cache at most 8 real DXF sources by brand, basename, size and mtime."""
    def __init__(self,max_entries=8):
        if type(max_entries) is not int or not 1<=max_entries<=32:
            raise ValueError("NFB preview cache budget invalid")
        self.max_entries=max_entries
        self._entries=OrderedDict()
        self.parse_count=0

    def load(self,brand,filename,*,index_path=INDEX_PATH):
        path=resolve_indexed_dxf_path(brand,filename,index_path=index_path)
        try:
            stat=path.stat()
            revision=(stat.st_size,stat.st_mtime_ns)
        except OSError:
            revision=None
        # Normalize resolved identity for same brand/model; never reuse an
        # identically named model from a different brand.
        key=(brand,filename,str(path),revision)
        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key]
        value=inspect_indexed_nfb_preview(brand,filename,index_path=index_path)
        self.parse_count+=1
        # A changed or deleted source cannot reuse its old inventory.
        for stale in list(self._entries):
            if stale[:3]==key[:3]:
                del self._entries[stale]
        self._entries[key]=value
        while len(self._entries)>self.max_entries:
            self._entries.popitem(last=False)
        return value


class Nfb2DViewport:
    """Pure 2D viewport; no Tk/app/3D state mutations on any interaction."""
    def __init__(self):
        self.preview=None
        self.cx=self.cy=0.0
        self.scale=1.0
        self._fit=True

    def set_source(self,preview):
        if not isinstance(preview,NfbDxfPreview):
            raise TypeError("NFB preview source must be indexed source result")
        self.preview=preview
        self._fit=True

    def reset(self,width,height):
        if width<=0 or height<=0:
            raise ValueError("NFB viewport screen dimensions invalid")
        bounds=self.preview.bounds if self.preview else None
        if bounds is None:
            self.cx=self.cy=0.
            self.scale=1.
        else:
            a,b,c,d=bounds
            self.cx=(a+c)/2
            self.cy=(b+d)/2
            self.scale=min((width-24)/max(c-a,1e-6),
                           (height-24)/max(d-b,1e-6))
            if not isfinite(self.scale) or self.scale<=0:
                self.scale=1.
        self._fit=False

    def zoom(self,factor,width,height,*,anchor=None):
        if not 0<factor<100 or not isfinite(factor):
            raise ValueError("NFB viewport zoom factor invalid")
        if self._fit: self.reset(width,height)
        point=anchor or (width/2,height/2)
        before=self.to_world(point[0],point[1],width,height)
        self.scale=min(10000,max(1e-5,self.scale*factor))
        after=self.to_world(point[0],point[1],width,height)
        self.cx+=before[0]-after[0]
        self.cy+=before[1]-after[1]

    def pan(self,delta_x,delta_y):
        if self._fit:
            raise ValueError("NFB preview viewport requires initial fit")
        self.cx-=delta_x/self.scale
        self.cy+=delta_y/self.scale

    def to_world(self,x,y,width,height):
        return self.cx+(x-width/2)/self.scale,self.cy-(y-height/2)/self.scale

    def to_screen(self,x,y,width,height):
        return width/2+(x-self.cx)*self.scale,height/2-(y-self.cy)*self.scale

    def strokes_for_canvas(self,width,height):
        if self._fit:self.reset(width,height)
        if not self.preview:return ()
        return tuple((aci,tuple(self.to_screen(*p,width,height) for p in pts))
                     for aci,pts in self.preview.strokes)
