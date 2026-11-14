"""Receiving Base Plate Settings GUI entry: submit operator inputs to Engine.

The Engine owns the physical Base Plate validation, source commit and rollback.
This module adds no GUI manufacturing fallback or second selection rule.
"""
from __future__ import annotations

from collections.abc import Mapping

from ae_engine import manufacturing_api


def commit_receiving_base_plate_settings(
    *, input_snapshot: dict, settings_values: Mapping,
    submit_geometry_update, config: Mapping | None,
):
    """Forward the existing Settings button transaction to public Engine."""
    return manufacturing_api.commit_operator_receiving_base_plate_settings(
        input_snapshot=input_snapshot, settings_values=settings_values,
        config=config, submit_geometry_update=submit_geometry_update,
    )
