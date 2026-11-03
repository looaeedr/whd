# -*- coding: utf-8 -*-
"""Phase6 compatibility aliases for canonical Engine physical Workspace state.

Main/Designer remain independent lifecycle and presentation owners; physical
presence, active identity, CustomPart provenance and profile stash do not.
"""
from ae_engine.manufacturing_api import (
    MANDATORY_PART, PART_ORDER, ACTIVE_REPAIR_POLICIES,
    normalize_existing_parts, repair_workspace_active_part as _repair_active,
    SharedWorkspaceState,
)
