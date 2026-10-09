# -*- coding: utf-8 -*-
"""Session-only Receiving switch tier presentation model.

OPEN-04 and OPEN-05 are unresolved: these values must not be placed in
receiving_layout, receiving_switch_layout, inner_door_layers, or project files.
No geometry, CUTTING, MARKING, or manufacturing callback belongs here.
"""
from __future__ import annotations

from dataclasses import dataclass

from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS

# Single source of nominal UI labels. These are NOT calculated geometry datums.
SWITCH_TIER_NOMINAL_MM = {"一層": (550,), "兩層": (290, 790)}
SWITCH_TIER_PLACEHOLDER = "請選擇"
SWITCH_TIER_BRAND_INHERIT = "沿用本套"
SWITCH_TIER_OUTPUT_NOTICE = "開關層數尚未連動製造輸出（不產生開孔／打標）"


def switch_tier_nominal_text(tier: str | None) -> str:
    values = SWITCH_TIER_NOMINAL_MM.get(tier)
    if values is None:
        return "標稱高度：尚未選擇（不是計算結果）"
    return f"標稱高度：{'／'.join(str(mm) for mm in values)} mm（不是計算結果）"


@dataclass
class SwitchTierPosition:
    name: str
    brand_override: str | None = None


class ReceivingSwitchTierUiModel:
    """UI-only per-Set value; not a manufacturing or persistence authority."""

    def __init__(self) -> None:
        self.switch_tier: str | None = None
        self.positions: list[SwitchTierPosition] = []

    def set_switch_tier(self, value: str | None) -> None:
        if value == SWITCH_TIER_PLACEHOLDER or value == "":
            value = None
        if value is not None and value not in SWITCH_TIER_NOMINAL_MM:
            raise ValueError(f"不支援的開關層數：{value}")
        if value == self.switch_tier:
            return
        self.switch_tier = value
        names = ("本層",) if value == "一層" else ("上層", "下層") if value == "兩層" else ()
        # Different tier layouts cannot implicitly inherit positions from another layout.
        self.positions = [SwitchTierPosition(name) for name in names]

    def set_brand_override(self, position: str, brand: str | None) -> None:
        if self.switch_tier != "兩層":
            raise ValueError("僅兩層開關可設定上下層品牌（暫定）")
        if brand in (None, "", SWITCH_TIER_BRAND_INHERIT):
            brand = None
        if brand is not None and brand not in RECEIVING_SWITCH_BRANDS:
            raise ValueError(f"不支援的開關品牌：{brand}")
        for item in self.positions:
            if item.name == position:
                item.brand_override = brand
                return
        raise ValueError(f"不支援的開關層位：{position}")

    def snapshot(self) -> dict[str, object]:
        """Detached presentation snapshot; never added to a project snapshot."""
        return {
            "switch_tier": self.switch_tier,
            "positions": [
                {"position": item.name, "brand_override": item.brand_override}
                for item in self.positions
            ],
        }
