# -*- coding: utf-8 -*-
"""Engine-owned read-only Fold Designer baseline-source hole projection.

Optional reference rows do not constitute certified manufacturing authorization.
"""
from __future__ import annotations
from typing import Mapping
from . import ae
from .cabinet_types import policy as cabinet_family_policy
from .corner_type_ui import is_unknown_model
from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from .sheetmetal_part_adapters import DoorFrameEdges


def fold_designer_secondary_scene_rows(scene):
    """Return numeric baseline hole rows, excluding the structural outline/BEND."""
    rows = []
    skipped_outline = False
    for primitive in getattr(scene, "primitives", ()):
        layer = str(getattr(primitive, "layer", "") or "")
        if layer not in {"CUTTING", "BLIND_HOLE"}:
            continue
        if isinstance(primitive, PolylinePrimitive):
            if layer == "CUTTING" and not skipped_outline:
                skipped_outline = True
                continue
            points = tuple(getattr(primitive, "points", ()) or ())
            if not getattr(primitive, "closed", False) or len(points) < 3:
                continue
            xs = [float(p.x) for p in points]; ys = [float(p.y) for p in points]
            rows.append({
                "kind": "方孔", "layer": layer,
                "x": (min(xs) + max(xs)) / 2.0,
                "y": (min(ys) + max(ys)) / 2.0,
                "d1": max(xs) - min(xs), "d2": max(ys) - min(ys),
            })
        elif isinstance(primitive, CirclePrimitive):
            center = primitive.center
            rows.append({
                "kind": "圓孔", "layer": layer,
                "x": float(center.x), "y": float(center.y),
                "d1": float(primitive.radius) * 2.0, "d2": 0.0,
            })
    return rows

def query_fold_designer_baseline_rows(
    part_key: str, model_name: str, values: Mapping[str, object],
) -> list[dict[str, object]]:
    """Resolve Fold Designer source-only holes through no-GUI Engine API."""
    model = str(model_name or "").strip()
    if not model or is_unknown_model(model) or part_key not in {"door", "head", "tail"}:
        return []
    v = dict(values or {})
    w, h, d, t, fw = (float(v[key]) for key in ("w", "h", "d", "t", "fw"))
    if part_key == "door":
        if hasattr(ae, "has_baseline_part") and not ae.has_baseline_part(model, "門.dxf"):
            return []
        door_fw = cabinet_family_policy.door_material_frame_width(
            model, frame_width=fw, thickness=t,
        )
        data = ae.get_stretched_door_data(
            model, w, h, t, door_fw,
            float(v.get("door_gap_w", ae.door_gap_w_def)),
            float(v.get("door_gap_h", ae.door_gap_h_def)),
            float(v.get("door_fold_l", ae.door_fold_left_def)),
            float(v.get("door_fold_r", ae.door_fold_right_def)),
            float(v.get("door_fold_t", ae.door_fold_top_def)),
            float(v.get("door_fold_b", ae.door_fold_bottom_def)),
            frame_edges=DoorFrameEdges(),
        )
    else:
        data = ae.get_stretched_end_cap_data(
            model, w, h, d, t, FW_val=fw, is_tail=(part_key == "tail"),
        )
    return fold_designer_secondary_scene_rows(data.scene)
