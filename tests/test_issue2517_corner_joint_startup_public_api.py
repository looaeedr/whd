# -*- coding: utf-8 -*-
"""#2517 GUI startup corner/Joint manufacturing state only uses public Engine."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from ae_engine.corner_type_ui import (
    apply_box_assembly_type, assembly_type_from_corner_state,
    new_manual_corner_pair_same_state, new_manual_corner_state,
)
from ae_engine.endcap_factory_fold import selection_from_raw, selection_to_raw
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection


def test_startup_public_api_exports_exact_existing_engine_owner():
    for public, original in (
        ("operator_new_manual_corner_state", new_manual_corner_state),
        ("operator_new_manual_corner_pair_same_state", new_manual_corner_pair_same_state),
        ("operator_assembly_type_from_corner_state", assembly_type_from_corner_state),
        ("operator_apply_box_assembly_type", apply_box_assembly_type),
        ("migrate_operator_assembly_joint_snapshot", migrate_legacy_snapshot_joints),
    ):
        assert getattr(api, public) is original
        assert getattr(ae_engine, public) is original

    root = Path(__file__).resolve().parents[1]
    source = root.joinpath("gui_modules", "application", "state_sync.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    ]
    for name in (
        "operator_new_manual_corner_state", "operator_new_manual_corner_pair_same_state",
        "operator_assembly_type_from_corner_state", "operator_apply_box_assembly_type",
        "migrate_operator_assembly_joint_snapshot",
    ):
        assert called.count(name) == 1
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module in {
            "ae_engine.corner_type_ui", "ae_engine.assembly_joint",
        } for node in ast.walk(tree)
    )


@pytest.mark.parametrize("initial", [CornerTypeId.INSERT, CornerTypeId.OVERLAY, CornerTypeId.INSERT_OVERLAY])
def test_public_corner_startup_matches_direct_engine_and_serialized_head_tail(initial):
    keys = ("head", "tail", "door", "base_plate")
    state = api.operator_new_manual_corner_state(keys)
    pairs = api.operator_new_manual_corner_pair_same_state(keys)
    assert state == new_manual_corner_state(keys)
    assert pairs == new_manual_corner_pair_same_state(keys)
    # A saved explicit Head/Tail type is retained by existing assembly intent precedence.
    for part in ("head", "tail"):
        state[part]["top_left"] = CornerTypeSelection(initial)
        state[part]["top_right"] = CornerTypeSelection(initial)
    direct_state, direct_pairs = deepcopy(state), deepcopy(pairs)
    inferred = api.operator_assembly_type_from_corner_state(state)
    assert inferred == assembly_type_from_corner_state(direct_state)
    api.operator_apply_box_assembly_type(state, pairs, inferred, reset_bottom_defaults=True)
    apply_box_assembly_type(direct_state, direct_pairs, inferred, reset_bottom_defaults=True)
    assert (state, pairs) == (direct_state, direct_pairs)

    saved = json.loads(json.dumps({
        part: {key: selection_to_raw(value) for key, value in corners.items()}
        for part, corners in state.items()
    }))
    restored = {
        part: {key: selection_from_raw(value) for key, value in corners.items()}
        for part, corners in saved.items()
    }
    assert restored == state


def test_invalid_assembly_and_joint_startup_sources_are_unchanged():
    state = new_manual_corner_state(("head", "tail"))
    pairs = new_manual_corner_pair_same_state(("head", "tail"))
    original = deepcopy((state, pairs))
    with pytest.raises(ValueError):
        api.operator_apply_box_assembly_type(state, pairs, "UNSUPPORTED_ASSEMBLY")
    assert (state, pairs) == original
    with pytest.raises(ValueError):
        api.operator_apply_box_assembly_type(state, pairs, CornerTypeId.CROSS)
    assert (state, pairs) == original

    source = {"assembly_joint_schema_version": 999, "assembly_type": "INSERT", "assembly_joints": []}
    original_source = deepcopy(source)
    with pytest.raises(ValueError):
        api.migrate_operator_assembly_joint_snapshot(source)
    assert source == original_source


def test_public_joint_startup_migration_matches_owner_without_changing_original():
    source = {"assembly_type": "INSERT_OVERLAY", "existing_parts": ["box_body", "head", "tail"]}
    original = deepcopy(source)
    assert api.migrate_operator_assembly_joint_snapshot(source) == migrate_legacy_snapshot_joints(source)
    assert source == original
