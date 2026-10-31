"""#2517: verified physical Joint CUTTING belongs in headless Engine."""
from __future__ import annotations

import inspect

import pytest
from shapely.geometry import box

from ae_engine import manufacturing_api as api
from ae_engine import assembly_collision as owner
from phase6_manufacturing_geometry import (
    _phase6_apply_resolved_cut_to_part as gui_part,
    _phase6_apply_resolved_cut_to_owner as gui_owner,
)
from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part


def _edge_cut(material):
    perimeter = material.exterior
    point = perimeter.interpolate(perimeter.length / 2)
    return box(point.x - 1.0, point.y - 1.0, point.x + 1.0, point.y + 1.0)


def test_cut_apply_methods_have_one_engine_owner_without_reverse_phase6_import():
    assert api.apply_verified_joint_cut_to_part is owner.apply_verified_joint_cut_to_part
    assert api.apply_verified_joint_cut_to_owner is owner.apply_verified_joint_cut_to_owner
    assert "manufacturing_api.apply_verified_joint_cut_to_part(" in inspect.getsource(gui_part)
    assert "manufacturing_api.apply_verified_joint_cut_to_owner(" in inspect.getsource(gui_owner)
    assert "from phase6_" not in inspect.getsource(owner.apply_verified_joint_cut_to_owner)
    assert "AssemblyScenePart" not in inspect.getsource(owner.apply_verified_joint_cut_to_owner)


def test_actual_receiving_divider_cut_changes_only_returned_final_scene_material():
    snapshot = _snapshot()
    _, divider = _divider_part(snapshot)
    original = divider.render_data.material
    cut = _edge_cut(original)
    result = api.apply_verified_joint_cut_to_part(divider, cut)
    legacy = gui_part(divider, cut)
    assert result.part_key == divider.part_key
    assert result.placement == divider.placement
    assert result.offset == divider.offset
    assert result.x_profile == divider.x_profile
    assert result.y_profile == divider.y_profile
    assert result.render_data.material.equals(legacy.render_data.material)
    assert float(result.render_data.material.area) < float(original.area)
    assert divider.render_data.material.equals(original)


def test_true_receiving_boxbody_piece_cut_keeps_unrelated_physical_sheets():
    body = _body_part(_snapshot())
    piece = next(p for p in body.render_data.pieces if p.role == "left_side")
    original = piece.render_data.material
    cut = _edge_cut(original)
    result = api.apply_verified_joint_cut_to_owner(body, "box_body:left_side", cut)
    assert result.part_key == "box_body"
    assert result.placement == body.placement
    assert result.render_data.preview_render_data is not None
    updated = {p.role: p for p in result.render_data.pieces}
    assert float(updated["left_side"].render_data.material.area) < float(original.area)
    assert piece.render_data.material.equals(original)
    for untouched in ("back", "right_side"):
        prior = next(p for p in body.render_data.pieces if p.role == untouched)
        assert updated[untouched] is prior
    assert result.render_data.preview_render_data.material.equals(
        gui_owner(body, "box_body:left_side", cut).render_data.preview_render_data.material
    )


def test_invalid_cut_owner_and_full_material_removal_reject_without_mutation():
    body = _body_part(_snapshot())
    with pytest.raises(ValueError, match="not under"):
        api.apply_verified_joint_cut_to_owner(body, "door:left_side", box(0, 0, 1, 1))
    with pytest.raises(ValueError, match="unknown Box Body piece role"):
        api.apply_verified_joint_cut_to_owner(body, "box_body:missing", box(0, 0, 1, 1))
    _, divider = _divider_part(_snapshot())
    minx, miny, maxx, maxy = map(float, divider.render_data.material.bounds)
    with pytest.raises(ValueError, match="removed all material"):
        api.apply_verified_joint_cut_to_part(
            divider, box(minx - 1, miny - 1, maxx + 1, maxy + 1)
        )
