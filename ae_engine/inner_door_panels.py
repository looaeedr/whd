# -*- coding: utf-8 -*-
"""Canonical physical sheet parts for enabled inner-door panels.

The authoritative enable state remains the family-owned ``inner_doors`` list.
This module only represents already-resolved physical panel dimensions and
projects them into DesignerWorkspace profiles; it owns no GUI state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def _stable_inner_door_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("inner_door_id must be a stable non-empty identifier")
    if ":" in text:
        raise ValueError("inner_door_id must not contain ':'")
    return text


def inner_door_panel_stable_id(inner_door_id: object) -> str:
    return f"inner_door:{_stable_inner_door_id(inner_door_id)}:panel"


@dataclass(frozen=True)
class InnerDoorPanelPart:
    stable_id: str
    inner_door_id: str
    cell_key: str
    width: float
    height: float
    thickness: float

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("inner-door panel dimensions must be positive")
        if self.thickness <= 0:
            raise ValueError("inner-door panel thickness must be > 0")


def derive_inner_door_panel(
    inner_door_id: object,
    *,
    cell_key: object,
    width: float,
    height: float,
    thickness: float,
) -> InnerDoorPanelPart:
    door_id = _stable_inner_door_id(inner_door_id)
    key = str(cell_key or "").strip()
    if not key:
        raise ValueError("inner-door panel cell_key must be non-empty")
    return InnerDoorPanelPart(
        stable_id=inner_door_panel_stable_id(door_id),
        inner_door_id=door_id,
        cell_key=key,
        width=float(width),
        height=float(height),
        thickness=float(thickness),
    )


def inner_door_panel_part_profiles(
    panels: Sequence[InnerDoorPanelPart],
) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Project physical flat panels into DesignerWorkspace profiles."""
    result: dict[str, dict[str, list[dict[str, object]]]] = {}
    for panel in tuple(panels or ()):
        result[str(panel.stable_id)] = {
            "X": [{"len": float(panel.width), "phase6_key": "inner_door_panel_width"}],
            "Y": [{"len": float(panel.height), "phase6_key": "inner_door_panel_height"}],
        }
    return result


def is_inner_door_panel_part_key(value: object) -> bool:
    key = str(value or "")
    return key.startswith("inner_door:") and key.endswith(":panel")
