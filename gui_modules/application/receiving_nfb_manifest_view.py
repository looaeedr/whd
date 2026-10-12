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
        f"NFB 已驗證板件 {allowed} 片（PAD／耳朵尚未驗收）"
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
