"""#2517 main GUI Settings source W/H/D/T/FW shares the public Engine contract."""
import configparser
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import operator_settings_transactions as owner
from phase6_settings_center import (
    SettingsService, apply_settings_to_ae, load_factory_defaults_from_ae,
    save_defaults_to_ini,
)


def _host(tmp_path):
    return SimpleNamespace(
        INI_PATH=tmp_path / "config.ini",
        config=configparser.ConfigParser(),
        W=800.0, H=1600.0, D=350.0, T=2.0, FW=25.0,
        DRAW_STOCK=False,
    )


@pytest.mark.parametrize("field,runtime_attr", [
    ("w", "W"), ("h", "H"), ("d", "D"), ("t", "T"), ("fw", "FW"),
])
@pytest.mark.parametrize("invalid", [
    True, False, 0, -3.25, "nan", "inf", "-inf", float("nan"),
])
def test_main_gui_rejects_bad_physical_mm_before_runtime_or_ini(
    field, runtime_attr, invalid, tmp_path,
):
    host = _host(tmp_path)
    service = SettingsService(host)
    before = service.snapshot().as_dict()
    old = getattr(host, runtime_attr)
    emitted = service.update({field: invalid})
    assert emitted.as_dict() == before
    assert getattr(host, runtime_attr) == old
    with pytest.raises(ValueError, match="包外尺寸"):
        apply_settings_to_ae(host, {field: invalid})
    with pytest.raises(ValueError, match="包外尺寸"):
        save_defaults_to_ini(host, {field: invalid}, keys=(field,), apply_runtime=False)
    assert not Path(host.INI_PATH).exists()


@pytest.mark.parametrize("field,runtime_attr", [
    ("w", "W"), ("h", "H"), ("d", "D"), ("t", "T"), ("fw", "FW"),
])
def test_main_gui_and_engine_accept_same_fractional_mm_source_and_ini(
    field, runtime_attr, tmp_path,
):
    host = _host(tmp_path)
    service = SettingsService(host)
    raw = "125.625"
    validated = api.normalize_operator_source_dimension(raw, field=field)
    asserted = service.update({field: raw})
    assert asserted[field] == getattr(host, runtime_attr) == validated
    service.persist_defaults(keys=(field,))
    parser = configparser.ConfigParser()
    parser.read(host.INI_PATH, encoding="utf-8")
    assert parser.getfloat("DEFAULT_SIZES", field.upper()) == validated


@pytest.mark.parametrize("raw,accepted", [
    ("false", False), ("OFF", False), ("no", False), ("true", True),
    ("on", True), ("1", True), (0, False), (1, True),
])
def test_main_gui_boolean_source_matches_engine(raw, accepted, tmp_path):
    host = _host(tmp_path)
    service = SettingsService(host)
    assert service.update({"draw_stock": raw})["draw_stock"] is accepted
    assert host.DRAW_STOCK is accepted
    assert api.normalize_operator_settings_boolean(raw) is accepted


@pytest.mark.parametrize("bad", ["maybe", "2", 2, -1, 1.5, None, float("nan")])
def test_invalid_gui_boolean_source_cannot_disable_stock_silently(bad, tmp_path):
    host = _host(tmp_path)
    service = SettingsService(host)
    service.update({"draw_stock": True})
    prior = service.snapshot().as_dict()
    assert service.update({"draw_stock": bad}).as_dict() == prior
    assert host.DRAW_STOCK is True
    with pytest.raises(ValueError, match="布林值"):
        apply_settings_to_ae(host, {"draw_stock": bad})


def test_factory_defaults_and_ui_display_remain_compatible(tmp_path):
    host = _host(tmp_path)
    host.default_config = {"DEFAULT_SIZES": {"W": "400.25", "H": "600.125",
                                            "D": "250.5", "T": "2", "FW": "25.5"},
                           "OUTPUT": {"draw_stock": "false"}}
    defaults = load_factory_defaults_from_ae(host)
    assert tuple(defaults[k] for k in ("w","h","d","t","fw")) == (
        400.25, 600.125, 250.5, 2.0, 25.5,
    )
    service = SettingsService(host)
    assert service.update({"ui_text_size": "大"})["ui_text_size"] == "large"


def test_main_gui_uses_engine_key_list_and_no_private_raw_truthiness():
    import inspect
    import phase6_settings_center as gui
    assert api.PHYSICAL_SNAPSHOT_SOURCE_KEYS is owner.PHYSICAL_SNAPSHOT_SOURCE_KEYS
    code = inspect.getsource(gui._coerce)
    assert "manufacturing_api.PHYSICAL_SNAPSHOT_SOURCE_KEYS" in code
    assert "manufacturing_api.normalize_operator_source_dimension(" in code
    assert "manufacturing_api.normalize_operator_settings_boolean(" in code
    assert "manufacturing_api.normalize_operator_settings_updates(" in code
    assert "return float(raw)" not in code
    assert 'return str(raw).strip().lower() in {' not in code
