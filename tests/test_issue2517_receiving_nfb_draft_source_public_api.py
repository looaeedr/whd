# -*- coding: utf-8 -*-
"""#2517 Receiving NFB editor source readbacks use the public Engine contract."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_fresh_nfb_defaults import initial_fresh_receiving_nfb_models
from ae_engine.receiving_legacy_nfb_editor_bootstrap import (
    recover_submitted_nfb_models_for_editor,
)
from ae_engine.receiving_shared_settings import transition_receiving_nfb_layer_heights


_GUI = (
    Path(__file__).resolve().parents[1]
    / "gui_modules/application/fold_designer_composition_receiving.py"
)


def _saved_pair():
    return {
        "nfb_config_submitted": True,
        "nfb_config": {
            "layer_count": 1,
            "holes": [
                {
                    "slot_index": 0, "model_filename": "nfbv5:士林:2P400",
                    "source_brand": "士林",
                },
                {
                    "slot_index": 1, "model_filename": "nfbv5:士林:3P125SN",
                    "source_brand": "士林",
                },
            ],
        },
    }


def test_public_editor_source_api_is_exact_existing_engine_owner():
    pairs = (
        (
            api.recover_receiving_submitted_nfb_models_for_editor,
            recover_submitted_nfb_models_for_editor,
        ),
        (api.initial_receiving_nfb_draft_models, initial_fresh_receiving_nfb_models),
        (
            api.transition_receiving_nfb_layer_heights,
            transition_receiving_nfb_layer_heights,
        ),
    )
    for public, canonical in pairs:
        assert public is canonical

    assert ae_engine.recover_receiving_submitted_nfb_models_for_editor is pairs[0][1]
    assert ae_engine.initial_receiving_nfb_draft_models is pairs[1][1]
    assert ae_engine.transition_receiving_nfb_layer_heights is pairs[2][1]
    for name in (
        "recover_receiving_submitted_nfb_models_for_editor",
        "initial_receiving_nfb_draft_models",
        "transition_receiving_nfb_layer_heights",
    ):
        assert name in ae_engine.__all__


def test_legacy_saved_pair_restore_parity_invalid_source_no_side_effects():
    initial = {
        "layers": 1, "models": ["nfbv5:士林:2P400", ""],
        "layer_heights_mm": [550.0, 830.0],
    }
    physical = _saved_pair()
    before = deepcopy((initial, physical))
    expected = recover_submitted_nfb_models_for_editor(initial, physical)
    actual = api.recover_receiving_submitted_nfb_models_for_editor(initial, physical)
    assert actual == expected
    assert actual["models"] == [
        ["nfbv5:士林:2P400", "nfbv5:士林:3P125SN"], ""
    ]
    assert actual["_restored_saved_nfb_models"] is True

    broken = deepcopy(physical)
    broken["nfb_config"]["holes"][1]["slot_index"] = 0
    assert api.recover_receiving_submitted_nfb_models_for_editor(initial, broken) == initial
    assert (initial, physical) == before


def test_fresh_draft_defaults_and_layer_count_transition_parity_and_rejection():
    models = ["", ""]
    first = deepcopy(models)
    # A non-default brand must not receive the Shihlin physical CSV model.
    assert api.initial_receiving_nfb_draft_models(
        models, layer_count=1, selected_brand="東元",
    ) == initial_fresh_receiving_nfb_models(
        models, layer_count=1, selected_brand="東元",
    ) == models
    assert models == first

    heights = [550.0, 830.0]
    before = deepcopy(heights)
    assert api.transition_receiving_nfb_layer_heights(
        heights, old_count=1, new_count=2,
    ) == transition_receiving_nfb_layer_heights(
        heights, old_count=1, new_count=2,
    ) == [330.0, 830.0]
    custom = [410.0, 830.0]
    assert api.transition_receiving_nfb_layer_heights(
        custom, old_count=1, new_count=2,
    ) == custom
    with pytest.raises(ValueError):
        api.initial_receiving_nfb_draft_models(
            [], layer_count=1, selected_brand="士林",
        )
    with pytest.raises(ValueError):
        api.transition_receiving_nfb_layer_heights(
            heights, old_count=1, new_count=True,
        )
    assert heights == before and models == first and custom == [410.0, 830.0]


def test_gui_receiving_editor_calls_public_source_api_not_private_imports():
    tree = ast.parse(_GUI.read_text(encoding="utf-8"))
    prohibited = {
        "ae_engine.receiving_legacy_nfb_editor_bootstrap",
        "ae_engine.receiving_fresh_nfb_defaults",
        "ae_engine.receiving_shared_settings",
    }
    assert not [
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in prohibited
    ]
    calls = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    }
    assert {
        "recover_receiving_submitted_nfb_models_for_editor",
        "initial_receiving_nfb_draft_models",
        "transition_receiving_nfb_layer_heights",
    } <= calls
