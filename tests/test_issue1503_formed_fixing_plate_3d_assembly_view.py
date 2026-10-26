# -*- coding: utf-8 -*-
"""#1503 T2/BEND23 source-formed EAR meshes in the *actual* assembly 3D view."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from phase6_final_scene_contracts import AssemblySceneRenderData
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _view():
    adapter = Phase6FinalSceneViewAdapter.__new__(Phase6FinalSceneViewAdapter)
    adapter._formed_ear_display_cache = None
    adapter.last_formed_ear_display_blocker = None
    return adapter


@pytest.mark.parametrize("fixture,quantity", ((_assembled, 2), (_two_tier, 4)))
def test_actual_signed_source_formed_skins_keep_physical_owner_when_base_hidden(
    fixture, quantity,
):
    snap = fixture()
    view = _view()
    visible = {"base_plate"} if quantity == 2 else {
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    }
    formed = view._formed_ear_assembly_preview(snap, visible)
    assert len(formed) == quantity
    assert len({r.part_id for r in formed}) == quantity
    assert view.last_formed_ear_display_blocker is None
    assert [r.side for r in formed] == ["left", "right"] * (quantity // 2)
    for row in formed:
        assert row.source_sheet_t_mm == pytest.approx(2.)
        assert row.source_bend_y_mm == pytest.approx(23.)
        assert row.actual_mid_surface_hinge_y_mm == pytest.approx(22.)
        assert row.actual_signed_forming_constructed
        assert row.side_wall_skin_contact_x_verified
        assert row.mapped_world_skins
        assert row.parent_base_back_skin_world_z_mm is not None
        assert not row.weld_contact_verified
        assert not row.side_sheet_uv_marking_ready
        assert not row.manufacturing_ready
    # Configure/resize redraw must re-use the exact immutable world mesh.
    assert view._formed_ear_assembly_preview(snap, visible) is not None
    again = view._formed_ear_assembly_preview(snap, visible)
    assert all(a is b for a, b in zip(formed, again))
    # Parent ownership is physical, NOT the 3D checkbox. Hiding the Base
    # Plate must retain the same certified EAR world skins at their true Z.
    without_base = view._formed_ear_assembly_preview(snap, set())
    assert len(without_base) == quantity
    assert all(a is b for a, b in zip(formed, without_base))
    assert [row.base_part_id for row in without_base] == [
        row.base_part_id for row in formed
    ]
    if quantity == 4:
        first_base_hidden = view._formed_ear_assembly_preview(
            snap, {"base_plate:nfb_layer:0"},
        )
        assert len(first_base_hidden) == quantity
        assert all(a is b for a, b in zip(formed, first_base_hidden))


def test_forming_cache_invalidates_for_an_other_bay_or_changed_csv_source():
    snap = _two_tier()
    view = _view()
    visible = {"base_plate:nfb_layer:0", "base_plate:nfb_layer:1"}
    before = view._formed_ear_assembly_preview(snap, visible)
    original_cache_key = view._formed_ear_display_cache[0]
    changed = deepcopy(snap)
    changed["_receiving_runtime_selection"]["bay_id"] = "other-bay"
    assert view._formed_ear_assembly_preview(changed, visible) == ()
    assert view.last_formed_ear_display_blocker
    assert view._formed_ear_display_cache[0] != original_cache_key
    restored = view._formed_ear_assembly_preview(snap, visible)
    assert len(restored) == 4 and all(x is not y for x, y in zip(before, restored))


def test_unsubmitted_source_never_creates_a_fake_production_ear():
    snap = _assembled()
    snap["nfb_config_submitted"] = False
    view = _view()
    assert view._formed_ear_assembly_preview(snap, {"base_plate"}) == ()
    assert view._formed_ear_display_cache is None


def test_assembly_scene_contract_contains_only_display_ear_field():
    from phase6_final_scene_projection import make_assembly_scene_render_data
    row = SimpleNamespace(
        part_id="ear", source_bend_verified=True,
        manufacturing_ready=False, weld_contact_verified=False,
    )
    render = make_assembly_scene_render_data(
        assembly_parts=(), formed_fixing_plate_skins=(row,),
    )
    assert isinstance(render, AssemblySceneRenderData)
    assert render.formed_fixing_plate_skins == (row,)
    assert render.assembly_parts == ()  # Not a manufacturing part.


def test_actual_renderer_draws_world_ear_skins_without_mesh_grid_lines():
    from matplotlib.figure import Figure
    from shapely.geometry import box
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_final_scene_contracts import (
        AssemblyScenePart, FinalSceneViewRequest,
    )
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer

    snapshot = _assembled()
    formed = _view()._formed_ear_assembly_preview(snapshot, {"base_plate"})
    fig = Figure()
    axis = fig.add_subplot(111, projection="3d")
    renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=axis))
    mat = box(0, 0, 10, 10)
    root = AssemblyScenePart(
        part_key="base_plate",
        render_data=SimpleNamespace(
            material=mat, scene=DrawingScene(), fold_guides=(),
            metadata={"manufacturing_ready": False},
        ),
        x_profile=({"len": 10., "core": "D"},),
        y_profile=({"len": 10., "core": "D"},),
    )
    scene = AssemblySceneRenderData(
        assembly_parts=(root,), visible_part_keys=("base_plate",),
        formed_fixing_plate_skins=formed,
    )
    request = FinalSceneViewRequest(
        render_data=scene, x_profile=(), y_profile=(),
        part_key="assembly", thickness=2.,
        finished_dimensions=(800., 1600., 350.),
    )
    world = renderer.render(request)
    assert len(world) > 2
    assert renderer.last_formed_ear_display_ids == (
        "base_plate:fixing_plate:left",
        "base_plate:fixing_plate:right",
    )
    # The overlay is a smooth filled surface (no mesh-grid wire overlay).
    assert len(axis.collections) >= 3
    assert renderer.last_cutting_mesh == world
