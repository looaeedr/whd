# -*- coding: utf-8 -*-
"""Schema-driven Phase6 manufacturing/default settings center.

The module is deliberately UI-agnostic. ``SettingsService`` owns committed
runtime settings; ``config.ini`` stores next-start persisted defaults, while
Fold Designer keeps its own transaction-local draft until the main GUI commits.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, is_dataclass, replace
import configparser
from pathlib import Path
from types import MappingProxyType
from typing import Iterable


GLOBAL_CONTEXT = "global"

UI_TEXT_SIZE_LABELS = {
    "small": "小",
    "medium": "中",
    "large": "大",
}
UI_TEXT_SIZE_BY_LABEL = {label: key for key, label in UI_TEXT_SIZE_LABELS.items()}
UI_TEXT_SIZE_FACTORS = {
    "small": 1.0,
    "medium": 1.2,
    "large": 1.4,
}

def normalize_ui_text_size(value) -> str:
    text = str(value or "small").strip()
    if text in UI_TEXT_SIZE_BY_LABEL:
        return UI_TEXT_SIZE_BY_LABEL[text]
    key = text.lower()
    return key if key in UI_TEXT_SIZE_LABELS else "small"

def ui_text_size_label(value) -> str:
    return UI_TEXT_SIZE_LABELS[normalize_ui_text_size(value)]

def ui_text_size_factor(value) -> float:
    return UI_TEXT_SIZE_FACTORS[normalize_ui_text_size(value)]


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


def _parser_for_ae(ae_module) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    ini_path = getattr(ae_module, "INI_PATH", None)
    if ini_path and Path(ini_path).exists():
        parser.read(ini_path, encoding="utf-8")
    elif hasattr(ae_module, "config"):
        # Copy instead of mutating the engine parser during a read.
        source = ae_module.config
        for section in source.sections():
            if not parser.has_section(section):
                parser.add_section(section)
            for option, value in source.items(section):
                parser.set(section, option, value)
    return parser


def _coerce(spec: SettingSpec, raw):
    if spec.kind == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if spec.kind == "choice":
        if spec.key == "ui_text_size":
            return normalize_ui_text_size(raw)
        return str(raw).strip()
    return float(raw)


def _runtime_default(ae_module, spec: SettingSpec):
    if spec.relief_attr:
        cfg = getattr(ae_module, "RELIEF_CONFIG", None)
        if cfg is not None and hasattr(cfg, spec.relief_attr):
            return getattr(cfg, spec.relief_attr)
    if spec.runtime_attr and hasattr(ae_module, spec.runtime_attr):
        return getattr(ae_module, spec.runtime_attr)
    if spec.key.startswith("base_plate_shrink_") and hasattr(ae_module, "base_plate_shrink_def"):
        return getattr(ae_module, "base_plate_shrink_def")
    return spec.default


def load_factory_defaults_from_ae(ae_module) -> dict[str, object]:
    """Load immutable factory defaults from ``ae_engine.ae.default_config``.

    This deliberately ignores ``config.ini`` and all already-mutated runtime
    module attributes.  It is the source used by the FoldDesigner
    ``還原初始值`` action.  When a newer setting has no historical
    ``default_config`` entry yet, the schema's own factory default is used.
    """
    source = getattr(ae_module, "default_config", None) or {}
    result: dict[str, object] = {}
    for spec in SETTING_SPECS:
        section = source.get(spec.section, {}) if isinstance(source, Mapping) else {}
        raw = None
        if isinstance(section, Mapping):
            if spec.option in section:
                raw = section[spec.option]
            elif spec.legacy_option and spec.legacy_option in section:
                raw = section[spec.legacy_option]
        if raw is None:
            raw = spec.default
        try:
            result[spec.key] = _coerce(spec, raw)
        except (TypeError, ValueError):
            result[spec.key] = _coerce(spec, spec.default)
    return result


def load_settings_from_ae(ae_module) -> dict[str, object]:
    """Load every supported setting, preserving existing config.ini semantics."""
    parser = _parser_for_ae(ae_module)
    result: dict[str, object] = {}
    for spec in SETTING_SPECS:
        raw = None
        if parser.has_option(spec.section, spec.option):
            raw = parser.get(spec.section, spec.option)
        elif spec.legacy_option and parser.has_option(spec.section, spec.legacy_option):
            raw = parser.get(spec.section, spec.legacy_option)
        if raw is None:
            raw = _runtime_default(ae_module, spec)
        try:
            result[spec.key] = _coerce(spec, raw)
        except (TypeError, ValueError):
            result[spec.key] = _coerce(spec, _runtime_default(ae_module, spec))
    return result


class Phase6Settings(Mapping[str, object]):
    """Immutable settings snapshot exposed by :class:`SettingsService`."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, object]):
        self._values = MappingProxyType(dict(values))

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def as_dict(self) -> dict[str, object]:
        return dict(self._values)


