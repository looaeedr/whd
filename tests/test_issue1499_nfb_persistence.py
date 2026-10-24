# -*- coding: utf-8 -*-
"""#1499 Receiving NFBConfig submission, Bay and quantity versions, v3 no-drop."""
import json
from copy import deepcopy

import pytest

from ae_engine.receiving_layout import (
    new_receiving_layout, normalize_receiving_layout,
    resize_receiving_bays, update_receiving_bay,
    project_receiving_bay_legacy_aliases,
)
from ae_engine.receiving_nfb_persistence import (
    normalize_nfb_config, normalize_nfb_saved_fields,
)
from phase6_quantity_model import (
    SCHEMA, SCHEMA_V2, QuantityModel,
)
from phase6_project_file import (
    PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3,
    write_project, read_project,
)


def _config(*, x=0, state="CONFIRMED", filename="400_140X257_107.dxf"):
    return {
        "holes": [{
            "physical_hole_id": "nfb:upper:layer:1:unit:1",
            "model_filename": filename,
            "manual_x_state": state,
            "manual_x_mm": x,
            "datum_revision": "w800t2-rev1",
            "datum_snapshot": {"width": 800, "thickness": 2},
            "rotation_deg": 90,
            "operator_offset_mm": [0, 5],
        }],
        "layer_count": 1, "quantity": 2,
    }


def _layout():
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    return resize_receiving_bays(layout, set_index=0, bay_count=2)


def _payload(layout, *, schema=PROJECT_SCHEMA_V1):
    return {"schema": schema, "snapshot": {
        "model": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout,
    }}


def test_unconfigured_bay_and_quantity_keep_legacy_schema(tmp_path):
    file = write_project(tmp_path / "old.p6fold", _payload(_layout()))
    raw = json.loads(file.read_text(encoding="utf-8"))
    assert raw["schema"] == PROJECT_SCHEMA_V2
    assert all("nfb_config" not in b
               for s in raw["snapshot"]["receiving_layout"]["sets"]
               for b in s["bays"])
    reloaded = read_project(file)
    assert reloaded["schema"] == PROJECT_SCHEMA_V2
    assert SCHEMA == "phase6-quantity-v1"
    assert QuantityModel().snapshot()["schema"] == SCHEMA


