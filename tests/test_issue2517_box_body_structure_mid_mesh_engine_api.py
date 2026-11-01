"""#2517: physical Box Body assembly mid-mesh belongs to public Engine."""
from __future__ import annotations

from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_settings_assembly_mesh as engine
from phase6_final_scene_projection import _phase6_box_body_structure_meshes


def test_actual_receiving_three_piece_mid_mesh_same_source_for_3d_and_2d():
    from tests.test_piece_level_joint_geometry import _receiving_body_part
    body = _receiving_body_part()
    render = body.render_data
    before = tuple(piece.render_data.material.wkb for piece in render.pieces)
    rows = api.resolve_box_body_structure_mid_meshes(render, thickness=2.0)
    assert len(rows) == 3
    assert [piece.role for piece, _mesh in rows] == [
        "left_side", "back", "right_side",
    ]
    assert all(mesh for _piece, mesh in rows)
    assert _phase6_box_body_structure_meshes(render, thickness=2.0) == list(rows)
    assert tuple(piece.render_data.material.wkb for piece in render.pieces) == before
    source = inspect.getsource(engine.resolve_receiving_settings_assembly_world_meshes)
    assert "resolve_box_body_structure_mid_meshes(data, thickness=thickness)" in source


def test_preview_only_datum_remains_empty_and_corruption_fails_closed():
    preview = SimpleNamespace(pieces=(SimpleNamespace(formed_w_end=0.0),))
    assert api.resolve_box_body_structure_mid_meshes(preview, thickness=2.0) == ()
    assert _phase6_box_body_structure_meshes(preview, thickness=2.0) == []
    bad = SimpleNamespace(pieces=(SimpleNamespace(formed_w_end=True),))
    with pytest.raises(ValueError, match="BOX_BODY_PIECE_OUTSIDE_DATUM_INVALID"):
        api.resolve_box_body_structure_mid_meshes(bad, thickness=2.0)


def test_finalscene_gui_is_only_public_engine_adapter(monkeypatch):
    called = []
    part = object()
    sentinel = ((part, (((0, 0, 0), (1, 0, 0), (0, 1, 0)),)),)

    def fake(render_data, *, thickness):
        called.append((render_data, thickness))
        return sentinel

    monkeypatch.setattr(api, "resolve_box_body_structure_mid_meshes", fake)
    request = object()
    assert _phase6_box_body_structure_meshes(request, thickness=1.5) == list(sentinel)
    assert called == [(request, 1.5)]
    src = inspect.getsource(_phase6_box_body_structure_meshes)
    assert "manufacturing_api.resolve_box_body_structure_mid_meshes" in src
    assert "_phase6_folded_mesh_from_polygon" not in src
    assert "_phase6_box_body_piece_world_mapper" not in src
