# -*- coding: utf-8 -*-
"""Compatibility facade: Quantity manufacturing calculations belong to Engine.

GUI still routes the already-established Phase6 resolution callback.  Source,
version projection, PartSpec replay and physical demand/BOM rules are Engine API.
"""
from ae_engine import manufacturing_api

QuantityManufacturingBatch = manufacturing_api.QuantityManufacturingBatch
quantity_manufacturing_groups = manufacturing_api.quantity_manufacturing_groups
quantity_nfb_checked_manufacturing_groups = manufacturing_api.quantity_nfb_checked_manufacturing_groups


def build_quantity_manufacturing_requests(base_request, workspace_snapshot):
    """Legacy GUI route to the common public Engine request builder."""
    return manufacturing_api.build_operator_quantity_manufacturing_requests(
        base_request, workspace_snapshot,
    )


def resolve_quantity_manufacturing(base_request, workspace_snapshot):
    """Legacy GUI route to the common public Engine quantity resolver."""
    import phase6_manufacturing_service as service
    return manufacturing_api.resolve_operator_quantity_manufacturing_batch(
        base_request, workspace_snapshot, resolve_request=service.resolve,
        request_builder=build_quantity_manufacturing_requests,
    )
