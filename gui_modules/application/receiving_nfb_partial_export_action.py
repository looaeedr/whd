# -*- coding: utf-8 -*-
"""Receiving GUI operator entry; all physical NFB inner-door DXF belongs to Engine.

Existing public symbols are stable compatibility aliases only. No source
identity, hole placement or partial manufacturing decision remains in GUI.
"""
from ae_engine.manufacturing_api import (
    nfb_verification_geometry_changed,
    export_verified_receiving_nfb_inner_door,
)
