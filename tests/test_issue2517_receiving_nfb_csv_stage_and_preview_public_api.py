# -*- coding: utf-8 -*-
"""#2517 Receiving NFB CSV model-source gating and Bay dimensions via public API."""
from copy import deepcopy
import ast
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.display_dimensions import resolve_operator_finished_dimensions as canonical_dimensions
from ae_engine.receiving_nfb_model_identity import (
    can_stage_receiving_nfb_csv_preview_refs as owner_gate,
    display_model_ref as owner_display,
    is_numeric_model_ref,
)

GUI = (
    Path(__file__).resolve().parents[1]
    / "gui_modules/application/fold_designer_composition_receiving.py"
)


def test_public_nfb_identity_projection_reuses_source_owner():
    assert api.can_stage_receiving_nfb_csv_preview_refs is owner_gate
    assert ae_engine.can_stage_receiving_nfb_csv_preview_refs is owner_gate
    assert api.display_receiving_nfb_model_ref is owner_display
    assert ae_engine.display_receiving_nfb_model_ref is owner_display
    assert {"can_stage_receiving_nfb_csv_preview_refs",
            "display_receiving_nfb_model_ref"} <= set(ae_engine.__all__)


@pytest.mark.parametrize("selected", (
    [],
    ["nfbv5:士林:2P400"],
    ["nfbv5:士林:2P400", "nfbv5:士林:3P125SN"],
    ["legacy2pole.dxf"],
    ["nfbv5:士林:2P400", "legacy2pole.dxf"],
    [None],
    ["nfbv5:不存在廠牌:2P400"],
))
def test_v5_csv_preview_gate_matches_previous_gui_and_never_mutates(selected):
    before = deepcopy(selected)
    expected = not selected or all(is_numeric_model_ref(item) for item in selected)
    assert api.can_stage_receiving_nfb_csv_preview_refs(selected) is expected
    assert selected == before
    assert api.can_stage_receiving_nfb_csv_preview_refs(tuple(selected)) is expected


def test_bad_stage_collection_is_rejected_before_source_commit():
    for value in (None, "", "nfbv5:士林:2P400", {}, 1, True):
        with pytest.raises(ValueError, match="NFB_CSV_PREVIEW_REFS_SEQUENCE_REQUIRED"):
            api.can_stage_receiving_nfb_csv_preview_refs(value)
    assert api.display_receiving_nfb_model_ref("nfbv5:士林:2P400") == "2P400"
    with pytest.raises(ValueError):
        api.display_receiving_nfb_model_ref("nfbv5:未知品牌:bad")


def test_public_bay_finished_dimensions_match_canonical_source_2d_3d():
    source = {"model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
    settings = {"t": 2.0}
    before = deepcopy((source, settings))
    direct = canonical_dimensions("box_body", snapshot=source, settings=settings)
    public = api.resolve_operator_finished_dimensions(
        "box_body", snapshot=source, settings=settings,
    )
    assert public == direct == (800.0, 1600.0, 350.0)
    assert (source, settings) == before


def test_fold_designer_uses_public_bay_and_csv_gate_not_private_imports():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    prohibited = (
        "ae_engine.display_dimensions",
        "ae_engine.receiving_nfb_model_identity",
        "ae_engine.receiving_switch_model_catalog",
    )
    assert not [
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in prohibited
    ]
    names = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    }
    assert {
        "resolve_operator_finished_dimensions",
        "display_receiving_nfb_model_ref",
        "can_stage_receiving_nfb_csv_preview_refs",
    } <= names
