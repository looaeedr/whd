# -*- coding: utf-8 -*-
"""Phase6 compatibility: BoxBody structure is owned by Engine public API.

This module must never access Engine private state modules or manufacture a
second Family policy. Existing imports retain identical classes and callables.
"""
from ae_engine.manufacturing_api import (
    BoxBodyStructureType, BackPanelMode, DEFAULT_STRUCTURE_TYPE,
    _default_join_settings, default_box_body_structure_state, _structure_type,
    legacy_box_body_structure_locked, _structure_locked_bool, normalize_box_body_structure_state,
    set_active_structure, activate_structure_with_defaults, set_structure_locked,
    _back_panel_mode, back_panel_mode, set_side_back_back_panel_mode,
    update_structure_config, _finite_dimension, _manual_integer,
    resolve_two_piece_widths, set_two_piece_width, reconcile_box_body_structure_for_total_w_change,
    set_join_seam_bend, resolve_three_piece_widths, set_three_piece_width,
    set_side_back_piece_profile, side_rear_bend_dimension_space, side_rear_bend_material_length,
    side_rear_bend_outside_length, set_side_back_geometry,
)
