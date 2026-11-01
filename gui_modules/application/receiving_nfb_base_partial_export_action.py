# -*- coding: utf-8 -*-
"""Existing Receiving GUI base-plate operator port; physical DXF belongs to Engine.

Only import/export compatibility remains. No manufacture or verification logic.
"""
from ae_engine.manufacturing_api import (
    prepare_verified_receiving_nfb_base_plate,
    export_verified_receiving_nfb_base_plate,
)
