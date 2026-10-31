# -*- coding: utf-8 -*-
"""Phase6 compatibility exports; Engine owns quantity-version state and rules."""
from ae_engine.manufacturing_api import (
    SCHEMA, SCHEMA_V2, SCHEMA_V3, QUANTITY_MODE, SET_BAY_MODE,
    QuantityModel, positive_piece_count, quantity_inherited_nfb_brand_conflicts,
    normalize_quantity_snapshot, quantity_only_change,
)
