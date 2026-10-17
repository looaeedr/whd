# -*- coding: utf-8 -*-
"""Read-only drawing of an actual V5 operator-configured inner-door FinalScene.

This canvas never creates its own CAD geometry: every stroke is sourced from
the same immutable trial PartRenderData that WHD can fold into a 3D mesh.
No manufacturing or project Save/Apply action is exposed here.
"""
from __future__ import annotations

from ae_engine.receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorTrial, STATUS,
)
from ae_engine.sheetmetal_drawing import (
    PolylinePrimitive, LinePrimitive, CirclePrimitive,
)


def _paint_real_finalscene(canvas, data, label, *, width=480, height=350):
    xmin, ymin, xmax, ymax = (float(v) for v in data.material.bounds)
    if xmax <= xmin or ymax <= ymin:
        raise ValueError("V5 實際內門板材展開尺寸不存在")
    width, height = max(float(width), 120), max(float(height), 160)
    scale = min((width - 40.0)/(xmax - xmin),
                (height - 42.0)/(ymax - ymin))
    cx, cy = (xmin+xmax)/2, (ymin+ymax)/2

    def xy(x, y):
        return (width/2 + (float(x)-cx)*scale,
                height/2 - (float(y)-cy)*scale)

    canvas.delete("v5-real-part")
    strokes = 0
    for row in data.scene.primitives:
        layer = str(row.layer).upper()
        color = {"CUTTING":"#29bb76", "BEND":"#d5a84c",
                 "MARKING":"#9daec4"}.get(layer, "#b0bfcd")
        if isinstance(row, PolylinePrimitive):
            pts = [xy(p.x, p.y) for p in row.points]
            if row.closed and pts:
                pts.append(pts[0])
            if len(pts) >= 2:
                coords = [n for point in pts for n in point]
                canvas.create_line(*coords, fill=color,
                                   width=2 if layer=="CUTTING" else 1,
                                   tags="v5-real-part")
                strokes += 1
        elif isinstance(row, LinePrimitive):
            canvas.create_line(*xy(row.p1.x, row.p1.y),
                               *xy(row.p2.x, row.p2.y),
                               fill=color, width=1, tags="v5-real-part")
            strokes += 1
        elif isinstance(row, CirclePrimitive):
            x, y = xy(row.center.x, row.center.y)
            r = float(row.radius)*scale
            canvas.create_oval(x-r, y-r, x+r, y+r, outline=color,
                               width=1.5, tags="v5-real-part")
            strokes += 1
    if not strokes:
        raise ValueError("V5 真實內門 FinalScene 未建立圖元")
    canvas.create_text(
        8, 10, anchor="nw", fill="#b0bfcd",
        text=label,
        tags="v5-real-part",
    )
    return strokes



def paint_v5_real_inner_door_trial(canvas, trial, *, width=480, height=350):
    if (not isinstance(trial, NfbV5ConfiguredInnerDoorTrial)
            or trial.status != STATUS or trial.manufacturing_ready
            or trial.render_data.metadata.get("nfb_trial_export_approved") is not False):
        raise ValueError("V5 內門只能繪製尚未驗證的真實 FinalScene 試作")
    return _paint_real_finalscene(
        canvas, trial.render_data, "WHD 真實內門展開｜V5 試作（未核准製造）",
        width=width, height=height,
    )


def paint_v5_real_base_trial(canvas, trial, *, width=480, height=350):
    """Draw actual EAR-owned base scene, not a diagram of a hole quartet."""
    from ae_engine.receiving_nfb_v5_actual_base_screws import (
        NfbV5ActualBaseScrewTrial, STATUS as BASE_STATUS,
    )
    if (not isinstance(trial, NfbV5ActualBaseScrewTrial)
            or trial.status != BASE_STATUS or trial.manufacturing_ready
            or trial.render_data.metadata.get("nfb_trial_export_approved") is not False
            or trial.render_data.metadata.get("nfb_base_mfg2_release_approved") is not False):
        raise ValueError("V5 底板只能顯示原實體 EAR 工作面未核准試作")
    return _paint_real_finalscene(
        canvas, trial.render_data, "WHD 真實底板／EAR／螺絲孔｜V5 試作（未核准製造）",
        width=width, height=height,
    )
