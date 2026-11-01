"""Compatibility imports: Engine owns derived physical part source/namespace plans.

The workspace controller remains the sole mutating owner. Historical callers
keep the same immutable classes and function objects; no second identity logic.
"""
from ae_engine.derived_part_projection import (
    FrozenMappingValue,
    FrozenSequenceValue,
    DerivedPartProfileProjection,
    DerivedPartFeatureProjection,
    DerivedPartNamespaceProjection,
    DerivedPartProjectionRequest,
    DerivedPartRequestAssemblyInput,
    DerivedPartSyncPlan,
    build_derived_part_projection_request,
    build_derived_part_sync_plan,
    profile_projection,
    feature_projection,
    namespace_projection,
    materialize_profiles,
    materialize_features,
    materialize_namespace,
    _freeze,
    _thaw,
    _unique_keys,
)

__all__ = [
    "FrozenMappingValue",
    "FrozenSequenceValue",
    "DerivedPartProfileProjection",
    "DerivedPartFeatureProjection",
    "DerivedPartNamespaceProjection",
    "DerivedPartProjectionRequest",
    "DerivedPartRequestAssemblyInput",
    "DerivedPartSyncPlan",
    "build_derived_part_projection_request",
    "build_derived_part_sync_plan",
    "profile_projection",
    "feature_projection",
    "namespace_projection",
    "materialize_profiles",
    "materialize_features",
    "materialize_namespace"
]
