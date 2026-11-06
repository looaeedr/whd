# -*- coding: utf-8 -*-
"""#2517 public transactions for Receiving candidate and transient NFB draft GUI."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_hole_candidates as holes
from ae_engine import receiving_inner_door_candidates as inner
from ae_engine import receiving_nfb_ui1a as nfb
from ae_engine import receiving_nfb_ui1a_edits as edits
from ae_engine import receiving_nfb_brand_transition as brand

GUI = Path(__file__).resolve().parents[1] / "gui_modules/application/fold_designer_composition_receiving.py"
MODEL = "400_140X257_107.dxf"


def test_public_facade_uses_identical_engine_transaction_owners():
    aliases = (
        (api.receiving_hole_candidates_for, holes.candidates_for),
        (api.receiving_hole_candidate_features, holes.candidate_features),
        (api.create_receiving_hole_candidate, holes.create_candidate),
        (api.update_receiving_hole_candidate, holes.update_candidate),
        (api.delete_receiving_hole_candidate, holes.delete_candidate),
        (api.duplicate_receiving_hole_candidate, holes.duplicate_candidate),
        (api.normalize_receiving_hole_candidates, holes.normalize_candidates),
        (api.RECEIVING_INNER_DOOR_CANDIDATE_KEY, inner.KEY),
        (api.RECEIVING_INNER_DOOR_CANDIDATE_ROLE, inner.ROLE),
        (api.normalize_receiving_inner_door_candidates, inner.normalize_inner_candidates),
        (api.receiving_inner_door_versions, inner.inner_versions),
        (api.receiving_inner_door_candidate_config, inner.inner_config),
        (api.create_receiving_inner_door_candidate, inner.create_inner_candidate),
        (api.update_receiving_inner_door_candidate, inner.update_inner_candidate),
        (api.delete_receiving_inner_door_candidate, inner.delete_inner_candidate),
        (api.duplicate_receiving_inner_door_candidate, inner.duplicate_inner_candidate),
        (api.ReceivingNfbDraftEditSession, edits.NfbUi1aEditSession),
        (api.normalize_receiving_nfb_editable_draft, edits.editable_nfb_draft),
        (api.insert_receiving_nfb_draft_slot, edits.insert_nfb_slot),
        (api.delete_receiving_nfb_draft_slot, edits.delete_nfb_slot),
        (api.move_receiving_nfb_draft_slot, edits.move_nfb_slot),
        (api.replace_receiving_nfb_draft_slot_model, edits.replace_nfb_slot_model),
        (api.set_receiving_nfb_draft_manual_x, edits.set_nfb_manual_x),
        (api.set_receiving_nfb_draft_layer_rotation, edits.set_nfb_layer_rotation),
        (api.set_receiving_nfb_draft_slot_rotation, edits.set_nfb_slot_rotation),
        (api.project_receiving_nfb_draft_rotation, edits.effective_nfb_rotation),
        (api.project_receiving_nfb_draft_x_reset_impact, edits.nfb_x_reset_impact),
        (api.project_receiving_nfb_draft_reselections, brand.draft_new_reselections),
        (api.RECEIVING_NFB_DRAFT_INHERIT, nfb.INHERIT),
        (api.RECEIVING_NFB_DRAFT_OVERRIDE, nfb.OVERRIDE),
        (api.RECEIVING_NFB_DRAFT_NEEDS_RESELECTION, nfb.NEEDS_RESELECTION),
        (api.new_receiving_nfb_draft, nfb.new_nfb_ui1a_draft),
        (api.reconcile_receiving_nfb_draft_set_brand, nfb.reconcile_set_brand),
        (api.set_receiving_nfb_draft_layer_count, nfb.set_nfb_draft_layer_count),
        (api.set_receiving_nfb_draft_layer_brand, nfb.set_nfb_layer_brand),
        (api.set_receiving_nfb_draft_slot_brand, nfb.set_nfb_slot_brand),
        (api.add_receiving_nfb_draft_slot, nfb.add_nfb_draft_slot),
        (api.select_receiving_nfb_draft_slot_model, nfb.select_nfb_slot_model),
        (api.remove_receiving_nfb_draft_slot, nfb.remove_nfb_draft_slot),
        (api.project_receiving_nfb_draft_layer_brand, nfb.effective_nfb_layer_brand),
        (api.project_receiving_nfb_draft_slot_brand, nfb.effective_nfb_slot_brand),
        (api.preview_receiving_nfb_draft, nfb.nfb_ui1a_preview),
    )
    assert all(public is original for public, original in aliases)


def test_head_tail_versions_parity_and_rejected_edit_leaves_library_unmodified():
    source = holes.normalize_candidates()
    before = deepcopy(source)
    library, version = api.create_receiving_hole_candidate(source, "head", ())
    assert (library, version) == holes.create_candidate(source, "head", ())
    copy, copied = api.duplicate_receiving_hole_candidate(library, "head", version, "tail")
    assert (copy, copied) == holes.duplicate_candidate(library, "head", version, "tail")
    assert api.receiving_hole_candidate_features(copy, "tail", copied) == []
    updated = api.update_receiving_hole_candidate(copy, "head", version, ())
    assert updated == holes.update_candidate(copy, "head", version, ())
    assert api.delete_receiving_hole_candidate(updated, "head", version) == holes.delete_candidate(updated, "head", version)
    for operation in (
        lambda: api.update_receiving_hole_candidate(copy, "head", version, ("bad-feature",)),
        lambda: api.delete_receiving_hole_candidate(copy, "head", "head-v99"),
        lambda: api.create_receiving_hole_candidate(copy, True, ()),
    ):
        with pytest.raises(ValueError):
            operation()
    assert source == before and copy == library | {"tail": copy["tail"]}


def test_inner_door_versions_parity_and_rejected_edit_keeps_original_config():
    source = inner.normalize_inner_candidates()
    config = {"layers": 1, "models": [MODEL, ""], "layer_heights_mm": [550, 830], "features": {}}
    before = deepcopy((source, config))
    library, version = api.create_receiving_inner_door_candidate(source, config)
    assert (library, version) == inner.create_inner_candidate(source, config)
    copied, copy_id = api.duplicate_receiving_inner_door_candidate(library, version)
    assert (copied, copy_id) == inner.duplicate_inner_candidate(library, version)
    assert api.receiving_inner_door_candidate_config(copied, copy_id) == config
    assert api.update_receiving_inner_door_candidate(copied, version, config) == inner.update_inner_candidate(copied, version, config)
    invalid = {**config, "layers": True}
    for operation in (
        lambda: api.update_receiving_inner_door_candidate(copied, version, invalid),
        lambda: api.create_receiving_inner_door_candidate(copied, invalid),
        lambda: api.delete_receiving_inner_door_candidate(copied, "inner-door-v99"),
    ):
        with pytest.raises(ValueError):
            operation()
    assert (source, config) == before and copied["versions"][0]["config"] == config


def test_nfb_gui_draft_parity_and_undo_rejected_edits_do_not_leak():
    draft = api.new_receiving_nfb_draft(set_brand="士林", layer_count=1, model_layers=([MODEL], ""))
    original = deepcopy(draft)
    state = api.normalize_receiving_nfb_editable_draft(draft)
    assert state == edits.editable_nfb_draft(draft)
    expected = edits.set_nfb_manual_x(state, 0, 0, 12)
    assert api.set_receiving_nfb_draft_manual_x(state, 0, 0, 12) == expected
    session = api.ReceivingNfbDraftEditSession(state)
    before = deepcopy(session.current)
    receipt = session.apply("X", api.set_receiving_nfb_draft_manual_x, 0, 0, 12)
    assert receipt.new_draft == expected
    assert session.undo().old_draft == before
    for operation in (
        lambda: session.apply("BAD_X", api.set_receiving_nfb_draft_manual_x, 0, 0, float("nan")),
        lambda: session.apply("BAD_INSERT", api.insert_receiving_nfb_draft_slot, 0, -1),
        lambda: session.apply("BAD_ROTATION", api.set_receiving_nfb_draft_layer_rotation, 0, True),
    ):
        with pytest.raises(ValueError):
            operation()
        assert session.current == before
    assert draft == original and state != expected


def test_gui_candidate_and_nfb_draft_edit_imports_are_only_public_engine():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    target = {"ae_engine.receiving_hole_candidates",
              "ae_engine.receiving_inner_door_candidates",
              "ae_engine.receiving_nfb_ui1a_edits",
              "ae_engine.receiving_nfb_brand_transition",
              "ae_engine.receiving_nfb_ui1a"}
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not [node for node in imports if node.module in target]
    delegated = {name.asname: name.name
                 for node in imports if node.module == "ae_engine.manufacturing_api"
                 for name in node.names if name.asname}
    assert delegated["create_candidate"] == "create_receiving_hole_candidate"
    assert delegated["update_inner_candidate"] == "update_receiving_inner_door_candidate"
    assert delegated["NfbUi1aEditSession"] == "ReceivingNfbDraftEditSession"
    assert delegated["set_nfb_manual_x"] == "set_receiving_nfb_draft_manual_x"
