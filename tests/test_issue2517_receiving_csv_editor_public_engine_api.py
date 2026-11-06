# -*- coding: utf-8 -*-
"""#2517: original Receiving NFB CSV Hole Editor consumes one public Engine source."""
from __future__ import annotations

import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_nfb_csv_editor_features import (
    editor_nfb_features_from_csv as canonical_engine_owner,
)
from gui_modules.application import fold_designer_composition_receiving as gui


def test_public_operator_csv_draft_is_exact_original_engine_callable():
    assert "editor_nfb_features_from_csv" in ae_engine.__all__
    assert ae_engine.editor_nfb_features_from_csv is canonical_engine_owner
    assert api.editor_nfb_features_from_csv is canonical_engine_owner


def test_both_original_hole_editor_operations_delegate_without_private_geometry():
    source = inspect.getsource(gui)
    assert source.count("manufacturing_api.editor_nfb_features_from_csv(") == 2
    assert "from ae_engine.receiving_nfb_csv_editor_features import" not in source
    assert "openings = editor_nfb_features_from_csv(" not in source
    assert "stage(config, openings)" in source
    assert "stage_in_editor(config, openings)" in source


def test_public_entry_keeps_original_invalid_layer_rejection():
    # No caller may turn a bogus physical tier into a manufactured opening.
    invalid_config = {
        "layers": True,
        "layer_heights_mm": [330., 830.],
        "models": ["", ""],
        "features": {},
    }
    for call in (ae_engine.editor_nfb_features_from_csv,
                 api.editor_nfb_features_from_csv, canonical_engine_owner):
        with pytest.raises(ValueError, match="內門層數必須為 1 或 2"):
            call({"model": "受電箱"}, invalid_config)
