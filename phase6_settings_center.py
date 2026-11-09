# -*- coding: utf-8 -*-
"""Schema-driven Phase6 manufacturing/default settings center.

The module is deliberately UI-agnostic. ``SettingsService`` owns committed
runtime settings; ``config.ini`` stores next-start persisted defaults, while
Fold Designer keeps its own transaction-local draft until the main GUI commits.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
import configparser
from pathlib import Path
from types import MappingProxyType
from typing import Iterable

from ae_engine import manufacturing_api


GLOBAL_CONTEXT = manufacturing_api.OPERATOR_GLOBAL_SETTINGS_CONTEXT

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


# Canonical manufacturing Settings keys, defaults and contexts are Engine-owned.
# The GUI retains only UI text-size presentation and INI/Tk transport.
SettingSpec = manufacturing_api.OperatorSettingSpec
SETTING_SPECS = manufacturing_api.OPERATOR_SETTING_SPECS
_SPEC_BY_KEY = {spec.key: spec for spec in SETTING_SPECS}
settings_for_context = manufacturing_api.operator_settings_for_context


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
        # A malformed saved boolean must not silently become False.
        return manufacturing_api.normalize_operator_settings_boolean(raw)
    if spec.kind == "choice":
        if spec.key == "ui_text_size":
            return normalize_ui_text_size(raw)
        return str(raw).strip()
    if spec.key in manufacturing_api.PHYSICAL_SNAPSHOT_SOURCE_KEYS:
        # Outside physical W/H/D/T/FW are validated once in the Engine,
        # including bool, NaN, infinity, zero and negative source values.
        return manufacturing_api.normalize_operator_source_dimension(
            raw, field=spec.key,
        )
    # Other numeric Fold/Hole/Relief/plate settings keep their existing signed
    # ranges. The Engine's pre-existing numeric gate alone rejects bool, NaN
    # and infinity; do not invent GUI manufacturing limits or formulas.
    normalized = manufacturing_api.normalize_operator_settings_updates(
        {spec.key: spec.default}, {spec.key: raw},
    )
    if spec.key not in normalized:
        raise ValueError(f"{spec.key} 設定值必須是有限數值")
    return normalized[spec.key]


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


def project_fold_designer_factory_snapshot() -> dict[str, object]:
    """Read manufacturing factory defaults only through the public Engine API.

    UI text size remains display-only and is normalized by this GUI adapter.
    This never reads persisted user INI or mutable runtime manufacturing values.
    """
    result = manufacturing_api.project_operator_factory_default_settings()
    result["ui_text_size"] = normalize_ui_text_size(result["ui_text_size"])
    return result


def load_factory_defaults_from_ae(ae_module) -> dict[str, object]:
    """Legacy settings-service host: project the same Engine factory defaults.

    Synthetic/older hosts may supply a factory config map. An absent one uses
    the original catalog defaults, not the process-global live Engine state.
    """
    source = getattr(ae_module, "default_config", None) or {}
    result = manufacturing_api.project_operator_factory_default_settings(
        source_config=source,
    )
    result["ui_text_size"] = normalize_ui_text_size(result["ui_text_size"])
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
    """Forward committed operator Settings to the Engine runtime transaction.

    The GUI selects known input fields only; Engine validates every physical
    value and applies the AE scalar, Relief and fixed-hole policy together.
    This does not write config.ini or infer manufacturing from UI state.
    """
    specs = _selected_specs(keys=keys) if keys is not None else tuple(
        _SPEC_BY_KEY[k] for k in values.keys() if k in _SPEC_BY_KEY
    )
    selected_keys = tuple(spec.key for spec in specs if spec.key in values)
    manufacturing_api.apply_operator_runtime_settings_to_ae(
        ae_module, values, keys=selected_keys,
    )


def _format_ini_value(spec: SettingSpec, value: object) -> str:
    if spec.kind == "bool":
        return "true" if bool(_coerce(spec, value)) else "false"
    if spec.kind == "choice":
        return str(_coerce(spec, value))
    number = _coerce(spec, value)
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
    if context == "base_plate":
        # Only the four explicitly persisted edges may update the legacy
        # shared value; other rows in a full Settings snapshot are not edits.
        selected_values = {key: values[key] for key in changed_keys}
        legacy_shrink = manufacturing_api.operator_legacy_shared_base_plate_shrink(
            selected_values,
        )
        if legacy_shrink is not None:
            if not parser.has_section("BASE_PLATE"):
                parser.add_section("BASE_PLATE")
            parser.set("BASE_PLATE", "shrink", _format_ini_value(
                _SPEC_BY_KEY["base_plate_shrink_top"], legacy_shrink,
            ))

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
CORNER_KEYS = manufacturing_api.MANUAL_CORNER_KEYS


def _corner_section(part_key: str) -> str:
    return f"CORNER_{str(part_key).upper()}"


def load_corner_defaults_from_ini(ae_module):
    """Read persisted INI only; Engine owns physical CornerType decoding."""
    parser = _parser_for_ae(ae_module)
    states = {}
    pairs = {}
    for part_key in CORNER_PARTS:
        section = _corner_section(part_key)
        if not parser.has_section(section):
            continue
        corner_state, pair_state = manufacturing_api.project_operator_corner_ini_load_section(
            dict(parser.items(section)),
        )
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
    corners = dict((corner_state or {}).get(part_key) or {})
    for option, value in manufacturing_api.project_operator_corner_ini_save_options(
        corners, pairs,
    ).items():
        if value is None:
            parser.remove_option(section, option)
        else:
            parser.set(section, option, value)

    ini_path.parent.mkdir(parents=True, exist_ok=True)
    with ini_path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    if hasattr(ae_module, "config"):
        ae_module.config.clear()
        ae_module.config.read(ini_path, encoding="utf-8")
