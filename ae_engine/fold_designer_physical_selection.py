"""Canonical physical-part selection for Fold Designer's headless readback.

The adapter may parse operator dimensions, but physical identity and Family
topology are resolved here. Never manufacture a fallback for a stale part ID.
"""
from __future__ import annotations

from collections.abc import Mapping

from .cabinet_types import policy as cabinet_family_policy
from .door_dividers import derive_box_body_dividers
from .inner_door_frames import InnerDoorFrameSet, derive_all_inner_door_frames


def resolve_fold_designer_divider_part(part_key: str, divider_input: Mapping[str, object]):
    """Select one real Divider from the existing canonical Door-grid topology."""
    if not isinstance(divider_input, Mapping):
        raise ValueError("中隔設定資料必須為物件")
    dividers = derive_box_body_dividers(
        divider_input["columns"],
        depth=divider_input["depth"],
        thickness=divider_input["thickness"],
        layout_scope=divider_input["layout_scope"],
        handle_edges=divider_input["handle_edges"],
        model_name=divider_input["model_name"],
    )
    divider = next((part for part in dividers if part.stable_id == part_key), None)
    if divider is None:
        raise ValueError(f"中隔 stable_id 不存在於 authoritative topology: {part_key}")
    return divider


def resolve_fold_designer_frame_part(
    part_key: str, payload: Mapping[str, object] | None, *,
    default_thickness: float,
):
    """Resolve Family-owned or legacy explicit frame sets without GUI topology."""
    data = dict(payload or {})
    if cabinet_family_policy.has_inner_door_frame_derivation(data):
        frame_sets = list(cabinet_family_policy.derive_inner_door_frame_sets(data))
    else:
        frame_sets = []
        thickness = float(data.get("t", default_thickness))
        for item in tuple(data.get("inner_doors") or ()):
            if not isinstance(item, dict):
                continue
            stable_id = str(item.get("stable_id") or "").strip()
            spans = item.get("frame_spans")
            if not stable_id or not isinstance(spans, dict) or not spans:
                continue
            included = tuple(
                str(side).strip().lower()
                for side in tuple(item.get("included_frame_sides") or ("top", "bottom", "left", "right"))
            )
            frame_sets.append(InnerDoorFrameSet(
                inner_door_id=stable_id,
                spans=dict(spans),
                thickness=thickness,
                included_sides=included,
            ))
    frames = derive_all_inner_door_frames(tuple(frame_sets))
    frame = next((part for part in frames if part.stable_id == part_key), None)
    if frame is None:
        raise ValueError(f"內門框 stable_id 不存在於 authoritative topology: {part_key}")
    return frame


def resolve_fold_designer_panel_part(part_key: str, payload: Mapping[str, object] | None):
    """Select the Family-derived finished physical panel, never a GUI guess."""
    panels = cabinet_family_policy.derive_inner_door_panels(dict(payload or {}))
    panel = next((part for part in panels if part.stable_id == part_key), None)
    if panel is None:
        raise ValueError(f"內門板 stable_id 不存在於 authoritative topology: {part_key}")
    return panel
