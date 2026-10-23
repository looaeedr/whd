# -*- coding: utf-8 -*-
"""#1501 display-only formatting of live NFB physical part manifest.

A rendering helper cannot create manufacturing authorization; that belongs
to the runtime #1498 gate and the existing part-based DXF writer.
"""


def nfb_manifest_display_lines(view):
    if not isinstance(view,dict) or "status" not in view:
        raise TypeError("NFB manufacturing status must be a live view")
    state=view["status"]
    if state=="LEGACY":
        return ("未配置 NFB｜依原有加工流程",)
    if state=="BLOCKED":
        return ("NFB 尚不可匯出："+str(view.get("reason","尚未重驗來源")),)
    if state=="CSV_V5_SCOPED_DIAGNOSTIC":
        if (view.get("actual_export_count") is not None or view.get("rows")
                or view.get("manufacturing_ready") is not False
                or view.get("whole_ready") is not False):
            raise ValueError("CSV V5 status must not claim manufactured parts")
        lines=["現行 CSV NFB 已提交｜"+str(view.get("derived_state"))
               +"｜逐顆來源診斷（實體仍須在出圖時重驗）"]
        for unit in view.get("unit_rows", ()):
            if unit.get("manufacturing_verified") is not False:
                raise ValueError("CSV V5 unit cannot fake manufacturing approval")
            layer, slot = unit.get("layer_index"), unit.get("slot_index")
            label=(f"第{layer+1 if type(layer) is int else '?'}層／"
                   f"第{slot+1 if type(slot) is int else '?'}顆")
            errors=tuple(unit.get("reasons") or ())
            state_text=("未驗證："+"、".join(errors) if errors
                        else "CSV 來源可讀／實體待驗")
            lines.append(label+"｜"+str(unit.get("physical_hole_id"))
                         +"｜"+str(unit.get("model_filename"))+"｜"+state_text)
        for part in view.get("part_rows", ()):
            if part.get("nfb_affected") is True:
                reasons=tuple(part.get("reasons") or ())
                if not reasons:
                    raise ValueError("NFB affected physical part needs reasons")
                lines.append(
                    "物理板件 "+str(part["part_id"])+"｜NFB 依賴待驗｜"
                    +"、".join(str(reason) for reason in reasons)
                )
            elif part.get("nfb_affected") is False:
                lines.append("物理板件 "+str(part["part_id"])+"｜不受 NFB 缺項連坐")
            else:
                raise ValueError("CSV V5 part evidence invalid")
        return tuple(lines)
    if state=="CSV_SOURCE_RECHECK_ONLY":
        # This is not WHOLE_READY or a source-scoped manufacturing receipt.
        # Never invent a piece count from the current CSV identity alone.
        if view.get("actual_export_count") is not None or view.get("rows"):
            raise ValueError("CSV recheck-only display cannot claim manufactured parts")
        return (
            "現行 CSV NFB 已提交｜內門＋底板部分 DXF 需按出圖鍵再驗證；"
            "不代表整箱可製造",
        )
    if state not in ("PARTIAL_ONLY","WHOLE_READY"):
        raise ValueError("NFB manufacturing view status unsupported")
    rows=tuple(view.get("rows",()))
    allowed=view.get("actual_export_count",0)
    if type(allowed) is not int or allowed<0:
        raise ValueError("NFB manifest display count must be a nonnegative integer")
    # This is only a read-only UI projection, but it must not show a false
    # green manufacturing count when a stale/contradictory view is supplied.
    actual_ready=0
    for item in rows:
        if not isinstance(item,dict):
            raise ValueError("NFB manifest row must be a mapping")
        count=item.get("actual_count")
        status=item.get("status")
        may_export=item.get("may_export")
        if type(count) is not int or count<=0:
            raise ValueError("NFB manifest row count must be positive")
        if type(may_export) is not bool:
            raise ValueError("NFB manifest row export decision must be boolean")
        if status not in ("READY","UNAFFECTED","BLOCKED"):
            raise ValueError("NFB manifest row status not recognized")
        if may_export is not (status in ("READY","UNAFFECTED")):
            raise ValueError("NFB manifest row status/export mismatch")
        if may_export:
            actual_ready+=count
    if allowed!=actual_ready:
        raise ValueError("NFB manifest displayed count differs from physical rows")
    if state=="WHOLE_READY" and (
            any(not row["may_export"] for row in rows)
            or view.get("unresolved_dependencies")):
        raise ValueError("NFB manifest full-ready display has blocked dependencies")
    header=(
        f"NFB 板件狀態：可加工 {allowed} 片（僅部分可出）"
        if state=="PARTIAL_ONLY" else
        f"NFB 已驗證板件 {allowed} 片（PAD／整箱製造仍須獨立驗收）"
    )
    lines=[header]
    for item in rows:
        if not isinstance(item,dict):
            raise ValueError("NFB manifest row must be a mapping")
        details="、".join(item.get("reasons",())) or "已驗證"
        label="可出" if item.get("may_export") is True else "受阻"
        lines.append(
            f"{item['part_id']}｜{item['role']}｜{label}｜"
            f"{item['actual_count']} 片｜{details}"
        )
    for unresolved in view.get("unresolved_dependencies",()):
        lines.append("缺少來源／板件身份："+str(unresolved))
    if state=="PARTIAL_ONLY":
        lines.append("此為部分製造清單，不代表整套可交付")
    return tuple(lines)


