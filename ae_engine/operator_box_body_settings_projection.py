"""Public Engine projection for operator BoxBody structural settings.

Canonical saved state owns split widths, Receiving side/back rear-flange
dimension space, and relief settings. GUI owns presentation only.
"""
from __future__ import annotations

from typing import Mapping

from .box_body_structure_state import (
    BoxBodyStructureType,
    normalize_box_body_structure_state,
    resolve_two_piece_widths,
    resolve_three_piece_widths,
    set_structure_locked,
    side_rear_bend_outside_length,
)
from .cabinet_types import policy as cabinet_family_policy


def operator_toggle_box_body_structure_lock(state: Mapping[str, object] | None) -> dict:
    """Toggle the canonical persisted bool (including old 'false' text)."""
    normalized = normalize_box_body_structure_state(state)
    return set_structure_locked(normalized, not normalized["locked"])


def project_operator_box_body_structure_settings(
    state: Mapping[str, object] | None,
    total_w: float,
    *,
    snapshot: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return existing Settings rows from the single Engine physical source.

    Invalid persisted split dimensions fail closed; no geometry is reconstructed
    from a preview or manufactured from a display-only fallback.
    """
    normalized = normalize_box_body_structure_state(state)
    active = BoxBodyStructureType(normalized["active_type"])
    cfg = normalized["configs"][active.value]
    piece_values: dict[str, tuple[str, str, float, str, str]] = {}
    mode = "integral"
    if active is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
        mode = "two_w"
        left, right = resolve_two_piece_widths(normalized, total_w)
        piece_values = {
            "box_body:left": ("width", "W 包外", left, "mm", "left"),
            "box_body:right": ("width", "W 包外", right, "mm", "right"),
        }
    elif active is BoxBodyStructureType.THREE_PIECE_W_SPLIT:
        mode = "three_w"
        left, middle, right = resolve_three_piece_widths(normalized, total_w)
        piece_values = {
            "box_body:left": ("width", "W 包外", left, "mm", "left"),
            "box_body:middle": ("width", "W 包外", middle, "mm", "middle"),
            "box_body:right": ("width", "W 包外", right, "mm", "right"),
        }
    elif active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
        mode = "side_back"
        source = dict(snapshot or {})
        if cabinet_family_policy.box_body_profile_uses_outside_dimensions(source):
            rear_bend = side_rear_bend_outside_length(
                normalized, float(source.get("t", 2.0))
            )
        else:
            rear_bend = float(cfg.get("side_rear_bend", 15))
        width_comp_t = float(cfg.get("back_width_comp_t", 0.5))
        piece_values = {
            "box_body:left_side": (
                "rear_bend", "後折", rear_bend, "mm", "side_rear_bend"
            ),
            "box_body:back": (
                "width_comp_t", "寬補償", width_comp_t, "T", "back_width_comp_t"
            ),
            "box_body:right_side": (
                "rear_bend", "後折", rear_bend, "mm", "side_rear_bend"
            ),
        }

    advanced_fields: tuple[dict[str, object], ...] = ()
    if mode in {"two_w", "three_w"}:
        advanced_fields = (
            {"label": "封頭尾額外避讓", "field": "endcap_extra_relief",
             "value": cfg.get("endcap_extra_relief", 5), "suffix": "mm"},
            {"label": "封頭尾單邊留肉", "field": "endcap_single_side_meat_t",
             "value": cfg.get("endcap_single_side_meat_t", 0.5), "suffix": "T"},
            {"label": "底板避讓總長", "field": "baseplate_relief_length",
             "value": cfg.get("baseplate_relief_length", 20), "suffix": "mm"},
            {"label": "底板單邊留肉", "field": "baseplate_single_side_meat_t",
             "value": cfg.get("baseplate_single_side_meat_t", 0.5), "suffix": "T"},
        )
    return {
        "active_type": active,
        "mode": mode,
        "piece_values": piece_values,
        "seam_bend": cfg.get("seam_bend", 12),
        "advanced_fields": advanced_fields,
    }
