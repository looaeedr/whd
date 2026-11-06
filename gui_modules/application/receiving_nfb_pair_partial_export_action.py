# -*- coding: utf-8 -*-
"""Receiving NFB operator compatibility aliases to the public WHD Engine API.

No physical part eligibility, source validation, CSV geometry, CHECK/Q,
DXF serialization, or manufacturing decision is owned by this GUI module.
"""
from ae_engine.manufacturing_api import (
    NfbPairedPartOnlyDxf,
    NfbCsvVerifiedPhysicalSite, NfbCsvVerifiedExportScope,
    export_verified_receiving_nfb_door_base_pair,
    NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
    export_current_csv_nfb_door_base_pair,
)
# Legacy private readback name is an alias of the already-public Engine scope API.
# The two-tier manufacturing entry is internal to the Engine public pair operation.
from ae_engine.manufacturing_api import (
    resolve_verified_csv_v5_export_scope as _verified_csv_v5_export_scope,
)
