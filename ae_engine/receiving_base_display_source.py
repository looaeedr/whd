# -*- coding: utf-8 -*-
"""Read-only Receiving Base Plate display source evidence for GUI clients.

A resolvable physical BasePlatePartSpec input is NOT manufacturing release.
The canonical Receiving resolver remains sole owner of source selection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .receiving_base_plate_config import receiving_base_plate_values


@dataclass(frozen=True)
class ReceivingBasePlateDisplaySource:
    status: Literal["NOT_APPLICABLE", "RESOLVED_DISPLAY_ONLY", "UNAVAILABLE", "INVALID"]
    reason: str = ""

    @property
    def source_available(self) -> bool:
        return self.status == "RESOLVED_DISPLAY_ONLY"


def inspect_receiving_base_plate_display_source(
    snapshot, cabinet_family: str,
) -> ReceivingBasePlateDisplaySource:
    """Project source resolver success/error; never infer from old UI fields.

    Keep historical non-Receiving UI filtering and error classification.
    A source for *display* is never an EAR weld or DXF approval.
    """
    if cabinet_family != "受電箱":
        return ReceivingBasePlateDisplaySource("NOT_APPLICABLE")
    try:
        source = receiving_base_plate_values(snapshot)
    except (ValueError, TypeError, KeyError) as exc:
        return ReceivingBasePlateDisplaySource("INVALID", str(exc))
    if source is None:
        return ReceivingBasePlateDisplaySource("UNAVAILABLE")
    return ReceivingBasePlateDisplaySource("RESOLVED_DISPLAY_ONLY")
