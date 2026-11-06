"""#2517 canonical BoxBody collision source mesh is Engine-owned."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from ae_engine import manufacturing_api, project_box_body_collision_source_mesh
from ae_engine.assembly_geometry import thicken_triangle_surface
from phase6_final_scene_renderer import Phase6FinalSceneRenderer


def _mid_surface():
    return (((0., 0., 0.), (10., 0., 0.), (0., 10., 0.)),)


def test_resolved_physical_world_skins_are_not_thickened_again():
    mid = _mid_surface()
    already_solid = thicken_triangle_surface(mid, 2.)
    piece = SimpleNamespace(role="left")
    data = SimpleNamespace(pieces=(piece,))
    result = project_box_body_collision_source_mesh(
        data, box_body_world=mid,
        placed_piece_meshes=((piece, already_solid),),
        physical_piece_world=((piece, already_solid),),
        thickness=2.,
    )
    assert result == already_solid
    assert len(result) == len(already_solid)
    assert manufacturing_api.project_box_body_collision_source_mesh is (
        project_box_body_collision_source_mesh
    )


def test_unresolved_piece_mid_surfaces_and_integral_need_exactly_one_T():
    mid = _mid_surface()
    piece = SimpleNamespace(role="left")
    expected = thicken_triangle_surface(mid, 2.)
    pieces = SimpleNamespace(pieces=(piece,))
    assert project_box_body_collision_source_mesh(
        pieces, box_body_world=mid,
        placed_piece_meshes=((piece, mid),),
        thickness=2.,
    ) == expected
    assert project_box_body_collision_source_mesh(
        SimpleNamespace(pieces=()), box_body_world=mid,
        thickness=2.,
    ) == expected
    assert project_box_body_collision_source_mesh(
        pieces, box_body_world=mid, thickness=2.,
    ) == ()
    assert project_box_body_collision_source_mesh(
        SimpleNamespace(pieces=()), box_body_world=(), thickness=2.,
    ) == ()


def test_display_must_use_public_engine_and_leave_physical_solver_out():
    src = inspect.getsource(Phase6FinalSceneRenderer)
    snippet = src[src.index('if bool(getattr(render_data, "show_interference", False)):'):]
    snippet = snippet[:snippet.index('if getattr(part_data, "pieces", None):')]
    assert "manufacturing_api.project_box_body_collision_source_mesh(" in snippet
    assert "collision.extend(" not in snippet
    assert "thicken_triangle_surface(" not in snippet
    from ae_engine import box_body_collision_source_mesh as owner
    own = inspect.getsource(owner)
    for forbidden in ("phase6_", "tkinter", "matplotlib"):
        assert forbidden not in own