class SettingsService:
    """Own the committed Phase6 runtime settings behind one small seam."""

    def __init__(self, ae_module):
        self._ae_module = ae_module
        self._current = Phase6Settings(load_settings_from_ae(ae_module))
        self._factory = Phase6Settings(load_factory_defaults_from_ae(ae_module))
        apply_settings_to_ae(ae_module, self._current)

    def snapshot(self) -> Phase6Settings:
        return Phase6Settings(self._current)

    def factory_snapshot(self) -> Phase6Settings:
        return Phase6Settings(self._factory)

    def _normalize_updates(self, values: Mapping[str, object]) -> dict[str, object]:
        clean: dict[str, object] = {}
        for key, raw in dict(values or {}).items():
            spec = _SPEC_BY_KEY.get(str(key))
            if spec is None:
                continue
            try:
                clean[spec.key] = _coerce(spec, raw)
            except (TypeError, ValueError):
                continue
        return clean

    def update(self, values: Mapping[str, object]) -> Phase6Settings:
        clean = self._normalize_updates(values)
        if not clean:
            return self.snapshot()

        merged = self._current.as_dict()
        changed = {key: value for key, value in clean.items() if merged.get(key) != value}
        if not changed:
            return self.snapshot()

        merged.update(changed)
        self._current = Phase6Settings(merged)
        apply_settings_to_ae(self._ae_module, changed)
        return self.snapshot()

    def persist_defaults(
        self,
        *,
        context: str = GLOBAL_CONTEXT,
        values: Mapping[str, object] | None = None,
        keys: Iterable[str] | None = None,
    ) -> None:
        persisted = self._current.as_dict()
        if values is not None:
            persisted.update(self._normalize_updates(values))
        save_defaults_to_ini(
            self._ae_module, persisted, context=context, keys=keys, apply_runtime=False
        )


def _selected_specs(context: str | None = None, keys: Iterable[str] | None = None):
    if keys is not None:
        wanted = {str(k) for k in keys}
        return tuple(spec for spec in SETTING_SPECS if spec.key in wanted)
    return settings_for_context(context or GLOBAL_CONTEXT)


def apply_settings_to_ae(ae_module, values: Mapping[str, object], *, keys: Iterable[str] | None = None) -> None:
    """Mirror committed runtime settings into the already-imported AE module.

    This does not write config.ini. New main-GUI production paths call it through
    ``SettingsService.update``; the function remains public for legacy callers.
    """
    specs = _selected_specs(keys=keys) if keys is not None else tuple(
        _SPEC_BY_KEY[k] for k in values.keys() if k in _SPEC_BY_KEY
    )
    relief_changes = {}
    for spec in specs:
        if spec.key not in values:
            continue
        value = _coerce(spec, values[spec.key])
        if spec.relief_attr:
            relief_changes[spec.relief_attr] = value
        elif spec.runtime_attr:
            setattr(ae_module, spec.runtime_attr, value)

    if relief_changes:
        current = getattr(ae_module, "RELIEF_CONFIG", None)
        if current is not None:
            try:
                if is_dataclass(current):
                    current = replace(current, **relief_changes)
                else:
                    for name, value in relief_changes.items():
                        setattr(current, name, value)
                setattr(ae_module, "RELIEF_CONFIG", current)
            except Exception:
                # A custom/frozen non-dataclass engine object may not be mutable;
                # persistence still succeeds and explicit PartSpec values remain safe.
                pass

    # Fixed EndCap holes are consumed through a policy object created at engine
    # import time.  Rebuild that object too, otherwise editing the hidden HOLES
    # values would update module scalars but not the actual preview/DXF geometry.
    fixed_hole_keys = {
        "hang_hole_r", "hang_hole_y_up", "sq_x_left", "sq_y_bottom",
        "sq_width", "sq_height", "bottom_hole_r", "bottom_hole_y",
    }
    if fixed_hole_keys.intersection(values):
        policy = getattr(ae_module, "VAULT_ENDCAP_FEATURE_POLICY", None)
        if policy is not None:
            def point_like(current, x, y):
                try:
                    return type(current)(float(x), float(y))
                except Exception:
                    return (float(x), float(y))
            changes = {
                "hanging_hole_radius": float(getattr(ae_module, "hang_hole_r", 3.2)),
                "hanging_hole_y_from_top_bend": float(getattr(ae_module, "hang_hole_y_up", 6.0)),
                "square_hole_origin": point_like(
                    getattr(policy, "square_hole_origin", (3.0, 18.0)),
                    getattr(ae_module, "sq_x_left", 3.0), getattr(ae_module, "sq_y_bottom", 18.0),
                ),
                "square_hole_size": point_like(
                    getattr(policy, "square_hole_size", (4.0, 4.0)),
                    getattr(ae_module, "sq_width", 4.0), getattr(ae_module, "sq_height", 4.0),
                ),
                "tail_bottom_hole_radius": float(getattr(ae_module, "bottom_hole_r", 2.5)),
                "tail_bottom_hole_y": float(getattr(ae_module, "bottom_hole_y", 5.0)),
            }
            try:
                if is_dataclass(policy):
                    policy = replace(policy, **changes)
                else:
                    for name, value in changes.items():
                        setattr(policy, name, value)
                setattr(ae_module, "VAULT_ENDCAP_FEATURE_POLICY", policy)
            except Exception:
                pass

    # Maintain legacy shared base-plate default only when the four edge values
    # are equal; explicit runtime GUI values remain authoritative otherwise.
    shrink_keys = (
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right",
    )
    if all(k in values for k in shrink_keys):
        vals = [float(values[k]) for k in shrink_keys]
        if max(vals) - min(vals) < 1e-9:
            setattr(ae_module, "base_plate_shrink_def", vals[0])


