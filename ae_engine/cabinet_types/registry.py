# -*- coding: utf-8 -*-
"""Cabinet-family registry for the replaceable AE engine package.

Phase 5 only establishes dispatch identity.  Cabinet-specific manufacturing
rules belong in each family adapter and must be added from confirmed factory
rules; the registry never invents geometry.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CabinetTypeRegistration:
    canonical_name: str
    aliases: tuple[str, ...]
    module_name: str
    implemented: bool = True


_REGISTRY: dict[str, CabinetTypeRegistration] = {}


def _key(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise KeyError("empty cabinet type")
    return text.casefold()


def register_cabinet_type(registration: CabinetTypeRegistration) -> CabinetTypeRegistration:
    """Register one cabinet family and all of its aliases."""
    names = (registration.canonical_name, *registration.aliases)
    for name in names:
        key = _key(name)
        previous = _REGISTRY.get(key)
        if previous is not None and previous != registration:
            raise ValueError(f"cabinet type alias already registered: {name!r}")
    for name in names:
        _REGISTRY[_key(name)] = registration
    return registration


def resolve_cabinet_type(name: str) -> CabinetTypeRegistration:
    """Resolve canonical cabinet-family metadata from a name or alias."""
    key = _key(name)
    try:
        return _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"unknown cabinet type: {name!r}") from exc


def registered_cabinet_types() -> tuple[CabinetTypeRegistration, ...]:
    """Return unique registrations in deterministic canonical-name order."""
    unique = {item.canonical_name: item for item in _REGISTRY.values()}
    return tuple(unique[name] for name in sorted(unique))
