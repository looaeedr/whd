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
    NfbUi1aEditSession, editable_nfb_draft, effective_nfb_rotation, set_nfb_manual_x,
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
    source_before_session = deepcopy(old)
    # The edit session intentionally upgrades a raw model draft with stable IDs,
    # angle and X fields; compare to that canonical baseline, not raw input.
    original = editable_nfb_draft(old)
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
    assert not session.dirty and old == source_before_session

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


def test_ac36_swt07_unconfigured_and_committed_quantity_clones_remain_independent_on_disk(
    tmp_path,
):
    """Actual current QuantityModel + real V3 project Save/Reload.

    An UNCONFIGURED version never acquires dormant NFBConfig by duplication.
    A truly submitted version deep-clones only its scoped NFB configuration;
    the copied X needs per-version reconfirmation, zero remains a numeric
    operator value, and subsequent edits never leak into another version.
    """
    q = QuantityModel()
    original = q.selected_version_id
    assert q.nfb_config_for_version(original) == {}
    original_blank = q.add_version()
    assert original_blank != original
    assert q.nfb_config_for_version(original_blank) == {}

    # Duplicate an UNCONFIGURED source twice. No residual NFBConfig is
    # allowed to reappear when the other version is subsequently submitted.
    blank_copy = q.add_version()
    assert blank_copy not in {original, original_blank}
    assert q.nfb_config_for_version(blank_copy) == {}

    q.select(original)
    committed = deepcopy(_config())
    committed["holes"][0]["manual_x_state"] = "UNVERIFIED_BASIS"
    committed["holes"][0]["manual_x_mm"] = 0
    q.set_version_nfb_config(original, submitted=True, config=committed)
    assert q.nfb_config_for_version(original)["nfb_config_submitted"] is True

    signed_copy = q.add_version()
    assert signed_copy not in {original, original_blank, blank_copy}
    first = q.nfb_config_for_version(original)["nfb_config"]
    clone = q.nfb_config_for_version(signed_copy)["nfb_config"]
    assert q.nfb_config_for_version(signed_copy)["nfb_config_submitted"] is True
    assert first == clone
    assert clone is not first and clone["holes"] is not first["holes"]
    assert first["holes"][0]["manual_x_mm"] == 0
    assert clone["holes"][0]["manual_x_state"] != "CONFIRMED"
    assert first["holes"][1]["manual_x_state"] == clone["holes"][1]["manual_x_state"] == "NONE"

    # Edits in a duplicated scoped version are not a mutation of source.
    copied_override = deepcopy(clone)
    copied_override["holes"][0]["rotation_deg"] = 270
    copied_override["holes"][0]["manual_x_mm"] = 125
    q.set_version_nfb_config(
        signed_copy, submitted=True, config=copied_override,
    )
    assert q.nfb_config_for_version(original)["nfb_config"]["holes"][0][
        "rotation_deg"
    ] == 90
    assert q.nfb_config_for_version(original)["nfb_config"]["holes"][0][
        "manual_x_mm"
    ] == 0
    assert q.nfb_config_for_version(signed_copy)["nfb_config"]["holes"][0][
        "rotation_deg"
    ] == 270
    assert q.nfb_config_for_version(signed_copy)["nfb_config"]["holes"][0][
        "manual_x_mm"
    ] == 125
    assert not q.nfb_config_for_version(original_blank)
    assert not q.nfb_config_for_version(blank_copy)

    # Reset one selected version to UNCONFIGURED without modifying another
    # submitted version, or persisting a dormant hole list.
    q.set_version_nfb_config(signed_copy, submitted=False)
    assert q.nfb_config_for_version(signed_copy) == {}
    assert q.nfb_config_for_version(original)["nfb_config_submitted"] is True
    q.select(signed_copy)
    next_blank = q.add_version()
    assert q.nfb_config_for_version(next_blank) == {}

    before = q.snapshot()
    assert before["schema"] == SCHEMA_V2
    for row in before["versions"]:
        if row["version_id"] in {original_blank, blank_copy, signed_copy, next_blank}:
            assert row.get("nfb_config_submitted") is not True
            assert row.get("nfb_config") is None
        else:
            assert row["version_id"] == original
            assert row["nfb_config_submitted"] is True
    saved = write_project(
        tmp_path / "ac36_swt07_quantity_clone.p6fold",
        _project({
            "active_mode": "quantity", "quantity": before,
            "receiving_quantity_box": {
                "w": 800, "h": 1600, "d": 350,
            },
        }),
    )
    assert saved.exists()
    on_disk = json.loads(saved.read_text(encoding="utf-8"))
    assert on_disk["schema"] == PROJECT_SCHEMA_V3
    assert on_disk["snapshot"]["quantity"]["schema"] == SCHEMA_V2

    reopened = QuantityModel.from_payload(read_project(saved)["snapshot"]["quantity"])
    assert reopened.snapshot() == before
    assert reopened.nfb_config_for_version(original)["nfb_config_submitted"] is True
    assert reopened.nfb_config_for_version(original)["nfb_config"]["holes"][0][
        "manual_x_mm"
    ] == 0
    for version in (original_blank, blank_copy, signed_copy, next_blank):
        assert reopened.nfb_config_for_version(version) == {}

    # Even after actual Save/Reload, duplicating an unconfigured selection
    # cannot silently resurrect the old submitted version's NFB holes.
    reopened.select(next_blank)
    further = reopened.add_version()
    assert reopened.nfb_config_for_version(further) == {}
    assert reopened.nfb_config_for_version(original)["nfb_config_submitted"] is True
    assert reopened.nfb_config_for_version(original)["nfb_config"]["holes"][0][
        "manual_x_mm"
    ] == 0


