"""#2517: one canonical true-T world skin solver for 2D/3D clients."""
from __future__ import annotations

from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_settings_assembly_mesh as engine
import phase6_final_scene_projection as gui


def test_real_receiving_side_back_physical_world_skins_same_for_2d_and_3d():
    from tests.test_piece_level_joint_geometry import _receiving_body_part

    body = _receiving_body_part()
    dims = (800.0, 600.0, 350.0)
    before = tuple(piece.render_data.material.wkb for piece in body.render_data.pieces)
    actual = api.resolve_box_body_true_world_piece_meshes(
        body, dimensions=dims, thickness=2.0,
    )
    source = api.build_joint_world_geometry(
        (body,), dims, 2.0,
    )["world_triangles_by_part"]
    assert [piece.role for piece, _ in actual] == [
        "left_side", "back", "right_side",
    ]
    assert all(mesh == tuple(source["box_body:" + piece.role]) for piece, mesh in actual)
    assert gui._phase6_box_body_true_world_piece_meshes(
        body, dimensions=dims, thickness=2.0,
    ) == actual
    inspection = api.resolve_receiving_settings_assembly_world_meshes(
        (body,), finished_dimensions=dims, thickness=2.0,
    )
    assert [(role, mesh) for role, _, mesh in inspection] == [
        (piece.role, mesh) for piece, mesh in actual
    ]
    assert before == tuple(piece.render_data.material.wkb for piece in body.render_data.pieces)


def test_previews_are_empty_and_bad_physical_width_fails_closed():
    stub = SimpleNamespace(
        part_key="box_body",
        render_data=SimpleNamespace(pieces=(SimpleNamespace(formed_w_end=0.0),)),
    )
    assert api.resolve_box_body_true_world_piece_meshes(
        stub, dimensions=(800, 600, 350), thickness=2,
    ) == ()
    assert api.resolve_box_body_true_world_piece_meshes(
        SimpleNamespace(part_key="box_body", render_data=SimpleNamespace(pieces=())),
        dimensions=(800, 600, 350), thickness=2,
    ) == ()
    corrupt = SimpleNamespace(
        part_key="box_body",
        render_data=SimpleNamespace(pieces=(SimpleNamespace(formed_w_end=True),)),
    )
    with pytest.raises(ValueError, match="BOX_BODY_PIECE_OUTSIDE_DATUM_INVALID"):
        api.resolve_box_body_true_world_piece_meshes(
            corrupt, dimensions=(800, 600, 350), thickness=2,
        )


def test_wrong_source_part_and_assembled_dimensions_fail_closed():
    from tests.test_piece_level_joint_geometry import _receiving_body_part

    body = _receiving_body_part()
    fake = SimpleNamespace(part_key="head", render_data=body.render_data)
    with pytest.raises(ValueError, match="must originate in box_body"):
        api.resolve_box_body_true_world_piece_meshes(
            fake, dimensions=(800, 600, 350), thickness=2,
        )
    with pytest.raises(ValueError, match="requires assembled W/H/D"):
        api.resolve_box_body_true_world_piece_meshes(
            body, dimensions=(800, 600), thickness=2,
        )


def test_finalscene_phase6_adapter_only_calls_public_engine_api(monkeypatch):
    marker = ((object(), (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)),)
    calls = []

    def fake(part, *, dimensions, thickness):
        calls.append((part, dimensions, thickness))
        return marker

    monkeypatch.setattr(api, "resolve_box_body_true_world_piece_meshes", fake)
    part = object()
    assert gui._phase6_box_body_true_world_piece_meshes(
        part, dimensions=(1, 2, 3), thickness=1.5,
    ) is marker
    assert calls == [(part, (1, 2, 3), 1.5)]
    gui_src = inspect.getsource(gui._phase6_box_body_true_world_piece_meshes)
    assert "manufacturing_api.resolve_box_body_true_world_piece_meshes" in gui_src
    assert "build_joint_world_geometry" not in gui_src
    assert "formed_w_end" not in gui_src
    engine_src = inspect.getsource(engine.resolve_receiving_settings_assembly_world_meshes)
    assert "resolve_box_body_true_world_piece_meshes(" in engine_src
