"""Thin routing helpers for hole-editor entry points.

This module owns no committed geometry or project state.  It only adapts the
legacy head/tail entry point into the existing unified editor authority.
"""

from __future__ import annotations

from tkinter import messagebox

from ae_engine.sheetmetal_features import (
    RectGuide,
    Vec2,
    feature_surface_from_rect,
    feature_to_legacy_hole,
    legacy_hole_to_feature,
    resolve_endcap_finished_face_guide,
)


def open_hole_editor(host, key):
    """Route the legacy head/tail command into the host's unified editor."""
    label_map = {"head": "封頭", "tail": "封尾"}
    if key not in label_map:
        messagebox.showerror("開孔失敗", f"未知板面: {key}")
        return

    try:
        values = host.get_float_values()
    except ValueError:
        messagebox.showerror("輸入錯誤", "請先確保主畫面所有數值輸入正確")
        return

    width = float(values["w"])
    height = float(values["d"])
    thickness = float(values["t"])
    face_guide = resolve_endcap_finished_face_guide(width, height, thickness)
    surface = feature_surface_from_rect(
        f"{key}_finished_face",
        face_guide.min_point,
        face_guide.max_point,
    )

    legacy = host.tail_holes if key == "tail" else host.head_holes
    host.surface_features[key] = [legacy_hole_to_feature(hole) for hole in legacy]

    def sync_legacy():
        legacy[:] = [
            feature_to_legacy_hole(feature, width, height)
            for feature in host.surface_features[key]
        ]

    reference_guide = RectGuide(
        Vec2(0.0, 0.0),
        Vec2(width, height),
        "finished_boundary",
    )
    host._open_unified_hole_editor(
        key,
        label_map[key],
        surface,
        width,
        height,
        sync_callback=sync_legacy,
        reference_guide=reference_guide,
    )
