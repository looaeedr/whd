# -*- coding: utf-8 -*-
"""Legacy GUI entry; physical quantity/NFB rules exist only in public Engine API."""
from ae_engine.manufacturing_api import (
    QuantityNfbPartialSelection, verify_quantity_nfb_inner_door,
    select_quantity_nfb_partial, quantity_partial_live_manifests,
)
