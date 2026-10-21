# -*- coding: utf-8 -*-
"""Map common PAD locator squares to the selected NFB's actual base datum.

No product-specific values. Selected CSV/PadPattern owns each dimension;
NfbPanelDatum owns the true panel UV transformation.
"""
from __future__ import annotations

from .receiving_nfb_pad_generator import PadPattern
from .receiving_nfb_numeric_panel_projection import NfbPanelDatum


def project_pad_base_squares(datum: NfbPanelDatum, pattern: PadPattern):
    if not isinstance(datum, NfbPanelDatum) or datum.role != "base-plate":
        raise ValueError("PAD 方孔需要實際底板 NFB 中心")
    datum.validate()
    if not isinstance(pattern, PadPattern) or pattern.manufacturing_ready:
        raise ValueError("PAD 定位方孔必須源自共用加工規則")
    return tuple(
        tuple(datum.map_xy(vertex) for vertex in square)
        for square in pattern.base_square_holes_xy_mm
    )
