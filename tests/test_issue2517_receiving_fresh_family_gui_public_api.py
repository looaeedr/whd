# -*- coding: utf-8 -*-
"""#2517 GUI Receiving first switch uses the canonical public Family/NFB owners."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy
from ae_engine.receiving_fresh_nfb_defaults import seed_fresh_receiving_nfb_source
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from ae_engine.sheetmetal_feature_core import ProfileFeature
from phase6_project_file import _encode, _decode


@pytest.mark.parametrize("public,owner", [
    ("operator_apply_fresh_family_defaults", policy.apply_fresh_family_defaults),
    ("operator_resolve_box_body_structure_state", policy.resolve_box_body_structure_state),
    ("operator_endcap_bottom_selection", policy.endcap_bottom_selection),
    ("operator_new_receiving_layout", new_receiving_layout),
    ("operator_seed_fresh_receiving_nfb_source", seed_fresh_receiving_nfb_source),
    ("migrate_operator_assembly_joint_snapshot", migrate_legacy_snapshot_joints),
])
def test_gui_fresh_receiving_public_api_is_original_engine_callable(public, owner):
    assert getattr(api, public) is owner
    assert getattr(ae_engine, public) is owner


def test_gui_family_switch_call_sites_no_longer_import_private_mfg_sources():
    src = Path(__file__).resolve().parents[1].joinpath(
        "gui_modules", "application", "cabinet_controller.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "manufacturing_api"
    ]
    for name in (
        "operator_apply_fresh_family_defaults", "operator_resolve_box_body_structure_state",
        "operator_endcap_bottom_selection", "operator_new_receiving_layout",
        "operator_seed_fresh_receiving_nfb_source", "migrate_operator_assembly_joint_snapshot",
    ):
        assert calls.count(name) == 1
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module in {
            "ae_engine.cabinet_types", "ae_engine.assembly_joint",
            "ae_engine.receiving_fresh_nfb_defaults", "ae_engine.receiving_layout",
        } for node in ast.walk(tree)
    )


def _first_switch_snapshot(api_owner):
    values = api_owner.operator_apply_fresh_family_defaults({"t": 2}, "受電箱")
    original = deepcopy(values)
    values["receiving_layout"] = api_owner.operator_new_receiving_layout(
        width=values["w"], height=values["h"], depth=values["d"],
    )
    values["active_mode"] = "set_bay"
    state = api_owner.operator_seed_fresh_receiving_nfb_source(values)
    assert original["model"] == "受電箱"
    assert values["receiving_layout"]["sets"][0]["bays"][0].get("nfb_config_submitted") is not True
    return state


def test_public_first_switch_matches_direct_owner_and_saved_physical_nfb():
    seeded = _first_switch_snapshot(api)
    original = policy.apply_fresh_family_defaults({"t": 2}, "受電箱")
    original["receiving_layout"] = new_receiving_layout(
        width=original["w"], height=original["h"], depth=original["d"],
    )
    original["active_mode"] = "set_bay"
    expected = seed_fresh_receiving_nfb_source(original)
    assert seeded == expected
    assert api.operator_resolve_box_body_structure_state(
        "受電箱", None
    ) == policy.resolve_box_body_structure_state("受電箱", None)
    assert api.operator_endcap_bottom_selection("受電箱") == policy.endcap_bottom_selection("受電箱")
    assert seeded["nfb_config_submitted"] is True
    features = [f for row in seeded["part_features"].values() for f in row]
    assert len(features) == 1 and isinstance(features[0], ProfileFeature)
    assert features[0].source_type == "NFB_CSV_SOURCE"
    assert features[0].layer == "CUTTING"
    saved = _decode(_encode(seeded))
    assert saved["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] == (
        seeded["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]
    )
    assert api.operator_seed_fresh_receiving_nfb_source(seeded) == seeded


def test_invalid_family_bay_and_csv_source_does_not_mutate_input():
    base = {"t": 2}
    snapshot = deepcopy(base)
    settings = api.operator_apply_fresh_family_defaults(base, "受電箱")
    assert base == snapshot
    assert settings is not base
    for invalid in (0, float("nan"), float("inf"), True):
        with pytest.raises((TypeError, ValueError)):
            api.operator_new_receiving_layout(width=invalid, height=1600, depth=350)
    state = deepcopy(settings)
    state["active_mode"] = "quantity"
    original = deepcopy(state)
    with pytest.raises(ValueError, match="RECEIVING_FRESH_NFB_EXPECTS_SET_BAY"):
        api.operator_seed_fresh_receiving_nfb_source(state)
    assert state == original

    joint = {"assembly_joint_schema_version": 999, "assembly_joints": []}
    unchanged = deepcopy(joint)
    with pytest.raises(ValueError):
        api.migrate_operator_assembly_joint_snapshot(joint)
    assert joint == unchanged
