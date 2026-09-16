"""Assembly/corner presentation and routing helpers only."""

from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
from ae_engine.corner_type_ui import CORNER_PAIR_CORNERS
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CrossCornerMode,
    normalize_corner_selection,
)


def sync_endcap_fw_controls(host):
    box_fw = float(host.fw_z_var.get())
    for part, var, follow_var, combo in (
        ("head", host.fw_head_var, host.fw_head_follow_var, getattr(host, "cb_fw_head", None)),
        ("tail", host.fw_tail_var, host.fw_tail_follow_var, getattr(host, "cb_fw_tail", None)),
    ):
        state = host.endcap_fw_state.setdefault(part, {"follow_box": True, "value": box_fw})
        follow = bool(state.get("follow_box", True))
        follow_var.set(follow)
        value = box_fw if follow else float(state.get("value", box_fw))
        text = host._fold_designer_number_text(value)
        if var.get() != text:
            var.set(text)
        if combo is not None:
            combo.configure(state="normal")


def sync_fold_designer_manual_corner_context(host, active_part):
    key = str(active_part or "")
    if key in {"indicator_box", "indicator_door"} and key in host.manual_corner_state:
        host._manual_corner_part_override = key
    else:
        host._manual_corner_part_override = None
    host.refresh_corner_type_panel()


def fixed_corner_summary(host, part_key, current_cabinet_type_name):
    if current_cabinet_type_name == "受電箱" and part_key in {"head", "tail"}:
        joint_state = dict(getattr(host, "assembly_joint_state", {}) or {})
        bottom_relation = edge_relation_for_part(joint_state, part_key, "BOTTOM")
        if bottom_relation is AssemblyJointRelation.WRAP:
            bottom_summary = "下方：包覆貼外（BOTTOM＝WRAP；FW 基準＝側板後折＋1T）"
        elif bottom_relation is AssemblyJointRelation.INSERT:
            bottom_summary = "下方：標準截角（BOTTOM＝嵌入；WRAP 關閉）"
        elif bottom_relation is None:
            bottom_summary = "下方：標準截角（BOTTOM Joint 未定義）"
        else:
            bottom_summary = f"下方：標準截角（BOTTOM＝{bottom_relation.value}）"
        return "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n" + bottom_summary
    return host._FIXED_CORNER_SUMMARIES.get(part_key, "目前板件使用固定截角規則")


def normalize_manual_corner_target(host, part_key):
    target = host.manual_active_corner_var.get()
    same = host.manual_corner_pair_same[part_key]
    pair = host._pair_for_corner_target(target)
    if pair is None:
        target = "top"
        pair = "top"
    if same[pair]:
        target = pair
    elif target == pair:
        target = CORNER_PAIR_CORNERS[pair][0]
    host.manual_active_corner_var.set(target)
    return target


def corner_parameter_summary(host_cls, selection):
    selection = normalize_corner_selection(selection)
    if selection.type_id is CornerTypeId.CROSS:
        mode = host_cls._CORNER_MODE_LABELS[selection.cross_mode]
        if selection.cross_mode is CrossCornerMode.STANDARD:
            return mode
        direction = host_cls._CORNER_DIRECTION_LABELS[selection.direction]
        return f"{mode}｜{direction}｜{host_cls._corner_number_text(selection.amount_t)}T"
    if selection.type_id is CornerTypeId.OVERLAY:
        return f"留肉（高）｜{host_cls._corner_number_text(selection.amount_t)}T"
    if selection.type_id is CornerTypeId.INSERT:
        return f"多切（高）｜{host_cls._corner_number_text(selection.amount_t)}T"
    return (
        f"貼外留肉 {host_cls._corner_number_text(selection.amount_t)}T｜"
        f"嵌入留肉 {host_cls._corner_number_text(selection.secondary_retain_t)}T｜"
        f"深度 {host_cls._corner_number_text(selection.secondary_depth_t)}T"
    )
