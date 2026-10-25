# -*- coding: utf-8 -*-
"""#1503: EAR visibility is a 3D preference, not manufacturing authority."""

from phase6_final_scene_projection import make_assembly_scene_render_data


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
