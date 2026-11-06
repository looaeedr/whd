# -*- coding: utf-8 -*-
"""#2517: committed Quantity NFB is never silently hidden by root alias drift.

The saved Quantity version is the source authority.  The root submission
flag is a replaceable GUI/assembly projection, not permission to manufacture
an empty inner door.  Non-selected versions remain isolated.
"""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_quantity_versions import QuantityModel


def _quantity_with_submitted_csv():
    quantity = QuantityModel()
    config = {
        "layer_count": 1,
        "holes": [{
            "physical_hole_id": "physical:nfb:1",
            "model_filename": numeric_model_ref("士林", "2P400"),
            "source_brand": "士林",
            "layer_index": 0, "slot_index": 0, "layer_count": 1,
            "manual_x_state": "UNVERIFIED_BASIS",
            "manual_x_mm": None,
            "rotation_deg": 0,
        }],
    }
    quantity.set_version_nfb_config(
        quantity.selected_version_id, submitted=True, config=config,
    )
    return quantity


@pytest.mark.parametrize("root_submission", (False, None))
def test_selected_submitted_quantity_nfb_cannot_disappear_before_finalscene(
    root_submission,
):
    quantity = _quantity_with_submitted_csv()
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": quantity.snapshot(),
    }
    if root_submission is not None:
        snapshot["nfb_config_submitted"] = root_submission
    original = deepcopy(snapshot)
    with pytest.raises(
        ValueError,
        match="NFB_COMMITTED_CSV_QUANTITY_VERSION_IDENTITY_DRIFT",
    ):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
    assert snapshot == original


def test_unsubmitted_selected_quantity_version_does_not_borrow_other_version_nfb():
    quantity = _quantity_with_submitted_csv()
    other_id = quantity.add_version()
    quantity.set_version_nfb_config(other_id, submitted=False)
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": quantity.snapshot(), "nfb_config_submitted": False,
    }
    original = deepcopy(snapshot)
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None
    assert snapshot == original


def test_unconfigured_quantity_project_still_returns_no_nfb_source():
    quantity = QuantityModel()
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": quantity.snapshot(),
    }
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None


def test_corrupted_quantity_version_cannot_be_treated_as_no_nfb():
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": {"schema": "unknown"}, "nfb_config_submitted": False,
    }
    with pytest.raises(ValueError):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )


def _legacy_nfb_config():
    return {
        "layer_count": 1,
        "holes": [{
            "physical_hole_id": "physical:nfb:1",
            "model_filename": "OLD_2P400.dxf",
            "layer_index": 0, "slot_index": 0, "layer_count": 1,
            "manual_x_state": "NONE",
            "manual_x_mm": None,
            "rotation_deg": 0,
        }],
    }


def test_stale_legacy_root_cannot_hide_selected_csv_quantity_nfb():
    quantity = _quantity_with_submitted_csv()
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": quantity.snapshot(), "nfb_config_submitted": True,
        "nfb_config": _legacy_nfb_config(),
    }
    original = deepcopy(snapshot)
    # Previously the legitimate-looking legacy root took the early return
    # before the Engine resolved the actual selected V5 Quantity owner.
    with pytest.raises(
        ValueError, match="NFB_COMMITTED_CSV_QUANTITY_VERSION_IDENTITY_DRIFT",
    ):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
    assert snapshot == original


def test_legacy_root_cannot_borrow_nfb_from_an_unsubmitted_selected_version():
    quantity = _quantity_with_submitted_csv()
    selected_id = quantity.add_version()
    quantity.set_version_nfb_config(selected_id, submitted=False)
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": quantity.snapshot(), "nfb_config_submitted": True,
        "nfb_config": _legacy_nfb_config(),
    }
    original = deepcopy(snapshot)
    with pytest.raises(
        ValueError, match="NFB_COMMITTED_CSV_QUANTITY_VERSION_IDENTITY_DRIFT",
    ):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
    assert snapshot == original


def test_actual_selected_legacy_quantity_nfb_keeps_historical_source_path():
    quantity = QuantityModel()
    quantity.set_version_nfb_config(
        quantity.selected_version_id,
        submitted=True, config=_legacy_nfb_config(),
    )
    selected = quantity.nfb_config_for_version(quantity.selected_version_id)
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": quantity.snapshot(), "nfb_config_submitted": True,
        "nfb_config": deepcopy(selected["nfb_config"]),
    }
    original = deepcopy(snapshot)
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None
    assert snapshot == original


def test_legacy_snapshot_without_quantity_owner_preserves_old_early_return():
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "nfb_config_submitted": True, "nfb_config": _legacy_nfb_config(),
    }
    assert manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
        snapshot,
    ) is None


def test_malformed_selected_quantity_cannot_hide_behind_valid_legacy_alias():
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": {"schema": "unknown"},
        "nfb_config_submitted": True, "nfb_config": _legacy_nfb_config(),
    }
    with pytest.raises(ValueError):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
