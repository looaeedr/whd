"""#2517: optional physical EAR/PAD 3D views honor one Engine Family Registry."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import receiving_ear_display_sources as ear
from ae_engine import receiving_pad_display_sources as pad
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier
from tests.test_issue2517_receiving_pad_display_source_public_api import _real_pad_source


_ALIASES = ("受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  ")


def _view():
    view = object.__new__(Phase6FinalSceneViewAdapter)
    view._formed_ear_display_cache = None
    view.last_formed_ear_display_blocker = None
    view._formed_pad_display_cache = None
    view.last_formed_pad_display_blocker = None
    return view


@pytest.mark.parametrize("family", _ALIASES)
def test_real_committed_ear_headless_and_gui_share_formed_3d_for_every_alias(family):
    original = _assembled()
    source = deepcopy(original)
    source["model"] = family
    before = deepcopy(source)

    assert api.receiving_ear_assembly_display_active(source) is True
    assert ae_engine.receiving_ear_assembly_display_active is (
        ear.receiving_ear_assembly_display_active
    )
    actual = api.resolve_receiving_ear_assembly_display_skins(source)
    baseline = api.resolve_receiving_ear_assembly_display_skins(original)
    assert len(actual) == len(baseline) == 2
    assert [(x.part_id, x.base_part_id, x.source_bend_y_mm)
            for x in actual] == [
                (x.part_id, x.base_part_id, x.source_bend_y_mm)
                for x in baseline
            ]
    assert all(
        item.source_bend_verified and item.mapped_world_skins
        and not item.manufacturing_ready and not item.weld_contact_verified
        for item in actual
    )

    gui = _view()
    assert gui._formed_ear_assembly_preview(source, set()) == actual
    assert gui._formed_ear_assembly_preview(source, set()) == actual
    assert gui.last_formed_ear_display_blocker is None
    assert source == before


def test_real_two_tier_ear_alias_uses_four_independent_physical_parents():
    source = deepcopy(_two_tier())
    source["model"] = "  ReCeIvInG  "
    assert api.receiving_ear_assembly_display_active(source)
    skins = api.resolve_receiving_ear_assembly_display_skins(source)
    assert len(skins) == 4
    assert [x.base_part_id for x in skins] == (
        ["base_plate:nfb_layer:0"] * 2
        + ["base_plate:nfb_layer:1"] * 2
    )
    assert all(not x.manufacturing_ready for x in skins)


@pytest.mark.parametrize("family", ("receiving", "  ReCeIvInG  "))
def test_real_verified_pad_base_2d_cuts_feed_same_formal_3d_display(family):
    original, original_parts = _real_pad_source()
    snapshot = deepcopy(original)
    snapshot["model"] = family
    before = deepcopy(snapshot)
    assert api.receiving_pad_assembly_display_active(snapshot)
    assert ae_engine.receiving_pad_assembly_display_active is (
        pad.receiving_pad_assembly_display_active
    )

    baseline = api.resolve_receiving_pad_assembly_display_skins(original, original_parts)
    actual = api.resolve_receiving_pad_assembly_display_skins(snapshot, original_parts)
    assert baseline and actual
    assert [(x.part_id, x.parent_base_id, x.owner_hole_id) for x in baseline] == [
        (x.part_id, x.parent_base_id, x.owner_hole_id) for x in actual
    ]
    assert all(
        item.four_tab_mesh_mating_verified
        and item.base_slab_collision_verified
        and item.world_triangles
        and not item.manufacturing_ready
        and not item.assembly_contact_certified
        for item in actual
    )
    assert any(
        primitive.layer == "CUTTING"
        for part in original_parts
        for primitive in part.render_data.scene.primitives
        if hasattr(part, "render_data")
    )

    gui = _view()
    assert gui._formed_pad_assembly_preview(
        snapshot, {"base_plate"}, original_parts,
    ) == actual
    assert gui.last_formed_pad_display_blocker is None
    assert snapshot == before


def test_true_project_save_reload_preserves_registered_ear_source_and_3d(tmp_path):
    import phase6_project_file as project

    snapshot = deepcopy(_assembled())
    snapshot["model"] = "receiving"
    target = project.write_project(
        tmp_path / "real-receiving-ear-alias.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": snapshot},
    )
    stored = project.read_project(target)["snapshot"]
    assert api.operator_canonical_family_name(stored) == "受電箱"
    assert api.receiving_ear_assembly_display_active(stored)
    assert [skin.part_id for skin in api.resolve_receiving_ear_assembly_display_skins(stored)] == [
        skin.part_id for skin in api.resolve_receiving_ear_assembly_display_skins(snapshot)
    ]
    # An independently serialized operator source must keep the same domain gate.
    json_source = json.loads(json.dumps(stored, ensure_ascii=False))
    assert api.receiving_ear_assembly_display_active(json_source)


@pytest.mark.parametrize("source", (
    {"model": "金庫型", "nfb_config_submitted": True},
    {"model": "UNKNOWN", "nfb_config_submitted": True},
    {"model": "receiving", "nfb_config_submitted": False},
    {"model": "receiving", "nfb_config_submitted": "true"},
    {"model": "receiving", "nfb_config_submitted": 1},
    {"cabinet_type": "receiving", "nfb_config_submitted": None},
    [],
    None,
))
def test_invalid_or_uncommitted_family_cannot_create_optional_physical_3d(source):
    assert not api.receiving_ear_assembly_display_active(source)
    assert not api.receiving_pad_assembly_display_active(source)
    if isinstance(source, dict):
        assert api.resolve_receiving_ear_assembly_display_skins(source) == ()
        assert api.resolve_receiving_pad_assembly_display_skins(source, ()) == ()


def test_final_scene_gui_has_no_second_family_or_submitted_gate_for_ear_3d():
    owner = inspect.getsource(Phase6FinalSceneViewAdapter._formed_ear_assembly_preview)
    assert "manufacturing_api.receiving_ear_assembly_display_active(snapshot)" in owner
    assert 'snapshot.get("model")' not in owner
    assert 'snapshot.get("nfb_config_submitted")' not in owner
    material = inspect.getsource(pad.receiving_pad_assembly_display_active)
    assert "cabinet_family_policy.canonical_family_name(snapshot)" in material
    mesh_source = inspect.getsource(
        __import__("ae_engine.receiving_nfb_pad_assembly_preview",
                   fromlist=["build_committed_pad_assembly_display"])
        .build_committed_pad_assembly_display
    )
    assert "receiving_pad_assembly_display_active(snapshot)" in mesh_source
