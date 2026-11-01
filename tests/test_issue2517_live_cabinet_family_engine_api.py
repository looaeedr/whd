"""#2517: live Cabinet Family resolution is Engine-owned for UI and 3D service."""
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api, resolve_live_cabinet_family
from phase6_manufacturing_geometry import _phase6_current_cabinet_family
from phase6_manufacturing_service import _cabinet_family


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_registered_family_uses_headless_engine_registry(model):
    assert resolve_live_cabinet_family({"model": model}) == model
    assert manufacturing_api.resolve_live_cabinet_family is resolve_live_cabinet_family


def test_unregistered_custom_and_empty_preserve_legacy_family_any_fallback():
    assert resolve_live_cabinet_family({"cabinet_type": "  CUSTOM_SOURCE_7 "}) == "CUSTOM_SOURCE_7"
    assert resolve_live_cabinet_family({}) == "金庫型"
    assert resolve_live_cabinet_family({"model": "  "}) == "金庫型"


def test_live_selector_overrides_snapshot_without_mutating_source():
    original = {"model": "金庫型", "cabinet_type": "other"}
    assert resolve_live_cabinet_family(original, " 受電箱 ") == "受電箱"
    assert original == {"model": "金庫型", "cabinet_type": "other"}
    assert resolve_live_cabinet_family(original, "  ") == "金庫型"


def test_phase6_gui_delegates_without_canonicalizing_or_selecting_model(monkeypatch):
    observed = []
    def fake(snapshot, live):
        observed.append((snapshot, live))
        return "ENGINE_FAMILY"
    monkeypatch.setattr(manufacturing_api, "resolve_live_cabinet_family", fake)
    app = SimpleNamespace(_phase6_input_snapshot={"model": "legacy"}, baseline_model_var=SimpleNamespace(get=lambda: "operator"))
    assert _phase6_current_cabinet_family(app) == "ENGINE_FAMILY"
    assert observed == [({"model": "legacy"}, "operator")]
    source = inspect.getsource(_phase6_current_cabinet_family)
    assert "resolve_cabinet_type" not in source
    assert "金庫型" not in source


def test_invalid_widget_getter_uses_saved_snapshot_not_hidden_gui_policy():
    def bad_get():
        raise RuntimeError("widget torn down")
    app = SimpleNamespace(_phase6_input_snapshot={"model": "受電箱"}, baseline_model_var=SimpleNamespace(get=bad_get))
    assert _phase6_current_cabinet_family(app) == "受電箱"


def test_phase6_manufacturing_service_uses_same_engine_family():
    for model in ("受電箱", "金庫型", "  UNREGISTERED ", ""):
        assert _cabinet_family(SimpleNamespace(cabinet_model=model)) == resolve_live_cabinet_family({"model": model})
    assert "resolve_cabinet_type" not in inspect.getsource(_cabinet_family)
