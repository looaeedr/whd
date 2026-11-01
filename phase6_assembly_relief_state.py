"""Legacy Phase6 import facade for persisted relief state.

No second manufacturing-state validation, registry revision check or geometry
serialization lives here.  All names are identical Engine public API objects.
Existing Python imports and stored project JSON remain backward compatible.
"""
from __future__ import annotations

from ae_engine.manufacturing_api import (
    RELIEF_CONTRACT_VERSION,
    relief_profile_fingerprint,
    structure_fingerprint,
    build_current_source_signature,
    source_matches_current,
    committed_relief_cuts,
    build_persisted_relief_state,
)

__all__ = ["RELIEF_CONTRACT_VERSION","relief_profile_fingerprint","structure_fingerprint","build_current_source_signature","source_matches_current","committed_relief_cuts","build_persisted_relief_state"]