def test_ac36_swt07_confirmed_zero_is_revoked_on_quantity_copy_not_erased(
    tmp_path,
):
    """A copied version inherits model/X provenance, NEVER source approval."""
    from tests.test_issue1499_nfb_persistence import _config as confirmed_config

    q = QuantityModel()
    source = q.selected_version_id
    q.set_version_nfb_config(source, submitted=True, config=confirmed_config(x=0))
    source_hole = q.nfb_config_for_version(source)["nfb_config"]["holes"][0]
    assert source_hole["manual_x_state"] == "CONFIRMED"
    assert source_hole["manual_x_mm"] == 0
    target = q.add_version()
    copied_hole = q.nfb_config_for_version(target)["nfb_config"]["holes"][0]
    assert copied_hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert copied_hole["manual_x_mm"] == 0
    assert copied_hole["model_filename"] == source_hole["model_filename"]
    assert copied_hole["rotation_deg"] == source_hole["rotation_deg"]
    assert copied_hole["datum_revision"] == source_hole["datum_revision"]
    assert copied_hole["datum_snapshot"] == source_hole["datum_snapshot"]
    assert q.nfb_config_for_version(source)["nfb_config"]["holes"][0][
        "manual_x_state"
    ] == "CONFIRMED"

    path = write_project(tmp_path / "ac36_copy_reconfirm.p6fold", _project({
        "active_mode": "quantity",
        "quantity": q.snapshot(),
        "receiving_quantity_box": {"w": 800, "h": 1600, "d": 350},
    }))
    disk = read_project(path)
    assert disk["schema"] == PROJECT_SCHEMA_V3
    reload = QuantityModel.from_payload(disk["snapshot"]["quantity"])
    first_hole = reload.nfb_config_for_version(source)["nfb_config"]["holes"][0]
    second_hole = reload.nfb_config_for_version(target)["nfb_config"]["holes"][0]
    assert first_hole["manual_x_state"] == "CONFIRMED"
    assert second_hole["manual_x_state"] == "RECONFIRM_REQUIRED"
    assert first_hole["manual_x_mm"] == second_hole["manual_x_mm"] == 0

    # Resetting the cloned version cannot unsubmit or change the source.
    reload.set_version_nfb_config(target, submitted=False)
    assert reload.nfb_config_for_version(target) == {}
    assert reload.nfb_config_for_version(source)["nfb_config"]["holes"][0][
        "manual_x_state"
    ] == "CONFIRMED"
    again = write_project(tmp_path / "ac36_reconfirmed_source_preserved.p6fold",
                          _project({
                              "active_mode": "quantity",
                              "quantity": reload.snapshot(),
                              "receiving_quantity_box": {
                                  "w": 800, "h": 1600, "d": 350,
                              },
                          }))
    final = QuantityModel.from_payload(read_project(again)["snapshot"]["quantity"])
    assert final.nfb_config_for_version(target) == {}
    assert final.nfb_config_for_version(source)["nfb_config"]["holes"][0][
        "manual_x_mm"
    ] == 0


def test_ac42_detached_real_csv_nfb_preview_cancel_undo_never_certifies_or_mutates_dxf(
    tmp_path,
):
    """UI-1A draft preview has no MFG-1 authority, even with a real DXF.

    Original Tk native MFG-1 buttons and physical source verification are
    separately covered in mandatory current #1500 tests. This test proves
    the complementary editor draft/legacy persistence/source-byte boundary,
    not an original Windows UI operator receipt.
    """
    from hashlib import sha256
    from tests.test_issue1497_configured_nfb_manufacturing_release import _source

    index, source, profile = _source(tmp_path)
    original_source_hash = sha256(source.read_bytes()).hexdigest()
    assert original_source_hash == profile.source_sha256

    initial = editable_nfb_draft(_draft())
    session = NfbUi1aEditSession(_draft())
    assert session.current == initial
    original_preview = nfb_ui1a_preview(
        session.current, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert original_preview["can_manufacture"] is False
    assert original_preview["has_absolute_x"] is False

    # A visible editor X=0 and angle control is still detached UI-1A draft.
    receipt = session.apply(
        "X0_PREVIEW_ONLY", set_nfb_manual_x, 0, 0, 0,
        datum={"box_width_mm": 800},
    )
    assert receipt is not None
    assert session.current["layers"][0]["slots"][0]["manual_x_mm"] == 0
    preview = nfb_ui1a_preview(
        session.current, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert preview["can_manufacture"] is False
    assert preview["has_absolute_x"] is False
    assert session.undo().action == "X0_PREVIEW_ONLY"
    assert session.current == initial
    assert not session.dirty

    session.apply("TEMP_X", set_nfb_manual_x, 0, 0, 33,
                  datum={"box_width_mm": 800})
    assert session.dirty
    assert session.escape() == initial
    assert not session.dirty
    assert sha256(source.read_bytes()).hexdigest() == original_source_hash

    # The actual V3 writer must not persist an unapproved UI-1A NFB edit:
    # there is no submitted NFB to upconvert or replace old parts.
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    original_bay = deepcopy(layout["sets"][0]["bays"][0])
    path = write_project(
        tmp_path / "ac42_draft_never_applied.p6fold",
        _project({"active_mode": "set_bay", "receiving_layout": layout}),
    )
    saved = read_project(path)
    row = saved["snapshot"]["receiving_layout"]["sets"][0]["bays"][0]
    assert row == original_bay
    assert row.get("nfb_config_submitted") is not True
    assert "nfb_config" not in row
    assert "X0_PREVIEW_ONLY" not in path.read_text(encoding="utf-8")
    assert "TEMP_X" not in path.read_text(encoding="utf-8")
    assert sha256(source.read_bytes()).hexdigest() == original_source_hash
