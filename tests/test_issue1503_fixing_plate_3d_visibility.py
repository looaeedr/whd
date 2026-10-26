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


import hashlib
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("base_visible", (True, False))
@pytest.mark.parametrize("ear_visible", (True, False))
def test_forming_ear_independent_from_base_plate_3d_visibility(base_visible, ear_visible):
    """Four independent Base Plate / fixing plate 3D checkbox combinations.

    This protects the real FinalScene EAR-source filtering seam. The physical
    owner remains the Base Plate; that owner must not force the UI visibility.
    """
    from ae_engine.receiving_base_fixing_plate_geometry import SOURCE_DXF_SHA256
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter

    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    source_key = hashlib.sha256(
        (SOURCE_DXF_SHA256 + repr(snapshot)).encode("utf-8")
    ).hexdigest()
    source_skin = SimpleNamespace(
        part_id="base_plate:fixing_plate:left",
        base_part_id="base_plate:nfb_layer:1",
    )
    view = object.__new__(Phase6FinalSceneViewAdapter)
    view._formed_ear_display_cache = (source_key, (source_skin,), None)
    view.last_formed_ear_display_blocker = None
    visible_keys = ("box_body", "base_plate") if base_visible else ("box_body",)

    skins = view._formed_ear_assembly_preview(snapshot, set(visible_keys))
    scene = make_assembly_scene_render_data(
        assembly_parts=(),
        visible_part_keys=visible_keys,
        formed_fixing_plate_skins=skins,
        show_fixing_plate_mesh=ear_visible,
    )
    assert scene.visible_part_keys == visible_keys
    assert scene.formed_fixing_plate_skins == (source_skin,)
    assert scene.show_fixing_plate_mesh is ear_visible
    assert scene.formed_fixing_plate_skins[0].base_part_id == "base_plate:nfb_layer:1"


@pytest.mark.parametrize("synthetic_group", (False, True))
def test_fixing_plate_checkbox_nested_inside_base_plate_without_master_visibility_gate(
    synthetic_group,
):
    """The real Tk checkbox lives under Base Plate details, not top-level.

    Hiding the base sheet does not alter the fixing-plate checkbox; rerendering
    keeps its value and Receiving-only mode controls its visibility.
    """
    import tkinter as tk
    from phase6_assembly_panel import Phase6AssemblyPanel, AssemblyPanelActions
    from phase6_assembly_presentation import (
        AssemblyPresentationModel,
        AssemblyPresentationRow,
        AssemblySyntheticGroup,
    )

    root = tk.Tk()
    root.withdraw()
    events = []
    try:
        panel = Phase6AssemblyPanel(
            root,
            actions=AssemblyPanelActions(
                on_visibility_changed=lambda: events.append("change"),
                on_multi_settings=lambda: None,
            ),
        )
        part = AssemblyPresentationRow(
            part_key=("base_plate_c0_r0" if synthetic_group else "base_plate"),
            label="底板",
        )
        model = AssemblyPresentationModel(entries=(
            AssemblySyntheticGroup("base_plate", "底板", (part,))
            if synthetic_group else part,
        ))
        panel.render(model)
        panel.set_multi_settings_visible(True)
        parent = (
            panel.group_detail_frames["base_plate"]
            if synthetic_group else panel.detail_frames["base_plate"]
        )
        entry = panel.fixing_plate_visibility_entry
        assert entry is not None
        assert entry.master is parent
        assert entry.winfo_manager() == "pack"
        assert entry.winfo_parent() != str(panel.host)
        assert panel.is_fixing_plate_visible() is True

        base_key = "base_plate_c0_r0" if synthetic_group else "base_plate"
        panel.visible_vars[base_key].set(False)
        assert panel.is_fixing_plate_visible() is True
        check = entry.winfo_children()[0]
        check.invoke()  # independently hide EAR while Base Plate stays hidden
        assert panel.is_fixing_plate_visible() is False
        assert panel.visible_vars[base_key].get() is False
        check.invoke()  # independently re-show EAR, leaving base hidden
        assert panel.is_fixing_plate_visible() is True
        assert panel.visible_vars[base_key].get() is False
        assert events == ["change", "change"]

        panel.render(model)
        assert panel.is_fixing_plate_visible() is True
        assert panel.fixing_plate_visibility_entry.master is (
            panel.group_detail_frames["base_plate"]
            if synthetic_group else panel.detail_frames["base_plate"]
        )
        panel.set_multi_settings_visible(False)
        assert not panel.fixing_plate_visibility_entry.winfo_manager()
        panel.set_multi_settings_visible(True)
        assert panel.fixing_plate_visibility_entry.winfo_manager() == "pack"
    finally:
        root.destroy()
