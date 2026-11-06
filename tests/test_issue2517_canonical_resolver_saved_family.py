# -*- coding: utf-8 -*-
"""#2517 immutable request Family ownership: saved state unless live override.

The test checks the existing single Engine Family resolver rather than adding
a manufacturing or preview fallback in the GUI or CADSplit adapter.
"""
import inspect

import pytest

from ae_engine.manufacturing_contracts import (
    ManufacturingResolveRequest, manufacturing_request_fingerprint,
)
from ae_engine.manufacturing_resolver import (
    _cabinet_family, resolve as resolve_manufacturing_request,
)


@pytest.mark.parametrize(
    ("snapshot", "live_model", "expected"),
    [
        ({"model": "受電箱"}, "", "受電箱"),
        ({"model": "RECEIVING"}, "", "受電箱"),
        ({"model": "receiving"}, "", "受電箱"),
        ({"cabinet_type": "receiving"}, "", "受電箱"),
        ({"model": "金庫型"}, "", "金庫型"),
        ({"model": "金庫型"}, "RECEIVING", "受電箱"),
        ({"model": "受電箱"}, "金庫型", "金庫型"),
        ({"model": "RO"}, "", "RO"),
        ({"model": "未註冊舊箱型"}, "", "未註冊舊箱型"),
        ({}, "", "金庫型"),
    ],
)
def test_immutable_manufacturing_request_uses_same_saved_live_family_precedence(
    snapshot, live_model, expected,
):
    request = ManufacturingResolveRequest(
        input_snapshot=snapshot,
        cabinet_model=live_model,
        canonical_part_keys=(),
    )
    original_fingerprint = manufacturing_request_fingerprint(request)
    assert _cabinet_family(request) == expected
    assert manufacturing_request_fingerprint(request) == original_fingerprint
    assert dict(request.input_snapshot) == snapshot


def test_real_resolver_routes_relief_and_receiving_marking_through_same_family():
    # The existing Engine-owned orchestration must consume the one canonical
    # Family answer at BOTH manufacturing decisions, never re-infer from a GUI.
    source = inspect.getsource(resolve_manufacturing_request)
    assert "cabinet_family=_cabinet_family(request)" in source
    assert 'if _cabinet_family(request) == "受電箱":' in source


def test_missing_scene_still_fails_without_mock_manufacturing_geometry():
    request = ManufacturingResolveRequest(
        input_snapshot={"model": "receiving"},
        canonical_part_keys=(),
    )
    with pytest.raises(ValueError, match="no parts available"):
        resolve_manufacturing_request(request)
