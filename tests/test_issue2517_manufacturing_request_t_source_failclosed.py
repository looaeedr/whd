"""#2517 manufacturing request never invents 2 mm physical plate thickness."""
from copy import deepcopy
import inspect

import pytest

from phase6_manufacturing_adapter import build_manufacturing_request
from tests.test_issue356_manufacturing_adapter import _fake_app


@pytest.mark.parametrize("raw", [None, True, False, "invalid", "", "nan", "inf", "-2", 0, -2])
def test_explicit_invalid_snapshot_t_is_rejected_without_falling_back(raw):
    app = _fake_app()
    app._phase6_input_snapshot["t"] = raw
    before = deepcopy(app._phase6_input_snapshot)
    with pytest.raises(ValueError, match="包外尺寸"):
        build_manufacturing_request(app)
    assert app._phase6_input_snapshot == before


@pytest.mark.parametrize("raw", [None, True, "invalid", "", "nan", "inf", 0, -2])
def test_invalid_settings_t_never_downgrades_to_2mm(raw):
    app = _fake_app()
    app._phase6_input_snapshot.pop("t")
    app._settings_values["t"] = raw
    before = deepcopy(app._phase6_input_snapshot)
    with pytest.raises(ValueError, match="包外尺寸"):
        build_manufacturing_request(app)
    assert app._phase6_input_snapshot == before


def test_missing_both_physical_t_sources_is_rejected():
    app = _fake_app()
    app._phase6_input_snapshot.pop("t")
    app._settings_values.pop("t")
    with pytest.raises(ValueError, match="包外尺寸"):
        build_manufacturing_request(app)


@pytest.mark.parametrize("raw", ["1.25", 2.5, 3])
def test_valid_sparse_snapshot_uses_exact_settings_t(raw):
    app = _fake_app()
    app._phase6_input_snapshot.pop("t")
    app._settings_values["t"] = raw
    request = build_manufacturing_request(app)
    assert request.input_snapshot["t"] == float(raw)
    assert "t" not in app._phase6_input_snapshot


def test_valid_authoritative_snapshot_t_overrides_stale_settings_t():
    app = _fake_app()
    app._phase6_input_snapshot["t"] = 2.35
    app._settings_values["t"] = "invalid stale cache"
    result = build_manufacturing_request(app)
    assert result.input_snapshot["t"] == 2.35
    assert app._settings_values["t"] == "invalid stale cache"


def test_adapter_uses_existing_engine_validator_without_gui_default():
    src = inspect.getsource(build_manufacturing_request)
    assert 'manufacturing_api.normalize_operator_source_dimension(' in src
    assert 'raw_t, field="t"' in src
    assert "snapshot.setdefault(\"t\", _num(" not in src
    assert 'snapshot.get("t", 2.0)' not in src
