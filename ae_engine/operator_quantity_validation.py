# -*- coding: utf-8 -*-
"""Source-only immutable operator Quantity context verification for manufacturing.

Engine owns the live version Feature validation before request build or cache
reuse; GUI supplies snapshots and never decides DXF feature legality.
"""
from __future__ import annotations

from collections.abc import Mapping

from .receiving_quantity_box import require_valid_quantity_features


def validate_operator_manufacturing_quantity_context(
    input_snapshot, live_workspace_snapshot=None,
):
    """Validate current Quantity version using only canonical live owner fields.

    Keep non-Quantity modes a no-op. The actual finished-face hole/boundary
    checks, plus original Traditional Chinese fail-closed error, remain in
    require_valid_quantity_features and are never reproduced here.
    """
    if not isinstance(input_snapshot, Mapping) or input_snapshot.get("active_mode") != "quantity":
        return None
    live = live_workspace_snapshot if isinstance(live_workspace_snapshot, Mapping) else {}
    source = {
        **input_snapshot,
        **{key: live[key] for key in ("quantity", "receiving_quantity_box") if key in live},
    }
    return require_valid_quantity_features(source)
