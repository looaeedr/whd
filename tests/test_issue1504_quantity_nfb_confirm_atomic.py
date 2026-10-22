# -*- coding: utf-8 -*-
"""#1504 true Quantity Confirm All atomic staging, not another UI-only receipt.

Invalid physical common box/source must not partially submit live version NFB;
valid source is projected through the exact production Quantity/Family adapter.
"""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine.receiving_nfb_csv_committed_config import preview_quantity_nfb_submission
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from phase6_quantity_model import QuantityModel, SCHEMA, SCHEMA_V2
from phase6_receiving_modes import fresh_receiving_mode

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui_modules" / "application" / "fold_designer_composition_receiving.py"


def _source_config():
    return {
        "layer_count": 1,
        "holes": [{
            "physical_hole_id": "inner_door:slot:nfb:layer:0:slot:0",
            "model_filename": numeric_model_ref("士林", "2P400"),
            "source_brand": "士林",
            "layer_index": 0,
            "slot_index": 0,
            "manual_x_state": "UNVERIFIED_BASIS",
            "manual_x_mm": None,
            "rotation_deg": 90,
        }],
    }


def _quantity_snapshot():
    return fresh_receiving_mode(
        "quantity", {"w": 800, "h": 1600, "d": 350},
    )


def test_invalid_real_family_box_rejects_confirmation_without_changing_quantity():
    qty = QuantityModel()
    qty.add_version()
    original_qty = qty.snapshot()
    snapshot = _quantity_snapshot()
    bad = deepcopy(snapshot)
    bad["receiving_quantity_box"]["w"] = 0
    before = deepcopy(bad)

    with pytest.raises(ValueError, match="W.*有限正數"):
        preview_quantity_nfb_submission(bad, qty, _source_config())
    assert qty.snapshot() == original_qty
    assert bad == before
    assert qty.snapshot()["schema"] == SCHEMA
    assert all("nfb_config_submitted" not in row
               for row in qty.snapshot()["versions"])


def test_current_csv_source_rejected_before_any_live_version_change():
    qty = QuantityModel()
    snapshot = _quantity_snapshot()
    original = qty.snapshot()
    bad_config = _source_config()
    bad_config["holes"][0]["source_brand"] = "東元"
    with pytest.raises(ValueError, match="mismatch"):
        preview_quantity_nfb_submission(snapshot, qty, bad_config)
    assert qty.snapshot() == original
    assert snapshot["quantity"] == original


def test_valid_projection_shows_current_version_only_but_live_owner_stays_unmodified():
    qty = QuantityModel()
    first = qty.selected_version_id
    second = qty.add_version()
    assert first != second
    before = deepcopy(qty.snapshot())
    snap = _quantity_snapshot()
    projected = preview_quantity_nfb_submission(snap, qty, _source_config())
    assert snap == _quantity_snapshot()
    assert qty.snapshot() == before
    assert projected["quantity"]["schema"] == SCHEMA_V2
    rows = projected["quantity"]["versions"]
    by_id = {r["version_id"]: r for r in rows}
    assert by_id[first]["nfb_config_submitted"] is False
    assert by_id[first]["nfb_config"] is None
    assert by_id[second]["nfb_config_submitted"] is True
    selected_bay = projected["receiving_layout"]["sets"][0]["bays"][0]
    assert selected_bay["nfb_config_submitted"] is True
    assert selected_bay["nfb_config"]["holes"][0]["rotation_deg"] == 90
    assert selected_bay["nfb_config"]["holes"][0]["manual_x_state"] == "UNVERIFIED_BASIS"

    # The original operator confirmation commits only after projection was valid.
    qty.set_version_nfb_config(second, submitted=True, config=_source_config())
    assert qty.snapshot() == projected["quantity"]
    assert qty.nfb_config_for_version(first) == {}
    assert qty.nfb_config_for_version(second)["nfb_config"]["holes"][0][
        "model_filename"] == numeric_model_ref("士林", "2P400")


def test_main_confirm_all_orders_detached_projection_before_live_version_write():
    source = GUI.read_text(encoding="utf-8")
    start = source.index('def confirmed(actual_part, features, staged_config):')
    end = source.index('if mode == "single":', start)
    quantity_commit = source[start:end]
    precheck = quantity_commit.index("projected = preview_quantity_nfb_submission(")
    mutation = quantity_commit.index("quantity.set_version_nfb_config(")
    assert precheck < mutation
    assert "from ae_engine.receiving_nfb_csv_committed_config import (" in quantity_commit
    assert "committed_csv_nfb_config, preview_quantity_nfb_submission" in quantity_commit
