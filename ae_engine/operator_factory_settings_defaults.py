"""#2517: Engine-owned manufacturing factory defaults for all operator parts.

Factory reset always derives from AE's immutable default_config contract,
never config.ini or mutable runtime. UI-only text size is passed through
untouched for the presentation layer to normalize. Unknown fields cannot be
introduced by clients; the catalogue is the single source of supported keys.
"""
from __future__ import annotations

from collections.abc import Mapping

from . import ae
from .operator_settings_catalog import SETTING_SPECS
from .operator_settings_transactions import (
    PHYSICAL_SNAPSHOT_SOURCE_KEYS,
    normalize_operator_settings_boolean,
    normalize_operator_settings_updates,
    normalize_operator_source_dimension,
)


def _qualified_default(spec, raw):
    if spec.kind == "choice":
        # UI text size is NOT a manufacturing parameter.
        return raw
    if spec.kind == "bool":
        return normalize_operator_settings_boolean(raw)
    if spec.key in PHYSICAL_SNAPSHOT_SOURCE_KEYS:
        return normalize_operator_source_dimension(raw, field=spec.key)
    normalized = normalize_operator_settings_updates(
        {spec.key: spec.default}, {spec.key: raw},
    )
    if spec.key not in normalized:
        raise ValueError(f"{spec.key} 設定值必須是有限數值")
    return normalized[spec.key]


def project_operator_factory_default_settings(
    *, source_config: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Resolve detached factory settings via the existing public Engine gates.

    `source_config` is an optional legacy-test/host source; when absent the
    Engine reads its own factory `ae.default_config` at call time. Never read
    live runtime values or persisted user config.ini. A corrupt factory field
    falls back ONLY to that known catalog field's original factory default,
    not to a live setting or to another Family.
    """
    source = ae.default_config if source_config is None else source_config
    if not isinstance(source, Mapping):
        source = {}
    resolved: dict[str, object] = {}
    for spec in SETTING_SPECS:
        section = source.get(spec.section, {})
        value = None
        if isinstance(section, Mapping):
            if spec.option in section:
                value = section[spec.option]
            elif spec.legacy_option and spec.legacy_option in section:
                value = section[spec.legacy_option]
        if value is None:
            value = spec.default
        try:
            resolved[spec.key] = _qualified_default(spec, value)
        except (TypeError, ValueError, OverflowError):
            resolved[spec.key] = _qualified_default(spec, spec.default)
    return resolved
