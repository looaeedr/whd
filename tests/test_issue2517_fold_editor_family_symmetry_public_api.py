"""#2517 Fold GUI family symmetry capability is a public Engine query."""
from types import SimpleNamespace
import inspect
import pytest

from ae_engine import manufacturing_api
from ae_engine import box_body_symmetry_allowed as root_symmetry
from ae_engine.cabinet_types.policy import box_body_symmetry_allowed as family_symmetry
from phase6_bending_ui import _phase6_box_symmetry_allowed


@pytest.mark.parametrize("model,allowed", [("金庫型", True), ("受電箱", False)])
def test_public_family_symmetry_preserves_canonical_policy(model, allowed):
    assert manufacturing_api.box_body_symmetry_allowed is family_symmetry
    assert root_symmetry is family_symmetry
    assert manufacturing_api.box_body_symmetry_allowed(model) is allowed
    assert manufacturing_api.box_body_symmetry_allowed({"model": model}) is allowed


def test_gui_prefers_live_family_capability_over_stale_snapshot(monkeypatch):
    called = []
    def public_query(model):
        called.append(model)
        return model == "金庫型"
    monkeypatch.setattr(manufacturing_api, "box_body_symmetry_allowed", public_query)
    class Var:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value
    host = SimpleNamespace(_phase6_input_snapshot={"model": "金庫型"}, baseline_model_var=Var("受電箱"))
    assert _phase6_box_symmetry_allowed(host) is False
    assert called == ["受電箱"]
    host.baseline_model_var = Var("")
    assert _phase6_box_symmetry_allowed(host) is True
    assert called[-1] == "金庫型"


def test_gui_family_capability_only_delegates_without_private_policy_import():
    source = inspect.getsource(_phase6_box_symmetry_allowed)
    assert "manufacturing_api.box_body_symmetry_allowed(model)" in source
    assert "cabinet_family_policy" not in source
    import phase6_bending_ui as module
    full = inspect.getsource(module)
    assert "from ae_engine.cabinet_types import policy" not in full
