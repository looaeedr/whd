# -*- coding: utf-8 -*-
"""#1504 AC-21/SWT-14: real CURRENT CSV quantity-version partial evidence.

This proves physical V5 source provenance, independent version copies,
three-tier transient UI inheritance and .p6fold persistence.  It deliberately
DOES NOT claim each version has its own editable DEFAULT BRAND: the current
operator's Single brand selector is still bound to the common box.  That
missing GUI/domain owner remains an explicit unsigned acceptance blocker.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_refs, parse_numeric_model_ref
from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, NEEDS_RESELECTION, new_nfb_ui1a_draft,
    set_nfb_layer_brand, set_nfb_slot_brand, select_nfb_slot_model,
    reconcile_set_brand, effective_nfb_slot_brand, nfb_ui1a_preview,
)
from ae_engine.receiving_nfb_persistence import normalize_nfb_config
from phase6_quantity_model import QuantityModel, SCHEMA_V2
from phase6_project_file import PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V3, write_project, read_project


def _refs():
    shihlin = numeric_model_refs("士林")
    teco = numeric_model_refs("東元")
    assert shihlin and teco
    assert parse_numeric_model_ref(shihlin[0])[0] == "士林"
    assert parse_numeric_model_ref(teco[0])[0] == "東元"
    return shihlin[0], teco[0]


def _config(ref, x, *, brand_mode=INHERIT):
    brand, _ = parse_numeric_model_ref(ref)
    return {
        "layer_count": 1,
        "holes": [{
            "physical_hole_id": "nfb:quantity:upper:one",
            "model_filename": ref,
            "source_brand": brand,
            "brand_mode": brand_mode,
            "rotation_deg": 90,
            "manual_x_mm": x,
            "manual_x_state": "CONFIRMED",
            "datum_revision": "operator-physical-version",
            "datum_snapshot": {"w": 800, "owner": "upper"},
        }],
    }


def _save(q, path):
    return write_project(path, {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "受電箱",
            "active_mode": "quantity",
            "quantity": q.snapshot(),
            "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
        },
    })


def test_ac21_swt14_current_v5_each_version_model_brand_and_operator_basis_are_independent(
    tmp_path,
):
    a, b = _refs()
    model = QuantityModel()
    first = model.selected_version_id
    model.set_version_nfb_config(first, submitted=True,
                                 config=_config(a, 0))
    before = deepcopy(model.nfb_config_for_version(first))
    second = model.add_version()
    cloned = model.nfb_config_for_version(second)["nfb_config"]["holes"][0]
    assert cloned["model_filename"] == a
    assert cloned["source_brand"] == "士林"
    assert cloned["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert cloned["manual_x_mm"] == 0
    assert cloned["rotation_deg"] == 90
    assert model.nfb_config_for_version(first) == before
    model.set_version_nfb_config(
        second, submitted=True, config=_config(b, 180.25, brand_mode=OVERRIDE)
    )
    assert model.nfb_config_for_version(first) == before
    second_before = deepcopy(model.nfb_config_for_version(second))
    assert second_before["nfb_config"]["holes"][0]["source_brand"] == "東元"
    assert second_before["nfb_config"]["holes"][0]["brand_mode"] == OVERRIDE
    assert second_before["nfb_config"]["holes"][0]["manual_x_mm"] == 180.25
    assert model.snapshot()["schema"] == SCHEMA_V2

    path = _save(model, tmp_path / "independent-versions.p6fold")
    reopened = read_project(path)
    assert reopened["schema"] == PROJECT_SCHEMA_V3
    restored = QuantityModel.from_payload(reopened["snapshot"]["quantity"])
    assert restored.nfb_config_for_version(first) == before
    assert restored.nfb_config_for_version(second) == second_before
    restored.set_version_nfb_config(second, submitted=False)
    assert restored.nfb_config_for_version(first) == before
    assert restored.nfb_config_for_version(second) == {}
    assert model.nfb_config_for_version(second) == second_before
    assert model.nfb_config_for_version(first) == before


def test_ac21_swt14_three_tier_current_csv_brand_inheritance_never_rewrites_model():
    a, b = _refs()
    draft = new_nfb_ui1a_draft(
        set_brand="士林", layer_count=2,
        model_layers=([a, a], [a]),
    )
    original = deepcopy(draft)
    draft = set_nfb_layer_brand(draft, 0, mode=OVERRIDE, value="東元")
    draft = set_nfb_slot_brand(draft, 0, 0, mode=OVERRIDE, value="士林")
    draft = select_nfb_slot_model(draft, 0, 1, b, catalog={"東元": (b,)})
    assert [effective_nfb_slot_brand(draft, 0, slot) for slot in (0, 1)] == [
        "士林", "東元",
    ]
    assert effective_nfb_slot_brand(draft, 1, 0) == "士林"
    preview = nfb_ui1a_preview(
        draft, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert [u["status"] for row in preview["layers"] for u in row["slots"]] == [
        "MODEL_SELECTED", "MODEL_SELECTED", "MODEL_SELECTED",
    ]
    changed_parent = reconcile_set_brand(draft, "東元")
    assert [effective_nfb_slot_brand(changed_parent, 0, i) for i in (0, 1)] == [
        "士林", "東元",
    ]
    assert effective_nfb_slot_brand(changed_parent, 1, 0) == "東元"
    stale = nfb_ui1a_preview(
        changed_parent, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert stale["layers"][1]["slots"][0]["status"] == NEEDS_RESELECTION
    assert changed_parent["layers"][1]["slots"][0]["filename"] == a
    assert changed_parent["layers"][1]["slots"][0]["source_brand"] == "士林"
    assert original["set_brand"] == "士林"
    assert not stale["can_manufacture"]
    assert not stale["has_absolute_x"]


def test_ac21_swt14_invalid_cross_brand_current_v5_submission_is_atomic():
    a, b = _refs()
    model = QuantityModel()
    version = model.selected_version_id
    model.set_version_nfb_config(version, submitted=True, config=_config(a, 0))
    before = deepcopy(model.snapshot())
    invalid = _config(b, 180.25)
    invalid["holes"][0]["source_brand"] = "士林"
    with pytest.raises(ValueError, match="mismatch"):
        model.set_version_nfb_config(version, submitted=True, config=invalid)
    assert model.snapshot() == before
    returned = model.nfb_config_for_version(version)
    returned["nfb_config"]["holes"][0]["model_filename"] = b
    returned["nfb_config"]["holes"][0]["datum_snapshot"]["w"] = -1
    assert model.snapshot() == before
    assert normalize_nfb_config(_config(a, 0))["holes"][0]["source_brand"] == "士林"


def test_ac21_swt14_quantity_brand_ui_actual_owner_gap_remains_unsigned():
    # Audit rather than an invented full GUI acceptance: currently the
    # existing 'single' brand selection is common-box scope, and the
    # per-version config is only read in current editor's Confirm All.
    gui = (Path(__file__).resolve().parents[1] /
           "gui_modules/application/fold_designer_composition_receiving.py").read_text(
               encoding="utf-8"
           )
    assert 'source.get("receiving_quantity_box")' in gui
    assert 'def single_brand():' in gui
    assert 'update_common_box(source, {"switch_brand": value})' in gui
    assert 'quantity.set_version_nfb_config(' in gui
    assert 'get_brand=(single_brand if single else' in gui
    assert 'set_brand=set_single_brand if single else set_global_brand' in gui
    # Existing multi-Set authority must remain separate: no fake
    # second Set.switch_brand field may be added to NFBConfig.
    assert 'if "brand" in value or "switch_brand" in value:' in (
        Path(__file__).resolve().parents[1] /
        "ae_engine/receiving_nfb_persistence.py"
    ).read_text(encoding="utf-8")
