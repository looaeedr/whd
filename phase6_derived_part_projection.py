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
class DerivedPartRequestAssemblyInput:
    """Already-derived projections plus workspace identity needed to assemble intent."""

    door_part_keys: tuple[str, ...]
    door_profiles: Mapping[str, Mapping[str, Iterable[Any]]]
    base_plate_profiles: Mapping[str, Mapping[str, Iterable[Any]]]
    divider_profiles: Mapping[str, Mapping[str, Iterable[Any]]]
    inner_profiles: Mapping[str, Mapping[str, Iterable[Any]]]
    box_piece_profiles: Mapping[str, Mapping[str, Iterable[Any]]]
    current_piece_keys: tuple[str, ...]
    source_parts: tuple[str, ...]
    available_parts: tuple[str, ...]
    source_part_features: Mapping[str, Iterable[Any]]
    known_feature_keys: tuple[str, ...]
    single_door_profiles: Mapping[str, Iterable[Any]] | None
    single_base_plate_profiles: Mapping[str, Iterable[Any]] | None
    active_part: str | None
    selected_part: str | None


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


def build_derived_part_projection_request(
    data: DerivedPartRequestAssemblyInput,
) -> DerivedPartProjectionRequest:
    """Assemble immutable workspace intent from already-derived projections.

    Domain derivation stays with the caller/current domain owners.  This owner
    only decides namespace replacement, add/remove/stash intent, and legacy
    active/selected identity repair before the navigation owner applies a plan.
    """
    if not isinstance(data, DerivedPartRequestAssemblyInput):
        raise TypeError("data must be DerivedPartRequestAssemblyInput")

    door_keys = tuple(str(key) for key in data.door_part_keys)
    available = set(str(key) for key in data.available_parts)
    source_parts = set(str(key) for key in data.source_parts)
    known_features = set(str(key) for key in data.known_feature_keys)
    current_piece_keys = set(str(key) for key in data.current_piece_keys)

    remove_part_keys: list[str] = []
    add_parts: list[DerivedPartProfileProjection] = []
    stash_profiles: list[DerivedPartProfileProjection] = []
    stash_features: list[DerivedPartFeatureProjection] = []

    if door_keys and "door" in available:
        remove_part_keys.append("door")
    for key in door_keys:
        if key not in known_features and key in data.source_part_features:
            stash_features.append(
                feature_projection(key, data.source_part_features[key])
            )
    if (
        not door_keys
        and "door" in source_parts
        and "door" not in available
        and data.single_door_profiles is not None
    ):
        add_parts.append(profile_projection("door", data.single_door_profiles))

    if door_keys and "base_plate" in available:
        remove_part_keys.append("base_plate")
    if (
        not door_keys
        and "base_plate" in source_parts
        and "base_plate" not in available
        and data.single_base_plate_profiles is not None
    ):
        add_parts.append(
            profile_projection("base_plate", data.single_base_plate_profiles)
        )

    desired_piece_keys = set(str(key) for key in data.box_piece_profiles)
    for key in sorted(current_piece_keys - desired_piece_keys):
        remove_part_keys.append(key)
    for key, profiles in data.box_piece_profiles.items():
        projection = profile_projection(key, profiles)
        if key in available:
            stash_profiles.append(projection)
        else:
            add_parts.append(projection)

    active_repair = None
    selected_repair = None
    if door_keys:
        first_door = door_keys[0]
        first_base = first_door.replace("door_", "base_plate_", 1)
        if data.active_part == "door":
            active_repair = first_door
        elif data.active_part == "base_plate":
            active_repair = first_base
        if data.selected_part == "door":
            selected_repair = first_door
        elif data.selected_part == "base_plate":
            selected_repair = first_base

    return DerivedPartProjectionRequest(
        namespaces=(
            namespace_projection("door_c", data.door_profiles),
            namespace_projection("base_plate_c", data.base_plate_profiles),
            namespace_projection("box_body:divider:", data.divider_profiles),
            namespace_projection("inner_door:", data.inner_profiles),
        ),
        remove_part_keys=tuple(remove_part_keys),
        add_parts=tuple(add_parts),
        stash_profiles=tuple(stash_profiles),
        stash_features=tuple(stash_features),
        active_part_repair=active_repair,
        selected_part_repair=selected_repair,
    )


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
