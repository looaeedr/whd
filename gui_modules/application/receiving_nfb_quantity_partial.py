"""Compatibility import only; all quantity NFB manufacturing lives in ae_engine.

New GUI and external Engine clients must call ae_engine.manufacturing_api.
No source verification, physical selection, or manufacturing rules live here.
"""
from ae_engine.receiving_nfb_quantity_partial import *  # noqa: F401,F403
from ae_engine.receiving_nfb_quantity_partial import _independent
