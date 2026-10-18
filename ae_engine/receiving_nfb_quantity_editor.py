# -*- coding: utf-8 -*-
"""#1901: source-verified NFB openings for the existing Single quantity door.

A Single quantity sheet has a physical panel, NOT a fake Set/Bay/version.
Both routes use the same MFG-1 DXF/Color150 geometry authority. This proof is
transient editor input, not a Bay submission or manufacturing release.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re
from typing import Mapping

from .cabinet_types import policy as cabinet_family_policy
from .receiving_nfb_cutting_manufacturing import read_nfb_runtime_source_profiles_csv
from .receiving_nfb_dxf_source import inspect_nfb_dxf_source
from .receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole, NfbValidatedInnerDoorRender,
    configured_nfb_inner_door_render_data,
)
from .receiving_nfb_2d_preview import resolve_indexed_dxf_path
from .receiving_nfb_ui1a_edits import editable_nfb_draft, effective_nfb_rotation
from .receiving_nfb_ui1b_bridge import _active_slots
from .receiving_switch_model_catalog import INDEX_PATH


@dataclass(frozen=True)
class NfbVerifiedQuantityDoorProof:
    """Original DXF proof bound to one existing quantity-mode door only."""
    snapshot_at_verification: dict
    part_id: str
    verified_door: NfbValidatedInnerDoorRender
    source_path: str
    source_sha256: str
    world_x_by_unit: tuple[tuple[str, float], ...]
    draft_at_verification: dict


def _quantity_panel(snapshot):
    if snapshot.get("model") != "受電箱" or snapshot.get("active_mode") != "quantity":
        raise ValueError("單只 NFB 驗證必須使用現有受電箱數量模式")
    panels = tuple(
        p for p in cabinet_family_policy.derive_inner_door_panels(snapshot)
        if str(p.cell_key).endswith(":0")
    )
    if len(panels) != 1:
        raise ValueError("單只必須有唯一、可驗證的上層實體內門")
    return panels[0]


def verify_quantity_nfb_inner_door_source(
    draft, *, snapshot: Mapping[str, object],
    world_x_by_unit: Mapping[str, float],
    index_path: str | Path = INDEX_PATH,
    profile_path: str | Path | None = None,
    selected_source_path: str | Path | None = None,
):
    """Prove actual NFB CUTTING on this physical Single door, without Bay IDs."""
    state = editable_nfb_draft(draft)
    if state["status"] != "UNSUBMITTED_NFB_DRAFT_PREVIEW_ONLY":
        raise ValueError("NFB 草稿已變更，請重新驗證")
    panel = _quantity_panel(snapshot)
    candidates = []
    from .receiving_nfb_ui1a import effective_nfb_slot_brand
    for li, layer in enumerate(state["layers"][:state["layer_count"]]):
        for si, slot in enumerate(layer["slots"]):
            if slot["filename"] is not None:
                candidates.append((effective_nfb_slot_brand(state, li, si), slot["filename"]))
    if len(set(candidates)) != 1 or not candidates:
        raise ValueError("單次真實 DXF 驗證僅支援同一 NFB 來源型號")
    brand, filename = candidates[0]
    # The one verified source follows the actual slot brand. An explicit
    # per-slot brand override is valid even when the global brand differs.
    index = Path(index_path)
    profile_file = Path(profile_path) if profile_path is not None else index.parent / "來源輪廓索引.csv"
    profiles = read_nfb_runtime_source_profiles_csv(profile_file)
    matched = [p for p in profiles if (p.brand, p.indexed_filename.casefold())
               == (brand, filename.casefold())]
    if len(matched) != 1:
        raise ValueError("NFB 單只尚無原始 DXF/Color150 可驗證來源")
    profile = matched[0]
    if selected_source_path is None:
        source = resolve_indexed_dxf_path(brand, filename, index_path=index)
    else:
        source = Path(selected_source_path)
        pattern = re.escape(Path(filename).stem) + r"(?:\([1-9][0-9]*\))?\.dxf"
        if re.fullmatch(pattern, source.name, re.IGNORECASE) is None:
            raise ValueError("NFB 選取檔名不屬於此品牌／型號原始 DXF")
    if not source.is_file():
        raise ValueError("NFB 原始 DXF 不存在，不能帶入正式開孔")
    from .receiving_nfb_editable_source import resolve_editable_nfb_source_profile
    profile = resolve_editable_nfb_source_profile(source, profile=profile)
    entries = _active_slots(state, profile=profile)
    ids = {slot["unit_id"] for _li, slot in entries}
    if (not isinstance(world_x_by_unit, Mapping)
            or set(world_x_by_unit) != ids
            or any(type(value) not in (int, float) or not isfinite(float(value))
                   for value in world_x_by_unit.values())):
        raise ValueError("單只每顆 NFB 必須有現有箱體的實際世界 X")
    holes = tuple(
        NfbConfiguredInnerDoorHole(
            physical_hole_id=f"nfb:quantity:{panel.stable_id}:{slot['unit_id']}",
            world_x_mm=float(world_x_by_unit[slot["unit_id"]]),
            layer_count=state["layer_count"], slot_index=li,
            rotation_deg=effective_nfb_rotation(
                state, li, state["layers"][li]["slots"].index(slot),
            ),
        )
        for li, slot in entries
    )
    verified = configured_nfb_inner_door_render_data(
        snapshot, panel.inner_door_id, holes=holes,
        index_path=index, source_path=source, profile=profile,
    )
    inventory = inspect_nfb_dxf_source(source)
    if (not verified.manufacturing_ready or verified.part_id != panel.stable_id
            or verified.source_sha256 != inventory.source_sha256
            or inventory.source_sha256 != profile.source_sha256):
        raise ValueError("NFB 單只原始 DXF SHA 或實體內門驗證不一致")
    return NfbVerifiedQuantityDoorProof(
        snapshot_at_verification=deepcopy(dict(snapshot)),
        part_id=panel.stable_id, verified_door=verified,
        source_path=str(source), source_sha256=inventory.source_sha256,
        world_x_by_unit=tuple(sorted(
            (uid, float(value)) for uid, value in world_x_by_unit.items()
        )),
        draft_at_verification=deepcopy(state),
    )


def assert_quantity_nfb_proof_current(proof, *, snapshot, draft=None):
    """Reject stale physical geometry, changed source bytes or another door."""
    if not isinstance(proof, NfbVerifiedQuantityDoorProof):
        raise TypeError("單只 NFB 必須提供本片實體內門的原始來源驗證")
    previous = proof.snapshot_at_verification
    if draft is not None and editable_nfb_draft(draft) != proof.draft_at_verification:
        raise ValueError("單只 NFB 型號／轉向／層數已修改，須重新驗證原始來源")
    physical_fields = ("model", "active_mode", "w", "h", "d", "t", "fw",
                       "multi_door_enabled", "inner_doors",
                       "receiving_inner_door_layer_heights_mm")
    if any(snapshot.get(key) != previous.get(key) for key in physical_fields):
        raise ValueError("單只箱體／內門定位已變更，須重新驗證原始 NFB")
    current = _quantity_panel(snapshot)
    original = _quantity_panel(previous)
    if current != original or current.stable_id != proof.part_id:
        raise ValueError("單只尺寸／內門幾何已變更，須重新驗證原始 NFB")
    if ((snapshot.get("part_features") or {}).get(proof.part_id, ())
            != (previous.get("part_features") or {}).get(proof.part_id, ())):
        raise ValueError("單只原內門既有開孔已變更，須重新驗證")
    try:
        digest = sha256(Path(proof.source_path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("NFB 原始 DXF 已遺失，須重新驗證") from exc
    if digest != proof.source_sha256:
        raise ValueError("NFB 原始 DXF 已變更，須重新驗證")
    if (proof.verified_door.part_id != proof.part_id
            or not proof.verified_door.manufacturing_ready):
        raise ValueError("NFB 來源與目前單只板件驗證失效")
    return proof


def preview_quantity_nfb_v5_on_actual_inner_door(
    draft, *, snapshot: Mapping[str, object],
    world_x_by_unit: Mapping[str, float],
):
    """Read-only numeric V5 trial on the existing Single door; no fake Bay ID.

    Returns the physical trial, its real configured holes and inner door ID.
    The result is explicitly NOT approved for manufacturing / Hole Editor
    CUTTING before the separate numeric-source certification requirement.
    """
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_ui1a import effective_nfb_slot_brand
    from .receiving_nfb_v5_configured_inner_door import (
        NfbV5ConfiguredInnerDoorHole, trial_configured_nfb_v5_inner_door_render_data,
    )
    state = editable_nfb_draft(draft)
    if state["status"] != "UNSUBMITTED_NFB_DRAFT_PREVIEW_ONLY":
        raise ValueError("NFB V5 單只預覽只能用未提交草稿")
    panel = _quantity_panel(snapshot)
    entries = []
    expected = set()
    for li, layer in enumerate(state["layers"][:state["layer_count"]]):
        for si, unit in enumerate(layer["slots"]):
            if unit["filename"] is None:
                continue
            brand = effective_nfb_slot_brand(state, li, si)
            parsed = parse_numeric_model_ref(unit["filename"])
            if parsed is None or parsed[0] != brand or unit.get("source_brand") != brand:
                raise ValueError("NFB V5 單只型號必須有符合廠牌的數值 CSV")
            uid = unit["unit_id"]
            if not isinstance(uid, str) or not uid or uid in expected:
                raise ValueError("NFB V5 單只 NFB 身分缺失或重複")
            expected.add(uid)
            x = world_x_by_unit.get(uid) if isinstance(world_x_by_unit, Mapping) else None
            if type(x) not in (int, float) or not isfinite(float(x)):
                raise ValueError("NFB V5 單只每顆必須指定實際世界 X")
            entries.append(NfbV5ConfiguredInnerDoorHole(
                physical_hole_id=f"nfb:quantity:{panel.stable_id}:{uid}",
                brand=brand, model_ref=unit["filename"],
                world_x_mm=float(x), layer_count=state["layer_count"],
                slot_index=li,
                rotation_deg=effective_nfb_rotation(state, li, si),
            ))
    if not entries or not isinstance(world_x_by_unit, Mapping) or set(world_x_by_unit) != expected:
        raise ValueError("NFB V5 單只實際世界 X 與型號件數不一致")
    trial = trial_configured_nfb_v5_inner_door_render_data(
        snapshot, panel.inner_door_id, holes=tuple(entries),
    )
    if getattr(trial, "manufacturing_ready", True):
        raise ValueError("NFB V5 試作不得冒充已通過製造驗證")
    return trial, tuple(entries), panel.inner_door_id
