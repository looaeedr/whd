# -*- coding: utf-8 -*-
"""Current CSV V5 #1504 batch: real editor transaction → versions → .p6fold.

Tests are actual application ports and on-disk JSON Save/Reload, not a set of
matching test names. A source lacking physical X never receives manufacture
authority; this is not replacement for two independent GUI projects.
"""
from copy import deepcopy
import json
import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, new_nfb_ui1a_draft, nfb_ui1a_preview,
)
from ae_engine.receiving_nfb_ui1a_edits import (
    NfbUi1aEditSession, effective_nfb_rotation, set_nfb_manual_x,
    set_nfb_slot_rotation, set_nfb_layer_rotation, move_nfb_slot,
)
from ae_engine.receiving_layout import new_receiving_layout, update_receiving_bay
from ae_engine.receiving_nfb_persistence import normalize_nfb_config
from phase6_project_file import PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V3, write_project, read_project
from phase6_quantity_model import QuantityModel, SCHEMA_V2, SCHEMA

MODEL_A = numeric_model_ref("士林", "2P400")
MODEL_B = numeric_model_ref("士林", "3P125SN")

def _config():
    return {"layer_count": 1, "holes": [
        {"physical_hole_id": "nfb:one", "unit_id": "unit:one", "model_filename": MODEL_A,
         "source_brand": "士林", "layer_index": 0, "slot_index": 0,
         "manual_x_state": "UNVERIFIED_BASIS", "manual_x_mm": 0, "rotation_deg": 90},
        {"physical_hole_id": "nfb:two", "unit_id": "unit:two", "model_filename": MODEL_B,
         "source_brand": "士林", "layer_index": 0, "slot_index": 1,
         "manual_x_state": "NONE", "manual_x_mm": None, "rotation_deg": 0},
    ]}

def _project(snapshot):
    return {"schema": PROJECT_SCHEMA_V1, "snapshot": {
        "model": "受電箱", **snapshot
    }}

def _draft():
    return new_nfb_ui1a_draft(set_brand="士林", layer_count=2,
                              model_layers=([MODEL_A, MODEL_B], [MODEL_A]))

def test_ac06_native_edit_cancel_undo_illegal_mutating_callback_and_authority_save(tmp_path):
    old = _draft()
    original = deepcopy(old)
    session = NfbUi1aEditSession(old)
    assert session.apply("X", set_nfb_manual_x, 0, 0, 0,
                         datum={"box_width_mm": 800}) is not None
    assert session.apply("ANGLE", set_nfb_slot_rotation, 0, 0,
                         mode=OVERRIDE, value=90) is not None
    assert session.current["layers"][0]["slots"][0]["manual_x_mm"] == 0
    before_invalid = deepcopy(session.current)

    def mutate_then_fail(candidate):
        candidate["layers"][0]["slots"][0]["filename"] = "FORGED.dxf"
        candidate["layers"][0]["slots"][0]["manual_x_mm"] = 9999
        raise ValueError("actual collision")

    with pytest.raises(ValueError, match="actual collision"):
        session.apply("REJECT_COLLISION", mutate_then_fail)
    assert session.current == before_invalid
    with pytest.raises(ValueError):
        session.apply("INVALID_LAYER", move_nfb_slot, 0, 90, 0)
    assert session.current == before_invalid
    receipt = session.undo()
    assert receipt.action == "ANGLE"
    assert session.current["layers"][0]["slots"][0]["manual_x_mm"] == 0
    session.undo()
    assert session.current == original
    assert session.dirty is False
    session.apply("TEMP_X", set_nfb_manual_x, 1, 0, 18)
    assert session.dirty
    assert session.escape() == original
    assert not session.dirty and old == original

    # The modal session does not secretly submit a NFB configuration to Bay.
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    payload = _project({"active_mode": "set_bay", "receiving_layout": layout})
    file = write_project(tmp_path / "cancelled.p6fold", payload)
    reopened = read_project(file)["snapshot"]
    bay = reopened["receiving_layout"]["sets"][0]["bays"][0]
    assert "nfb_config" not in bay and "nfb_config_submitted" not in bay
    assert "FORGED.dxf" not in file.read_text(encoding="utf-8")
    assert "TEMP_X" not in file.read_text(encoding="utf-8")

