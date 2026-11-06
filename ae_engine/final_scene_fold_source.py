# -*- coding: utf-8 -*-
"""Engine canonical Fold source projection from final BEND and CUTTING geometry.

Move-only from Phase6 FinalScene: this is material/geometry source interpretation,
not Matplotlib presentation.  Drawing source and canonical existing Fold solver
remain unchanged, including numerical tolerances and return shapes.
"""
from __future__ import annotations

def scene_fold_boundaries(scene, material):
    """Use final BEND primitives as unfolded fold positions."""
    # 3D 輸入/Fold Profile 是上游；製造 scene BEND 為展開料長線位，FinalScene 僅投影成形。
    # BEND/料長與包外在完整拓樸/T 下可雙向驗算；禁止由組合渲染資料回寫 3D 操作輸入。
    from .sheetmetal_drawing import LinePrimitive
    minx, miny, maxx, maxy = (float(v) for v in material.bounds)
    xs, ys = [], []
    for primitive in getattr(scene, "primitives", ()):
        if not isinstance(primitive, LinePrimitive) or str(getattr(primitive, "layer", "")).upper() != "BEND":
            continue
        x1, y1 = float(primitive.p1.x), float(primitive.p1.y)
        x2, y2 = float(primitive.p2.x), float(primitive.p2.y)
        if abs(x1 - x2) <= 1e-6 and minx + 1e-7 < x1 < maxx - 1e-7:
            xs.append((x1 + x2) / 2.0)
        elif abs(y1 - y2) <= 1e-6 and miny + 1e-7 < y1 < maxy - 1e-7:
            ys.append((y1 + y2) / 2.0)

    def uniq(values):
        out = []
        for value in sorted(values):
            if not out or abs(value - out[-1]) > 1e-6:
                out.append(value)
        return out

    return (tuple([minx] + uniq(xs) + [maxx]), tuple([miny] + uniq(ys) + [maxy]))


def profile_to_scene_boundaries(profile, boundaries):
    """Keep only bend angles from UI; material segment lengths come from final BENDs."""
    segs = [dict(seg) for seg in (profile or ())]
    if len(segs) != len(boundaries) - 1:
        return segs
    for i, seg in enumerate(segs):
        seg["len"] = float(boundaries[i + 1]) - float(boundaries[i])
        seg.pop("ui_len_add", None)
    return segs


def fold_ownership_exemptions(material, xb, yb):
    """Infer double-fold corner ownership from final CUTTING topology only.

    Material in a corner fold cell that touches only the horizontal outside edge
    belongs to the top/bottom flange and must not also receive the X fold.  The
    vertical-only case analogously suppresses the Y fold.
    """
    from shapely.geometry import box, LineString

    if len(xb) < 3 or len(yb) < 3:
        return []
    x0, x1, xr1, xr0 = map(float, (xb[0], xb[1], xb[-2], xb[-1]))
    y0, y1, yt1, yt0 = map(float, (yb[0], yb[1], yb[-2], yb[-1]))
    specs = (
        (box(x0, y0, x1, y1), LineString(((x0, y0), (x0, y1))), LineString(((x0, y0), (x1, y0)))),
        (box(xr1, y0, xr0, y1), LineString(((xr0, y0), (xr0, y1))), LineString(((xr1, y0), (xr0, y0)))),
        (box(x0, yt1, x1, yt0), LineString(((x0, yt1), (x0, yt0))), LineString(((x0, yt0), (x1, yt0)))),
        (box(xr1, yt1, xr0, yt0), LineString(((xr0, yt1), (xr0, yt0))), LineString(((xr1, yt0), (xr0, yt0)))),
    )

    def polygon_parts(geom):
        if geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            return [geom] if geom.area > 1e-9 else []
        return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "Polygon" and g.area > 1e-9]

    out = []
    tol = 1e-7
    for cell, vertical_edge, horizontal_edge in specs:
        for piece in polygon_parts(material.intersection(cell)):
            touches_v = piece.boundary.intersection(vertical_edge).length > tol
            touches_h = piece.boundary.intersection(horizontal_edge).length > tol
            if touches_h and not touches_v:
                out.append(("x", piece))
            elif touches_v and not touches_h:
                out.append(("y", piece))
    return out