def test_submitted_bay_save_reload_v3_retains_exact_zero_and_independent_copy(tmp_path):
    layout = _layout()
    config = _config(x=0)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1,
        nfb_config_submitted=True, nfb_config=config,
    )
    copy = resize_receiving_bays(layout, set_index=0, bay_count=3)
    original = copy["sets"][0]["bays"][1]["nfb_config"]
    clone = copy["sets"][0]["bays"][2]["nfb_config"]
    assert clone["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert original["holes"][0]["manual_x_state"] == "CONFIRMED"
    clone["holes"][0]["manual_x_mm"] = 100
    assert original["holes"][0]["manual_x_mm"] == 0
    assert config["holes"][0]["manual_x_mm"] == 0
    file = write_project(tmp_path / "nfb-bay.p6fold", _payload(copy))
    raw = json.loads(file.read_text(encoding="utf-8"))
    assert raw["schema"] == PROJECT_SCHEMA_V3
    rows = raw["snapshot"]["receiving_layout"]["sets"][0]["bays"]
    assert rows[1]["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert "nfb_config_submitted" not in rows[0]
    restored = read_project(file)["snapshot"]
    reloaded_rows = restored["receiving_layout"]["sets"][0]["bays"]
    assert reloaded_rows[1]["nfb_config"]["holes"][0]["datum_snapshot"] == {
        "width": 800, "thickness": 2,
    }
    assert reloaded_rows[2]["nfb_config"]["holes"][0]["manual_x_mm"] == 100
    assert project_receiving_bay_legacy_aliases(
        restored, set_index=0, bay_index=0, validate_common=False,
    ).get("nfb_config_submitted") is None


def test_confirmed_x_zero_is_not_missing_and_none_is_not_zero():
    good = normalize_nfb_config(_config(x=0))
    assert good["holes"][0]["manual_x_mm"] == 0
    with pytest.raises(ValueError, match="requires explicit numeric"):
        normalize_nfb_config(_config(x=None))
    n = normalize_nfb_config(_config(x=None, state="NONE"))
    assert n["holes"][0]["manual_x_mm"] is None
    assert normalize_nfb_saved_fields({
        "nfb_config_submitted": False, "nfb_config": _config(),
    }) == {}


def test_quantity_versions_have_isolated_saved_nfb_and_reconfirm_on_duplicate():
    q = QuantityModel()
    q.set_version_nfb_config(q.selected_version_id, submitted=True, config=_config())
    assert q.snapshot()["schema"] == SCHEMA_V2
    v2 = q.add_version()
    assert q.nfb_config_for_version(v2)["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert q.nfb_config_for_version("quantity-v1")["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    saved = q.snapshot()
    restored = QuantityModel.from_payload(saved)
    restored.set_version_nfb_config(v2, submitted=True, config=_config(x=200))
    assert restored.nfb_config_for_version("quantity-v1")["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    restored.set_version_nfb_config(v2, submitted=False)
    assert restored.snapshot()["schema"] == SCHEMA_V2
    restored.set_version_nfb_config("quantity-v1", submitted=False)
    assert restored.snapshot()["schema"] == SCHEMA
    assert all("nfb_config" not in row for row in restored.snapshot()["versions"])


def test_quantity_p6fold_root_and_embedded_version_schema_upgrade_together(tmp_path):
    q=QuantityModel()
    q.set_version_nfb_config(q.selected_version_id, submitted=True, config=_config(x=0))
    payload={"schema": PROJECT_SCHEMA_V1, "snapshot": {
        "model":"受電箱", "active_mode":"quantity", "quantity":q.snapshot(),
        "receiving_quantity_box":{
            "w":800, "h":1600, "d":350,
        },
    }}
    output=write_project(tmp_path/"quantity-nfb.p6fold",payload)
    data=json.loads(output.read_text(encoding="utf-8"))
    assert data["schema"] == PROJECT_SCHEMA_V3
    assert data["snapshot"]["quantity"]["schema"] == SCHEMA_V2
    assert "receiving_layout" not in data["snapshot"]
    loaded=read_project(output)
    assert loaded["schema"] == PROJECT_SCHEMA_V3
    assert loaded["snapshot"]["quantity"]["versions"][0]["nfb_config"]["holes"][0]["manual_x_mm"] == 0


def test_old_schema_reader_must_not_silently_strip_new_nfb_scope(tmp_path):
    layout=update_receiving_bay(
        _layout(), set_index=0,bay_index=0,
        nfb_config_submitted=True,nfb_config=_config(),
    )
    output=write_project(tmp_path/"new.p6fold",_payload(layout))
    raw=json.loads(output.read_text(encoding="utf-8"))
    for legacy in (PROJECT_SCHEMA_V1,PROJECT_SCHEMA_V2):
        corrupted=deepcopy(raw)
        corrupted["schema"]=legacy
        file=tmp_path/f"downgraded-{legacy}.p6fold"
        file.write_text(json.dumps(corrupted,ensure_ascii=False),encoding="utf-8")
        with pytest.raises(ValueError,match="old schema"):
            read_project(file)
    with pytest.raises(ValueError,match="孔型版本"):
        QuantityModel.from_payload({
            "schema":"phase6-quantity-v1",
            "versions":[{
                "version_id":"quantity-v1","piece_count":1,
                "head_features":[],"tail_features":[],
                "nfb_config_submitted":True,"nfb_config":_config(),
            }],"selected_version_id":"quantity-v1","next_version_number":2,
        })


def test_derived_flags_not_saved_and_invalid_nfb_fails_without_fallback(tmp_path):
    layout=_layout()
    bad=_config()
    bad["readiness"]="READY"
    with pytest.raises(ValueError,match="derived"):
        update_receiving_bay(
            layout, set_index=0,bay_index=0,
            nfb_config_submitted=True,nfb_config=bad,
        )
    assert normalize_receiving_layout(layout)["sets"][0]["bays"][0].get("nfb_config") is None
    with pytest.raises(ValueError,match="must preserve its actual NFBConfig"):
        update_receiving_bay(
            layout, set_index=0,bay_index=0,nfb_config_submitted=True,
        )
    with pytest.raises(ValueError,match="boolean"):
        update_receiving_bay(
            layout, set_index=0,bay_index=0,
            nfb_config_submitted="true",nfb_config=_config(),
        )


def test_receiving_bay_width_change_requires_nfb_x_reconfirmation_and_preserves_sibling(tmp_path):
    """Changing W invalidates old X datum without deleting model/position."""
    layout = _layout()
    for index in (0, 1):
        layout = update_receiving_bay(
            layout, set_index=0, bay_index=index,
            nfb_config_submitted=True,
            nfb_config=_config(x=0 if index == 0 else 100),
        )
    original = deepcopy(layout)
    same = update_receiving_bay(layout, set_index=0, bay_index=0, width=800)
    assert same["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"

    changed = update_receiving_bay(layout, set_index=0, bay_index=0, width=750)
    left, right = changed["sets"][0]["bays"]
    assert left["width"] == 750
    assert left["nfb_config_submitted"] is True
    moved = left["nfb_config"]["holes"][0]
    assert moved["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert moved["manual_x_mm"] == 0
    assert moved["datum_revision"] == "w800t2-rev1"
    assert moved["datum_snapshot"] == {"width": 800, "thickness": 2}
    assert moved["model_filename"] == _config()["holes"][0]["model_filename"]
    assert right == original["sets"][0]["bays"][1]
    assert layout == original

    # Returning to W800 or issuing a same-width update cannot resurrect the
    # previous operator confirmation, and Save→Reload cannot grant it.
    returned = update_receiving_bay(changed, set_index=0, bay_index=0, width=800)
    returned = update_receiving_bay(returned, set_index=0, bay_index=0, width=800)
    assert returned["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    project = write_project(tmp_path / "changed-bay.p6fold", _payload(returned))
    reopened = read_project(project)["snapshot"]["receiving_layout"]["sets"][0]["bays"]
    assert reopened[0]["nfb_config"]["holes"][0]["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert reopened[0]["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert reopened[1] == original["sets"][0]["bays"][1]


def test_receiving_bay_width_and_new_nfb_config_cannot_smuggle_stale_confirmed_x():
    layout = _layout()
    # Same operation changing geometry and installing a legacy W800-confirmed
    # configuration must not escape the invalidation gate.
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0, width=750,
        nfb_config_submitted=True, nfb_config=_config(x=0),
    )
    hole = layout["sets"][0]["bays"][0]["nfb_config"]["holes"][0]
    assert hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert hole["manual_x_mm"] == 0

    # No physical W change: a normal fresh, explicitly submitted NFB config
    # remains CONFIRMED, so the guard does not block unrelated edits.
    stable = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=_config(x=8),
    )
    assert stable["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == "CONFIRMED"
    for state in ("NONE", "UNVERIFIED_BASIS", "RECONFIRM_REQUIRED"):
        config = _config(x=0, state=state)
        fresh = update_receiving_bay(
            stable, set_index=0, bay_index=0,
            width=780, nfb_config_submitted=True, nfb_config=config,
        )
        assert fresh["sets"][0]["bays"][0]["nfb_config"]["holes"][0]["manual_x_state"] == state
