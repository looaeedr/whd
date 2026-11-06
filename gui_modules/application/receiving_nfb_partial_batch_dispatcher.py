# -*- coding: utf-8 -*-
"""Legacy Receiving GUI port: all NFB partial manufacture/export belongs to Engine.

The original names remain callable for existing controls and Python clients.
No product eligibility, identity, count, DXF or file-publication rule lives here.
"""
# Legacy external tests monkeypatch batch.os.link; this aliases the same os
# module used by the Engine publisher without owning any export behavior.
import os

from ae_engine.manufacturing_api import (
    require_highlighted_nfb_inner_doors,
    export_highlighted_nfb_inner_doors,
)