def highlighted_nfb_manifest_lines(ports, set_index, highlighted_bays):
    """Project saved, current per-Bay proof into read-only operator text.

    Never turn preview status into manufacturing approval. In particular,
    mixed or stale selections must show their blocked rows; export is gated
    separately by the real partial DXF writer.
    """
    from collections.abc import Mapping

    if not isinstance(ports, Mapping) or not callable(ports.get("manifest")):
        raise TypeError("NFB live manifest port required")
    if type(set_index) is not int or set_index < 0:
        raise ValueError("NFB Set index invalid")
    bays=tuple(highlighted_bays)
    if (not bays or len(set(bays))!=len(bays)
            or any(type(bi) is not int or bi<0 for bi in bays)):
        raise ValueError("NFB highlighted Bay selection invalid")

    lines=[]
    has_submitted=False
    for bay_index in bays:
        current=ports["manifest"](set_index,bay_index)
        if not isinstance(current,Mapping):
            raise TypeError("NFB live manifest must be a mapping")
        state=current.get("status")
        if state=="LEGACY":
            lines.append((f"第{set_index+1}套／第{bay_index+1}連"
                          "｜未配置 NFB｜原有加工流程"))
            continue
        has_submitted=True
        prefix=f"第{set_index+1}套／第{bay_index+1}連"
        if state=="BLOCKED":
            lines.append(prefix+"｜NFB 尚不可匯出："+str(
                current.get("reason") or "缺少來源驗證"))
            continue
        if state=="CSV_SOURCE_RECHECK_ONLY":
            lines.append(
                prefix+"｜"+nfb_manifest_display_lines(dict(current))[0]
            )
            continue
        if state=="CSV_V5_SCOPED_DIAGNOSTIC":
            set_id,bay_id=current.get("set_id"),current.get("bay_id")
            if (not isinstance(set_id,str) or not set_id.strip()
                    or not isinstance(bay_id,str) or not bay_id.strip()):
                raise ValueError("NFB CSV V5 scoped identity is missing")
            version=current.get("version_id")
            if version is not None and not isinstance(version,str):
                raise ValueError("NFB CSV V5 version identity invalid")
            lines.append(
                prefix+f"｜Set {set_id}／Bay {bay_id}／版本 "
                +(version if version else "即時設定")
            )
            lines.extend(nfb_manifest_display_lines(dict(current)))
            continue
        ids=tuple(current.get(key) for key in ("set_id","bay_id","version_id"))
        if any(not isinstance(value,str) or not value.strip() for value in ids):
            raise ValueError("NFB live manifest missing Set/Bay/version stable IDs")
        lines.append(
            prefix+f"｜Set {ids[0]}／Bay {ids[1]}／版本 {ids[2]}"
        )
        lines.extend(nfb_manifest_display_lines(dict(current)))
    # Do not change the legacy UI when EVERY highlighted Bay is unconfigured.
    return tuple(lines) if has_submitted else ()
