# -*- coding: utf-8 -*-
"""Legacy Phase6 service entry: UI request in, canonical Engine result out.

No geometry construction, Family/Joint relief rule, 3D projection, or FinalScene
manufacturing calculation lives here; Engine owns the only resolver.
"""
from ae_engine import manufacturing_api
from ae_engine.manufacturing_api import (
    ManufacturingResolveRequest, ManufacturingResolveResult,
)


def resolve(request):
    """Backward-compatible direct client of the Engine manufacturing API."""
    if not isinstance(request, ManufacturingResolveRequest):
        raise TypeError("request must be ManufacturingResolveRequest")
    result = manufacturing_api.resolve_manufacturing_request(request)
    if not isinstance(result, ManufacturingResolveResult):
        raise TypeError("Engine must return ManufacturingResolveResult")
    return result


__all__ = ["resolve"]
