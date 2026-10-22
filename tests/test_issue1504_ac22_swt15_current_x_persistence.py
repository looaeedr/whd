# -*- coding: utf-8 -*-
"""#1504 NFB-AC-22 / SWT-AC-15: current V5 unknown-X persistence chain.

These witnesses exercise actual typed CSV model identities, the native UI-1A
edit port, explicit X=0 versus NONE, root/Bay and quantity project writes,
read/reopen, and rejection of manufactured readiness in saved user input.
They do not claim Windows GUI UAT or authorize DXF manufacturing.
"""
from copy import deepcopy
import json

import pytest

from ae_engine.receiving_nfb_x_projection import nominal_nfb_x_group
from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft
from ae_engine.receiving_nfb_ui1a_edits import set_nfb_manual_x
from ae_engine.receiving_layout import new_receiving_layout, update_receiving_bay
from ae_engine.receiving_nfb_persistence import normalize_nfb_config
from phase6_project_file import (
    PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3,
    read_project, write_project,
)
from phase6_quantity_model import QuantityModel, SCHEMA, SCHEMA_V2

MODEL = "nfbv5:士林:2P400"
DATUM = {
    "box_width_mm": 800,
    "layer_index": 0,
    "unit_ids_in_order": ["unit:one", "unit:two"],
    "nominal_rule_revision": nominal_nfb_x_group(800, 2).revision,
}


def _config():
    return {
        "layer_count": 1,
        "holes": [
            {
                "physical_hole_id": "nfb:one",
                "unit_id": "unit:one",
                "model_filename": MODEL,
                "source_brand": "士林",
                "layer_index": 0,
                "slot_index": 0,
                "manual_x_state": "UNVERIFIED_BASIS",
                "manual_x_mm": 0,
                "datum_snapshot": deepcopy(DATUM),
                "rotation_deg": 90,
            },
            {
                "physical_hole_id": "nfb:two",
                "unit_id": "unit:two",
                "model_filename": MODEL,
                "source_brand": "士林",
                "layer_index": 0,
                "slot_index": 1,
                "manual_x_state": "NONE",
                "manual_x_mm": None,
                "datum_snapshot": None,
                "rotation_deg": 0,
            },
        ],
    }


def _bay_layout(*, submitted=True):
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    if submitted:
        return update_receiving_bay(
            layout, set_index=0, bay_index=0,
            nfb_config_submitted=True, nfb_config=_config(),
        )
    return layout


def test_nfb_ac22_ui_edit_zero_and_clear_have_distinct_unverified_states():
    draft = new_nfb_ui1a_draft(
        set_brand="士林", model_layers=([MODEL, MODEL], ""),
    )
    original = deepcopy(draft)
    edited = set_nfb_manual_x(draft, 0, 0, 0, datum=DATUM)
    assert draft == original  # modal edit must not mutate the authoritative draft
    unit = edited["layers"][0]["slots"][0]
    assert unit["manual_x_mm"] == 0.
    assert unit["manual_x_state"] == "UNVERIFIED_BASIS"
    assert unit["datum_snapshot"] == DATUM
    cleared = set_nfb_manual_x(edited, 0, 0, None)
    assert cleared["layers"][0]["slots"][0]["manual_x_mm"] is None
    assert cleared["layers"][0]["slots"][0]["manual_x_state"] == "NONE"
    assert cleared["layers"][0]["slots"][0]["datum_snapshot"] is None
    assert edited["layers"][0]["slots"][0] == unit
    assert not any("manufacturing_ready" in item
                   for item in edited["layers"][0]["slots"])


