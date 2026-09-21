"""Pure immutable planning seam for topology-derived physical-part synchronization.

This module deliberately owns no workspace/navigation mutation and no manufacturing
geometry formulas.  Callers derive authoritative profiles/features through their
existing domain owners, freeze those projections into a request, and receive a
stable plan describing the workspace intent to apply elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class DerivedPartProfileProjection:
    part_key: str
    profiles: tuple[Any, ...] = ()


@dataclass(frozen=True)
class DerivedPartFeatureProjection:
    part_key: str
    features: tuple[Any, ...] = ()


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


def profile_projection(part_key: str, profiles: Iterable[Any]) -> DerivedPartProfileProjection:
    """Freeze already-derived authoritative profiles; no geometry is calculated here."""
    return DerivedPartProfileProjection(str(part_key), tuple(profiles))


def feature_projection(part_key: str, features: Iterable[Any]) -> DerivedPartFeatureProjection:
    """Freeze already-derived authoritative features; no geometry is calculated here."""
    return DerivedPartFeatureProjection(str(part_key), tuple(features))


def namespace_projection(
    namespace: str,
    part_profiles: Mapping[str, Iterable[Any]],
) -> DerivedPartNamespaceProjection:
    """Freeze a namespace replacement while preserving caller-provided order."""
    return DerivedPartNamespaceProjection(
        namespace=str(namespace),
        parts=tuple(profile_projection(key, value) for key, value in part_profiles.items()),
    )
