"""Receiving Base Plate Settings transaction with explicit state ownership.

A settings action may validate and update the existing physical Base Plate
selection only.  No GUI application object, new manufactured part, or
illustrative DXF world-coordinate mapping is accepted here.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from ae_engine import manufacturing_api


def commit_receiving_base_plate_settings(
    *, input_snapshot: dict, settings_values: Mapping,
    submit_geometry_update, config: Mapping | None,
):
    """Validate actual structural geometry then atomically commit one selection."""
    config = manufacturing_api.validate_receiving_base_plate_settings(
        input_snapshot=input_snapshot, settings_values=settings_values,
        config=config,
    )

    existed = "receiving_base_plate" in input_snapshot
    previous = deepcopy(input_snapshot.get("receiving_base_plate"))
    try:
        if config is None:
            input_snapshot.pop("receiving_base_plate", None)
        else:
            input_snapshot["receiving_base_plate"] = deepcopy(dict(config))
        submit_geometry_update()
    except Exception:
        if existed:
            input_snapshot["receiving_base_plate"] = previous
        else:
            input_snapshot.pop("receiving_base_plate", None)
        raise
    return deepcopy(input_snapshot.get("receiving_base_plate"))
