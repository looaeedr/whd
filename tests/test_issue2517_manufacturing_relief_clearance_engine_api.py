# -*- coding: utf-8 -*-
"""#2517: GUI and headless manufacturing share Engine clearance validation."""
import inspect
from math import isfinite
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
import phase6_manufacturing_adapter as gui


@pytest.mark.parametrize("raw,expected", [
    (None, 0.0), ("", 0.0), ("  ", 0.0), ("0", 0.0),
    ("2.5", 2.5), (3.125, 3.125), (-2, 0.0), (" -3.5 ", 0.0),
])
def test_operator_and_direct_engine_requests_share_clearance_source(raw, expected):
    app = SimpleNamespace(assembly_relief_clearance_var=SimpleNamespace(get=lambda: raw))
    assert api.normalize_operator_relief_clearance(raw) == expected
    assert gui._relief_clearance(app) == expected
    request = api.ManufacturingResolveRequest(relief_clearance=raw)
    assert request.relief_clearance == expected
    assert isfinite(request.relief_clearance)


@pytest.mark.parametrize("bad", [
    True, False, "invalid", "NaN", "Infinity", float("nan"),
    float("inf"), -float("inf"), 10 ** 400,
])
def test_invalid_clearance_cannot_enter_manufacturing_semantic_fingerprint(bad):
    with pytest.raises(ValueError, match="MANUFACTURING_RELIEF_CLEARANCE_INVALID"):
        api.normalize_operator_relief_clearance(bad)
    with pytest.raises(ValueError, match="MANUFACTURING_RELIEF_CLEARANCE_INVALID"):
        api.ManufacturingResolveRequest(relief_clearance=bad)


def test_request_default_and_precision_remain_backward_compatible():
    assert api.ManufacturingResolveRequest().relief_clearance == 0.0
    val = 0.12345678901235
    assert api.ManufacturingResolveRequest(relief_clearance=val).relief_clearance == round(val, 12)


def test_gui_only_reads_tk_and_delegates_to_public_engine():
    src = inspect.getsource(gui._relief_clearance)
    assert "manufacturing_api.normalize_operator_relief_clearance(raw)" in src
    assert "max(" not in src
    assert "float(" not in src
