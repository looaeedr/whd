# -*- coding: utf-8 -*-
"""#1503: EAR visibility is a 3D preference, not manufacturing authority."""

from phase6_final_scene_projection import make_assembly_scene_render_data
from phase6_final_scene_contracts import AssemblyVisibility


def test_legacy_visibility_tuple_unpacks_without_exposing_3d_preference_as_part():
    result = AssemblyVisibility(
        ("box_body", "base_plate"), ("box_body:left_side",),
        show_fixing_plate_mesh=False,
    )
    part_keys, side_keys = result
    assert len(result) == 2
    assert part_keys == ("box_body", "base_plate")
    assert side_keys == ("box_body:left_side",)
    assert result.show_fixing_plate_mesh is False
    assert result == (part_keys, side_keys)


def test_fixing_plate_mesh_toggle_preserves_canonical_source_skins():
    """A hidden EAR must remain available for SIDE marks and full re-show."""
    source_ear = object()
    shown = make_assembly_scene_render_data(
        assembly_parts=(),
        formed_fixing_plate_skins=(source_ear,),
    )
    hidden = make_assembly_scene_render_data(
        assembly_parts=(),
        formed_fixing_plate_skins=(source_ear,),
        show_fixing_plate_mesh=False,
    )
    assert shown.show_fixing_plate_mesh is True
    assert hidden.show_fixing_plate_mesh is False
    assert shown.formed_fixing_plate_skins == hidden.formed_fixing_plate_skins
    assert hidden.formed_fixing_plate_skins == (source_ear,)
    assert hidden.assembly_parts == shown.assembly_parts
