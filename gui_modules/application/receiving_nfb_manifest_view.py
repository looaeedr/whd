# -*- coding: utf-8 -*-
"""#1501 read-only GUI strings for the Engine-validated live NFB manifest.

Only formatting and operator display are owned here; physical eligibility,
counts, source diagnosis consistency and scope are checked by public Engine.
"""
from ae_engine import manufacturing_api


def nfb_manifest_display_lines(view):
    view = manufacturing_api.validate_receiving_nfb_manifest_view(view)
    state = view["status"]
    if state == "LEGACY":
        return ("未配置 NFB｜依原有加工流程",)
    if state == "BLOCKED":
        return ("NFB 尚不可匯出：" + str(view.get("reason", "尚未重驗來源")),)
    if state == "CSV_V5_SCOPED_DIAGNOSTIC":
        lines = ["現行 CSV NFB 已提交｜" + str(view.get("derived_state"))
                 + "｜逐顆來源診斷（實體仍須在出圖時重驗）"]
        for unit in view.get("unit_rows", ()):
            layer, slot = unit.get("layer_index"), unit.get("slot_index")
            label = (f"第{layer+1 if type(layer) is int else '?'}層／"
                     f"第{slot+1 if type(slot) is int else '?'}顆")
            errors = tuple(unit.get("reasons") or ())
            state_text = ("配置未驗證：" + "、".join(errors) if errors
                          else "配置已驗證｜CSV 來源可讀／實體待驗")
            lines.append(label + "｜" + str(unit.get("physical_hole_id"))
                         + "｜" + str(unit.get("model_filename")) + "｜" + state_text)
        for part in view.get("part_rows", ()):
            if part.get("nfb_affected") is True:
                reasons = tuple(part.get("reasons") or ())
                lines.append("物理板件 " + str(part["part_id"]) + "｜NFB 依賴待驗｜"
                             + "、".join(str(reason) for reason in reasons))
            else:
                lines.append("物理板件 " + str(part["part_id"]) + "｜不受 NFB 缺項連坐")
        for reason in tuple(view.get("unresolved_dependencies") or ()):
            if str(reason).startswith("NFB_REAL_"):
                lines.append("缺少實體板件來源｜" + str(reason))
        return tuple(lines)
    if state == "CSV_SOURCE_RECHECK_ONLY":
        return (
            "現行 CSV NFB 已提交｜內門＋底板部分 DXF 需按出圖鍵再驗證；"
            "不代表整箱可製造",
        )
    rows = tuple(view.get("rows", ()))
    allowed = view.get("actual_export_count", 0)
    header = (
        f"NFB 板件狀態：可加工 {allowed} 片（僅部分可出）"
        if state == "PARTIAL_ONLY" else
        f"NFB 已驗證板件 {allowed} 片（PAD／整箱製造仍須獨立驗收）"
    )
    lines = [header]
    for item in rows:
        details = "、".join(item.get("reasons", ())) or "已驗證"
        label = "可出" if item.get("may_export") is True else "受阻"
        lines.append(
            f"{item['part_id']}｜{item['role']}｜{label}｜"
            f"{item['actual_count']} 片｜{details}"
        )
    for unresolved in view.get("unresolved_dependencies", ()):
        lines.append("缺少來源／板件身份：" + str(unresolved))
    if state == "PARTIAL_ONLY":
        lines.append("此為部分製造清單，不代表整套可交付")
    return tuple(lines)


def highlighted_nfb_manifest_lines(ports, set_index, highlighted_bays):
    """Format Engine-validated current per-Bay evidence; never authorize DXF."""
    selected = manufacturing_api.validate_receiving_nfb_highlighted_manifest(
        ports, set_index, highlighted_bays,
    )
    lines = []
    has_submitted = False
    for bay_index, current in selected:
        state = current["status"]
        prefix = f"第{set_index+1}套／第{bay_index+1}連"
        if state == "LEGACY":
            lines.append(prefix + "｜未配置 NFB｜原有加工流程")
            continue
        has_submitted = True
        if state == "BLOCKED":
            lines.append(prefix + "｜NFB 尚不可匯出：" +
                         str(current.get("reason") or "缺少來源驗證"))
            continue
        if state == "CSV_SOURCE_RECHECK_ONLY":
            lines.append(prefix + "｜" + nfb_manifest_display_lines(current)[0])
            continue
        if state == "CSV_V5_SCOPED_DIAGNOSTIC":
            set_id, bay_id = current.get("set_id"), current.get("bay_id")
            version = current.get("version_id")
            lines.append(prefix + f"｜Set {set_id}／Bay {bay_id}／版本 "
                         + (version if version else "即時設定"))
            lines.extend(nfb_manifest_display_lines(current))
            continue
        ids = tuple(current.get(key) for key in ("set_id", "bay_id", "version_id"))
        lines.append(prefix + f"｜Set {ids[0]}／Bay {ids[1]}／版本 {ids[2]}")
        lines.extend(nfb_manifest_display_lines(current))
    return tuple(lines) if has_submitted else ()
