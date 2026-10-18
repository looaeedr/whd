# -*- coding: utf-8 -*-
"""#1500 real UI-1A operator WORLD-X dialog -> current inner-door source proof.

No guessed plate IDs, no duplicate model catalog, no source aliases by name.
Single unambiguous upper physical inner-door is required for current MFG-1.
MFG-2 plate IDs remain unresolved+blocked, rather than invented to allow
unsafe whole-box manufacturing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .cabinet_types import policy as cabinet_family_policy
from .receiving_nfb_cutting_manufacturing import read_nfb_runtime_source_profiles_csv
from .receiving_nfb_manufacturing_release import X_REVISION
from .receiving_nfb_x_projection import (
    W800_THREE_DATUM_REVISION, resolve_w800_three_whd_x,
)
from .receiving_nfb_part_readiness import NfbPhysicalScope
from .receiving_nfb_ui1a import effective_nfb_slot_brand
from .receiving_nfb_ui1a_edits import editable_nfb_draft
from .receiving_nfb_ui1b_bridge import verify_nfb_ui1a_for_submit
from .receiving_nfb_2d_preview import resolve_indexed_dxf_path
from .receiving_switch_model_catalog import INDEX_PATH


def derive_w800_three_world_x_by_unit(
    draft, *, snapshot: Mapping[str, object], inner_door_id: str | None = None,
) -> dict[str, float]:
    """Use the ACTUAL WHD 723-mm inner-door CUTTING to locate configured 3-up NFB.

    Only a complete W800/T2/upper-1100 three-unit row (one or two layers)
    is covered by #1494. An empty, extra, unknown or repeated slot is NOT
    a three-unit physical configuration. No center is inferred for W600,
    W750, one-unit or two-unit arrangements.
    """
    state = editable_nfb_draft(draft)
    layers = tuple(state["layers"][:state["layer_count"]])
    if len(layers) not in (1, 2):
        raise ValueError("WHD W800x3 X only covers 1/2 complete NFB layers")
    selected_id = inner_door_id
    if selected_id is None:
        upper = [r for r in snapshot.get("inner_doors", ())
                 if isinstance(r, Mapping)
                 and str(r.get("cell_key", "")).endswith(":0")
                 and isinstance(r.get("stable_id"), str)
                 and r["stable_id"].strip()]
        if len(upper) != 1:
            raise ValueError("WHD W800x3 cannot choose an ambiguous upper inner door")
        selected_id = upper[0]["stable_id"]
    results: dict[str, float] = {}
    for layer in layers:
        slots = layer["slots"]
        if len(slots) != 3 or any(slot["filename"] is None for slot in slots):
            raise ValueError("WHD W800x3 needs exactly three configured NFB units per layer")
        for position, slot in enumerate(slots):
            uid = slot["unit_id"]
            if not isinstance(uid, str) or not uid or uid in results:
                raise ValueError("WHD W800x3 NFB unit IDs must be unique")
            actual = resolve_w800_three_whd_x(
                snapshot, selected_id, slot_index=position,
            )
            if actual.revision != W800_THREE_DATUM_REVISION:
                raise ValueError("WHD W800x3 X evidence version changed")
            results[uid] = actual.box_world_x_mm
    return results


def verify_current_nfb_ui_draft(
    draft,
    *, layout: Mapping[str,object], set_index: int, bay_index: int,
    version_id: str, projected_snapshot: Mapping[str,object],
    world_x_by_unit: Mapping[str,float],
    index_path: str | Path = INDEX_PATH,
    profile_path: str | Path | None = None,
    selected_source_path: str | Path | None = None,
    canonical_w800_three: bool = False,
):
    """Proof from actual runtime source and part, never a fake READY badge."""
    if not isinstance(version_id,str) or not version_id.strip():
        raise ValueError("正式 NFB 必須先選擇已儲存的內門版本")
    state=editable_nfb_draft(draft)
    if state["status"]!="UNSUBMITTED_NFB_DRAFT_PREVIEW_ONLY":
        raise ValueError("NFB 草稿狀態已變更，請重新讀取")
    if projected_snapshot.get("model")!="受電箱":
        raise ValueError("NFB 實體驗證只適用受電箱")
    if not projected_snapshot.get("multi_door_enabled"):
        raise ValueError("NFB 實體驗證需要有效內門")
    try:
        row=layout["sets"][set_index]
        bay=row["bays"][bay_index]
    except (IndexError,KeyError,TypeError) as exc:
        raise ValueError("NFB 選擇的實體套／連不存在") from exc
    if row.get("switch_brand")!=state["set_brand"]:
        raise ValueError("NFB 廠牌與目前 Receiving Set 不一致")
    candidates=[]
    for layer_index,layer in enumerate(state["layers"][:state["layer_count"]]):
        for pos,slot in enumerate(layer["slots"]):
            if slot["filename"] is None:
                continue
            candidates.append((
                effective_nfb_slot_brand(state,layer_index,pos),
                slot["filename"],
            ))
    if not candidates:
        raise ValueError("NFB 尚未選擇實際開關型號")
    if len(set(candidates))!=1:
        raise ValueError("目前 MFG-1 僅能一次驗證單一來源型號；不同型號不得混用 DXF")
    brand,filename=candidates[0]
    source_index=Path(index_path)
    source_profile=Path(profile_path) if profile_path is not None else (
        source_index.parent/"來源輪廓索引.csv"
    )
    profiles=read_nfb_runtime_source_profiles_csv(source_profile)
    matched=[p for p in profiles if (p.brand,p.indexed_filename.casefold())
             ==(brand,filename.casefold())]
    if len(matched)!=1:
        raise ValueError("NFB 來源輪廓 CSV 尚未建立該型號的真實 SHA/Color150 資料")
    if selected_source_path is not None:
        # A numbered browser-downloaded copy is okay ONLY if #1497 also
        # verifies its exact original byte SHA and selected Color150 handle.
        import re
        chosen=Path(selected_source_path)
        pattern=(re.escape(Path(filename).stem)
                 + r"(?:\([1-9][0-9]*\))?\.dxf")
        if not re.fullmatch(pattern,chosen.name,re.IGNORECASE):
            raise ValueError("選取 DXF 並非 CSV 型號原檔或其編號副本")
        real_source=chosen
    else:
        real_source=resolve_indexed_dxf_path(brand,filename,index_path=source_index)
    if not real_source.is_file():
        raise ValueError(f"NFB 缺原始 DXF：{real_source}（僅預覽，不可提交）")
    owners={str(d.get("stable_id")):str(d.get("cell_key"))
            for d in projected_snapshot.get("inner_doors",())
            if isinstance(d,dict)}
    panels=tuple(cabinet_family_policy.derive_inner_door_panels(projected_snapshot))
    upper=[p for p in panels if p.inner_door_id in owners
           and owners[p.inner_door_id]==p.cell_key
           and str(p.cell_key).endswith(":0")]
    if len(upper)!=1:
        raise ValueError("NFB 當前連沒有唯一、可核對的上方實體內門板")
    part=upper[0]
    scope=NfbPhysicalScope(
        set_id=row["stable_id"],bay_id=bay["stable_id"],
        version_id=version_id,submitted=True,
        inner_door_part_id=part.stable_id,
        # DO NOT guess another part's stable identity. Other plate exports
        # remain blocked as unresolved in #1498 until #1501.
    )
    try:
        box={"w":float(projected_snapshot["w"]),
             "h":float(projected_snapshot["h"]),
             "t":float(projected_snapshot["t"])}
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError("NFB 實體世界 X 缺少受電箱 W/H/T 基準") from exc
    if type(canonical_w800_three) is not bool:
        raise ValueError("WHD canonical W800x3 selection must be an explicit bool")
    if canonical_w800_three:
        expected = derive_w800_three_world_x_by_unit(
            state, snapshot=projected_snapshot,
            inner_door_id=part.inner_door_id,
        )
        if (not isinstance(world_x_by_unit, Mapping)
                or set(world_x_by_unit) != set(expected)
                or any(type(world_x_by_unit[uid]) not in (int, float)
                       or abs(float(world_x_by_unit[uid]) - value) > 1e-6
                       for uid, value in expected.items())):
            raise ValueError("WHD W800x3 world X differs from actual canonical panel")
    datum={
        **box,"part_id":part.stable_id,
        "inner_door_id":part.inner_door_id,
        "cell_key":part.cell_key,
        "profile_revision":matched[0].revision,
    }
    if canonical_w800_three:
        datum["whd_canonical_x_revision"] = W800_THREE_DATUM_REVISION
        datum["whd_canonical_world_x_by_unit"] = dict(expected)
    return verify_nfb_ui1a_for_submit(
        state,layout=layout,set_index=set_index,bay_index=bay_index,
        version_id=version_id,snapshot=projected_snapshot,
        inner_door_id=part.inner_door_id,
        physical_scope=scope,world_x_by_unit=world_x_by_unit,
        datum_revision=(W800_THREE_DATUM_REVISION if canonical_w800_three
                        else X_REVISION),datum_snapshot=datum,
        index_path=source_index,source_path=real_source,profile=matched[0],
    )



def preview_current_nfb_v5_ui_draft(
    draft,
    *,
    layout: Mapping[str, object],
    set_index: int,
    bay_index: int,
    version_id: str,
    projected_snapshot: Mapping[str, object],
    world_x_by_unit: Mapping[str, float],
    _with_holes: bool = False,
):
    """Physical V5 operator preview; never stage or submit a manufactured NFB.

    Uses the same original UI-1A effective brand, stable unit IDs, set/Bay
    identity and world-X entry, then the canonical #1497 inner-door placement,
    Y projection and real FinalScene; no original DXF required for V5.
    """
    from math import isfinite
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_ui1a_edits import effective_nfb_rotation
    from .receiving_nfb_v5_configured_inner_door import (
        NfbV5ConfiguredInnerDoorHole,
        trial_configured_nfb_v5_inner_door_render_data,
    )

    state = editable_nfb_draft(draft)
    if state["status"] != "UNSUBMITTED_NFB_DRAFT_PREVIEW_ONLY":
        raise ValueError("NFB V5 預覽必須使用未提交草稿")
    if not isinstance(version_id, str) or not version_id.strip():
        raise ValueError("NFB V5 請先儲存內門版本")
    if (type(set_index) is not int or type(bay_index) is not int
            or not isinstance(layout, Mapping)):
        raise ValueError("NFB V5 必須指定目前實體 Set/Bay")
    try:
        row = layout["sets"][set_index]
        bay = row["bays"][bay_index]
    except (TypeError, KeyError, IndexError) as exc:
        raise ValueError("NFB V5 指定的實體 Set/Bay 不存在") from exc
    # The current multi-Bay layout may not persist a switch_brand field:
    # its authoritative editable brand is the active NFB draft. When a Set
    # explicitly stores its own brand, disagreement still fails closed.
    if row.get("switch_brand", state["set_brand"]) != state["set_brand"]:
        raise ValueError("NFB CSV 廠牌與目前實體 Set 不一致")
    if bay.get("nfb_config_submitted") is True:
        raise ValueError("NFB V5 已提交設定不可用試作預覽覆蓋")
    if not isinstance(world_x_by_unit, Mapping):
        raise ValueError("NFB V5 必須由操作員提供各顆實際世界 X")
    owners = [
        p for p in projected_snapshot.get("inner_doors", ())
        if isinstance(p, Mapping)
        and isinstance(p.get("stable_id"), str)
        and str(p.get("cell_key", "")).endswith(":0")
    ]
    if len(owners) != 1:
        raise ValueError("NFB V5 需要唯一的上方實體內門")
    inner_door_id = owners[0]["stable_id"]
    entries = []
    expected_ids: set[str] = set()
    for layer_index, layer in enumerate(state["layers"][:state["layer_count"]]):
        for slot_index, unit in enumerate(layer["slots"]):
            if unit["filename"] is None:
                continue
            brand = effective_nfb_slot_brand(state, layer_index, slot_index)
            parsed = parse_numeric_model_ref(unit["filename"])
            if parsed is None or parsed[0] != brand or unit.get("source_brand") != brand:
                raise ValueError("NFB V5 型號需要同廠牌有效數值 CSV；舊 DXF 不可混入")
            uid = unit["unit_id"]
            if not isinstance(uid, str) or not uid or uid in expected_ids:
                raise ValueError("NFB V5 實體 unit ID 缺少或重複")
            expected_ids.add(uid)
            x = world_x_by_unit.get(uid)
            if type(x) not in (int, float) or not isfinite(float(x)):
                raise ValueError("NFB V5 每顆都必須有有效的世界 X")
            entries.append(NfbV5ConfiguredInnerDoorHole(
                physical_hole_id=f"nfb:{row['stable_id']}:{bay['stable_id']}:{uid}",
                brand=brand, model_ref=unit["filename"],
                world_x_mm=float(x), layer_count=state["layer_count"],
                slot_index=layer_index,
                rotation_deg=effective_nfb_rotation(state, layer_index, slot_index),
            ))
    if not entries or set(world_x_by_unit) != expected_ids:
        raise ValueError("NFB V5 世界 X 必須與全部已選實體開關一一對應")
    # Actual final geometry and collisions are re-evaluated on every preview.
    # Nothing here writes the project's NFBConfig, source proof or DXF file.
    door = trial_configured_nfb_v5_inner_door_render_data(
        projected_snapshot, inner_door_id, holes=tuple(entries),
    )
    if _with_holes:
        return door, tuple(entries), inner_door_id
    return door



def preview_current_nfb_v5_door_base_ui_draft(
    draft, *,
    layout: Mapping[str, object],
    set_index: int,
    bay_index: int,
    version_id: str,
    projected_snapshot: Mapping[str, object],
    world_x_by_unit: Mapping[str, float],
    base_spec,
):
    """Operator's single action produces real door AND original EAR-base scenes.

    No source-file selection, project mutation, dummy base, manufactured DXF
    or unwarranted second-layer base. A distinct real base owner is required
    for each separate switch Y row, exactly as in existing #1502.
    """
    from .receiving_nfb_v5_live_base_preview import (
        preview_v5_on_existing_receiving_base,
    )
    door, entries, inner_door_id = preview_current_nfb_v5_ui_draft(
        draft, layout=layout, set_index=set_index, bay_index=bay_index,
        version_id=version_id, projected_snapshot=projected_snapshot,
        world_x_by_unit=world_x_by_unit, _with_holes=True,
    )
    base = preview_v5_on_existing_receiving_base(
        projected_snapshot, inner_door_id, door=door,
        configured_holes=entries, base_spec=base_spec,
    )
    return door, base