def _format_ini_value(spec: SettingSpec, value: object) -> str:
    if spec.kind == "bool":
        return "true" if bool(_coerce(spec, value)) else "false"
    if spec.kind == "choice":
        return str(_coerce(spec, value))
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def save_defaults_to_ini(
    ae_module,
    values: Mapping[str, object],
    *,
    context: str = GLOBAL_CONTEXT,
    keys: Iterable[str] | None = None,
    apply_runtime: bool = True,
) -> None:
    """Persist one context while preserving unrelated INI data.

    ``apply_runtime`` defaults to the historical behavior for compatibility.
    ``SettingsService.persist_defaults`` always disables it so persistence cannot
    commit a Fold Designer draft into the current runtime.
    """
    specs = _selected_specs(context=context, keys=keys)
    ini_path = Path(getattr(ae_module, "INI_PATH"))
    parser = configparser.ConfigParser()
    if ini_path.exists():
        parser.read(ini_path, encoding="utf-8")
    elif hasattr(ae_module, "config"):
        source = ae_module.config
        for section in source.sections():
            parser.add_section(section)
            for option, value in source.items(section):
                parser.set(section, option, value)

    changed_keys = []
    for spec in specs:
        if spec.key not in values:
            continue
        if not parser.has_section(spec.section):
            parser.add_section(spec.section)
        parser.set(spec.section, spec.option, _format_ini_value(spec, values[spec.key]))
        changed_keys.append(spec.key)

    # If all four specific shrink values are the same, keep the old key in sync
    # so older engine versions still see the same default.
    shrink_keys = (
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right",
    )
    if context == "base_plate" and all(k in values for k in shrink_keys):
        vals = [float(values[k]) for k in shrink_keys]
        if max(vals) - min(vals) < 1e-9:
            if not parser.has_section("BASE_PLATE"):
                parser.add_section("BASE_PLATE")
            parser.set("BASE_PLATE", "shrink", _format_ini_value(_SPEC_BY_KEY[shrink_keys[0]], vals[0]))

    ini_path.parent.mkdir(parents=True, exist_ok=True)
    with ini_path.open("w", encoding="utf-8") as fh:
        parser.write(fh)

    # Replace the engine's parser contents to avoid an old in-memory view.
    if hasattr(ae_module, "config"):
        ae_module.config.clear()
        ae_module.config.read(ini_path, encoding="utf-8")
    if apply_runtime:
        apply_settings_to_ae(ae_module, values, keys=changed_keys)

CORNER_PARTS = ("head", "tail", "door", "base_plate", "indicator_box", "indicator_door")
CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")


def _corner_section(part_key: str) -> str:
    return f"CORNER_{str(part_key).upper()}"


