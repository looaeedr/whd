# -*- coding: utf-8 -*-
"""Legacy Phase6 import seam for Engine-owned BoxBody structure state.

All enums, persistence, Family split calculations, physical-bend and back-panel
manufacturing mode selection have exactly one owner in ae_engine.
"""
from ae_engine.box_body_structure_state import *  # noqa: F401,F403
from ae_engine.box_body_structure_state import (
    _default_join_settings, _structure_type, _structure_locked_bool,
    _back_panel_mode, _finite_dimension, _manual_integer,
)
