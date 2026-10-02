# -*- coding: utf-8 -*-
"""Replaceable AE manufacturing engine package."""
from .contracts import (
    ManufacturingPolicy, ManufacturingContext, DoorPartSpec, BoxBodyPartSpec,
    EndCapPartSpec, BasePlatePartSpec, IndicatorBoxPartSpec, PartExportResult, PartSpec,
)
from .manufacturing_api import (
    generate_part, resolve_policy, expected_baseline_path_for, door_finished_face_size,
    door_indicator_offset_for_finished_center, indicator_box_opening_feature,
    indicator_small_door_spec,
)
from .cabinet_types import (
    CabinetTypeRegistration, registered_cabinet_types, resolve_cabinet_type,
)
from .certified_relief_registry import (
    CertifiedReliefStatus, CertifiedReliefRule, CertifiedReliefResult,
    CertifiedCornerPolicyRule, CertifiedReliefRegistryError, CertifiedReliefRegistryAmbiguityError,
    registered_certified_relief_rules, registered_certified_corner_policy_rules,
    lookup_certified_endcap_relief, lookup_certified_corner_state, certified_corner_policy_for_part,
    certified_rule_revision_exists, build_relief_promotion_candidate,
)
from . import ae, manufacturing_api

__all__ = [
    "ae", "manufacturing_api", "generate_part", "resolve_policy",
    "expected_baseline_path_for", "door_finished_face_size",
    "door_indicator_offset_for_finished_center", "indicator_box_opening_feature",
    "indicator_small_door_spec", "ManufacturingPolicy", "ManufacturingContext",
    "DoorPartSpec", "BoxBodyPartSpec", "EndCapPartSpec", "BasePlatePartSpec",
    "IndicatorBoxPartSpec", "PartExportResult", "PartSpec",
    "CabinetTypeRegistration", "registered_cabinet_types", "resolve_cabinet_type",
    "CertifiedReliefStatus", "CertifiedReliefRule", "CertifiedReliefResult",
    "CertifiedCornerPolicyRule", "CertifiedReliefRegistryError", "CertifiedReliefRegistryAmbiguityError",
    "registered_certified_relief_rules", "registered_certified_corner_policy_rules",
    "lookup_certified_endcap_relief", "lookup_certified_corner_state", "certified_corner_policy_for_part",
    "certified_rule_revision_exists", "build_relief_promotion_candidate",
]
