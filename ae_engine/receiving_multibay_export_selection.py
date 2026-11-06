# -*- coding: utf-8 -*-
"""#2517 Engine Receiving multi-Bay export eligibility (not certification)."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from .live_cabinet_family import resolve_live_cabinet_family
from .receiving_dxf_groups import RECEIVING_COMPOSED_DXF_MODES
from .receiving_layout import normalize_receiving_layout


@dataclass(frozen=True)
class ReceivingMultiBayExportPlan:
    """Detached source topology and source-only NFB independence decision."""

    use_multibay: bool
    bay_count: int
    independent_only: bool
    layout: dict | None

    def preview_layout_for_bay(self, set_index: int, bay_index: int) -> dict | None:
        """Isolate independent HEAD/TAIL/outer DOOR without changing saved NFB."""
        if not self.use_multibay or self.layout is None:
            raise ValueError("RECEIVING_MULTIBAY_SOURCE_PLAN_NOT_ACTIVE")
        if not self.independent_only:
            return None
        preview = deepcopy(self.layout)
        preview["sets"][set_index]["bays"][bay_index]["nfb_config_submitted"] = False
        return preview


def plan_receiving_multibay_export_source(
    saved_snapshot: Mapping, flags: Mapping, group_mode: str | None = None,
) -> ReceivingMultiBayExportPlan:
    """Choose original multi-Bay exporter; all actual DXF gates remain unchanged.

    Ungrouped legacy one-Bay snapshots retain the established exporter.
    Grouped one-Bay is limited to physically NFB-independent sheet selection.
    """
    if not isinstance(saved_snapshot, Mapping) or not isinstance(flags, Mapping):
        raise TypeError("RECEIVING_MULTIBAY_SOURCE_SNAPSHOT_REQUIRED")
    if group_mode is not None and group_mode not in RECEIVING_COMPOSED_DXF_MODES:
        raise ValueError("未知的 DXF 合併模式")
    raw_layout = saved_snapshot.get("receiving_layout") or {}
    raw_sets = raw_layout.get("sets", ()) if isinstance(raw_layout, Mapping) else ()
    count = 0
    if isinstance(raw_sets, (list, tuple)):
        for row in raw_sets:
            if isinstance(row, Mapping):
                bays = row.get("bays", ())
                if not isinstance(bays, (list, tuple)):
                    raise ValueError("RECEIVING_MULTIBAY_BAYS_INVALID")
                count += len(bays)
    independent = (
        any(bool(flags.get(key)) for key in ("head", "tail", "door"))
        and not any(bool(value) for key, value in flags.items()
                    if key not in {"head", "tail", "door"})
    )
    eligible = (
        resolve_live_cabinet_family(saved_snapshot) == "受電箱"
        and saved_snapshot.get("active_mode", "set_bay") == "set_bay"
        and (count > 1 or (count == 1 and group_mode is not None and independent))
    )
    if not eligible:
        return ReceivingMultiBayExportPlan(False, count, independent, None)
    layout = normalize_receiving_layout(raw_layout)
    if count != sum(len(row["bays"]) for row in layout["sets"]):
        raise ValueError("多連實體連數與目前標準組合體資料不一致")
    return ReceivingMultiBayExportPlan(True, count, independent, layout)
