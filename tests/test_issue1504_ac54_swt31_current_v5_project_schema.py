# -*- coding: utf-8 -*-
"""#1504 NFB-AC-54 / SWT-AC-31: CURRENT V5 project schema no-drop.

Unlike historical #1499 fixtures, this tests a real numeric CSV V5 identity
through the installed .p6fold writer/reader for both Set/Bay and Quantity.
Old schema version readers MUST reject NFB-bearing data rather than silently
discarding a model, manual X/datum, rotation or any future operator field.
No manufacturing readiness is encoded or inferred from successful reload.
"""
from copy import deepcopy
import json

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
)
from ae_engine.receiving_nfb_persistence import contains_submitted_nfb
from phase6_quantity_model import QuantityModel, SCHEMA, SCHEMA_V2
from phase6_project_file import (
    PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3,
    write_project, read_project,
)


MODEL = numeric_model_ref("士林", "2P400")


def _current_v5_config(*, world_x=0.0):
    return {
        "layer_count": 1,
        "holes": [{
            "physical_hole_id": "nfb:v5:upper:one",
            "model_filename": MODEL,
            "source_brand": "士林",
            "manual_x_state": "CONFIRMED",
            "manual_x_mm": world_x,
            "datum_revision": "WHD_SOURCE_CONFIRMED",
            "datum_snapshot": {"w": 800, "inner_door": "upper"},
            "rotation_deg": 90,
            "operator_marker_v5": {"preserve": "source-owned-numeric-identity"},
        }],
    }


def _layout():
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )


def _set_bay_payload(layout):
    return {"schema": PROJECT_SCHEMA_V1, "snapshot": {
        "model": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout,
    }}


def _quantity_payload(quantity):
    return {"schema": PROJECT_SCHEMA_V1, "snapshot": {
        "model": "受電箱", "active_mode": "quantity",
        "quantity": quantity.snapshot(),
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    }}


