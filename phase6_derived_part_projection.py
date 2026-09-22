"""Pure immutable planning seam for topology-derived physical-part synchronization.

This module deliberately owns no workspace/navigation mutation and no manufacturing
geometry formulas. Callers derive authoritative profiles/features through their
existing domain owners, freeze those projections into a request, and receive a
stable plan describing the workspace intent to apply elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class FrozenMappingValue:
    items: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class FrozenSequenceValue:
    items: tuple[Any, ...] = ()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return FrozenMappingValue(
            tuple((str(key), _freeze(item)) for key, item in value.items())
        )
    if isinstance(value, (list, tuple)):
        return FrozenSequenceValue(tuple(_freeze(item) for item in value))
    if isinstance(value, (set, frozenset)):
        frozen = tuple(_freeze(item) for item in value)
        return FrozenSequenceValue(tuple(sorted(frozen, key=repr)))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, FrozenMappingValue):
        return {key: _thaw(item) for key, item in value.items}
    if isinstance(value, FrozenSequenceValue):
        return [_thaw(item) for item in value.items]
    return value


@dataclass(frozen=True)
class DerivedPartProfileProjection:
    part_key: str
    profiles: FrozenMappingValue = FrozenMappingValue()


@dataclass(frozen=True)
class DerivedPartFeatureProjection:
    part_key: str
    features: FrozenSequenceValue = FrozenSequenceValue()


@dataclass(frozen=True)
class DerivedPartNamespaceProjection:
    namespace: str
    parts: tuple[DerivedPartProfileProjection, ...] = ()


@dataclass(frozen=True)
class DerivedPartProjectionRequest:
    namespaces: tuple[DerivedPartNamespaceProjection, ...] = ()
    remove_part_keys: tuple[str, ...] = ()
    add_parts: tuple[DerivedPartProfileProjection, ...] = ()
    stash_profiles: tuple[DerivedPartProfileProjection, ...] = ()
    stash_features: tuple[DerivedPartFeatureProjection, ...] = ()
    active_part_repair: str | None = None
    selected_part_repair: str | None = None


@dataclass(frozen=True)
class DerivedPartSyncPlan:
    namespaces: tuple[DerivedPartNamespaceProjection, ...] = ()
    remove_part_keys: tuple[str, ...] = ()
    add_parts: tuple[DerivedPartProfileProjection, ...] = ()
    stash_profiles: tuple[DerivedPartProfileProjection, ...] = ()
    stash_features: tuple[DerivedPartFeatureProjection, ...] = ()
    active_part_repair: str | None = None
    selected_part_repair: str | None = None


def _unique_keys(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


def build_derived_part_sync_plan(
    request: DerivedPartProjectionRequest,
) -> DerivedPartSyncPlan:
    """Return a deterministic immutable plan without touching workspace state."""
    if not isinstance(request, DerivedPartProjectionRequest):
        raise TypeError("request must be DerivedPartProjectionRequest")
    return DerivedPartSyncPlan(
        namespaces=tuple(request.namespaces),
        remove_part_keys=_unique_keys(request.remove_part_keys),
        add_parts=tuple(request.add_parts),
        stash_profiles=tuple(request.stash_profiles),
        stash_features=tuple(request.stash_features),
        active_part_repair=request.active_part_repair,
        selected_part_repair=request.selected_part_repair,
    )


def profile_projection(
    part_key: str,
    profiles: Mapping[str, Iterable[Any]],
) -> DerivedPartProfileProjection:
    """Freeze already-derived authoritative profiles; no geometry is calculated here."""
    frozen = _freeze(dict(profiles or {}))
    if not isinstance(frozen, FrozenMappingValue):
        raise TypeError("profile projection must freeze to a mapping")
    return DerivedPartProfileProjection(str(part_key), frozen)


def feature_projection(
    part_key: str,
    features: Iterable[Any],
) -> DerivedPartFeatureProjection:
    """Freeze already-derived authoritative features; no geometry is calculated here."""
    frozen = _freeze(tuple(features or ()))
    if not isinstance(frozen, FrozenSequenceValue):
        raise TypeError("feature projection must freeze to a sequence")
    return DerivedPartFeatureProjection(str(part_key), frozen)


def namespace_projection(
    namespace: str,
    part_profiles: Mapping[str, Mapping[str, Iterable[Any]]],
) -> DerivedPartNamespaceProjection:
    """Freeze a namespace replacement while preserving caller-provided order."""
    return DerivedPartNamespaceProjection(
        namespace=str(namespace),
        parts=tuple(
            profile_projection(key, profiles)
            for key, profiles in dict(part_profiles or {}).items()
        ),
    )


def materialize_profiles(
    projection: DerivedPartProfileProjection,
) -> dict[str, list[Any]]:
    """Return a detached mutable copy for the existing workspace mutation API."""
    value = _thaw(projection.profiles)
    if not isinstance(value, dict):
        raise TypeError("profile projection did not materialize to a mapping")
    return value


def materialize_features(
    projection: DerivedPartFeatureProjection,
) -> list[Any]:
    """Return a detached mutable copy for the existing workspace mutation API."""
    value = _thaw(projection.features)
    if not isinstance(value, list):
        raise TypeError("feature projection did not materialize to a sequence")
    return value


def materialize_namespace(
    projection: DerivedPartNamespaceProjection,
) -> dict[str, dict[str, list[Any]]]:
    """Materialize one namespace only at the workspace mutation boundary."""
    return {
        item.part_key: materialize_profiles(item)
        for item in projection.parts
    }
