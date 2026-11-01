"""#2517: Engine owns the live Quantity NFB export-source eligibility gate.

This is an operator-source contract, not manufacturing source certification.
A numeric CSV version is not permitted to borrow another version's saved NFB
configuration or silently fall back to a legacy supplier-DXF route.
No GUI, Tk or IO dependency may enter this module.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .receiving_nfb_model_identity import parse_numeric_model_ref


@dataclass(frozen=True)
class QuantityExportSourceDecision:
    """Read-only Engine decision consumed by original GUI/other API clients."""

    use_current_csv_export: bool
    submitted_version_ids: tuple[str, ...]


def _submitted_facts(versions):
    facts = {}
    for row in versions:
        if not isinstance(row, Mapping):
            raise ValueError("NFB 數量版本格式無效，禁止出圖")
        if row.get("nfb_config_submitted") is True:
            version_id = row.get("version_id")
            if not isinstance(version_id, str) or not version_id:
                raise ValueError("NFB 版本缺少穩定來源身分，禁止出圖")
            if version_id in facts:
                raise ValueError("NFB 版本來源身分重複，禁止出圖")
            facts[version_id] = row.get("nfb_config")
    return facts


def plan_quantity_export_source(input_snapshot, workspace_snapshot):
    """Validate saved-vs-live NFB sources and select a lawful source route.

    The original per-version NFB source gate still independently validates
    *actual* CSV bytes, dimensions, datum and physical material before DXF.
    This decision only prevents mixing numeric/legacy sources at this earlier
    operator-export boundary; it is never a manufacturing READY certificate.
    """
    if not isinstance(input_snapshot, Mapping) or not isinstance(workspace_snapshot, Mapping):
        raise TypeError("QUANTITY_EXPORT_SOURCE_SNAPSHOT_REQUIRED")
    input_quantity = input_snapshot.get("quantity") or {}
    live_quantity = workspace_snapshot.get("quantity") or {}
    if not isinstance(input_quantity, Mapping) or not isinstance(live_quantity, Mapping):
        raise ValueError("NFB 數量來源資料結構無效，禁止出圖")
    input_facts = _submitted_facts(input_quantity.get("versions", ()) or ())
    live_facts = _submitted_facts(live_quantity.get("versions", ()) or ())
    if input_facts != live_facts:
        raise ValueError("NFB 數量版本與目前工作狀態不一致，請重新套用後再出圖")

    submitted_rows = tuple(
        row for row in live_quantity.get("versions", ()) or ()
        if row.get("nfb_config_submitted") is True
    )
    use_csv = False
    if input_snapshot.get("model") == "受電箱" and submitted_rows:
        numeric = []
        for row in submitted_rows:
            config = row.get("nfb_config") or {}
            if not isinstance(config, Mapping):
                raise ValueError("NFB 數量來源資料結構無效，禁止出圖")
            holes = config.get("holes") or ()
            if not isinstance(holes, (tuple, list)):
                raise ValueError("NFB 數量孔位來源格式無效，禁止出圖")
            is_numeric = bool(holes) and all(
                isinstance(hole, Mapping)
                and parse_numeric_model_ref(hole.get("model_filename")) is not None
                for hole in holes
            )
            numeric.append(is_numeric)
        if any(numeric) and not all(numeric):
            raise ValueError("NFB 數量版本混用數值 CSV 與舊 DXF，禁止混源整批出圖")
        use_csv = bool(numeric) and all(numeric)

    return QuantityExportSourceDecision(
        use_current_csv_export=use_csv,
        submitted_version_ids=tuple(live_facts),
    )
