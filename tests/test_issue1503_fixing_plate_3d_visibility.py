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


def test_fixing_plate_skin_visibility_is_independent_of_base_plate_in_all_four_states():
    """EAR display meshes are source-backed even with their parent hidden."""
    import hashlib
    from types import SimpleNamespace
    from ae_engine.receiving_base_fixing_plate_geometry import SOURCE_DXF_SHA256
    from phase6_final_scene_view import Phase6FinalSceneViewAdapter

    source = {"model": "受電箱", "nfb_config_submitted": True}
    key = hashlib.sha256((SOURCE_DXF_SHA256 + repr(source)).encode("utf-8")).hexdigest()
    skin = SimpleNamespace(part_id="base_plate:fixing_plate:left", base_part_id="base_plate")
    view = object.__new__(Phase6FinalSceneViewAdapter)
    view._formed_ear_display_cache = (key, (skin,), None)
    view.last_formed_ear_display_blocker = None

    for base_visible in (False, True):
        for fixing_visible in (False, True):
            visible_parts = ("base_plate",) if base_visible else ()
            resolved_skins = view._formed_ear_assembly_preview(source, set(visible_parts))
            projected = make_assembly_scene_render_data(
                assembly_parts=(),
                visible_part_keys=visible_parts,
                formed_fixing_plate_skins=resolved_skins,
                show_fixing_plate_mesh=fixing_visible,
            )
            assert projected.formed_fixing_plate_skins == (skin,)
            assert projected.visible_part_keys == visible_parts
            assert projected.show_fixing_plate_mesh is fixing_visible
    assert view.last_formed_ear_display_blocker is None


def test_fixing_plate_checkbox_is_nested_in_regular_base_details_but_independent():
    import tkinter as tk
    from phase6_assembly_panel import AssemblyPanelActions, Phase6AssemblyPanel
    from phase6_assembly_presentation import build_assembly_presentation_model

    root = tk.Tk()
    root.withdraw()
    calls = []
    try:
        panel = Phase6AssemblyPanel(
            root, actions=AssemblyPanelActions(
                on_visibility_changed=lambda: calls.append("redraw"),
                on_multi_settings=lambda: None,
            ),
        )
        panel.set_multi_settings_visible(True)
        panel.render(build_assembly_presentation_model(
            ("box_body", "base_plate"), label_for=str,
        ))
        assert panel.fixing_plate_visibility_entry.master is panel.detail_frames["base_plate"]
        assert panel.fixing_plate_visibility_entry.winfo_manager() == "pack"
        assert panel.fixing_plate_visibility_entry not in panel.host.pack_slaves()
        base_visible = panel.visible_vars["base_plate"]
        for base in (False, True):
            for ear in (False, True):
                base_visible.set(base)
                panel.fixing_plate_visible_var.set(ear)
                assert base_visible.get() is base
                assert panel.is_fixing_plate_visible() is ear
        # Rebuild must retain EAR preference regardless of Base Plate state.
        base_visible.set(False)
        panel.fixing_plate_visible_var.set(True)
        panel.render(build_assembly_presentation_model(
            ("box_body", "base_plate"), label_for=str,
        ))
        assert panel.visible_vars["base_plate"].get() is False
        assert panel.is_fixing_plate_visible() is True
        assert panel.fixing_plate_visibility_entry.master is panel.detail_frames["base_plate"]
        panel.fixing_plate_visibility_entry.winfo_children()[0].invoke()
        assert panel.is_fixing_plate_visible() is False
        assert panel.visible_vars["base_plate"].get() is False
        assert calls[-1] == "redraw"
    finally:
        root.destroy()


def test_fixing_plate_checkbox_is_nested_in_multi_base_group_and_keeps_own_state():
    import tkinter as tk
    from phase6_assembly_panel import AssemblyPanelActions, Phase6AssemblyPanel
    from phase6_assembly_presentation import build_assembly_presentation_model

    root = tk.Tk()
    root.withdraw()
    try:
        panel = Phase6AssemblyPanel(
            root, actions=AssemblyPanelActions(
                on_visibility_changed=lambda: None,
                on_multi_settings=lambda: None,
            ),
        )
        panel.set_multi_settings_visible(True)
        model = build_assembly_presentation_model(
            ("box_body", "base_plate_c1_r1", "base_plate_c2_r1"),
            label_for=str,
        )
        panel.render(model)
        assert panel.fixing_plate_visibility_entry.master is panel.group_detail_frames["base_plate"]
        for base in (False, True):
            for ear in (False, True):
                for key in ("base_plate_c1_r1", "base_plate_c2_r1"):
                    panel.visible_vars[key].set(base)
                panel.fixing_plate_visible_var.set(ear)
                assert panel.is_fixing_plate_visible() is ear
                assert all(panel.visible_vars[k].get() is base for k in (
                    "base_plate_c1_r1", "base_plate_c2_r1",
                ))
        panel.fixing_plate_visible_var.set(True)
        panel.set_multi_settings_visible(False)
        assert not panel.fixing_plate_visibility_entry.winfo_manager()
        panel.set_multi_settings_visible(True)
        assert panel.fixing_plate_visibility_entry.winfo_manager() == "pack"
        assert panel.is_fixing_plate_visible() is True
    finally:
        root.destroy()
