# -*- coding: utf-8 -*-
"""#2517 both Quantity GUI request/cache gates consume the same real Engine API."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine import operator_quantity_validation as policy


def test_non_quantity_mode_does_not_call_quantity_solver(monkeypatch):
    called = []
    monkeypatch.setattr(policy, "require_valid_quantity_features", lambda _: called.append(True))
    for snapshot in (None, {}, {"active_mode": "set_bay"}, {"active_mode": "single"}):
        assert manufacturing_api.validate_operator_manufacturing_quantity_context(
            snapshot, {"quantity": object()},
        ) is None
    assert called == []


def test_headless_live_quantity_overrides_only_canonical_workspace_fields(monkeypatch):
    captured = []
    monkeypatch.setattr(policy, "require_valid_quantity_features",
                        lambda source: captured.append(source.copy()))
    snapshot = {
        "active_mode": "quantity", "model": "金庫型", "w": 800, "t": 2,
        "quantity": {"old": True}, "receiving_quantity_box": {"old": True},
        "keep": 17,
    }
    live = {"quantity": {"new": True}, "receiving_quantity_box": {"new": True},
            "w": 999, "extra": "ignored"}
    before = deepcopy((snapshot, live))
    manufacturing_api.validate_operator_manufacturing_quantity_context(snapshot, live)
    assert captured == [{
        **snapshot, "quantity": {"new": True},
        "receiving_quantity_box": {"new": True},
    }]
    assert captured[0]["w"] == 800
    assert (snapshot, live) == before


def test_real_out_of_bounds_quantity_feature_still_blocks_dxf():
    from ae_engine.receiving_quantity_versions import QuantityModel
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    model = QuantityModel(head_features=[
        CircleFeature(8, FeatureAnchor.PANEL_CENTER, Vec2(9000, 0))
    ])
    snapshot = {
        "model": "金庫型", "active_mode": "quantity",
        "w": 400, "d": 250, "t": 2,
        "quantity": model.snapshot(),
    }
    with pytest.raises(ValueError, match="不能輸出 DXF"):
        manufacturing_api.validate_operator_manufacturing_quantity_context(snapshot)


def test_gui_request_and_cache_require_one_public_engine_gate():
    from pathlib import Path
    source = Path("phase6_manufacturing_adapter.py").read_text(encoding="utf-8")
    assert source.count("manufacturing_api.validate_operator_manufacturing_quantity_context(") == 2
    assert "from ae_engine.receiving_quantity_box import" not in source
    assert "require_valid_quantity_features(" not in source
