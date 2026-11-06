"""#2517 Receiving legacy initial W/H/D must consume the public Engine API."""
from __future__ import annotations

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import receiving_mode_controls


@pytest.mark.parametrize("mode", ["set_bay", "quantity"])
def test_receiving_initial_dimensions_match_canonical_engine_family(mode):
    engine_values = manufacturing_api.receiving_default_box_dimensions()
    assert engine_values == {"w": 800, "h": 1600, "d": 350}
    from_gui = receiving_mode_controls.ask_initial_dimensions(None, mode)
    assert from_gui == engine_values
    from_gui["w"] = 999
    assert receiving_mode_controls.ask_initial_dimensions(None, mode) == engine_values


def test_legacy_gui_only_delegates_default_dimensions_to_public_engine(monkeypatch):
    requests = []

    def fake_defaults():
        requests.append("public")
        return {"w": 901, "h": 1701, "d": 401}

    monkeypatch.setattr(manufacturing_api, "receiving_default_box_dimensions", fake_defaults)
    assert receiving_mode_controls.ask_initial_dimensions(None, "set_bay") == {
        "w": 901, "h": 1701, "d": 401,
    }
    assert requests == ["public"]


@pytest.mark.parametrize("invalid", ["", "other", None, False, 1])
def test_invalid_mode_rejected_before_engine_default_lookup(monkeypatch, invalid):
    def should_not_call():
        raise AssertionError("invalid GUI choice reached Engine")

    monkeypatch.setattr(manufacturing_api, "receiving_default_box_dimensions", should_not_call)
    with pytest.raises(ValueError, match="不合法的受電箱操作模式"):
        receiving_mode_controls.ask_initial_dimensions(None, invalid)
