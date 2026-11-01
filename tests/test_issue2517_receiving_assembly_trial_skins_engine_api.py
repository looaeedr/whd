"""#2517 Engine owns source gates/triangles for assembled EAR/PAD 3D display."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import (
    manufacturing_api,
    ReceivingAssemblyTrialSkinMesh,
    project_receiving_assembly_trial_world_skin_meshes,
)
from ae_engine.receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
)
from ae_engine.receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier
from phase6_final_scene_renderer import Phase6FinalSceneRenderer


def _formed(snapshot):
    return tuple(build_receiving_formed_fixing_plate_skins(snapshot, e.ear_id)
                 for e in resolve_receiving_tier_ear_mating_xy(snapshot))


def _pad(**changes):
    defaults = dict(
        part_id="base_plate:nfb_pad:0", world_triangles=(
            ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)),
        ),
        manufacturing_ready=False, assembly_contact_certified=False,
        source_flat_and_bend_verified=True, actual_base_squares_present=True,
    )
    defaults.update(changes)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize("snapshot,quantity", ((_assembled, 2), (_two_tier, 4)))
def test_headless_real_source_ear_world_skin_projection_and_order(snapshot, quantity):
    rows = _formed(snapshot())
    before = repr(rows)
    result = manufacturing_api.project_receiving_assembly_trial_world_skin_meshes(
        formed_fixing_plate_skins=rows,
    )
    assert len(result) == quantity
    assert all(isinstance(mesh, ReceivingAssemblyTrialSkinMesh) for mesh in result)
    assert [mesh.role for mesh in result] == ["EAR"] * quantity
    assert [mesh.part_id for mesh in result] == [r.part_id for r in rows]
    for mesh, source in zip(result, rows):
        assert mesh.world_triangles == tuple(
            tuple(tuple(float(v) for v in p) for p in face.world)
            for face in source.mapped_world_skins
        )
        assert mesh.world_triangles
    assert repr(rows) == before
    assert manufacturing_api.project_receiving_assembly_trial_world_skin_meshes is (
        project_receiving_assembly_trial_world_skin_meshes
    )
    with pytest.raises(FrozenInstanceError):
        result[0].part_id = "forged"


def test_ear_hidden_is_display_only_and_does_not_hide_pad():
    ear = _formed(_assembled())
    pad = _pad()
    both = project_receiving_assembly_trial_world_skin_meshes(
        formed_fixing_plate_skins=ear, formed_nfb_pad_skins=(pad,),
    )
    assert [x.role for x in both] == ["EAR", "EAR", "PAD"]
    assert both[-1].world_triangles == pad.world_triangles
    hidden = project_receiving_assembly_trial_world_skin_meshes(
        formed_fixing_plate_skins=ear, formed_nfb_pad_skins=(pad,),
        show_fixing_plate_mesh=False,
    )
    assert [x.part_id for x in hidden] == [pad.part_id]
    assert project_receiving_assembly_trial_world_skin_meshes() == ()


@pytest.mark.parametrize("change", (
    {"source_bend_verified": False},
    {"actual_signed_forming_constructed": False},
    {"manufacturing_ready": True},
    {"weld_contact_verified": True},
    {"mapped_world_skins": ()},
))
def test_ear_invalid_source_or_forged_production_approval_fails_closed(change):
    first, second = _formed(_assembled())
    source = replace(first, **change)
    error = ("EAR_3D_FORMED_SKIN_EMPTY" if "mapped_world_skins" in change
             else "EAR_3D_SOURCE_OR_MANUFACTURING_GATE_FAILED")
    with pytest.raises(ValueError, match=error):
        project_receiving_assembly_trial_world_skin_meshes(
            formed_fixing_plate_skins=(source, second),
        )
    # The existing visibility option only hides meshes, not a safety release.
    assert project_receiving_assembly_trial_world_skin_meshes(
        formed_fixing_plate_skins=(source,), show_fixing_plate_mesh=False,
    ) == ()


@pytest.mark.parametrize("change", (
    {"manufacturing_ready": True},
    {"assembly_contact_certified": True},
    {"source_flat_and_bend_verified": False},
    {"actual_base_squares_present": False},
    {"world_triangles": ()},
))
def test_pad_invalid_source_or_forged_mfg_approval_is_rejected(change):
    error = ("PAD_3D_PREVIEW_EMPTY_MESH" if "world_triangles" in change
             else "PAD_3D_PREVIEW_SOURCE_OR_MFG_GATE_INVALID")
    with pytest.raises(ValueError, match=error):
        project_receiving_assembly_trial_world_skin_meshes(
            formed_nfb_pad_skins=(_pad(**change),),
        )


def test_gui_consumes_engine_meshes_without_physical_source_rules():
    src = inspect.getsource(Phase6FinalSceneRenderer.render)
    assert "manufacturing_api.project_receiving_assembly_trial_world_skin_meshes(" in src
    body = src[src.index("trial_skins = manufacturing_api."):src.index(
        "# EAR contact lines are MARKING on the mother SIDE plate")]
    for forbidden in (
        "source_bend_verified", "manufacturing_ready",
        "assembly_contact_certified", "actual_base_squares_present",
        "mapped_world_skins", "world_triangles or ()",
    ):
        assert forbidden not in body
    from ae_engine import receiving_assembly_trial_display_skins as owner
    own = inspect.getsource(owner)
    for forbidden in ("from phase6_", "import phase6_", "gui_modules",
                      "tkinter", "matplotlib"):
        assert forbidden not in own
