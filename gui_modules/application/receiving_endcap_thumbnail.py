# -*- coding: utf-8 -*-
"""Receiving head/tail thumbnail drawn from saved Hole Editor feature geometry.

Presentation only: use the source feature coordinates; never infer missing
holes, infer bend allowances or generate manufacturing/DXF geometry.
"""
from __future__ import annotations

from collections import Counter

from ae_engine import manufacturing_api

PALETTE = {
    "CUTTING": "#6bd9e9",
    "MARKING": "#f1c36f",
    "BLIND_HOLE": "#b39fff",
}


def endcap_preview_geometry(features, width, depth):
    """Legacy GUI helper: project saved holes through the public Engine API."""
    return manufacturing_api.receiving_endcap_feature_preview_shapes(
        features, width, depth,
    )


def paint_endcap_thumbnail(canvas, features, width, depth, *, title="封頭尾"):
    """Paint source feature outlines into a scaled finished-face rectangle."""
    shapes, unsupported = (((), 0) if features is None else
                           endcap_preview_geometry(features, width, depth))
    w, d = float(width), float(depth)
    canvas.delete("all")
    cw = max(170, int(canvas.cget("width")), int(canvas.winfo_width()))
    ch = max(122, int(canvas.cget("height")), int(canvas.winfo_height()))
    canvas.create_rectangle(0, 0, cw, ch, fill="#1a2734", outline="")
    canvas.create_text(10, 13, text=title, anchor="w",
                       fill="#f1f5f9", font=("TkDefaultFont", 9, "bold"))
    left, top, right, bottom = 17, 29, cw - 16, ch - 37
    scale = min((right-left)/w, (bottom-top)/d)
    face_w, face_h = w*scale, d*scale
    x0, y0 = (left+right-face_w)/2, (top+bottom-face_h)/2
    canvas.create_rectangle(x0, y0, x0+face_w, y0+face_h,
                            fill="#24384b", outline="#a3b4c7", width=1)
    def xy(x, y):
        return x0 + float(x)*scale, y0 + (d-float(y))*scale
    if features is None:
        canvas.create_text(cw / 2, top + (bottom-top)/2,
                           text="尚未選擇候選版本", fill="#a3b4c7",
                           font=("TkDefaultFont", 9))
    for kind, layer, data in shapes:
        color = PALETTE.get(layer.upper(), "#c7d2fe")
        if kind == "circle":
            x, y, radius = data
            cx, cy = xy(x, y)
            r = radius*scale
            canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                               outline=color, width=1.5, tags=("feature",))
        else:
            pts, closed = data
            flat = [v for px, py in pts for v in xy(px, py)]
            if closed and len(flat) >= 6:
                canvas.create_polygon(*flat, fill="", outline=color,
                                      width=1.5, tags=("feature",))
            else:
                canvas.create_line(*flat, fill=color, width=1.5,
                                   tags=("feature",))
    counts = Counter(layer.upper() for _kind, layer, _data in shapes)
    footer = ("尚未選擇版本" if features is None else
              f"已繪 {len(shapes)} 筆線圖")
    if unsupported:
        footer += f"｜{unsupported} 筆無法預覽"
    canvas.create_text(10, ch - 24, text=footer, anchor="w",
                       fill="#d5e1ed", font=("TkDefaultFont", 8))
    canvas.create_text(10, ch - 10, text="依孔位資料示意，非製造驗收",
                       anchor="w", fill="#9fb0bf", font=("TkDefaultFont", 8))
    canvas._receiving_endcap_preview = {
        "shapes": shapes, "unsupported": unsupported,
        "counts": dict(counts), "source_count": None if features is None else len(features),
    }
    return canvas._receiving_endcap_preview
