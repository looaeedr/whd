# -*- coding: utf-8 -*-
"""#2517 Engine-owned source identity for the existing Receiving PAD+Base CHECK/Q button.

This is a read-only operator selection. It does not infer a physical PAD,
certify manufacturing, or bypass the independent paired DXF source/fit gates.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from .cabinet_types.policy import canonical_family_name


@dataclass(frozen=True)
class ReceivingPadBaseExportSource:
    snapshot: dict
    version_id: str


def resolve_receiving_pad_base_export_source(snapshot) -> ReceivingPadBaseExportSource:
    """Resolve the selected quantity version OR persisted Set/Bay source once.

    The GUI supplies only the currently committed operator snapshot. Quantity
    IDs are distinct from synthetic Set/Bay identities, and singleton fallback
    is valid only when its submitted NFB matches the selected root NFB exactly.
    The return contains a detached copy; it is not a manufacturing approval.
    """
    if (not isinstance(snapshot, Mapping)
            or canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("nfb_config_submitted") is not True):
        raise ValueError("須在受電箱提交 NFB 後，才能輸出 PAD＋底板")
    source = deepcopy(dict(snapshot))
    if source.get("active_mode") == "quantity":
        from .receiving_quantity_versions import QuantityModel
        from .receiving_quantity_box import project_common_box
        model = QuantityModel.from_payload(source.get("quantity"))
        version_id = model.selected_version_id
        committed = model.nfb_config_for_version(version_id)
        if (committed.get("nfb_config_submitted") is not True
                or committed.get("nfb_config") != source.get("nfb_config")):
            raise ValueError("PAD＋底板數量版本的 NFB 來源已失效")
        return ReceivingPadBaseExportSource(project_common_box(source), version_id)

    if source.get("active_mode", "set_bay") != "set_bay":
        raise ValueError("PAD＋底板沒有目前 Set／Bay 的實體選取")
    # Persisted project load already validates full topology and confirmed
    # NFB rows. This read-only selection also supports historical headless
    # raw source snapshots; validate IDs against their actual saved rows
    # without inventing another layout normalization/certification pass.
    layout = source.get("receiving_layout")
    sets = layout.get("sets") if isinstance(layout, Mapping) else None
    if (not isinstance(sets, (list, tuple)) or not sets
            or any(not isinstance(row, Mapping)
                   or not isinstance(row.get("bays"), (list, tuple))
                   or not row["bays"] for row in sets)):
        raise ValueError("PAD＋底板 Set／Bay 實體選取已失效")
    runtime = source.get("_receiving_runtime_selection")
    if not isinstance(runtime, Mapping):
        # Only a genuinely unique saved physical Bay can supply an implicit
        # selection. Multi-Bay exports must carry the actual selected IDs.
        if len(sets) != 1 or len(sets[0]["bays"]) != 1:
            raise ValueError("PAD＋底板沒有目前 Set／Bay 的實體選取")
        runtime = {
            "set_id": sets[0]["stable_id"],
            "bay_id": sets[0]["bays"][0]["stable_id"],
            "set_index": 0, "bay_index": 0,
        }
        source["_receiving_runtime_selection"] = runtime

    set_id = str(runtime.get("set_id") or "").strip()
    bay_id = str(runtime.get("bay_id") or "").strip()
    if not set_id or not bay_id:
        raise ValueError("PAD＋底板缺少 Set／Bay 實際識別碼")
    si = runtime.get("set_index")
    bi = runtime.get("bay_index")
    # A displayed/current runtime ID is not independent manufacturing
    # authority. Verify it against the original persisted physical topology,
    # rather than accepting any nonblank string as a new Bay/version.
    if (type(si) is not int or type(bi) is not int
            or not 0 <= si < len(sets)
            or not 0 <= bi < len(sets[si]["bays"])
            or set_id != sets[si]["stable_id"]
            or bay_id != sets[si]["bays"][bi]["stable_id"]):
        raise ValueError("PAD＋底板 Set／Bay 實體選取已失效")
    selected_bay = sets[si]["bays"][bi]
    if (selected_bay.get("nfb_config_submitted") is not True
            or selected_bay.get("nfb_config") != source.get("nfb_config")):
        raise ValueError("PAD＋底板 Set／Bay 實體選取的 NFB 來源已失效")
    return ReceivingPadBaseExportSource(source, f"{set_id}__{bay_id}")
