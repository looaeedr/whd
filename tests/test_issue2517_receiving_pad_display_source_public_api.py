# -*- coding: utf-8 -*-
"""#2517 actual PAD source and cache are Engine API, never a GUI MFG decision."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from ae_engine.receiving_nfb_committed_final_scene import apply_committed_csv_v5_to_canonical_parts


def _real_pad_source():
    snap = _current()
    snap["receiving_base_plate"] = {
        "pattern": "LEFT_FLAT_SIDE", "height": 340.,
        "shrink_top": 20., "shrink_bottom": 20.,
        "shrink_left": 45., "shrink_right": 45., "bend": 20.,
    }
    rows = snap["nfb_config"]["holes"]
    rows[0].update(model_filename="nfbv5:士林:3P400SN", source_brand="士林")
    rows[1].update(model_filename="nfbv5:士林:100HN-s", source_brand="士林", rotation_deg=0)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    base = _make(snap)
    actual = apply_committed_csv_v5_to_canonical_parts(snap, (base,))
    return snap, actual


def test_real_committed_base_cutting_and_pad_world_skins_via_public_engine():
    snapshot, actual = _real_pad_source()
    assert manufacturing_api.receiving_pad_assembly_display_active(snapshot)
    fingerprint = manufacturing_api.receiving_pad_assembly_display_source_key(snapshot, actual)
    skins = manufacturing_api.resolve_receiving_pad_assembly_display_skins(snapshot, actual)
    assert isinstance(fingerprint, str) and len(fingerprint) == 64
    assert len(skins) == 1
    assert skins[0].owner_hole_id == snapshot["nfb_config"]["holes"][1]["physical_hole_id"]
    assert skins[0].parent_base_id == "base_plate"
    assert skins[0].four_tab_mesh_mating_verified
    assert skins[0].base_slab_collision_verified
    assert not skins[0].manufacturing_ready
    assert not skins[0].assembly_contact_certified
    assert skins[0].world_triangles


def test_unsubmitted_and_vault_cannot_display_pad_or_make_mfg():
    for source in (
        {"model": "金庫型", "nfb_config_submitted": True},
        {"model": "受電箱", "nfb_config_submitted": False},
        {"model": "受電箱"},
    ):
        assert not manufacturing_api.receiving_pad_assembly_display_active(source)
        assert manufacturing_api.resolve_receiving_pad_assembly_display_skins(source, ()) == ()


def test_claimed_manufacture_is_rejected_by_engine_not_gui(monkeypatch):
    import ae_engine.receiving_nfb_pad_assembly_preview as source
    bogus = SimpleNamespace(manufacturing_ready=True, assembly_contact_certified=False)
    monkeypatch.setattr(source, "build_committed_pad_assembly_display", lambda _s, _p: (bogus,))
    with pytest.raises(ValueError, match="PAD_DISPLAY_MFG_OR_CONTACT_GATE_INVALID"):
        manufacturing_api.resolve_receiving_pad_assembly_display_skins(
            {"model": "受電箱", "nfb_config_submitted": True}, (),
        )


def test_gui_delegates_source_validation_to_public_engine(monkeypatch):
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter
    view = Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    view._formed_pad_display_cache = None
    view.last_formed_pad_display_blocker = None
    calls = []
    parent = SimpleNamespace(part_key="base_plate")
    skin = SimpleNamespace(parent_base_id="base_plate", part_id="pad:real")
    monkeypatch.setattr(manufacturing_api, "receiving_pad_assembly_display_active", lambda _: True)
    monkeypatch.setattr(manufacturing_api, "receiving_pad_assembly_display_source_key", lambda *_: "real-source")
    def resolve(*args):
        calls.append(args)
        return (skin,)
    monkeypatch.setattr(manufacturing_api, "resolve_receiving_pad_assembly_display_skins", resolve)
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    assert view._formed_pad_assembly_preview(snapshot, {"base_plate"}, (parent,)) == (skin,)
    assert view._formed_pad_assembly_preview(snapshot, {"base_plate"}, (parent,)) == (skin,)
    assert len(calls) == 1
    assert view._formed_pad_assembly_preview(snapshot, set(), (parent,)) == ()
    assert view.last_formed_pad_display_blocker is None