def load_corner_defaults_from_ini(ae_module):
    """載入各板件可選的截角預設值，回傳可直接序列化的資料。

    新的截角製造參數會和 type id 一起保存。舊 C01-C04 區段仍可讀取；
    缺少的新語意欄位稍後由幾何引擎統一轉換並補回相容預設值。
    """
    parser = _parser_for_ae(ae_module)
    states = {}
    pairs = {}
    for part_key in CORNER_PARTS:
        section = _corner_section(part_key)
        if not parser.has_section(section):
            continue
        pair_state = {
            "top": parser.getboolean(section, "top_same", fallback=True),
            "bottom": parser.getboolean(section, "bottom_same", fallback=True),
        }
        corner_state = {}
        for corner_key in CORNER_KEYS:
            if not parser.has_option(section, corner_key):
                continue
            type_id = parser.get(section, corner_key, fallback="CROSS").strip().upper()
            rotation = parser.getint(section, f"{corner_key}_rotation", fallback=0) % 4
            if type_id != "C02":
                rotation = 0
            raw = {"type_id": type_id, "rotation_quadrants": rotation}
            text_fields = {
                "cross_mode": f"{corner_key}_cross_mode",
                "direction": f"{corner_key}_direction",
            }
            for field, option in text_fields.items():
                if parser.has_option(section, option):
                    value = parser.get(section, option).strip().lower()
                    if value:
                        raw[field] = value
            float_fields = {
                "amount_t": f"{corner_key}_amount_t",
                "secondary_retain_t": f"{corner_key}_secondary_retain_t",
                "secondary_depth_t": f"{corner_key}_secondary_depth_t",
            }
            for field, option in float_fields.items():
                if parser.has_option(section, option):
                    try:
                        raw[field] = parser.getfloat(section, option)
                    except ValueError:
                        pass
            corner_state[corner_key] = raw
        if corner_state:
            states[part_key] = corner_state
        pairs[part_key] = pair_state
    return states, pairs

def save_corner_defaults_to_ini(ae_module, corner_state, corner_pair_same, *, context: str) -> None:
    """只保存指定板件的截角預設值，其他 INI 資料保持不動。"""
    part_key = str(context or "")
    if part_key not in CORNER_PARTS:
        return
    ini_path = Path(getattr(ae_module, "INI_PATH"))
    parser = configparser.ConfigParser()
    if ini_path.exists():
        parser.read(ini_path, encoding="utf-8")
    elif hasattr(ae_module, "config"):
        source = ae_module.config
        for section in source.sections():
            if not parser.has_section(section):
                parser.add_section(section)
            for option, value in source.items(section):
                parser.set(section, option, value)

    section = _corner_section(part_key)
    if not parser.has_section(section):
        parser.add_section(section)
    pairs = dict((corner_pair_same or {}).get(part_key) or {})
    parser.set(section, "top_same", "true" if bool(pairs.get("top", True)) else "false")
    parser.set(section, "bottom_same", "true" if bool(pairs.get("bottom", True)) else "false")
    corners = dict((corner_state or {}).get(part_key) or {})
    for corner_key in CORNER_KEYS:
        raw = corners.get(corner_key)
        if not isinstance(raw, Mapping):
            continue
        type_id = str(raw.get("type_id", "CROSS")).strip().upper()
        rotation = int(raw.get("rotation_quadrants", 0) or 0) % 4 if type_id == "C02" else 0
        parser.set(section, corner_key, type_id)
        parser.set(section, f"{corner_key}_rotation", str(rotation))

        semantic_options = {
            "cross_mode": f"{corner_key}_cross_mode",
            "direction": f"{corner_key}_direction",
            "amount_t": f"{corner_key}_amount_t",
            "secondary_retain_t": f"{corner_key}_secondary_retain_t",
            "secondary_depth_t": f"{corner_key}_secondary_depth_t",
        }
        for field, option in semantic_options.items():
            value = raw.get(field)
            if value is None or value == "":
                parser.remove_option(section, option)
                continue
            if field.endswith("_t"):
                try:
                    text = f"{float(value):g}"
                except (TypeError, ValueError):
                    parser.remove_option(section, option)
                    continue
            else:
                text = str(getattr(value, "value", value)).strip().lower()
            parser.set(section, option, text)

    ini_path.parent.mkdir(parents=True, exist_ok=True)
    with ini_path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    if hasattr(ae_module, "config"):
        ae_module.config.clear()
        ae_module.config.read(ini_path, encoding="utf-8")
