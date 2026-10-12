# -*- coding: utf-8 -*-
"""#1501 Receiving operator action -> live, source-verified partial inner-door DXF.

This is an explicit partial operation, NEVER the legacy whole-box DXF route.
Neither the cached UI manifest nor a persisted READY badge grants export.
Actual source bytes, saved NFBConfig, panel geometry and physical IDs are
checked again inside the existing #1635 manufacturing writer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.receiving_nfb_cutting_manufacturing import (
    read_nfb_runtime_source_profiles_csv,
)
from ae_engine.receiving_nfb_export_manifest import NfbActualPart, INNER_DOOR
from ae_engine.receiving_nfb_manufacturing_release import NfbConfiguredInnerDoorHole
from ae_engine.receiving_nfb_partial_export_writer import (
    export_current_nfb_inner_door_partial_dxf,
)
from ae_engine.receiving_nfb_ui1b_bridge import NfbVerifiedDraftSubmission
from ae_engine.receiving_switch_model_catalog import INDEX_PATH


_GEOMETRY_KEYS = (
    "model", "w", "h", "d", "t", "fw", "door_gap_w", "door_gap_h",
    "inner_doors", "door_layout_columns", "box_body_profile",
    "multi_door_enabled", "door_layout_scope",
)


def nfb_verification_geometry_changed(current: Mapping[str, object],
                                      verified: Mapping[str, object]) -> bool:
    """Shared read-only geometry fingerprint for UI readiness and real DXF.

    A status preview must invalidate the SAME fields as the manufacturing
    export action, including door gaps/flange and active layout scope.
    """
    if not isinstance(current, Mapping) or not isinstance(verified, Mapping):
        raise TypeError("NFB verified geometry requires two snapshots")
    return any(current.get(key) != verified.get(key) for key in _GEOMETRY_KEYS)


def export_verified_receiving_nfb_inner_door(
    bundle: NfbVerifiedDraftSubmission,
    *, layout: Mapping[str, object],
    current_snapshot: Mapping[str, object],
    output_path: str | Path,
    index_path: str | Path = INDEX_PATH,
    profile_path: str | Path | None = None,
):
    """Export one submitted, actually verified Receiving Bay inner door.

    The NFB-only button does not imply the box, middle/base, PAD, EAR, or
    quantity versions have been exported. Those remain independent scopes.
    Reopening a saved project without session source evidence must reverify.
    """
    if not isinstance(bundle, NfbVerifiedDraftSubmission):
        raise ValueError("NFB 需重新核對原始 DXF 與世界 X 才可部分出圖")
    if not isinstance(current_snapshot, Mapping) or not isinstance(layout, Mapping):
        raise TypeError("NFB actual Receiving geometry and layout are required")
    if nfb_verification_geometry_changed(
        current_snapshot, bundle.snapshot_at_verification,
    ):
        raise ValueError("NFB 實體內門已變更，須重新驗證後才可出圖")
    try:
        group = layout["sets"][bundle.set_index]
        bay = group["bays"][bundle.bay_index]
        brand = group["switch_brand"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("NFB 目前套／連已不存在") from exc
    scope = bundle.scope
    if (scope.submitted is not True
            or bay.get("nfb_config_submitted") is not True
            or (group.get("stable_id"), bay.get("stable_id"), bundle.version_id)
               != scope.identity):
        raise ValueError("NFB 現有套／連／版本不符合已提交的製造紀錄")
    if brand != bundle.verified_door.indexed_model_key[0]:
        raise ValueError("NFB 品牌已變更，來源必須重驗")
    if not bundle.can_submit:
        raise ValueError("NFB 已驗證內門資料失效")

    # Canonical physical derivation: do not fabricate an inner-door ID from
    # the Bay number or replace the measured WORLD-X with a nominal pitch.
    physical = tuple(
        part for part in cabinet_family_policy.derive_inner_door_panels(
            current_snapshot
        )
        if part.stable_id == scope.inner_door_part_id
    )
    if len(physical) != 1:
        raise ValueError("NFB 沒有唯一的實體內門板件")
    panel = physical[0]
    if (not str(panel.cell_key).endswith(":0")
            or not any(
                row.get("stable_id") == panel.inner_door_id
                and row.get("cell_key") == panel.cell_key
                for row in current_snapshot.get("inner_doors", ())
                if isinstance(row, Mapping)
            )):
        raise ValueError("NFB 上層內門與實體連位置不一致")

    index = Path(index_path)
    profiles = read_nfb_runtime_source_profiles_csv(
        Path(profile_path) if profile_path is not None
        else index.parent / "來源輪廓索引.csv"
    )
    model_key = bundle.verified_door.indexed_model_key
    matching = tuple(p for p in profiles if
                     (p.brand, p.indexed_filename.casefold())
                     == (model_key[0], model_key[1].casefold()))
    if len(matching) != 1:
        raise ValueError("NFB 原始輪廓資料已變更或來源不唯一")
    profile = matching[0]
    if profile.source_sha256 != bundle.source_inventory.source_sha256:
        raise ValueError("NFB DXF SHA 與已驗證來源不一致")
    proof_metadata = getattr(bundle.verified_door.render_data, "metadata", {})
    if (proof_metadata.get("nfb_source_handle")
            != profile.source_sha256 + ":" + profile.upper_handle
            or proof_metadata.get("nfb_profile_revision") != profile.revision):
        raise ValueError("NFB Color150 來源 handle／revision 已改變，須重新驗證")

    try:
        saved_holes = bay["nfb_config"]["holes"]
        holes = tuple(NfbConfiguredInnerDoorHole(
            physical_hole_id=item["physical_hole_id"],
            world_x_mm=item["manual_x_mm"],
            layer_count=item["layer_count"],
            slot_index=item["slot_index"],
            rotation_deg=item["rotation_deg"],
        ) for item in saved_holes)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("NFB 已儲存孔位不完整，不能加工") from exc
    if not holes:
        raise ValueError("NFB 已提交配置沒有實際加工孔")
    path, manifest = export_current_nfb_inner_door_partial_dxf(
        current_snapshot, panel.inner_door_id, output_path,
        saved_bay=bay, set_brand=brand,
        physical_scope=scope,
        actual_parts=(NfbActualPart(panel.stable_id, INNER_DOOR),),
        holes=holes, index_path=index, source_path=bundle.source_path,
        profile=profile, overwrite=False,
    )
    # An unresolved middle/base dependency must not be represented as a
    # whole-cabinet export simply because this request only names one panel.
    return path, manifest
