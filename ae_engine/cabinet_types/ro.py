# -*- coding: utf-8 -*-
"""RO / 落地盤 cabinet-family extension point.

The family name is registered now so callers have a stable dispatch contract.
Confirmed RO part/policy rules will be implemented here later; Phase 5 does not
invent cabinet geometry.
"""
from .registry import CabinetTypeRegistration

REGISTRATION = CabinetTypeRegistration(
    canonical_name="RO",
    aliases=("落地盤",),
    module_name=__name__,
    implemented=False,
)
