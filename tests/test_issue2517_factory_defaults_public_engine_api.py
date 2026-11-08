"""#2517 Factory Settings catalog/defaults must be single-source Engine API."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import inspect
import json

import pytest

import ae_engine
from ae_engine import ae, manufacturing_api as api
from ae_engine import operator_settings_catalog as catalog
from phase6_settings_center import (
    SETTING_SPECS, SettingSpec, load_factory_defaults_from_ae,
    project_fold_designer_factory_snapshot, settings_for_context,
)


def test_factory_catalog_is_same_identity_in_engine_gui_and_public_facade():
    assert api.OPERATOR_SETTING_SPECS is catalog.SETTING_SPECS is SETTING_SPECS
    assert api.OperatorSettingSpec is catalog.SettingSpec is SettingSpec
    assert api.OPERATOR_GLOBAL_SETTINGS_CONTEXT == "global"
    assert settings_for_context("door") == api.operator_settings_for_context("door")
    assert len(SETTING_SPECS) == len({spec.key for spec in SETTING_SPECS})
    assert ae_engine.project_operator_factory_default_settings is (
        api.project_operator_factory_default_settings
    )


def test_real_engine_factory_default_is_not_user_ini_or_live_runtime(monkeypatch):
    baseline = api.project_operator_factory_default_settings()
    # The configured current runtime is not the factory. A mutated INI and
    # changed live runtime may not rewrite the reset seed on Save→Reload.
    monkeypatch.setattr(ae, "W", baseline["w"] + 999)
    monkeypatch.setattr(ae, "zl1_def", baseline["zl1"] + 4.625)
    assert api.project_operator_factory_default_settings() == baseline
    expected = load_factory_defaults_from_ae(
        SimpleNamespace(default_config=deepcopy(ae.default_config))
    )
    assert project_fold_designer_factory_snapshot() == expected
    assert baseline == expected
    assert baseline["z_comp"] == float(ae.default_config["BOX_BODY_Z"]["z_comp"])
    baseline["w"] = -999
    assert api.project_operator_factory_default_settings()["w"] > 0


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_verified_legacy_factory_source_roundtrips_without_physical_precision_loss(family):
    original = {
        "DEFAULT_SIZES": {
            "W": "800.125", "H": "1600.375", "D": "350.625",
            "T": "2.25", "FW": "29.125",
        },
        "OUTPUT": {"draw_stock": "false"},
        "BOX_BODY_Z": {"zl1": "17.375", "zl2": "22.625"},
        "BASE_PLATE": {"shrink": "51.375"},
        "UI": {"text_size": "大"},
    }
    source = json.loads(json.dumps(original, ensure_ascii=False))
    before = deepcopy(source)
    result = api.project_operator_factory_default_settings(source_config=source)
    assert tuple(result[key] for key in ("w", "h", "d", "t", "fw")) == (
        800.125, 1600.375, 350.625, 2.25, 29.125,
    )
    assert result["zl1"] == 17.375 and result["zl2"] == 22.625
    for side in ("top", "bottom", "left", "right"):
        assert result[f"base_plate_shrink_{side}"] == 51.375
    assert result["draw_stock"] is False
    assert result["ui_text_size"] == "大"  # UI-only: Engine passes raw text
    assert load_factory_defaults_from_ae(
        SimpleNamespace(default_config=source)
    ) == {**result, "ui_text_size": "large"}
    assert source == before
    reloaded = json.loads(json.dumps({"model": family, "factory_defaults": result}, ensure_ascii=False))
    assert reloaded["factory_defaults"]["w"] == 800.125
    assert reloaded["model"] == family


@pytest.mark.parametrize("section,option,key,fallback", [
    ("DEFAULT_SIZES", "W", "w", 400.0),
    ("DEFAULT_SIZES", "T", "t", 2.0),
    ("DEFAULT_SIZES", "FW", "fw", 25.0),
    ("BOX_BODY_Z", "zl1", "zl1", 15.0),
    ("END_CAP_Y", "ybottom1", "ybottom1", 15.0),
    ("DOOR", "door_gap_w", "door_gap_w", 3.5),
    ("HOLES", "hang_hole_radius", "hang_hole_r", 3.2),
    ("OUTPUT", "draw_stock", "draw_stock", False),
])
@pytest.mark.parametrize("bad", ["bad", "nan", "inf", True])
def test_invalid_factory_values_cannot_create_manufacturing_input(
    section, option, key, fallback, bad,
):
    source = {section: {option: bad}}
    saved = deepcopy(source)
    if key == "draw_stock" and bad is True:
        # True is a valid raw operator boolean, not an invalid factory flag.
        pytest.skip("valid boolean source is covered by the acceptance case")
    result = api.project_operator_factory_default_settings(source_config=source)
    assert result[key] == fallback
    assert source == saved
    assert load_factory_defaults_from_ae(
        SimpleNamespace(default_config=source)
    )[key] == fallback


def test_factory_fallback_does_not_admit_external_unknown_setting_or_live_config():
    source = {"DEFAULT_SIZES": {"W": 0, "FW": "Infinity"},
              "DANGEROUS_FAMILY_OVERRIDE": {"hole": 1000},
              "OUTPUT": {"draw_stock": "maybe"}}
    result = api.project_operator_factory_default_settings(source_config=source)
    assert result["w"] == 400.0 and result["fw"] == 25.0
    assert result["draw_stock"] is False
    assert "DANGEROUS_FAMILY_OVERRIDE" not in result
    assert len(result) == len(SETTING_SPECS)


def test_fold_designer_snapshot_does_not_import_private_ae_or_recompute_factory():
    source = Path("gui_modules/application/fold_designer_snapshot_projection.py").read_text(
        encoding="utf-8"
    )
    assert "import ae_engine.ae" not in source
    assert "load_factory_defaults_from_ae(ae)" not in source
    assert "project_fold_designer_factory_snapshot()" in source
    projection = inspect.getsource(project_fold_designer_factory_snapshot)
    assert "manufacturing_api.project_operator_factory_default_settings()" in projection
    assert 'result["ui_text_size"] = normalize_ui_text_size' in projection
    assert "float(" not in projection and "bool(" not in projection
    from ae_engine import operator_factory_settings_defaults as owner
    engine = inspect.getsource(owner)
    assert "from gui_modules" not in engine
    assert "from phase6_" not in engine
    assert "import tkinter" not in engine
