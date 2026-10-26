# -*- coding: utf-8 -*-
"""#1492 right-hand source-only Tk canvas. Never issues product update intent."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ae_engine.receiving_nfb_2d_preview import Nfb2DViewport, NfbDxfPreviewCache
from ae_engine.receiving_nfb_model_identity import (
    parse_numeric_model_ref, selected_numeric_spec,
)
from ae_engine.receiving_nfb_numeric_catalog import brand_csv_path

_ACI_COLORS = {30:"#ffb064", 150:"#54c6ff", 212:"#cfb6ff", 3:"#69df90"}


class NfbDxfSourcePreviewPanel:
    """One retained controller per editor, cache keyed by real source revision."""

    def __init__(self,parent,*,index_path=None):
        self.frame=ttk.LabelFrame(parent,text="NFB 型號來源｜僅預覽")
        self.frame.pack(side="right",fill="both",padx=(12,0))
        self.canvas=tk.Canvas(self.frame,width=396,height=415,
                              background="#101c27",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True,padx=6,pady=6)
        self.cache=NfbDxfPreviewCache()
        self.viewport=Nfb2DViewport()
        self._index_path=index_path
        self._source_key=None
        self._drag_point=None
        self._numeric_spec=None
        self._numeric_mode=False
        self._numeric_zoom=1.0
        self._numeric_pan=(0.0,0.0)
        # Ephemeral source-only preview cache; never store manufacturing authority.
        # Keys include brand, model and source file revision.
        self._numeric_sources={}
        self.identity=tk.StringVar(master=self.frame,value="請選取左側 NFB 型號")
        self.reason=tk.StringVar(master=self.frame,value="尚未選擇 NFB 型號來源｜僅預覽")
        bar=ttk.Frame(self.frame)
        bar.pack(fill="x",padx=6)
        ttk.Button(bar,text="＋ 放大",command=lambda:self.zoom(1.25)).pack(side="left")
        ttk.Button(bar,text="－ 縮小",command=lambda:self.zoom(.8)).pack(side="left")
        ttk.Button(bar,text="重設",command=self.reset).pack(side="left")
        ttk.Label(self.frame,textvariable=self.identity,wraplength=385).pack(
            anchor="w",fill="x",padx=6,pady=(4,0))
        ttk.Label(self.frame,textvariable=self.reason,wraplength=385).pack(
            anchor="w",fill="x",padx=6,pady=(2,8))
        self.canvas.bind("<Configure>",lambda _event:self.paint())
        self.canvas.bind("<MouseWheel>",self._wheel)
        self.canvas.bind("<Button-4>",lambda e:self.zoom(1.2,(e.x,e.y)))
        self.canvas.bind("<Button-5>",lambda e:self.zoom(1/1.2,(e.x,e.y)))
        self.canvas.bind("<ButtonPress-1>",self._press)
        self.canvas.bind("<B1-Motion>",self._move)
        self.canvas.bind("<ButtonRelease-1>",lambda _event:self._release())

    def _size(self):
        return max(2,self.canvas.winfo_width()),max(2,self.canvas.winfo_height())

    def show(self,brand,filename):
        """Only read this one indexed model, never trigger app geometry recompute."""
        if filename is None:
            self._numeric_mode=False
            self.frame.configure(text="NFB 型號來源｜僅預覽")
            self._source_key=None
            self._numeric_spec=None
            self._numeric_zoom=1.0
            self._numeric_pan=(0.0,0.0)
            self.viewport.preview=None
            self.identity.set("空槽｜尚未選型")
            self.reason.set("空槽不是開孔；無製造幾何")
            self.paint()
            return
        if isinstance(filename,str) and filename.startswith("nfbv5:"):
            self._numeric_mode=True
            self.frame.configure(text="NFB 數值規格 CSV｜僅預覽")
            parsed=parse_numeric_model_ref(filename)
            try:
                if parsed is None or parsed[0]!=brand:
                    raise ValueError("V5 型號與選定廠牌不符")
                source_stamp=brand_csv_path(brand).stat()
                key=("v5",brand,filename,source_stamp.st_mtime_ns,
                     source_stamp.st_ctime_ns,source_stamp.st_size)
                spec=self._numeric_sources.get(key)
                if spec is None:
                    # Selecting/highlighting the same source must not
                    # reparse every row of the numeric brand CSV.
                    spec=selected_numeric_spec(brand,filename)
                    if spec is None:
                        raise ValueError("廠牌 CSV 已無此型號")
                    self._numeric_sources[key]=spec
                    # Bound memory across repeated model/brand revisions.
                    if len(self._numeric_sources)>8:
                        self._numeric_sources.pop(next(iter(self._numeric_sources)))
            except (ValueError,OSError,UnicodeError) as exc:
                self._numeric_spec=None
                self._source_key=None
                self.viewport.preview=None
                self.identity.set(f"{brand}｜{parsed[1] if parsed else filename}")
                self.reason.set(f"V5 數值來源未定：{exc}｜禁止製造")
                self.paint()
                return
            if key!=self._source_key:
                # A new model's viewport must not inherit the old model's
                # pan/zoom. Re-selecting the same model keeps operator view.
                self._numeric_zoom=1.0
                self._numeric_pan=(0.0,0.0)
            self._numeric_spec=spec
            self.viewport.preview=None
            self._source_key=key
            self.identity.set(f"{brand}｜{spec.model}｜開孔 {spec.opening_mm or '未知'}")
            missing="、".join(spec.missing_fields)
            self.reason.set("V5 數值孔位（未經實體／製造驗證）"
                            + (f"｜缺：{missing}｜禁止製造"
                               if missing else "｜CSV 數值完整；此處僅預覽，正式出圖需提交目前 Set/Bay 並核對實體內門／底板"))
            self.paint()
            return
        self._numeric_mode=False
        self.frame.configure(text="舊 DXF 來源｜僅預覽")
        self._numeric_spec=None
        try:
            opts={"index_path":self._index_path} if self._index_path is not None else {}
            result=self.cache.load(brand,filename,**opts)
        except (ValueError, OSError, UnicodeError) as exc:
            self._source_key=None
            self.viewport.preview=None
            self.identity.set(f"{brand}｜{filename}")
            self.reason.set(f"來源無法查證：{exc}｜僅預覽")
            self.paint()
            return
        key=(brand,filename,result.source_sha256,result.status)
        if key!=self._source_key:
            self.viewport.set_source(result)
            self._source_key=key
        self.identity.set(
            f"{brand}｜{filename}\n"
            f"原始來源 SHA：{result.source_sha256 or '缺失'}｜圖元 {result.entity_count}")
        self.reason.set(result.reason+"｜"+result.status)
        self.paint()

    def paint(self):
        self.canvas.delete("nfb-dxf")
        w,h=self._size()
        if self._numeric_spec is not None:
            self._paint_numeric(w,h)
            return
        for color,points in self.viewport.strokes_for_canvas(w,h):
            coords=[v for xy in points for v in xy]
            if len(coords)>=4:
                self.canvas.create_line(
                    *coords,fill=_ACI_COLORS.get(color,"#b6d0e2"),width=1.3,
                    tags=("nfb-dxf",),
                )
        if not self.viewport.preview or not self.viewport.preview.strokes:
            self.canvas.create_text(
                w/2,h/2,text=("CSV 型號數值不足／無法顯示"
                            if self._numeric_mode else
                            "舊 DXF 來源缺失／沒有可顯示的圖元"),
                fill="#9fbacb",tags=("nfb-dxf",),
            )

    def _paint_numeric(self,w,h):
        """Local V5 illustration only; never register an actual machined part."""
        spec=self._numeric_spec
        corners=spec.opening_corners_xy_mm
        screws=spec.screw_centers_xy_mm
        if corners is None:
            self.canvas.create_text(w/2,h/2,text="開孔尺寸未提供｜禁止製造",
                                    fill="#9fbacb",tags=("nfb-dxf",))
            return
        points=list(corners)+list(screws or ())
        xs=[x for x,y in points]
        ys=[y for x,y in points]
        if screws is not None:
            radius=spec.screw_diameter_mm/2.0
            xs += [x-radius for x,y in screws]+[x+radius for x,y in screws]
            ys += [y-radius for x,y in screws]+[y+radius for x,y in screws]
        extent=max(max(xs)-min(xs),max(ys)-min(ys),1.0)
        scale=0.8*min(w,h)/extent*self._numeric_zoom
        center_x=(max(xs)+min(xs))/2.0
        center_y=(max(ys)+min(ys))/2.0
        px,py=self._numeric_pan
        def screen(x,y):
            return (w/2+(x-center_x)*scale+px,
                    h/2-(y-center_y)*scale+py)
        x1,y1=screen(*corners[0]);x2,y2=screen(*corners[2])
        self.canvas.create_rectangle(x1,y2,x2,y1,outline="#54c6ff",width=2,
                                     tags=("nfb-dxf",))
        if screws is not None:
            r=spec.screw_diameter_mm/2.0*scale
            for x,y in screws:
                cx,cy=screen(x,y)
                self.canvas.create_oval(cx-r,cy-r,cx+r,cy+r,
                                        outline="#69df90",width=1.5,tags=("nfb-dxf",))
        cx,cy=screen(0,0)
        self.canvas.create_line(cx-8,cy,cx+8,cy,fill="#b6d0e2",tags=("nfb-dxf",))
        self.canvas.create_line(cx,cy-8,cx,cy+8,fill="#b6d0e2",tags=("nfb-dxf",))

    def reset(self):
        if self._numeric_spec is not None:
            self._numeric_zoom=1.0
            self._numeric_pan=(0.0,0.0)
        self.viewport._fit=True
        self.paint()

    def zoom(self,factor,anchor=None):
        if self._numeric_spec is not None:
            self._numeric_zoom=max(0.1,min(12.0,self._numeric_zoom*factor))
            self.paint()
            return
        if not self.viewport.preview or not self.viewport.preview.strokes:
            return
        w,h=self._size()
        self.viewport.zoom(factor,w,h,anchor=anchor)
        self.paint()

    def _wheel(self,event):
        if not event.delta:return
        self.zoom(1.2 if event.delta>0 else (1/1.2),(event.x,event.y))

    def _press(self,event):
        self._drag_point=(event.x,event.y)

    def _move(self,event):
        if self._drag_point is None:return
        if self._numeric_spec is not None:
            old=self._drag_point
            self._numeric_pan=(self._numeric_pan[0]+event.x-old[0],
                               self._numeric_pan[1]+event.y-old[1])
            self._drag_point=(event.x,event.y)
            self.paint()
            return
        if not self.viewport.preview:return
        if self.viewport._fit:self.viewport.reset(*self._size())
        old=self._drag_point
        self.viewport.pan(event.x-old[0],event.y-old[1])
        self._drag_point=(event.x,event.y)
        self.paint()

    def _release(self):
        self._drag_point=None
