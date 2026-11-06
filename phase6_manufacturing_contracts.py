# -*- coding: utf-8 -*-
"""Phase6 compatibility exports: immutable manufacturing DTOs belong to Engine.

This module deliberately contains no manufacturing freeze/fingerprint algorithm
or duplicate DTO classes. Existing Python call sites use the exact Engine API
classes and functions; changing a client import is not a schema version gate.
"""
from ae_engine.manufacturing_api import (
    FrozenMapping,
    FrozenObjectMapping,
    ManufacturingPartInput,
    ManufacturingResolveRequest,
    ManufacturingDiagnosticsResult,
    ManufacturingMutationResult,
    ManufacturingEffects,
    ManufacturingCacheReceipt,
    ManufacturingResolveResult,
    canonical_manufacturing_json,
    freeze_manufacturing_value,
    manufacturing_fingerprint,
    manufacturing_request_fingerprint,
    thaw_manufacturing_value,
)

__all__ = [
    "FrozenMapping",
    "FrozenObjectMapping",
    "ManufacturingPartInput",
    "ManufacturingResolveRequest",
    "ManufacturingDiagnosticsResult",
    "ManufacturingMutationResult",
    "ManufacturingEffects",
    "ManufacturingCacheReceipt",
    "ManufacturingResolveResult",
    "canonical_manufacturing_json",
    "freeze_manufacturing_value",
    "manufacturing_fingerprint",
    "manufacturing_request_fingerprint",
    "thaw_manufacturing_value"
]
