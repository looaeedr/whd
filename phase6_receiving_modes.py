"""Compatibility-only aliases for Engine-owned Receiving modes and sessions.

The GUI may select a mode, confirm dimensions and render the result, but never
builds Door/Set/Bay/NFB physical source or manages manufacture-specific IDs.
"""
from ae_engine.manufacturing_api import (
    ReceivingModeSession, fresh_receiving_mode,
    QuantityModel, QUANTITY_MODE, SET_BAY_MODE,
)
from ae_engine.cabinet_types import receiving
from ae_engine.receiving_quantity_box import BOX_KEY, positive_dimension, project_common_box
