# -*- coding: utf-8 -*-
"""#1492 right-hand source-only Tk canvas. Never issues product update intent."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ae_engine.receiving_nfb_2d_preview import Nfb2DViewport, NfbDxfPreviewCache

_ACI_COLORS = {30:"#ffb064", 150:"#54c6ff", 212:"#cfb6ff", 3:"#69df90"}


class NfbDxfSourcePreviewPanel:
    """One retained controller per editor, cache keyed by real source revision."""

    def __init__(self,parent,*,index_path=None):
        self.frame=ttk.LabelFrame(parent,text="原始 DXF 真圖｜僅預覽")
        self.frame.pack(side="right",fill="both",padx=(12,0))
        self.canvas=tk.Canvas(self.frame,width=396,height=415,
                              background="#101c27",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True,padx=6,pady=6)
        self.cache=NfbDxfPreviewCache()
        self.viewport=Nfb2DViewport()
        self._index_path=index_path
        self._source_key=None
        self._drag_point=None
        self.identity=tk.StringVar(master=self.frame,value="請選取左側 DXF 型號")
        self.reason=tk.StringVar(master=self.frame,value="真圖尚未讀取｜僅預覽")
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
            self._source_key=None
            self.viewport.preview=None
            self.identity.set("空槽｜尚未選型")
            self.reason.set("空槽不是開孔；無製造幾何")
            self.paint()
            return
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
        for color,points in self.viewport.strokes_for_canvas(w,h):
            coords=[v for xy in points for v in xy]
            if len(coords)>=4:
                self.canvas.create_line(
                    *coords,fill=_ACI_COLORS.get(color,"#b6d0e2"),width=1.3,
                    tags=("nfb-dxf",),
                )
        if not self.viewport.preview or not self.viewport.preview.strokes:
            self.canvas.create_text(
                w/2,h/2,text="來源缺失／沒有可顯示的真實 DXF 圖元",
                fill="#9fbacb",tags=("nfb-dxf",),
            )

    def reset(self):
        self.viewport._fit=True
        self.paint()

    def zoom(self,factor,anchor=None):
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
        if self._drag_point is None or not self.viewport.preview:return
        if self.viewport._fit:self.viewport.reset(*self._size())
        old=self._drag_point
        self.viewport.pan(event.x-old[0],event.y-old[1])
        self._drag_point=(event.x,event.y)
        self.paint()

    def _release(self):
        self._drag_point=None
