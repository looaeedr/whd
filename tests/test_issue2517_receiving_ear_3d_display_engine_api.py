# -*- coding: utf-8 -*-
"""#2517 Receiving EAR 3D display source is Engine-owned and never MFG-ready."""
from dataclasses import replace
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine import receiving_ear_display_sources as sources
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


@pytest.mark.parametrize("factory,count", [(_assembled, 2), (_two_tier, 4)])
def test_real_one_or_two_tier_ear_3d_uses_canonical_engine_sources(factory, count):
    snapshot = factory()
    formed = manufacturing_api.resolve_receiving_ear_assembly_display_skins(snapshot)
    assert len(formed) == count
    assert len({row.part_id for row in formed}) == count
    assert [row.base_part_id for row in formed] == (
        ["base_plate"] * 2 if count == 2
        else ["base_plate:nfb_layer:0"] * 2 + ["base_plate:nfb_layer:1"] * 2
    )
    assert all(
        row.source_bend_verified and row.mapped_world_skins
        and row.source_bend_y_mm == 23.0
        and row.actual_mid_surface_hinge_y_mm == 22.0
        and not row.weld_contact_verified
        and not row.manufacturing_ready
        for row in formed
    )
    assert manufacturing_api.receiving_ear_assembly_display_source_key(snapshot) == (
        sources.receiving_ear_assembly_display_source_key(snapshot)
    )


def test_ear_preview_never_claims_unsubmitted_manufacturing():
    original = _assembled()
    snapshot = deepcopy(original)
    snapshot["nfb_config_submitted"] = False
    assert manufacturing_api.resolve_receiving_ear_assembly_display_skins(snapshot) == ()
    snapshot["model"] = "金庫型"
    snapshot["nfb_config_submitted"] = True
    assert manufacturing_api.resolve_receiving_ear_assembly_display_skins(snapshot) == ()


def test_stale_bay_source_rejects_physical_ear_assembly():
    snapshot = deepcopy(_two_tier())
    snapshot["_receiving_runtime_selection"]["bay_id"] = "unknown-bay"
    with pytest.raises(ValueError):
        manufacturing_api.resolve_receiving_ear_assembly_display_skins(snapshot)


def test_forged_ear_mfg_readiness_never_painted(monkeypatch):
    snapshot = _assembled()
    actual = sources.build_receiving_formed_fixing_plate_skins(
        snapshot, "base_plate:fixing_plate:left",
    )
    monkeypatch.setattr(
        sources, "build_receiving_formed_fixing_plate_skins",
        lambda _snapshot, _part_id: replace(actual, manufacturing_ready=True),
    )
    with pytest.raises(ValueError, match="EAR_ASSEMBLY_DISPLAY_SOURCE_INCONSISTENT"):
        manufacturing_api.resolve_receiving_ear_assembly_display_skins(snapshot)


def test_final_scene_gui_calls_public_engine_and_only_caches(monkeypatch):
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter
    pane = object.__new__(Phase6FinalSceneViewAdapter)
    pane._formed_ear_display_cache = None
    pane.last_formed_ear_display_blocker = None
    calls = []
    sentinel = object()
    monkeypatch.setattr(
        manufacturing_api,
        "receiving_ear_assembly_display_source_key",
        lambda snapshot: "same-source",
    )
    def _engine(snap):
        calls.append(snap)
        return (sentinel,)
    monkeypatch.setattr(
        manufacturing_api, "resolve_receiving_ear_assembly_display_skins", _engine
    )
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    assert pane._formed_ear_assembly_preview(snapshot, set()) == (sentinel,)
    assert pane._formed_ear_assembly_preview(snapshot, set()) == (sentinel,)
    assert calls == [snapshot]
    assert pane.last_formed_ear_display_blocker is None
    # GUI does not know the manufacturing validator or reconstruct a new EAR.
    with pytest.raises(TypeError):
        sources.receiving_ear_assembly_display_source_key(None)
