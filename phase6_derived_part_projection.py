"""Compatibility mirror for Engine-owned immutable physical part sync plans.

All types, namespace repair and stash decisions are canonical ae_engine API.
GUI retains only historical names for old callers and test contracts.
"""
import ae_engine as _engine

FrozenMappingValue = _engine.FrozenMappingValue
FrozenSequenceValue = _engine.FrozenSequenceValue
DerivedPartProfileProjection = _engine.DerivedPartProfileProjection
DerivedPartFeatureProjection = _engine.DerivedPartFeatureProjection
DerivedPartNamespaceProjection = _engine.DerivedPartNamespaceProjection
DerivedPartProjectionRequest = _engine.DerivedPartProjectionRequest
DerivedPartRequestAssemblyInput = _engine.DerivedPartRequestAssemblyInput
DerivedPartSyncPlan = _engine.DerivedPartSyncPlan
build_derived_part_projection_request = _engine.build_derived_part_projection_request
build_derived_part_sync_plan = _engine.build_derived_part_sync_plan
profile_projection = _engine.profile_projection
feature_projection = _engine.feature_projection
namespace_projection = _engine.namespace_projection
materialize_profiles = _engine.materialize_profiles
materialize_features = _engine.materialize_features
materialize_namespace = _engine.materialize_namespace
_freeze = _engine._freeze
_thaw = _engine._thaw
_unique_keys = _engine._unique_keys

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
