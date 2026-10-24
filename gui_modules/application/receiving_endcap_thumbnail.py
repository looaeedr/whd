# -*- coding: utf-8 -*-
"""Receiving head/tail thumbnail drawn from saved Hole Editor feature geometry.

Presentation only: use the source feature coordinates; never infer missing
holes, infer bend allowances or generate manufacturing/DXF geometry.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite

from ae_engine.sheetmetal_feature_core import (
    CircleFeature, RectFeature, ProfileFeature,
    feature_finished_point, _rotate_local_point,
)
from ae_engine.sheetmetal_geometry import Vec2

PALETTE = {
    "CUTTING": "#6bd9e9",
    "MARKING": "#f1c36f",
    "BLIND_HOLE": "#b39fff",
}


def _known_feature(item):
    if isinstance(item, (CircleFeature, RectFeature, ProfileFeature)):
        return item
    if isinstance(item, dict) and {"type", "x", "y", "params"} <= set(item):
        # Legacy hole editor payloads carry real coordinates/parameters.
        from ae_engine.sheetmetal_features import legacy_hole_to_feature
        return legacy_hole_to_feature(item)
    return None


def endcap_preview_geometry(features, width, depth):
    """A testable list of real source circles and contours with their layers.

    Unsupported values are reported rather than drawn as invented features.
    Coordinates are in finished-face units, Y positive upward.
    """
    if isinstance(width, bool) or isinstance(depth, bool):
        raise ValueError("缺少有效封頭尾尺寸，無法預覽")
    w, d = float(width), float(depth)
    if not all(isfinite(v) and v > 0 for v in (w, d)):
        raise ValueError("缺少有效封頭尾尺寸，無法預覽")
    if not isinstance(features, (list, tuple)):
        raise ValueError("封頭尾孔位必須是 Feature 清單")
    shapes, unsupported = [], 0
    for original in features:
        try:
            feature = _known_feature(original)
            if feature is None:
                unsupported += 1
                continue
            center = feature_finished_point(feature, w, d)
            layer = str(feature.layer)
            if isinstance(feature, CircleFeature):
                radius = float(feature.diameter) / 2
                if radius <= 0 or not isfinite(radius):
                    raise ValueError("invalid radius")
                shapes.append(("circle", layer, (center.x, center.y, radius)))
                continue
            if isinstance(feature, RectFeature):
                hw, hh = float(feature.width) / 2, float(feature.height) / 2
                if min(hw, hh) <= 0 or not all(map(isfinite, (hw, hh))):
                    raise ValueError("invalid rectangle")
                corners = (Vec2(-hw, -hh), Vec2(hw, -hh),
                           Vec2(hw, hh), Vec2(-hw, hh))
                vertices = tuple(
                    (center.x + _rotate_local_point(p, feature.rotation_deg).x,
                     center.y + _rotate_local_point(p, feature.rotation_deg).y)
                    for p in corners
                )
                shapes.append(("path", layer, (vertices, True)))
                continue
            if isinstance(feature, ProfileFeature):
                contours = feature.layered_profiles or (
                    (layer, feature.points, len(feature.points) >= 3),
                )
                if not contours:
                    raise ValueError("empty profile")
                for contour_layer, points, closed in contours:
                    if len(points) < 2:
                        raise ValueError("short profile")
                    vertices = tuple(
                        (center.x + _rotate_local_point(p, feature.rotation_deg).x,
                         center.y + _rotate_local_point(p, feature.rotation_deg).y)
                        for p in points
                    )
                    shapes.append(("path", str(contour_layer), (vertices, bool(closed))))
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
            unsupported += 1
    return tuple(shapes), unsupported


def paint_endcap_thumbnail(canvas, features, width, depth, *, title="封頭尾"):
    """Paint source feature outlines into a scaled finished-face rectangle."""
    if isinstance(width, bool) or isinstance(depth, bool):
        raise ValueError("缺少有效封頭尾尺寸，無法預覽")
    w, d = float(width), float(depth)
    if not all(isfinite(v) and v > 0 for v in (w, d)):
        raise ValueError("缺少有效封頭尾尺寸，無法預覽")
    shapes, unsupported = (((), 0) if features is None else
                           endcap_preview_geometry(features, width, depth))
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
