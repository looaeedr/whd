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
import tkinter as tk

import pytest

from ae_engine.receiving_base_fixing_plate_geometry import SOURCE_DXF_SHA256
from phase6_assembly_panel import AssemblyPanelActions, Phase6AssemblyPanel
from phase6_assembly_presentation import AssemblyPresentationModel, AssemblyPresentationRow
from phase6_final_scene_view import Phase6FinalSceneViewAdapter


@pytest.mark.parametrize(
    ("base_plate_visible", "ear_visible"),
    [(True, True), (True, False), (False, True), (False, False)],
    ids=("both-visible", "ear-hidden", "base-hidden-ear-visible", "both-hidden"),
)
def test_fixing_plate_3d_visibility_four_independent_combinations(
    base_plate_visible, ear_visible,
):
    """A display-only EAR survives a hidden Base Plate; its own toggle wins."""
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    skins = (
        SimpleNamespace(part_id="EAR:left", base_part_id="base_plate:nfb_layer:1"),
        SimpleNamespace(part_id="EAR:right", base_part_id="base_plate:nfb_layer:1"),
    )
    fingerprint = hashlib.sha256(
        (SOURCE_DXF_SHA256 + repr(snapshot)).encode("utf-8")
    ).hexdigest()
    adapter = object.__new__(Phase6FinalSceneViewAdapter)
    adapter._formed_ear_display_cache = (fingerprint, skins, None)
    adapter.last_formed_ear_display_blocker = None

    visible = {"base_plate", "base_plate:nfb_layer:1"} if base_plate_visible else set()
    projected = adapter._formed_ear_assembly_preview(snapshot, visible)
    result = make_assembly_scene_render_data(
        assembly_parts=(),
        visible_part_keys=tuple(visible),
        formed_fixing_plate_skins=projected,
        show_fixing_plate_mesh=ear_visible,
    )
    assert result.formed_fixing_plate_skins == skins
    assert result.show_fixing_plate_mesh is ear_visible
    assert ("base_plate" in result.visible_part_keys) is base_plate_visible
    # The 3D renderer consumes both independent controls. A false EAR toggle
    # suppresses only the display, not the immutable 2D/MFG skin source.
    assert (
        bool(result.formed_fixing_plate_skins) and result.show_fixing_plate_mesh
    ) is ear_visible


def test_fixing_plate_checkbox_is_nested_under_base_plate_and_independent_on_rebuild():
    """Use genuine Tk widgets; no parent-checkbox propagation or stale toggle."""
    root = tk.Tk()
    root.withdraw()
    callbacks = []
    try:
        panel = Phase6AssemblyPanel(
            root,
            actions=AssemblyPanelActions(
                on_visibility_changed=lambda: callbacks.append("redraw"),
                on_multi_settings=lambda: None,
            ),
        )
        model = AssemblyPresentationModel(entries=(
            AssemblyPresentationRow(part_key="base_plate", label="底板"),
            AssemblyPresentationRow(part_key="box_body", label="箱身"),
        ))
        panel.set_multi_settings_visible(True)
        panel.render(model)
        panel.set_part_details_open("base_plate", True)
        entry = panel.fixing_plate_visibility_entry
        assert entry is not None
        assert entry.winfo_parent() == str(panel.detail_frames["base_plate"])
        assert entry.winfo_manager() == "pack"
        toggle = entry.winfo_children()[0]
        assert "底板固定片" in toggle.cget("text")
        assert "base_plate:fixing_plate" not in panel.visible_vars

        panel.visible_vars["base_plate"].set(False)
        panel.notify_visibility_changed()
        assert panel.is_fixing_plate_visible() is True
        toggle.invoke()
        assert panel.is_fixing_plate_visible() is False
        panel.render(model)
        assert panel.visible_vars["base_plate"].get() is False
        assert panel.is_fixing_plate_visible() is False
        assert panel.fixing_plate_visibility_entry.winfo_parent() == str(
            panel.detail_frames["base_plate"]
        )
        panel.fixing_plate_visibility_entry.winfo_children()[0].invoke()
        assert panel.is_fixing_plate_visible() is True
        assert callbacks.count("redraw") >= 3
        panel.set_multi_settings_visible(False)
        assert not panel.fixing_plate_visibility_entry.winfo_manager()
        panel.set_multi_settings_visible(True)
        assert panel.fixing_plate_visibility_entry.winfo_manager() == "pack"
    finally:
        root.destroy()


def test_multi_bay_base_plate_group_keeps_fixing_plate_toggle_independent():
    """The synthetic '底板' group also owns the EAR toggle, not the root UI."""
    from phase6_assembly_presentation import build_assembly_presentation_model

    root = tk.Tk()
    root.withdraw()
    callbacks = []
    try:
        panel = Phase6AssemblyPanel(
            root,
            actions=AssemblyPanelActions(
                on_visibility_changed=lambda: callbacks.append("redraw"),
                on_multi_settings=lambda: None,
            ),
        )
        model = build_assembly_presentation_model(
            ("base_plate_c1_r1", "base_plate_c2_r1"),
            label_for=lambda key: "底板" if key == "base_plate" else key,
        )
        panel.set_multi_settings_visible(True)
        panel.render(model)
        assert "base_plate" in panel.group_sections
        assert "base_plate" not in panel.visible_vars
        assert panel.toggle_group("base_plate") is True
        entry = panel.fixing_plate_visibility_entry
        assert entry is not None
        assert entry.winfo_parent() == str(
            panel.group_detail_frames["base_plate"]
        )
        assert entry.winfo_manager() == "pack"

        base_group = panel.group_sections["base_plate"]
        header = base_group.winfo_children()[0]
        header.winfo_children()[0].invoke()  # Hide both physical Base Plates.
        assert all(
            not panel.visible_vars[k].get()
            for k in ("base_plate_c1_r1", "base_plate_c2_r1")
        )
        assert panel.is_fixing_plate_visible() is True
        entry.winfo_children()[0].invoke()  # Hide only the EAR.
        assert panel.is_fixing_plate_visible() is False
        assert len(callbacks) == 2
        panel.render(model)
        assert panel.is_fixing_plate_visible() is False
        assert panel.fixing_plate_visibility_entry.winfo_parent() == str(
            panel.group_detail_frames["base_plate"]
        )
    finally:
        root.destroy()
