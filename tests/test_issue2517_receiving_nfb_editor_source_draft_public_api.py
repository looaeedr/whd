# -*- coding: utf-8 -*-
"""#2517 Receiving NFB editor model/Y draft source goes through public Engine."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_fresh_nfb_defaults as fresh
from ae_engine import receiving_legacy_nfb_editor_bootstrap as legacy
from ae_engine import receiving_shared_settings as shared
from ae_engine.receiving_nfb_model_identity import numeric_model_ref

GUI = Path(__file__).resolve().parents[1] / "gui_modules/application/fold_designer_composition_receiving.py"
REF = numeric_model_ref("士林", "2P400")


def test_public_api_is_exact_same_source_owner_as_private_engine():
    assert api.recover_receiving_submitted_nfb_models_for_editor is legacy.recover_submitted_nfb_models_for_editor
    assert api.initial_receiving_nfb_draft_models is fresh.initial_fresh_receiving_nfb_models
    assert api.transition_receiving_nfb_draft_layer_heights is shared.transition_receiving_nfb_layer_heights


def test_physical_committed_models_are_only_recovered_into_detached_editor_draft():
    initial = {"layers": 1, "models": ["", ""], "layer_heights_mm": [550.0, 830.0]}
    physical = {
        "nfb_config_submitted": True,
        "nfb_config": {
            "layer_count": 1,
            "holes": [{"model_filename": REF, "source_brand": "士林",
                       "layer_index": 0, "slot_index": 0}],
        },
    }
    before = deepcopy((initial, physical))
    actual = api.recover_receiving_submitted_nfb_models_for_editor(initial, physical)
    assert actual == legacy.recover_submitted_nfb_models_for_editor(initial, physical)
    assert actual["models"] == [[REF], ""]
    assert actual["_restored_saved_nfb_models"] is True
    assert (initial, physical) == before
    # Never replace operator choices or trust a mismatch in source brand.
    richer = {**initial, "models": [[REF], ""]}
    assert api.recover_receiving_submitted_nfb_models_for_editor(richer, physical) == richer
    forged = deepcopy(physical)
    forged["nfb_config"]["holes"][0]["source_brand"] = "WRONG"
    assert api.recover_receiving_submitted_nfb_models_for_editor(initial, forged) == initial
    assert (initial, physical) == before


def test_fresh_model_slot_seed_matches_csv_owner_without_writing_saved_models():
    empty = ["", ""]
    initial = deepcopy(empty)
    result = api.initial_receiving_nfb_draft_models(empty, layer_count=1, selected_brand="士林")
    assert result == fresh.initial_fresh_receiving_nfb_models(empty, layer_count=1, selected_brand="士林")
    assert result is not empty and empty == initial
    assert api.initial_receiving_nfb_draft_models(empty, layer_count=1, selected_brand="OTHER") == empty
    assert api.initial_receiving_nfb_draft_models([REF, ""], layer_count=1, selected_brand="士林") == [REF, ""]
    with pytest.raises(ValueError):
        api.initial_receiving_nfb_draft_models([], layer_count=1, selected_brand="士林")
    assert empty == initial


def test_draft_tier_change_preserves_manual_y_and_rejects_invalid_without_mutation():
    original = shared.default_receiving_nfb_layer_heights(1)
    source = deepcopy(original)
    moved = api.transition_receiving_nfb_draft_layer_heights(
        source, old_count=1, new_count=2,
    )
    assert moved == shared.transition_receiving_nfb_layer_heights(
        source, old_count=1, new_count=2,
    )
    assert moved == shared.default_receiving_nfb_layer_heights(2)
    assert source == original
    manual = [610.0, 940.0]
    assert api.transition_receiving_nfb_draft_layer_heights(
        manual, old_count=1, new_count=2,
    ) == manual
    assert manual == [610.0, 940.0]
    for old_count, new_count, heights in (
        (1, 3, original), (False, 2, original), (1, 2, [float("nan"), 940.0]),
        (1, 2, [940.0, 610.0]),
    ):
        saved = deepcopy(heights)
        with pytest.raises((ValueError, TypeError)):
            api.transition_receiving_nfb_draft_layer_heights(
                heights, old_count=old_count, new_count=new_count,
            )
        assert heights == saved or (len(heights) == len(saved) and
                                   all((a != a and b != b) or a == b
                                       for a, b in zip(heights, saved)))


def test_gui_imports_all_three_source_draft_transitions_from_public_engine():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    banned = {"ae_engine.receiving_legacy_nfb_editor_bootstrap",
              "ae_engine.receiving_fresh_nfb_defaults",
              "ae_engine.receiving_shared_settings"}
    assert not [n for n in imports if n.module in banned]
    delegated = {alias.asname: alias.name for node in imports
                 if node.module == "ae_engine.manufacturing_api"
                 for alias in node.names if alias.asname is not None}
    assert delegated["recover_submitted_nfb_models_for_editor"] == "recover_receiving_submitted_nfb_models_for_editor"
    assert delegated["initial_fresh_receiving_nfb_models"] == "initial_receiving_nfb_draft_models"
    assert delegated["transition_receiving_nfb_layer_heights"] == "transition_receiving_nfb_draft_layer_heights"
