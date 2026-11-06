# -*- coding: utf-8 -*-
"""#2517: NFB parent-brand scope, impact and Quantity write belong to Engine.

Neither the original Receiving modal nor CADSplit may count inherited
physical NFB source rows, fabricate per-version brands, or clear approved X.
The new public operations do not certify any CUTTING/FinalScene/DXF.
"""
from copy import deepcopy
from inspect import getsource

import ae_engine
import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_brand_transition import (
    project_receiving_quantity_nfb_parent_brand as engine_quantity_brand,
    update_receiving_quantity_nfb_parent_brand as engine_quantity_update,
    project_receiving_parent_brand_change_impact as engine_impact,
)
from ae_engine.receiving_layout import append_receiving_set, new_receiving_layout
from ae_engine.receiving_quantity_versions import QuantityModel
from gui_modules.application.fold_designer_composition_receiving import (
    open_receiving_multi_settings,
)
from tests.test_issue2517_receiving_nfb_csv_candidate_public_api import _source


def _quantity_snapshot(*, submitted=True):
    quantity = QuantityModel()
    if submitted:
        typed = manufacturing_api.candidate_committed_csv_nfb_config(_source())
        quantity.set_version_nfb_config(
            quantity.selected_version_id, submitted=True, config=typed,
        )
    return {
        "active_mode": "quantity", "quantity": quantity.snapshot(),
        "receiving_quantity_box": {
            "w": 800, "h": 1600, "d": 350, "switch_brand": "士林",
        },
    }


def _two_set_submitted_layout():
    layout = append_receiving_set(
        new_receiving_layout(width=800, height=1600, depth=350),
    )
    for si in (0, 1):
        layout = manufacturing_api.apply_receiving_nfb_csv_candidate(
            layout, set_index=si, bay_indices=(0,), source=_source(),
        )
    return layout


def test_public_facades_share_exact_nfb_parent_brand_owners():
    assert ae_engine.project_receiving_quantity_nfb_parent_brand is engine_quantity_brand
    assert manufacturing_api.project_receiving_quantity_nfb_parent_brand is engine_quantity_brand
    assert ae_engine.update_receiving_quantity_nfb_parent_brand is engine_quantity_update
    assert manufacturing_api.update_receiving_quantity_nfb_parent_brand is engine_quantity_update
    assert ae_engine.project_receiving_parent_brand_change_impact is engine_impact
    assert manufacturing_api.project_receiving_parent_brand_change_impact is engine_impact
    for name in (
        "project_receiving_quantity_nfb_parent_brand",
        "update_receiving_quantity_nfb_parent_brand",
        "project_receiving_parent_brand_change_impact",
    ):
        assert name in ae_engine.__all__


def test_engine_quantity_parent_preview_and_write_preserve_source_and_migrate_legacy():
    original = _quantity_snapshot()
    before = deepcopy(original)
    assert engine_quantity_brand(original) == "士林"
    assert engine_impact(original, "東元", mode="quantity") == 2
    assert engine_impact(original, "士林", mode="quantity") == 0
    assert original == before

    candidate, changed = engine_quantity_update(original, "東元")
    assert changed is True
    assert original == before
    assert candidate is not original
    assert candidate["receiving_quantity_box"] == original["receiving_quantity_box"]
    assert candidate["quantity"]["versions"][0]["nfb_parent_brand"] == "東元"
    assert candidate["quantity"]["versions"][0]["nfb_config"] == before["quantity"]["versions"][0]["nfb_config"]
    assert engine_quantity_brand(candidate) == "東元"
    unchanged, changed_again = engine_quantity_update(candidate, "東元")
    assert changed_again is False
    assert unchanged == candidate and unchanged is not candidate

    legacy = _quantity_snapshot(submitted=False)
    same_brand, migrated = engine_quantity_update(legacy, "士林")
    assert migrated and same_brand["quantity"]["versions"][0]["nfb_parent_brand"] == "士林"
    assert legacy["quantity"]["schema"] != same_brand["quantity"]["schema"]


def test_all_set_bay_parent_preview_counts_only_inherited_actual_holes():
    layout = _two_set_submitted_layout()
    before = deepcopy(layout)
    assert engine_impact(layout, "東元", mode="set_bay") == 4
    assert engine_impact(layout, "士林", mode="set_bay") == 0
    assert layout == before

    overridden = deepcopy(layout)
    overridden["sets"][1]["bays"][0]["nfb_config"]["holes"][0]["brand_mode"] = "OVERRIDE"
    assert engine_impact(overridden, "東元", mode="set_bay") == 3
    assert layout == before


def test_invalid_mode_or_brand_cannot_modify_quantity_or_set_bay():
    quantity = _quantity_snapshot()
    layout = _two_set_submitted_layout()
    q_before, l_before = deepcopy(quantity), deepcopy(layout)
    with pytest.raises(ValueError, match="模式"):
        engine_impact(layout, "東元", mode="some-other-mode")
    with pytest.raises(ValueError, match="廠牌"):
        engine_impact(layout, "不存在", mode="set_bay")
    with pytest.raises(ValueError, match="品牌"):
        engine_quantity_update(quantity, "不存在")
    with pytest.raises(ValueError, match="單箱體模式"):
        engine_quantity_update({"active_mode": "set_bay", "quantity": quantity["quantity"]}, "士林")
    assert layout == l_before and quantity == q_before


def test_gui_brand_entrypoints_only_supply_operator_scope_and_engine_result():
    source = getsource(open_receiving_multi_settings)
    read = source.split("    def single_brand():", 1)[1].split("    def set_single_brand(value):", 1)[0]
    commit = source.split("    def set_single_brand(value):", 1)[1].split("    def preview_parent_brand_impact(value):", 1)[0]
    impact = source.split("    def preview_parent_brand_impact(value):", 1)[1].split("    def set_global_brand(value):", 1)[0]
    assert "manufacturing_api.project_receiving_quantity_nfb_parent_brand(" in read
    assert "manufacturing_api.update_receiving_quantity_nfb_parent_brand(" in commit
    assert "manufacturing_api.project_receiving_parent_brand_change_impact(" in impact
    for entry in (read, commit, impact):
        assert "QuantityModel.from_payload(" not in entry
        assert "saved_parent_new_reselections(" not in entry
        assert "nfb_config_for_version(" not in entry
    assert '"set_bay"' in impact and '"quantity"' in impact
