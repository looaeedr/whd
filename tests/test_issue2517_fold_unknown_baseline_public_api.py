"""#2517: Fold Designer uses Engine-only custom/legacy baseline identity."""
from copy import deepcopy
from inspect import getsource
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.corner_type_ui import CUSTOM_MODEL_NAME, is_unknown_model
import fold_designer_bridge as bridge


def test_root_and_facade_expose_one_public_model_identity_and_default():
    assert ae_engine.is_unknown_operator_model is api.is_unknown_operator_model
    assert ae_engine.operator_default_custom_model_name == CUSTOM_MODEL_NAME
    assert api.operator_default_custom_model_name == CUSTOM_MODEL_NAME
    assert "operator_default_custom_model_name" in ae_engine.__all__
    for name in ("自訂", "未知類型", "金庫型", "受電箱", "其他基準", "", " 未知類型 "):
        assert api.is_unknown_operator_model(name) is is_unknown_model(name)


@pytest.mark.parametrize(
    "model, explicit, expected",
    (
        ("自訂", "", True),
        ("未知類型", None, True),
        ("  未知類型 ", "custom-v2", True),
        ("custom-v2", "custom-v2", True),
        (" custom-v2 ", " custom-v2 ", True),
        ("custom-v2", "", False),
        ("custom-v2", None, False),
        ("金庫型", "custom-v2", False),
        ("受電箱", "custom-v2", False),
        ("", "", False),
        ("", None, False),
        ("金庫型", "金庫型", True),
    ),
)
def test_explicit_saved_custom_baseline_matches_previous_gui_contract(
    model, explicit, expected,
):
    # Explicit saved project label remains an exact post-strip alias; unlike
    # known custom names it does not classify any other registered Family.
    assert api.is_unknown_operator_model(
        model, explicit_unknown_value=explicit,
    ) is expected
    host = SimpleNamespace(_baseline_unknown_value=explicit)
    before = deepcopy(vars(host))
    assert bridge._phase6_is_unknown_baseline(host, model) is expected
    assert vars(host) == before


def test_fold_designer_does_not_reconstruct_model_identity(monkeypatch):
    calls = []

    def engine_model_owner(model, *, explicit_unknown_value=None):
        calls.append((model, explicit_unknown_value))
        return True

    monkeypatch.setattr(api, "is_unknown_operator_model", engine_model_owner)
    host = SimpleNamespace(_baseline_unknown_value="saved-custom")
    assert bridge._phase6_is_unknown_baseline(host, "unregistered") is True
    assert calls == [("unregistered", "saved-custom")]
    body = getsource(bridge._phase6_is_unknown_baseline)
    assert "manufacturing_api.is_unknown_operator_model(" in body
    assert "LEGACY_CUSTOM_MODEL_NAMES" not in body
    assert "CUSTOM_MODEL_NAME" not in body


def test_fold_designer_default_label_uses_public_engine_value():
    init = getsource(bridge._phase6_prepare_predecessor_init)
    assert "manufacturing_api.operator_default_custom_model_name" in init
    assert "CUSTOM_MODEL_NAME" not in init
    bridge_source = getsource(bridge)
    assert "from ae_engine.corner_type_ui import" not in bridge_source
