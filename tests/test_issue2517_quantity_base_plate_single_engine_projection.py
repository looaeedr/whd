# -*- coding: utf-8 -*-
"""#2517 Receiving Quantity physical Base Plate derives from saved Engine W/T.

The GUI may select/preview, but shall never validate weld EAR holes using
Settings default W and publish a different Quantity physical common-box W.
"""
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_quantity_box import update_common_box as canonical_update
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from phase6_receiving_modes import fresh_receiving_mode
from tests.test_issue2517_receiving_base_plate_settings_engine_api import CENTER


def _quantity():
    return fresh_receiving_mode(
        "quantity", {"w": 800, "h": 1600, "d": 350}, thickness=2,
    )


def _project(source, config):
    return api.project_operator_receiving_quantity_base_plate_settings(
        source, config,
    )


def test_root_public_quantity_plate_api_is_one_engine_owner():
    assert ae_engine.project_operator_receiving_quantity_base_plate_settings is (
        api.project_operator_receiving_quantity_base_plate_settings
    )
    assert "project_operator_receiving_quantity_base_plate_settings" in ae_engine.__all__


def test_real_center_base_plate_uses_saved_common_box_and_preserves_unselected_version():
    source = _quantity()
    before = deepcopy(source)
    projected = _project(source, CENTER)
    assert source == before
    assert projected is not source
    assert projected["active_mode"] == "quantity"
    assert projected["receiving_base_plate"] == CENTER
    assert projected["receiving_quantity_box"]["receiving_base_plate"] == CENTER
    assert projected["receiving_base_plate"] is not CENTER
    assert projected["receiving_quantity_box"]["receiving_base_plate"] is not CENTER
    assert projected["quantity"] == before["quantity"]
    assert projected["w"] == projected["receiving_quantity_box"]["w"] == 800.0
    assert api.project_common_box(projected) == projected
    projected["receiving_quantity_box"]["receiving_base_plate"]["height"] = 7
    assert source == before
    assert CENTER["height"] == 280.0


def test_stale_gui_default_width_and_runtime_alias_cannot_change_ear_datum(monkeypatch):
    from ae_engine import receiving_base_plate_settings_validation as owner

    source = _quantity()
    source["w"] = 1180.0  # stale UI/assembly alias, not the saved Quantity W
    source["receiving_base_plate"] = {"old": "stale projection"}
    original = deepcopy(source)
    seen = []
    actual = owner.validate_receiving_base_plate_settings

    def observe(*, input_snapshot, settings_values, config):
        seen.append((input_snapshot["w"], input_snapshot["t"],
                     dict(settings_values)))
        return actual(
            input_snapshot=input_snapshot, settings_values=settings_values,
            config=config,
        )

    monkeypatch.setattr(owner, "validate_receiving_base_plate_settings", observe)
    projected = _project(source, CENTER)
    assert seen == [(800.0, 2.0, {"w": 800.0, "t": 2.0})]
    assert projected["w"] == 800.0
    assert projected["receiving_base_plate"] == CENTER
    assert source == original


def test_quantity_reset_clears_both_persisted_box_and_assembly_alias():
    source = _project(_quantity(), CENTER)
    original = deepcopy(source)
    cleared = _project(source, None)
    assert "receiving_base_plate" not in cleared
    assert "receiving_base_plate" not in cleared["receiving_quantity_box"]
    assert cleared["quantity"] == original["quantity"]
    assert source == original
    assert api.project_common_box(cleared) == cleared


@pytest.mark.parametrize("fault,expected", (
    ("wrong-family", "MODE_REQUIRED"),
    ("wrong-mode", "MODE_REQUIRED"),
    ("not-a-mapping", "MODE_REQUIRED"),
    ("missing-box", "SOURCE_REQUIRED"),
    ("missing-quantity", "SOURCE_REQUIRED"),
    ("malformed-quantity", "不合法"),
    ("bad-w", "有限正數"),
    ("missing-t", "有限正數"),
    ("nan-t", "有限正數"),
    ("bad-ear", ""),
    ("unknown-pattern", ""),
))
def test_invalid_quantity_physical_source_fails_closed_without_any_mutation(fault, expected):
    source = _quantity()
    config = deepcopy(CENTER)
    if fault == "wrong-family":
        source["model"] = "金庫型"
    elif fault == "wrong-mode":
        source["active_mode"] = "set_bay"
    elif fault == "not-a-mapping":
        source = ("wrong", "snapshot")
    elif fault == "missing-box":
        del source["receiving_quantity_box"]
    elif fault == "missing-quantity":
        del source["quantity"]
    elif fault == "malformed-quantity":
        source["quantity"] = {"schema": "illegal"}
    elif fault == "bad-w":
        source["receiving_quantity_box"]["w"] = 0
    elif fault == "missing-t":
        del source["t"]
    elif fault == "nan-t":
        source["t"] = float("nan")
    elif fault == "bad-ear":
        config["pattern"] = RECEIVING_BASE_PATTERN_LEFT
    elif fault == "unknown-pattern":
        config["pattern"] = "UNRECOGNIZED"
    original = deepcopy((source, config))
    with pytest.raises((ValueError, TypeError), match=expected or None):
        _project(source, config)
    if fault != "nan-t":
        assert (source, config) == original
    else:
        assert source["t"] != source["t"]  # NaN remains on same original source
        assert config == original[1]


def test_quantity_plate_persisted_box_survives_real_save_reload(tmp_path):
    import phase6_project_file as project

    source = _project(_quantity(), CENTER)
    filename = project.write_project(
        tmp_path / "2517-quantity-plate.p6fold", {
            "schema": project.PROJECT_SCHEMA,
            "snapshot": source,
        },
    )
    restored = project.read_project(filename)["snapshot"]
    assert restored["active_mode"] == "quantity"
    assert restored["receiving_quantity_box"]["receiving_base_plate"] == CENTER
    reprojected = api.project_common_box(restored)
    assert reprojected["receiving_quantity_box"]["receiving_base_plate"] == CENTER
    assert reprojected["receiving_base_plate"] == CENTER
    assert reprojected["quantity"] == source["quantity"]


def test_original_canonical_common_box_update_accepts_exact_verified_plate():
    source = _quantity()
    accepted = api.validate_receiving_base_plate_settings(
        input_snapshot=source,
        settings_values={"w": source["receiving_quantity_box"]["w"], "t": source["t"]},
        config=CENTER,
    )
    expected = canonical_update(
        api.project_common_box(source), {"receiving_base_plate": accepted},
    )
    assert _project(source, CENTER) == expected


def test_real_gui_quantity_branch_uses_single_public_engine_projection():
    source = (Path(__file__).resolve().parents[1]
              / "gui_modules/application/fold_designer_composition_receiving.py")
    text = source.read_text(encoding="utf-8")
    quantity = text.split("def receiving_base_plate_for_current_mode(config):", 1)[1].split(
        "def commit_vault_panel_name(", 1,
    )[0]
    assert "manufacturing_api.project_operator_receiving_quantity_base_plate_settings(" in quantity
    assert "manufacturing_api.update_common_box(" not in quantity
    assert "settings_values=app._settings_values" not in quantity.split(
        'return commit_receiving_base_plate_settings(', 1
    )[0]
    assert "candidate = _current_mode_snapshot(" not in quantity
    assert "_apply_mode_snapshot(self, namespace, source)" in quantity
    assert "return commit_receiving_base_plate_settings(" in quantity