def test_ac08_quantity_version_id_deep_clone_switch_delete_save_reload_identity(tmp_path):
    model = QuantityModel()
    first = model.selected_version_id
    model.set_version_nfb_config(first, submitted=True, config=_config())
    model.set_piece_count(3)
    second = model.add_version()
    assert model.nfb_config_for_version(second)["nfb_config"]["holes"][0][
        "manual_x_state"] == "UNVERIFIED_BASIS"
    changed = deepcopy(_config())
    changed["holes"][0]["model_filename"] = MODEL_B
    changed["holes"][1]["model_filename"] = MODEL_A
    changed["holes"][0]["manual_x_mm"] = 42
    changed["holes"][0]["rotation_deg"] = 180
    model.set_version_nfb_config(second, submitted=True, config=changed)
    model.set_piece_count(2)
    model.select(first)
    assert model.selected_piece_count == 3
    assert model.nfb_config_for_version(first)["nfb_config"]["holes"][0]["model_filename"] == MODEL_A
    assert model.nfb_config_for_version(second)["nfb_config"]["holes"][0]["model_filename"] == MODEL_B
    assert model.nfb_config_for_version(first)["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert model.nfb_config_for_version(second)["nfb_config"]["holes"][0]["manual_x_mm"] == 42
    assert model.total_piece_count == 5

    # A third duplicate must retain source provenance but not share mutable pointers.
    third = model.add_version()
    assert third not in {first, second}
    copy = model.nfb_config_for_version(third)
    copy["nfb_config"]["holes"][0]["manual_x_mm"] = 123
    assert model.nfb_config_for_version(first)["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert model.nfb_config_for_version(second)["nfb_config"]["holes"][0]["manual_x_mm"] == 42
    assert model.delete_selected(confirmed=False) is False
    assert model.delete_selected(confirmed=True) is True
    assert model.version_count == 2 and model.total_piece_count == 5
    assert model.selected_version_id == second
    model.select(first)

    path = write_project(tmp_path / "versions.p6fold", _project({
        "active_mode": "quantity", "quantity": model.snapshot(),
        "receiving_quantity_box": {"w":800,"h":1600,"d":350}
    }))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema"] == PROJECT_SCHEMA_V3
    assert saved["snapshot"]["quantity"]["schema"] == SCHEMA_V2
    restored = QuantityModel.from_payload(read_project(path)["snapshot"]["quantity"])
    assert restored.version_count == 2 and restored.total_piece_count == 5
    assert restored.selected_version_id == first
    assert restored.nfb_config_for_version(second)["nfb_config"]["holes"][0]["rotation_deg"] == 180
    assert restored.nfb_config_for_version(first)["nfb_config"]["holes"][0]["rotation_deg"] == 90
    restored.select(second)
    assert restored.nfb_config_for_version(first)["nfb_config"]["holes"][0]["manual_x_mm"] == 0
    assert model.snapshot() == QuantityModel.from_payload(model.snapshot()).snapshot()

def test_ac26_current_v5_quarter_turn_saved_bay_reload_does_not_fake_absolute_placement(tmp_path):
    draft = _draft()
    original = deepcopy(draft)
    draft = set_nfb_layer_rotation(draft,0,180)
    draft = set_nfb_slot_rotation(draft,0,0,mode=OVERRIDE,value=90)
    draft = set_nfb_manual_x(draft,0,0,0,datum={"box_width_mm":800})
    assert effective_nfb_rotation(draft,0,0) == 90
    assert effective_nfb_rotation(draft,0,1) == 180
    assert draft["layers"][0]["slots"][0]["manual_x_state"] == "UNVERIFIED_BASIS"
    assert original["layers"][0]["slots"][0].get("rotation") is None
    preview = nfb_ui1a_preview(draft,bay_width_mm=800,upper_cell_height_mm=1100)
    assert preview["can_manufacture"] is False
    assert preview["has_absolute_x"] is False

    cfg = deepcopy(_config())
    cfg["holes"][0]["rotation_deg"] = effective_nfb_rotation(draft,0,0)
    cfg["holes"][1]["rotation_deg"] = effective_nfb_rotation(draft,0,1)
    layout = update_receiving_bay(
        new_receiving_layout(width=800,height=1600,depth=350),
        set_index=0,bay_index=0,nfb_config_submitted=True,nfb_config=cfg,
    )
    path=write_project(tmp_path/"rotated.p6fold",_project({
        "active_mode":"set_bay","receiving_layout":layout,
    }))
    current=read_project(path)["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]
    assert current["nfb_config_submitted"] is True
    assert [h["rotation_deg"] for h in current["nfb_config"]["holes"]] == [90,180]
    assert [h["manual_x_state"] for h in current["nfb_config"]["holes"]] == [
        "UNVERIFIED_BASIS","NONE"
    ]
    assert [h["manual_x_mm"] for h in current["nfb_config"]["holes"]] == [0,None]
    assert all("manufacturing_ready" not in h and "absolute_x_mm" not in h
               for h in current["nfb_config"]["holes"])
    path2=write_project(tmp_path/"rotated-again.p6fold",read_project(path))
    assert read_project(path2)["snapshot"]["receiving_layout"]["sets"][0][
        "bays"][0]["nfb_config"]==normalize_nfb_config(cfg)

def test_version_copy_never_promotes_unknown_x_to_confirmed_or_cross_scope():
    original=QuantityModel()
    original.set_version_nfb_config(original.selected_version_id,
                                    submitted=True,config=_config())
    a=original.selected_version_id
    b=original.add_version()
    orig=original.nfb_config_for_version(a)["nfb_config"]
    clone=original.nfb_config_for_version(b)["nfb_config"]
    assert orig["holes"][0]["manual_x_state"]=="UNVERIFIED_BASIS"
    assert clone["holes"][0]["manual_x_state"]=="UNVERIFIED_BASIS"
    assert orig["holes"][1]["manual_x_state"]=="NONE"
    assert clone["holes"][1]["manual_x_state"]=="NONE"
    assert orig["holes"][0]["physical_hole_id"]==clone["holes"][0]["physical_hole_id"]
    clone["holes"][0]["rotation_deg"]=270
    assert original.nfb_config_for_version(a)["nfb_config"]["holes"][0]["rotation_deg"]==90
    assert original.nfb_config_for_version(b)["nfb_config"]["holes"][0]["rotation_deg"]==90
    for version in original.snapshot()["versions"]:
        for hole in version["nfb_config"]["holes"]:
            assert hole["manual_x_state"]!="CONFIRMED"
            assert "approved" not in hole