def test_nfb_ac22_v5_bay_x_zero_none_datum_order_save_reopen_never_auto_approves(tmp_path):
    payload = {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {"model": "受電箱", "active_mode": "set_bay",
                     "receiving_layout": _bay_layout()},
    }
    before = deepcopy(payload)
    path = write_project(tmp_path / "x-source.p6fold", payload)
    assert payload == before
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema"] == PROJECT_SCHEMA_V3
    assert saved["final_geometry"] == {}
    row = saved["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]
    assert row["nfb_config_submitted"] is True
    expected = normalize_nfb_config(_config())
    assert row["nfb_config"] == expected
    reloaded = read_project(path)
    assert reloaded["schema"] == PROJECT_SCHEMA_V3
    current = reloaded["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]
    assert current["nfb_config"] == expected
    holes = current["nfb_config"]["holes"]
    assert [h["unit_id"] for h in holes] == ["unit:one", "unit:two"]
    assert [h["manual_x_state"] for h in holes] == ["UNVERIFIED_BASIS", "NONE"]
    assert [h["manual_x_mm"] for h in holes] == [0, None]
    assert nominal_nfb_x_group(800, 2).manufacturing_ready is False
    assert holes[0]["datum_snapshot"] == DATUM
    assert holes[1]["datum_snapshot"] is None
    assert all(h["model_filename"] == MODEL and h["source_brand"] == "士林"
               for h in holes)
    assert all("manufacturing_ready" not in h and "approved" not in h
               for h in holes)
    second = write_project(tmp_path / "again.p6fold", reloaded)
    assert read_project(second)["snapshot"]["receiving_layout"]["sets"][0][
        "bays"][0]["nfb_config"] == expected


def test_swt_ac15_quantity_v5_x_zero_none_version_isolation_and_reopen(tmp_path):
    quantity = QuantityModel()
    first_id = quantity.selected_version_id
    quantity.set_version_nfb_config(
        first_id, submitted=True, config=_config(),
    )
    other_id = quantity.add_version()
    first = quantity.nfb_config_for_version(first_id)
    other = quantity.nfb_config_for_version(other_id)
    assert first["nfb_config_submitted"] is True
    assert other["nfb_config_submitted"] is True
    assert first["nfb_config"]["holes"][0]["manual_x_state"] == "UNVERIFIED_BASIS"
    assert other["nfb_config"]["holes"][0]["manual_x_state"] == "UNVERIFIED_BASIS"
    other["nfb_config"]["holes"][0]["datum_snapshot"]["box_width_mm"] = 750
    assert quantity.nfb_config_for_version(first_id)["nfb_config"]["holes"][0][
        "datum_snapshot"]["box_width_mm"] == 800
    path = write_project(tmp_path / "quantity-x.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {"model": "受電箱", "active_mode": "quantity",
                     "quantity": quantity.snapshot(),
                     "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350}},
    })
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema"] == PROJECT_SCHEMA_V3
    assert raw["snapshot"]["quantity"]["schema"] == SCHEMA_V2
    reopened = read_project(path)
    versions = reopened["snapshot"]["quantity"]["versions"]
    assert len(versions) == 2
    for version in versions:
        holes = version["nfb_config"]["holes"]
        assert [h["manual_x_mm"] for h in holes] == [0, None]
        assert [h["manual_x_state"] for h in holes] == ["UNVERIFIED_BASIS", "NONE"]
        assert holes[0]["datum_snapshot"] == DATUM
        assert all("manufacturing_ready" not in h for h in holes)
    restored = QuantityModel.from_payload(reopened["snapshot"]["quantity"])
    assert restored.nfb_config_for_version(first_id)["nfb_config"]["holes"][0][
        "datum_snapshot"] == DATUM


def test_current_x_persistence_rejects_fake_manufacturing_flags_and_nonfinite_x(tmp_path):
    layout = _bay_layout(submitted=False)
    for bad_key, value, fragment in (
        ("manufacturing_ready", True, "derived"),
        ("approved", True, "derived"),
        ("manual_x_mm", float("nan"), "finite"),
    ):
        config = _config()
        config["holes"][0][bad_key] = value
        with pytest.raises(ValueError, match=fragment):
            update_receiving_bay(
                layout, set_index=0, bay_index=0,
                nfb_config_submitted=True, nfb_config=config,
            )
        assert layout["sets"][0]["bays"][0].get("nfb_config") is None
    blank = write_project(tmp_path / "no-submit.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {"model": "受電箱", "active_mode": "set_bay",
                     "receiving_layout": layout},
    })
    assert read_project(blank)["schema"] == PROJECT_SCHEMA_V2
    assert SCHEMA == "phase6-quantity-v1"
    assert read_project(blank)["snapshot"]["receiving_layout"]["sets"][0][
        "bays"][0].get("nfb_config") is None
