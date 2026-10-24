# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Canonical physical sheet parts for enabled inner-door panels.

The authoritative enable state remains the family-owned ``inner_doors`` list.
This module only represents already-resolved physical panel dimensions and
projects them into DesignerWorkspace profiles; it owns no GUI state.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
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
    fold_left: float = 19.0
    fold_right: float = 19.0
    fold_top: float = 19.0
    fold_bottom: float = 19.0

    @property
    def unfolded_width(self) -> float:
        """Same Door blank formula: finished - 2T + left/right fold."""
        return self.width - 2.0 * self.thickness + self.fold_left + self.fold_right

    @property
    def unfolded_height(self) -> float:
        return self.height - 2.0 * self.thickness + self.fold_top + self.fold_bottom

    def __post_init__(self):
        for value in (self.width, self.height, self.thickness,
                      self.fold_left, self.fold_right, self.fold_top, self.fold_bottom):
            _finite_inner_door_panel_mm(value)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("inner-door panel dimensions must be positive")
        if self.thickness <= 0:
            raise ValueError("inner-door panel thickness must be > 0")
        if min(self.fold_left, self.fold_right, self.fold_top, self.fold_bottom) <= 0:
            raise ValueError("inner-door panel flanges must be positive")
        if self.unfolded_width <= self.fold_left + self.fold_right:
            raise ValueError("inner-door panel X core must be positive")
        if self.unfolded_height <= self.fold_bottom + self.fold_top:
            raise ValueError("inner-door panel Y core must be positive")


def _finite_inner_door_panel_mm(value):
    """Validate one physical inner-door source dimension before forming."""
    message = "inner-door panel dimensions must be finite numbers"
    if isinstance(value, bool):
        raise ValueError(message)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(message) from exc
    if not math.isfinite(number):
        raise ValueError(message)
    return number


def derive_inner_door_panel(
    inner_door_id: object,
    *,
    cell_key: object,
    width: float,
    height: float,
    thickness: float,
    fold_left: float = 19.0,
    fold_right: float = 19.0,
    fold_top: float = 19.0,
    fold_bottom: float = 19.0,
) -> InnerDoorPanelPart:
    door_id = _stable_inner_door_id(inner_door_id)
    key = str(cell_key or "").strip()
    if not key:
        raise ValueError("inner-door panel cell_key must be non-empty")
    for value in (width, height, thickness, fold_left, fold_right, fold_top, fold_bottom):
        _finite_inner_door_panel_mm(value)
    return InnerDoorPanelPart(
        stable_id=inner_door_panel_stable_id(door_id),
        inner_door_id=door_id,
        cell_key=key,
        width=float(width),
        height=float(height),
        thickness=float(thickness),
        fold_left=float(fold_left),
        fold_right=float(fold_right),
        fold_top=float(fold_top),
        fold_bottom=float(fold_bottom),
    )


def inner_door_panel_part_profiles(
    panels: Sequence[InnerDoorPanelPart],
) -> dict[str, dict[str, list[dict[str, object]]]]:
    """One canonical Door folded blank; previews and DXF must agree.

    The formed finished panel dimension is NOT the unfolded material width.
    Keep the standard Door's -2T+folds derivation only once.
    """
    result: dict[str, dict[str, list[dict[str, object]]]] = {}
    for panel in tuple(panels or ()):
        xcore = panel.unfolded_width - panel.fold_left - panel.fold_right
        ycore = panel.unfolded_height - panel.fold_bottom - panel.fold_top
        result[str(panel.stable_id)] = {
            "X": [
                {"len": float(panel.fold_left), "angle": 90.0, "phase6_key": "inner_door_fold_left"},
                {"len": float(xcore), "angle": 90.0, "core": "W", "phase6_key": "inner_door_face_width"},
                {"len": float(panel.fold_right), "phase6_key": "inner_door_fold_right"},
            ],
            "Y": [
                {"len": float(panel.fold_bottom), "angle": 90.0, "phase6_key": "inner_door_fold_bottom"},
                {"len": float(ycore), "angle": 90.0, "core": "H", "phase6_key": "inner_door_face_height"},
                {"len": float(panel.fold_top), "phase6_key": "inner_door_fold_top"},
            ],
        }
    return result


def is_inner_door_panel_part_key(value: object) -> bool:
    key = str(value or "")
    return key.startswith("inner_door:") and key.endswith(":panel")