def _load_raw(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _expect_current(row, world_x):
    hole = row["nfb_config"]["holes"][0]
    assert row["nfb_config_submitted"] is True
    assert hole["model_filename"] == MODEL
    assert hole["source_brand"] == "士林"
    assert hole["physical_hole_id"] == "nfb:v5:upper:one"
    assert hole["manual_x_state"] == "CONFIRMED"
    assert hole["manual_x_mm"] == world_x
    assert hole["rotation_deg"] == 90
    assert hole["datum_revision"] == "WHD_SOURCE_CONFIRMED"
    assert hole["datum_snapshot"] == {"w": 800, "inner_door": "upper"}
    assert hole["operator_marker_v5"] == {
        "preserve": "source-owned-numeric-identity",
    }
    assert "manufacturing_ready" not in hole
    assert "nfb_trial_export_approved" not in hole


def test_ac54_swt31_current_v5_submitted_set_bay_upgrades_root_and_preserves_all_operators(
    tmp_path,
):
    layout = update_receiving_bay(
        _layout(), set_index=0, bay_index=1,
        nfb_config_submitted=True, nfb_config=_current_v5_config(),
    )
    payload = _set_bay_payload(layout)
    before = deepcopy(payload)
    dest = write_project(tmp_path / "current-set-bay.p6fold", payload)
    assert payload == before
    raw = _load_raw(dest)
    assert raw["schema"] == PROJECT_SCHEMA_V3
    assert raw["final_geometry"] == {}
    rows = raw["snapshot"]["receiving_layout"]["sets"][0]["bays"]
    assert "nfb_config" not in rows[0]
    _expect_current(rows[1], 0.0)
    loaded = read_project(dest)
    assert loaded["schema"] == PROJECT_SCHEMA_V3
    assert contains_submitted_nfb(loaded["snapshot"])
    _expect_current(loaded["snapshot"]["receiving_layout"]["sets"][0]["bays"][1], 0.0)
    saved_again = write_project(tmp_path / "roundtrip.p6fold", loaded)
    reread = _load_raw(saved_again)
    assert reread["schema"] == PROJECT_SCHEMA_V3
    _expect_current(reread["snapshot"]["receiving_layout"]["sets"][0]["bays"][1], 0.0)
    assert "nfb_config" not in reread["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]


def test_ac54_swt31_current_v5_quantity_upgrades_both_schemas_and_isolates_versions(
    tmp_path,
):
    q = QuantityModel()
    first = q.selected_version_id
    q.set_version_nfb_config(first, submitted=True, config=_current_v5_config(world_x=0))
    second = q.add_version()
    assert q.snapshot()["schema"] == SCHEMA_V2
    assert q.nfb_config_for_version(second)["nfb_config"]["holes"][0][
        "manual_x_state"
    ] == "RECONFIRM_REQUIRED"
    q.set_version_nfb_config(second, submitted=True,
                             config=_current_v5_config(world_x=180.125))
    dest = write_project(tmp_path / "current-quantity.p6fold", _quantity_payload(q))
    raw = _load_raw(dest)
    assert raw["schema"] == PROJECT_SCHEMA_V3
    assert raw["snapshot"]["quantity"]["schema"] == SCHEMA_V2
    assert "receiving_layout" not in raw["snapshot"]
    versions = {v["version_id"]: v for v in raw["snapshot"]["quantity"]["versions"]}
    _expect_current(versions[first], 0)
    _expect_current(versions[second], 180.125)
    loaded = read_project(dest)
    assert loaded["schema"] == PROJECT_SCHEMA_V3
    restored = QuantityModel.from_payload(loaded["snapshot"]["quantity"])
    first_before = deepcopy(restored.nfb_config_for_version(first))
    restored.set_version_nfb_config(
        second, submitted=False,
    )
    assert restored.nfb_config_for_version(first) == first_before
    assert restored.snapshot()["schema"] == SCHEMA_V2
    restored.set_version_nfb_config(first, submitted=False)
    assert restored.snapshot()["schema"] == SCHEMA
    clean = write_project(tmp_path / "current-unconfigured-again.p6fold",
                          _quantity_payload(restored))
    assert _load_raw(clean)["schema"] == PROJECT_SCHEMA_V2
    assert _load_raw(clean)["snapshot"]["quantity"]["schema"] == SCHEMA


@pytest.mark.parametrize("scope", ("set_bay", "quantity"))
@pytest.mark.parametrize("old_schema", (PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V2))
def test_ac54_swt31_legacy_reader_cannot_silently_drop_current_v5_submitted(
    tmp_path, scope, old_schema,
):
    if scope == "set_bay":
        layout = update_receiving_bay(
            _layout(), set_index=0, bay_index=0,
            nfb_config_submitted=True, nfb_config=_current_v5_config(),
        )
        original = _set_bay_payload(layout)
    else:
        q = QuantityModel()
        q.set_version_nfb_config(q.selected_version_id, submitted=True,
                                 config=_current_v5_config())
        original = _quantity_payload(q)
    path = write_project(tmp_path / f"{scope}-valid.p6fold", original)
    raw = _load_raw(path)
    assert raw["schema"] == PROJECT_SCHEMA_V3
    damaged = deepcopy(raw)
    damaged["schema"] = old_schema
    attack = tmp_path / f"{scope}-downgraded-{old_schema}.p6fold"
    attack.write_text(json.dumps(damaged, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="old schema"):
        read_project(attack)
    assert _load_raw(path) == raw
    assert read_project(path)["schema"] == PROJECT_SCHEMA_V3


def test_ac54_swt31_legacy_quantity_schema_with_embedded_v5_rejected_without_mutation():
    q = QuantityModel()
    q.set_version_nfb_config(
        q.selected_version_id, submitted=True,
        config=_current_v5_config(),
    )
    current = q.snapshot()
    assert current["schema"] == SCHEMA_V2
    previous = deepcopy(current)
    corrupted = deepcopy(current)
    corrupted["schema"] = SCHEMA
    with pytest.raises(ValueError, match="孔型版本"):
        QuantityModel.from_payload(corrupted)
    assert q.snapshot() == previous
    assert QuantityModel.from_payload(previous).snapshot() == previous


@pytest.mark.parametrize("scope", ("set_bay", "quantity"))
def test_ac54_swt31_current_v5_unsubmitted_retains_existing_schema_and_no_nfb_authority(
    tmp_path, scope,
):
    if scope == "set_bay":
        payload = _set_bay_payload(_layout())
    else:
        payload = _quantity_payload(QuantityModel())
    saved = write_project(tmp_path / f"{scope}-old.p6fold", payload)
    raw = _load_raw(saved)
    assert raw["schema"] == PROJECT_SCHEMA_V2
    if scope == "quantity":
        assert raw["snapshot"]["quantity"]["schema"] == SCHEMA
        assert all("nfb_config" not in r
                   for r in raw["snapshot"]["quantity"]["versions"])
    else:
        assert all("nfb_config" not in bay
                   for set_row in raw["snapshot"]["receiving_layout"]["sets"]
                   for bay in set_row["bays"])
    reloaded = read_project(saved)
    assert reloaded["schema"] == PROJECT_SCHEMA_V2
    assert not contains_submitted_nfb(reloaded["snapshot"])
