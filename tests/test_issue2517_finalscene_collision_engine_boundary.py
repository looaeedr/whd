# -*- coding: utf-8 -*-
"""#2517 no GUI physical inventory / manufacturing collision arbitration."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine import assembly_collision_display_api as collision
from ae_engine.assembly_all_parts_collision import audit_all_physical_part_pairs


def _triangle(offset=0.0):
    return ((offset, 0., 0.), (offset + 1., 0., 0.), (offset, 1., 0.))


def test_engine_selects_actual_body_pieces_and_explicit_visibility(monkeypatch):
    real = {
        "box_body": (_triangle(),),
        "box_body:left_side": (_triangle(),),
        "box_body:right_side": (_triangle(10.),),
        "box_body:divider:one": (_triangle(5.),),
        "head": (_triangle(20.),),
        "inner_door:upper:left_frame": (_triangle(30.),),
    }
    monkeypatch.setattr(
        collision, "build_joint_world_geometry",
        lambda *_: {"world_triangles_by_part": real},
    )
    complete = manufacturing_api.project_assembly_collision_display_audit(
        (), (800., 1600., 350.), 2.,
    )
    assert set(complete.visible_keys) == set(real) - {"box_body"}
    selected = manufacturing_api.project_assembly_collision_display_audit(
        (), (800., 1600., 350.), 2.,
        visible_part_keys={"box_body", "head"},
        visible_box_body_piece_keys={"box_body:left_side"},
    )
    assert set(selected.visible_keys) == {
        "box_body:left_side", "box_body:divider:one", "head",
    }
    assert "box_body:right_side" not in selected.visible_keys
    assert "inner_door:upper:left_frame" not in selected.visible_keys


def test_original_collision_negative_and_pair_status_are_unchanged(monkeypatch):
    world = {"box_body:left_side": (_triangle(),), "head": (_triangle(10.),)}
    monkeypatch.setattr(collision, "build_joint_world_geometry",
                        lambda *_: {"world_triangles_by_part": world})
    checked = manufacturing_api.project_assembly_collision_display_audit(
        (), (800., 1600., 350.), 2.,
        visible_part_keys={"box_body", "head"},
    )
    original = audit_all_physical_part_pairs(
        world, visible_part_keys={"box_body:left_side", "head"},
    )
    assert checked == original
    assert checked.evaluated_pair_count == 1
    world["head"] = ()
    with pytest.raises(ValueError, match="ASSEMBLY_COLLISION_MISSING_VISIBLE_PARTS"):
        manufacturing_api.project_assembly_collision_display_audit(
            (), (800., 1600., 350.), 2.,
            visible_part_keys={"box_body", "head"},
        )


def test_real_receiving_head_divider_frames_all_paired_from_engine_only():
    from tests.test_issue1050_receiving_mother_plate_marking import (
        _snapshot, _full_receiving_geometry,
    )
    snapshot = _snapshot()
    existing = _full_receiving_geometry(snapshot)
    dims = (snapshot["w"], snapshot["h"], snapshot["d"])
    parts, diagnostics, _ = manufacturing_api.resolve_family_divider_reliefs(
        existing.parts, finished_dimensions=dims, sheet_thickness=snapshot["t"],
    )
    world = manufacturing_api.build_joint_world_geometry(
        parts, dims, snapshot["t"],
    )["world_triangles_by_part"]
    original = audit_all_physical_part_pairs(
        world, certified_relief_diagnostics=tuple(diagnostics),
    )
    public = manufacturing_api.project_assembly_collision_display_audit(
        parts, dims, snapshot["t"],
        certified_relief_diagnostics=tuple(diagnostics),
    )
    assert public == original
    assert public.unresolved
    assert "inner_door:upper:left_frame" in public.visible_keys
    assert any(
        {pair.left, pair.right} == {"head", "box_body:left_side"}
        for pair in public.unresolved
    )


def test_gui_renderer_uses_only_public_engine_collision_and_solid():
    source = Path("phase6_final_scene_renderer.py").read_text(encoding="utf-8")
    for private_import in (
        "from ae_engine.assembly_geometry import",
        "from ae_engine.assembly_all_parts_collision import",
    ):
        assert private_import not in source
    assert "_phase6_build_joint_world_geometry(" not in source
    for name in (
        "project_assembly_collision_display_audit", "collision_part_display_name",
        "restore_unrelieved_endcap_material", "restored_endcap_relief_delta",
        "thicken_triangle_surface", "MeshInterferenceDiagnostic",
    ):
        assert hasattr(manufacturing_api, name)
        assert "manufacturing_api." + name in source
