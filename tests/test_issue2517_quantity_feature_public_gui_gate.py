"""#2517 Quantity source validation is owned by public manufacturing_api."""
from inspect import getsource
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import fold_designer_composition_receiving as receiving


def test_common_quantity_preview_calls_public_engine_before_cache(monkeypatch):
    snapshot = {"active_mode": "quantity", "model": "受電箱"}
    seen = []

    monkeypatch.setattr(
        receiving, "_current_mode_snapshot",
        lambda self, namespace: snapshot,
    )

    def reject(value):
        seen.append(value)
        raise ValueError("ENGINE_QUANTITY_FEATURE_REJECTED")

    monkeypatch.setattr(
        manufacturing_api, "require_valid_operator_quantity_features", reject,
    )
    app = SimpleNamespace(_phase6_input_snapshot=snapshot)
    with pytest.raises(ValueError, match="ENGINE_QUANTITY_FEATURE_REJECTED"):
        receiving._common_preview_request(SimpleNamespace(app=app), None)
    assert seen == [snapshot]


def test_single_quantity_size_commit_uses_public_feature_gate():
    # The callback is nested inside the real Assembly dialog; assert its
    # source boundary rather than replacing Tk/QuantityModel with a fake model.
    source = getsource(receiving.open_receiving_multi_settings)
    assert "manufacturing_api.require_valid_operator_quantity_features(candidate)" in source
    assert "require_valid_quantity_features(candidate)" not in source
    assert "update_common_box(snapshot, " in source
    assert "_apply_mode_snapshot(self, namespace, candidate)" in source


def test_no_private_quantity_feature_validator_remains_in_receiving_gui():
    source = getsource(receiving)
    assert "from ae_engine.receiving_quantity_box import require_valid_quantity_features" not in source
    assert "update_common_box, require_valid_quantity_features" not in source
    assert "manufacturing_api.require_valid_operator_quantity_features(" in source
