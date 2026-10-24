# -*- coding: utf-8 -*-
"""Read-only drawing of an actual V5 operator-configured inner-door FinalScene.

This canvas never creates its own CAD geometry: every stroke is sourced from
the same immutable trial PartRenderData that WHD can fold into a 3D mesh.
No manufacturing or project Save/Apply action is exposed here.
"""
from __future__ import annotations

from math import isfinite

from ae_engine.receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorTrial, STATUS,
)
from ae_engine.sheetmetal_drawing import (
    PolylinePrimitive, LinePrimitive, CirclePrimitive,
)


def _paint_real_finalscene(canvas, data, label, *, width=480, height=350):
    if (data is None or getattr(data, "material", None) is None
            or data.material.is_empty
            or len(getattr(data.material, "bounds", ())) != 4):
        raise ValueError("V5 實際內門板材展開尺寸不存在")
    xmin, ymin, xmax, ymax = (float(v) for v in data.material.bounds)
    if (not all(isfinite(v) for v in (xmin, ymin, xmax, ymax))
            or xmax <= xmin or ymax <= ymin):
        raise ValueError("V5 實際內門板材展開尺寸不存在")
    if (isinstance(width, bool) or not isinstance(width, (int, float))
            or isinstance(height, bool) or not isinstance(height, (int, float))
            or not isfinite(float(width)) or not isfinite(float(height))):
        raise ValueError("V5 預覽畫布尺寸不合法")
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


def paint_v5_real_base_trial(
    canvas, trial, *, width=480, height=350, tier_label=None,
):
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
        canvas, trial.render_data,
        "WHD 真實底板／EAR／螺絲孔"
        + (f"｜{tier_label}" if tier_label else "")
        + "｜V5 試作（未核准製造）",
        width=width, height=height,
    )


def preview_v5_real_receiving_base_sources(
    snapshot, inner_door_id, *, door, configured_holes, root_base_spec,
):
    """One physical Base Plate source per NFB tier, without spoofing part IDs.

    The same #1502 Assembly PartSpec builder now supplies the source for 3D
    and this GUI. A not-yet-submitted Bay can still preview real INNER-DOOR
    CSV holes, but may not claim to have installed multi-tier Base Plates.
    """
    from ae_engine.contracts import BasePlatePartSpec
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    from ae_engine.receiving_nfb_layer_physical_parts import (
        source_receiving_nfb_tier_base_specs,
    )
    from ae_engine.receiving_nfb_v5_live_base_preview import (
        preview_v5_on_existing_receiving_base,
        preview_v5_on_existing_receiving_tier_bases,
    )

    entries = tuple(configured_holes)
    if not entries or not isinstance(root_base_spec, BasePlatePartSpec):
        raise ValueError("V5 底板尚未取得實際來源 PartSpec")
    counts = {row.layer_count for row in entries}
    if len(counts) != 1:
        raise ValueError("V5 不同 NFB 層數不可共用同一片實體底板")
    if counts == {1}:
        return (preview_v5_on_existing_receiving_base(
            snapshot, inner_door_id, door=door,
            configured_holes=entries, base_spec=root_base_spec,
        ),)
    if counts != {2}:
        raise ValueError("V5 尚未配置合法的實體 NFB 層數")
    # Root is only a SOURCE contract, never rename/copy it as another tier.
    current = receiving_base_plate_values(snapshot)
    if (current is None or root_base_spec.physical_id != "base_plate"
            or root_base_spec.features
            or any(
                isinstance(actual, bool) or not isinstance(actual, (int, float))
                or isinstance(expected, bool) or not isinstance(expected, (int, float))
                or not isfinite(float(actual)) or not isfinite(float(expected))
                or abs(float(actual) - float(expected)) > 1e-6
                for actual, expected in (
                    (root_base_spec.width, snapshot.get("w")),
                    (root_base_spec.height, current["h"]),
                    (root_base_spec.thickness, snapshot.get("t")),
                    (root_base_spec.bend, current["base_plate_bend"]),
                    (root_base_spec.shrink_left, current["base_plate_shrink_left"]),
                    (root_base_spec.shrink_right, current["base_plate_shrink_right"]),
                    (root_base_spec.shrink_top, current["base_plate_shrink_top"]),
                    (root_base_spec.shrink_bottom, current["base_plate_shrink_bottom"]),
                )
            )
            or root_base_spec.receiving_bend_pattern != current["receiving_bend_pattern"]):
        raise ValueError("V5 原始實體底板與目前 Set/Bay/尺寸來源不同步")
    specs = source_receiving_nfb_tier_base_specs(snapshot)
    return preview_v5_on_existing_receiving_tier_bases(
        snapshot, inner_door_id,
        door=door, configured_holes=entries, base_specs=specs,
    )


def clear_v5_checked_geometry_preview(
    popup, *, door_canvas, base_canvas,
):
    """Remove obsolete successful canvas geometry before ANY CSV re-check.

    The typed source proof is invalidated by its separate authority owner.
    This visual guard ensures the GUI cannot still display that discarded
    physical FinalScene as the current, valid NFB opening or tier base.
    """
    for canvas in (
        door_canvas, base_canvas,
        popup._receiving_v5_second_base_canvas,
    ):
        canvas.delete("v5-real-part")
    pages = popup._receiving_v5_tabs
    second = popup._receiving_v5_second_base_tab
    if str(second) in pages.tabs():
        pages.forget(second)
    pages.tab(popup._receiving_v5_base_primary_tab, text="底板尚未驗證")
