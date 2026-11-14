"""Canonical operator manufacturing settings catalog (GUI-independent).

The Phase6 settings screen uses these labels and contexts only for
presentation; physical setting identities, legacy INI fields, and fallback
values are owned by this Engine catalog.
"""
from __future__ import annotations
from dataclasses import dataclass

GLOBAL_CONTEXT = "global"

@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    contexts: tuple[str, ...]
    section: str
    option: str
    default: object
    kind: str = "float"  # float | bool | choice
    group: str = "一般"
    runtime_attr: str | None = None
    relief_attr: str | None = None
    legacy_option: str | None = None

    @property
    def global_setting(self) -> bool:
        return GLOBAL_CONTEXT in self.contexts


# Contexts intentionally describe where the value is edited, not every part
# that eventually consumes the value.  E.g. T/FW are global and therefore are
# not duplicated on every part page.
SETTING_SPECS: tuple[SettingSpec, ...] = (
    # Global dimensions / output.
    SettingSpec("w", "寬度 W", (GLOBAL_CONTEXT,), "DEFAULT_SIZES", "W", 400.0, group="箱體尺寸", runtime_attr="W"),
    SettingSpec("h", "高度 H", (GLOBAL_CONTEXT,), "DEFAULT_SIZES", "H", 600.0, group="箱體尺寸", runtime_attr="H"),
    SettingSpec("d", "深度 D", (GLOBAL_CONTEXT,), "DEFAULT_SIZES", "D", 250.0, group="箱體尺寸", runtime_attr="D"),
    SettingSpec("t", "板厚 T", (GLOBAL_CONTEXT,), "DEFAULT_SIZES", "T", 2.0, group="箱體尺寸", runtime_attr="T"),
    SettingSpec("fw", "框寬 FW", (GLOBAL_CONTEXT,), "DEFAULT_SIZES", "FW", 25.0, group="箱體尺寸", runtime_attr="FW"),
    SettingSpec("draw_stock", "輸出 STOCK", (GLOBAL_CONTEXT,), "OUTPUT", "draw_stock", False, kind="bool", group="輸出", runtime_attr="DRAW_STOCK"),
    SettingSpec("ui_text_size", "文字大小", (GLOBAL_CONTEXT,), "UI", "text_size", "small", kind="choice", group="介面"),

    # Current engine relief / legacy notch compatibility knobs.
    SettingSpec("relief_top_secondary_x_factor", "頂部二級截角 X 係數", (GLOBAL_CONTEXT,), "RELIEF", "top_secondary_x_factor", 0.5, group="Relief", relief_attr="top_secondary_x_factor"),
    SettingSpec("relief_top_secondary_depth_factor", "頂部二級截角深度係數", (GLOBAL_CONTEXT,), "RELIEF", "top_secondary_depth_factor", 2.0, group="Relief", relief_attr="top_secondary_depth_factor"),
    SettingSpec("relief_bottom_x_factor", "底部截角 X 係數", (GLOBAL_CONTEXT,), "RELIEF", "bottom_x_factor", 0.5, group="Relief", relief_attr="bottom_x_factor"),
    SettingSpec("relief_bottom_y_factor", "底部截角 Y 係數", (GLOBAL_CONTEXT,), "RELIEF", "bottom_y_factor", 0.5, group="Relief", relief_attr="bottom_y_factor"),
    SettingSpec("notch_bottom_gap", "舊 NOTCH：底部間隙", (GLOBAL_CONTEXT,), "NOTCH", "bottom_gap", 0.5, group="NOTCH 相容", runtime_attr="notch_bottom_gap"),
    SettingSpec("notch_sub_x_half", "舊 NOTCH：二級 X 係數", (GLOBAL_CONTEXT,), "NOTCH", "sub_x_half_t", 0.5, group="NOTCH 相容", runtime_attr="notch_sub_x_half"),
    SettingSpec("notch_sub_y_factor", "舊 NOTCH：二級 Y 係數", (GLOBAL_CONTEXT,), "NOTCH", "sub_y_factor", 2.0, group="NOTCH 相容", runtime_attr="notch_sub_y_factor"),

    # Box body.
    SettingSpec("zl1", "左外折 1", ("box_body",), "BOX_BODY_Z", "zl1", 15.0, group="折彎", runtime_attr="zl1_def"),
    SettingSpec("zl2", "左外折 2", ("box_body",), "BOX_BODY_Z", "zl2", 20.0, group="折彎", runtime_attr="zl2_def"),
    SettingSpec("zr1", "右外折 1", ("box_body",), "BOX_BODY_Z", "zr1", 15.0, group="折彎", runtime_attr="zr1_def"),
    SettingSpec("zr2", "右外折 2", ("box_body",), "BOX_BODY_Z", "zr2", 20.0, group="折彎", runtime_attr="zr2_def"),
    SettingSpec("z_comp", "箱身補料", ("box_body",), "BOX_BODY_Z", "z_comp", 3.0, group="補償", runtime_attr="z_comp_def"),

    # End cap geometry shared by head/tail in the current manufacturing model.
    SettingSpec("yl1", "左折", ("head", "tail"), "END_CAP_Y", "yl1", 15.0, group="折彎", runtime_attr="yl1_def"),
    SettingSpec("yr1", "右折", ("head", "tail"), "END_CAP_Y", "yr1", 15.0, group="折彎", runtime_attr="yr1_def"),
    SettingSpec("ytop1", "上折", ("head", "tail"), "END_CAP_Y", "ytop1", 16.0, group="折彎", runtime_attr="ytop1_def"),
    SettingSpec("ybottom1", "下折", ("head", "tail"), "END_CAP_Y", "ybottom1", 15.0, group="折彎", runtime_attr="ybottom1_def"),

    # Fixed EndCap hole policy: shared values appear on both head and tail.
    SettingSpec("hang_hole_r", "掛孔半徑", ("head", "tail"), "HOLES", "hang_hole_radius", 3.2, group="固定孔", runtime_attr="hang_hole_r"),
    SettingSpec("hang_hole_x", "舊掛孔 X（相容）", ("head", "tail"), "HOLES", "hang_hole_x_offset", 35.5, group="固定孔", runtime_attr="hang_hole_x"),
    SettingSpec("hang_hole_y_up", "掛孔距頂折線", ("head", "tail"), "HOLES", "hang_hole_y_from_top_bend", 6.0, group="固定孔", runtime_attr="hang_hole_y_up"),
    SettingSpec("sq_x_left", "方孔距左", ("head", "tail"), "HOLES", "square_hole_x_from_left", 3.0, group="固定孔", runtime_attr="sq_x_left"),
    SettingSpec("sq_width", "方孔寬", ("head", "tail"), "HOLES", "square_hole_width", 4.0, group="固定孔", runtime_attr="sq_width"),
    SettingSpec("sq_y_bottom", "方孔距底", ("head", "tail"), "HOLES", "square_hole_y_from_bottom", 18.0, group="固定孔", runtime_attr="sq_y_bottom"),
    SettingSpec("sq_height", "方孔高", ("head", "tail"), "HOLES", "square_hole_height", 4.0, group="固定孔", runtime_attr="sq_height"),
    SettingSpec("bottom_hole_r", "封尾底孔半徑", ("tail",), "HOLES", "bottom_hole_radius", 2.5, group="封尾固定孔", runtime_attr="bottom_hole_r"),
    SettingSpec("bottom_hole_y", "封尾底孔距底", ("tail",), "HOLES", "bottom_hole_y_from_bottom", 5.0, group="封尾固定孔", runtime_attr="bottom_hole_y"),

    # Door.
    SettingSpec("door_gap_w", "門縫 W", ("door",), "DOOR", "door_gap_w", 3.5, group="門縫", runtime_attr="door_gap_w_def"),
    SettingSpec("door_gap_h", "門縫 H", ("door",), "DOOR", "door_gap_h", 3.5, group="門縫", runtime_attr="door_gap_h_def"),
    SettingSpec("door_fold_l", "左折", ("door",), "DOOR", "door_fold_left", 19.0, group="折彎", runtime_attr="door_fold_left_def"),
    SettingSpec("door_fold_r", "右折", ("door",), "DOOR", "door_fold_right", 15.0, group="折彎", runtime_attr="door_fold_right_def"),
    SettingSpec("door_fold_t", "上折", ("door",), "DOOR", "door_fold_top", 15.0, group="折彎", runtime_attr="door_fold_top_def"),
    SettingSpec("door_fold_b", "下折", ("door",), "DOOR", "door_fold_bottom", 15.0, group="折彎", runtime_attr="door_fold_bottom_def"),

    # Base plate.  New per-edge keys are optional and fall back to legacy shrink.
    SettingSpec("base_plate_shrink_top", "上縮", ("base_plate",), "BASE_PLATE", "shrink_top", 55.0, group="收縮", legacy_option="shrink"),
    SettingSpec("base_plate_shrink_bottom", "下縮", ("base_plate",), "BASE_PLATE", "shrink_bottom", 55.0, group="收縮", legacy_option="shrink"),
    SettingSpec("base_plate_shrink_left", "左縮", ("base_plate",), "BASE_PLATE", "shrink_left", 55.0, group="收縮", legacy_option="shrink"),
    SettingSpec("base_plate_shrink_right", "右縮", ("base_plate",), "BASE_PLATE", "shrink_right", 55.0, group="收縮", legacy_option="shrink"),
    SettingSpec("base_plate_bend", "折邊", ("base_plate",), "BASE_PLATE", "bend", 15.0, group="折彎", runtime_attr="base_plate_bend_def"),

    # Indicator parts.
    SettingSpec("indicator_box_fold", "指示燈盒折邊", ("indicator_box",), "INDICATOR_BOX", "fold", 49.0, group="折彎", runtime_attr="indicator_box_fold_def"),
    SettingSpec("indicator_door_fold", "指示燈小門折邊", ("indicator_door",), "INDICATOR_SMALL_DOOR", "fold", 19.0, group="折彎", runtime_attr="indicator_small_door_fold_def"),
)

_SPEC_BY_KEY = {spec.key: spec for spec in SETTING_SPECS}


def settings_for_context(context: str) -> tuple[SettingSpec, ...]:
    """Return editable manufacturing/default settings for one 3D context."""
    key = str(context or GLOBAL_CONTEXT)
    return tuple(spec for spec in SETTING_SPECS if key in spec.contexts)
