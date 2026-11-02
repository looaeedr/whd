# -*- coding: utf-8 -*-
"""#2517: EndCap 3D-fallback permission cannot use Python's string truthiness."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api


@pytest.mark.parametrize("raw,wanted", [
    (None, False), ("", False), ("   ", False),
    (False, False), (0, False), (0.0, False),
    ("false", False), ("FALSE", False), (" 0 ", False),
    (True, True), (1, True), (1.0, True), ("true", True),
    (" TRUE ", True), ("1", True),
])
def test_gui_and_headless_request_share_same_fallback_permission(raw, wanted):
    assert api.normalize_operator_3d_fallback_flag(raw) is wanted
    request = api.ManufacturingResolveRequest(allow_3d_fallback=raw)
    assert request.allow_3d_fallback is wanted


@pytest.mark.parametrize("invalid", ["yes", "on", "off", "no", "disabled", 2, -1,
    0.2, float("nan"), float("inf"), 10 ** 400, {}, []])
def test_nonboolean_or_ambiguous_operator_input_fails_closed(invalid):
    with pytest.raises(ValueError, match="MANUFACTURING_3D_FALLBACK_FLAG_INVALID"):
        api.normalize_operator_3d_fallback_flag(invalid)
    with pytest.raises(ValueError, match="MANUFACTURING_3D_FALLBACK_FLAG_INVALID"):
        api.ManufacturingResolveRequest(allow_3d_fallback=invalid)


def test_fallback_flag_fingerprint_has_canonical_identity():
    a = api.ManufacturingResolveRequest(allow_3d_fallback="false")
    b = api.ManufacturingResolveRequest(allow_3d_fallback=False)
    c = api.ManufacturingResolveRequest(allow_3d_fallback="true")
    assert api.manufacturing_request_fingerprint(a) == api.manufacturing_request_fingerprint(b)
    assert api.manufacturing_request_fingerprint(a) != api.manufacturing_request_fingerprint(c)


def test_gui_no_longer_treats_nonempty_false_string_as_true():
    src = (Path(__file__).resolve().parents[1]
           / "phase6_manufacturing_adapter.py").read_text(encoding="utf-8")
    assert "manufacturing_api.normalize_operator_3d_fallback_flag(" in src
    assert 'allow_3d_fallback=bool(' not in src
