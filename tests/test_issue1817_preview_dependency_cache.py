# -*- coding: utf-8 -*-
"""#1817: Receiving per-Bay preview cache respects real spatial dependencies."""
from copy import deepcopy

from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    update_receiving_joint_alignment, project_receiving_bay_legacy_aliases,
    receiving_bay_assembly_offsets,
)
from gui_modules.application.fold_designer_composition_receiving import (
    _receiving_bay_preview_fingerprint_snapshot,
)
from phase6_sync_envelope import stable_fingerprint


def _layout(count=4):
    return resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=count,
    )


def _key(layout, bay_index, *, selective=True, **extra):
    projected = project_receiving_bay_legacy_aliases(
        {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":layout, **extra},
        set_index=0, bay_index=bay_index, validate_common=False,
    )
    key_input = (_receiving_bay_preview_fingerprint_snapshot(
        projected, set_index=0, bay_index=bay_index) if selective else projected)
    return stable_fingerprint(key_input)


def test_issue1817_distant_trailing_dimension_change_reuses_earlier_preview():
    original = _layout()
    copy_before = deepcopy(original)
    edited = update_receiving_bay(
        original, set_index=0, bay_index=3, width=950, height=1800, depth=415)
    assert original == copy_before
    assert _key(original, 0, selective=False) != _key(edited, 0, selective=False)
    assert _key(original, 0) == _key(edited, 0)
    assert _key(original, 1) == _key(edited, 1)
    # Bay3's right Joint and Bay4's own sheet must still re-resolve.
    assert _key(original, 2) != _key(edited, 2)
    assert _key(original, 3) != _key(edited, 3)
    for i in (0, 1):
        assert receiving_bay_assembly_offsets(original)[i] == (
            receiving_bay_assembly_offsets(edited)[i])


def test_issue1817_left_neighbor_and_prefix_dimension_changes_are_not_reused():
    original = _layout()
    edited = update_receiving_bay(
        original, set_index=0, bay_index=1, width=980, height=1900, depth=480)
    for i in range(4):
        assert _key(original, i) != _key(edited, i)
    assert receiving_bay_assembly_offsets(original)[2] != (
        receiving_bay_assembly_offsets(edited)[2])


def test_issue1817_joint_metadata_non_dimension_data_and_topology_invalidate():
    original = _layout()
    key = _key(original, 0)
    # Keep all joint records even if a changed joint is distant.
    changed = update_receiving_bay(original, set_index=0, bay_index=3, depth=460)
    changed = update_receiving_joint_alignment(
        changed, set_index=0, joint_index=2, depth_alignment="REAR")
    assert _key(changed, 0) != key
    changed = update_receiving_bay(
        original, set_index=0, bay_index=3,
        door_state={"multi_door_enabled":False})
    assert _key(changed, 0) != key
    changed = resize_receiving_bays(original, set_index=0, bay_count=5)
    assert _key(changed, 0) != key


def test_issue1817_key_projection_never_mutates_authority_and_fails_closed():
    source = {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":_layout()}
    before = deepcopy(source)
    reduced = _receiving_bay_preview_fingerprint_snapshot(
        source, set_index=0, bay_index=0)
    assert source == before
    assert "width" not in reduced["receiving_layout"]["sets"][0]["bays"][3]
    assert "width" in reduced["receiving_layout"]["sets"][0]["bays"][1]
    for candidate in (
        {**source, "active_mode":"quantity"},
        {**source, "model":"金庫型"},
        {**source, "receiving_layout":{"schema":"unknown","sets":[]}},
    ):
        assert _receiving_bay_preview_fingerprint_snapshot(
            candidate, set_index=0, bay_index=0) == candidate


def test_issue1817_noop_and_global_geometry_inputs_preserve_cache_key_policy():
    original = _layout()
    same = update_receiving_bay(
        original, set_index=0, bay_index=3, width=800, height=1600, depth=350)
    assert _key(original, 0) == _key(same, 0)
    assert _key(original, 0, t=2) != _key(original, 0, t=3)
    assert _key(original, 0, assembly_joints=[]) != (
        _key(original, 0, assembly_joints=[{"subject_part":"head"}]))


def test_issue1817_actual_joint_side_features_match_full_rebuild_for_untouched_bay():
    # This is the real certified joint-hole projection, not a drawn mock.
    from ae_engine.receiving_layout import receiving_bay_joint_face_features
    original = _layout()
    changed = update_receiving_bay(
        original, set_index=0, bay_index=3, width=1010, height=1810, depth=460)
    args = dict(set_index=0, bay_index=0, thickness=2, frame_width=29)
    original_faces = receiving_bay_joint_face_features(original, **args)
    fully_recomputed_faces = receiving_bay_joint_face_features(changed, **args)
    assert original_faces == fully_recomputed_faces
    assert _key(original, 0) == _key(changed, 0)


def test_issue1817_real_side_joint_features_same_as_full_rebuild_after_far_edit():
    # Real certified Receiving side locks; no fake/test-only hole positions.
    from ae_engine.receiving_layout import receiving_bay_joint_face_features
    original = _layout()
    edited = update_receiving_bay(
        original, set_index=0, bay_index=3, width=1010, height=1800, depth=460)
    args = dict(set_index=0, bay_index=0, thickness=2, frame_width=29)
    before = receiving_bay_joint_face_features(original, **args)
    after_full_rebuild = receiving_bay_joint_face_features(edited, **args)
    assert before == after_full_rebuild
    assert _key(original, 0) == _key(edited, 0)


def test_issue1817_real_preview_method_hits_cached_object_for_far_bay_edit(monkeypatch):
    """Exercise real Receiving preview cache-check call-site, not just helper."""
    from types import SimpleNamespace
    import pytest
    from ae_engine.cabinet_types import receiving
    from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
    from gui_modules.application.fold_designer_composition_receiving import (
        receiving_bay_preview_request,
    )
    from phase6_settings_profile_projection import project_part_dimensions
    import phase6_fold_profiles
    canonical = receiving.apply_family_defaults({"t":2.0})
    canonical.update(model="受電箱", active_mode="set_bay", receiving_layout=_layout())

    workspace = SimpleNamespace(
        part_profiles_snapshot=lambda: {},
        part_features_snapshot=lambda: {},
        part_face_features_snapshot=lambda: {},
    )
    app = SimpleNamespace(
        _phase6_input_snapshot=canonical, _settings_values={},
        designer_workspace=workspace,
        _phase6_corner_state={},
        state=SimpleNamespace(profiles_vault={"箱身": ()}),
    )
    def signature():
        projected = project_receiving_bay_legacy_aliases(
            dict(app._phase6_input_snapshot), set_index=0, bay_index=0)
        settings = {**dict(app._settings_values),
                    **{k:projected[k] for k in ("w", "h", "d")}}
        projected.update(settings)
        projected["part_dimensions"] = project_part_dimensions(projected)
        return stable_fingerprint({
            "snapshot":_receiving_bay_preview_fingerprint_snapshot(
                projected, set_index=0, bay_index=0,
                allow_suffix_topology_reuse=True),
            "profiles":workspace.part_profiles_snapshot(),
            "features":workspace.part_features_snapshot(),
            "face_features":workspace.part_face_features_snapshot(),
            "box_profile":app.state.profiles_vault.get("箱身", ()),
            "corners":app._phase6_corner_state,
        })
    old_signature=signature()
    cached=object()
    owner=SimpleNamespace(
        app=app,
        _receiving_bay_preview_cache={(0,0):(old_signature,cached)},
    )
    def would_be_full_solve(*args, **kwargs):
        raise LookupError("full geometry rebuild required")
    monkeypatch.setattr(
        phase6_fold_profiles, "merge_box_body_profile", would_be_full_solve)
    app._phase6_input_snapshot = {
        **canonical,
        "receiving_layout":update_receiving_bay(
            canonical["receiving_layout"], set_index=0, bay_index=3,
            width=950, height=1750, depth=420),
    }
    assert signature() == old_signature
    assert receiving_bay_preview_request(owner, None, 0, 0) is cached
    # Real append of a distant tail Bay also must NOT call manufacturing.
    app._phase6_input_snapshot = {
        **canonical,
        "receiving_layout":resize_receiving_bays(
            app._phase6_input_snapshot["receiving_layout"],
            set_index=0,bay_count=5),
    }
    assert signature() == old_signature
    assert receiving_bay_preview_request(owner, None, 0, 0) is cached
    # Right-neighbor Bay2 changes Bay1's certified side-lock geometry:
    # bypass must be impossible; even an isolated fake app must enter resolve.
    app._phase6_input_snapshot = {
        **canonical,
        "receiving_layout":update_receiving_bay(
            canonical["receiving_layout"], set_index=0, bay_index=1,
            width=950, height=1750, depth=420),
    }
    assert signature() != old_signature
    with pytest.raises(LookupError, match="full geometry rebuild required"):
        receiving_bay_preview_request(owner, None, 0, 0)


def test_issue1817_distant_prefix_edit_keeps_local_geometry_key_but_moves_anchor():
    original = _layout()
    modified = update_receiving_bay(
        original, set_index=0, bay_index=0, width=920, height=1800, depth=420)
    old_snap = project_receiving_bay_legacy_aliases(
        {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":original},
        set_index=0, bay_index=3, validate_common=False)
    new_snap = project_receiving_bay_legacy_aliases(
        {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":modified},
        set_index=0, bay_index=3, validate_common=False)
    def key(snap, rebase):
        return stable_fingerprint(_receiving_bay_preview_fingerprint_snapshot(
            snap, set_index=0, bay_index=3, allow_upstream_translation=rebase))
    assert key(old_snap, False) != key(new_snap, False)
    assert key(old_snap, True) == key(new_snap, True)
    assert receiving_bay_assembly_offsets(original)[3] != (
        receiving_bay_assembly_offsets(modified)[3])
    # A touching Bay3 edit still demands full geometry, never just a shift.
    neighbor = update_receiving_bay(
        original, set_index=0, bay_index=2, width=920, depth=420)
    neighbor_snap = project_receiving_bay_legacy_aliases(
        {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":neighbor},
        set_index=0, bay_index=3, validate_common=False)
    assert key(old_snap, True) != key(neighbor_snap, True)


def test_issue1817_immutable_world_translation_matches_canonical_full_placement():
    from phase6_final_scene_contracts import (
        AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
    )
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_rebase_preview_world_offsets,
    )
    original = _layout()
    changed = update_receiving_bay(
        original, set_index=0, bay_index=0, width=930, height=1740, depth=390)
    before = receiving_bay_assembly_offsets(original)[3]
    after = receiving_bay_assembly_offsets(changed)[3]
    material = object()
    local=(3.0, -6.0, 11.0)
    scene_part=AssemblyScenePart(
        part_key="box_body", render_data=material, x_profile=(), y_profile=(),
        offset=tuple(x+y for x,y in zip(local,before)))
    request=FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(
            assembly_parts=(scene_part,), preserve_endcap_core_origin=True),
        x_profile=(),y_profile=(),part_key="assembly",thickness=2.0)
    rebased=_receiving_rebase_preview_world_offsets(request,before,after)
    assert rebased is not None and rebased is not request
    updated=rebased.render_data.assembly_parts[0]
    assert updated is not scene_part and updated.render_data is material
    assert updated.offset == tuple(x+y for x,y in zip(local,after))
    assert scene_part.offset == tuple(x+y for x,y in zip(local,before))
    # Equivalent scene content, no changed material / 2D sheet or spec.
    assert rebased.finished_dimensions == request.finished_dimensions
    assert rebased.thickness == request.thickness
    assert rebased.render_data.preserve_endcap_core_origin


def test_issue1817_unsafe_preview_envelopes_cannot_be_translated():
    from phase6_final_scene_contracts import (
        AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
    )
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_rebase_preview_world_offsets,
    )
    part=AssemblyScenePart(part_key="box_body",render_data=object(),
                           x_profile=(),y_profile=())
    for scene in (
        AssemblySceneRenderData(assembly_parts=(part,),show_interference=True,
                                preserve_endcap_core_origin=True),
        AssemblySceneRenderData(assembly_parts=(part,),
                                preserve_endcap_core_origin=False),
        AssemblySceneRenderData(
            assembly_parts=(part,),joint_diagnostics=("unresolved",),
            preserve_endcap_core_origin=True),
        AssemblySceneRenderData(
            assembly_parts=(AssemblyScenePart(
                part_key="custom", render_data=object(),x_profile=(),y_profile=(),
                placement="standalone"),),preserve_endcap_core_origin=True),
    ):
        request=FinalSceneViewRequest(
            render_data=scene,x_profile=(),y_profile=(),part_key="assembly")
        assert _receiving_rebase_preview_world_offsets(
            request,(0,0,0),(10,10,10)) is None


def test_issue1817_real_preview_method_rebases_far_prefix_without_rebuilding(monkeypatch):
    """Actual preview method returns new world positions with identical materials."""
    from types import SimpleNamespace
    import pytest
    from ae_engine.cabinet_types import receiving
    from gui_modules.application.fold_designer_composition_receiving import (
        receiving_bay_preview_request,
    )
    from phase6_final_scene_contracts import (
        AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
    )
    from phase6_settings_profile_projection import project_part_dimensions
    import phase6_fold_profiles

    canonical = receiving.apply_family_defaults({"t":2.0})
    canonical.update(model="受電箱",active_mode="set_bay",receiving_layout=_layout())
    for field in ("assembly_joints","custom_parts","joint_relief_state"):
        canonical.pop(field,None)
    workspace=SimpleNamespace(
        part_profiles_snapshot=lambda: {},
        part_features_snapshot=lambda: {},
        part_face_features_snapshot=lambda: {},
    )
    app=SimpleNamespace(
        _phase6_input_snapshot=canonical, _settings_values={},
        designer_workspace=workspace,_phase6_corner_state={},
        state=SimpleNamespace(profiles_vault={"箱身": ()}))
    def signature():
        projected=project_receiving_bay_legacy_aliases(
            dict(app._phase6_input_snapshot), set_index=0, bay_index=3)
        settings={**dict(app._settings_values),
                  **{k:projected[k] for k in ("w","h","d")}}
        projected.update(settings)
        projected["part_dimensions"]=project_part_dimensions(projected)
        return stable_fingerprint({
            "snapshot":_receiving_bay_preview_fingerprint_snapshot(
                projected,set_index=0,bay_index=3,allow_upstream_translation=True),
            "profiles":workspace.part_profiles_snapshot(),
            "features":workspace.part_features_snapshot(),
            "face_features":workspace.part_face_features_snapshot(),
            "box_profile":app.state.profiles_vault.get("箱身",()),
            "corners":app._phase6_corner_state,
        })
    old_sig=signature()
    old_anchor=receiving_bay_assembly_offsets(canonical["receiving_layout"])[3]
    material=object()
    local=(8.0, 3.0, -5.0)
    body=AssemblyScenePart(
        part_key="box_body",render_data=material,x_profile=(),y_profile=(),
        offset=tuple(a+b for a,b in zip(local,old_anchor)))
    prior=FinalSceneViewRequest(
        render_data=AssemblySceneRenderData(
            assembly_parts=(body,),preserve_endcap_core_origin=True),
        x_profile=(),y_profile=(),part_key="assembly")
    def prefix(layout):
        return tuple((float(b["width"]),float(b["height"]),float(b["depth"]))
                     for b in layout["sets"][0]["bays"][:4])
    owner=SimpleNamespace(
        app=app,
        _receiving_bay_preview_cache={
            (0,3):(old_sig,prior,old_anchor,prefix(canonical["receiving_layout"]))})
    def cannot_solve(*args,**kwargs):
        raise LookupError("unexpected full solve")
    monkeypatch.setattr(
        phase6_fold_profiles, "merge_box_body_profile",cannot_solve)
    changed=update_receiving_bay(
        canonical["receiving_layout"],set_index=0,bay_index=0,
        width=900,height=1760,depth=430)
    app._phase6_input_snapshot={**canonical,"receiving_layout":changed}
    new_anchor=receiving_bay_assembly_offsets(changed)[3]
    assert new_anchor != old_anchor and signature() == old_sig
    result=receiving_bay_preview_request(owner,None,0,3)
    assert result is not prior
    new_part=result.render_data.assembly_parts[0]
    assert new_part.render_data is material
    assert new_part.offset == tuple(a+b for a,b in zip(local,new_anchor))
    assert body.offset == tuple(a+b for a,b in zip(local,old_anchor))
    assert receiving_bay_preview_request(owner,None,0,3) is result
    # Editing immediately adjacent Bay3 destroys the local-geometry key.
    neighbor=update_receiving_bay(
        canonical["receiving_layout"],set_index=0,bay_index=2,width=900)
    app._phase6_input_snapshot={**canonical,"receiving_layout":neighbor}
    with pytest.raises(LookupError,match="unexpected full solve"):
        receiving_bay_preview_request(owner,None,0,3)


def test_issue1817_tail_append_reuses_earlier_preview_but_not_old_terminal_bay():
    original = _layout(3)
    grown = resize_receiving_bays(original, set_index=0, bay_count=4)
    def key(layout, index):
        projected = project_receiving_bay_legacy_aliases(
            {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":layout},
            set_index=0, bay_index=index, validate_common=False)
        return stable_fingerprint(_receiving_bay_preview_fingerprint_snapshot(
            projected,set_index=0,bay_index=index,
            allow_suffix_topology_reuse=True))
    assert _key(original,0) != _key(grown,0)  # original full key invalidated
    assert key(original,0) == key(grown,0)
    assert key(original,1) == key(grown,1)
    assert key(original,2) != key(grown,2)
    assert receiving_bay_assembly_offsets(original) == (
        receiving_bay_assembly_offsets(grown)[:3])
    reduced = resize_receiving_bays(grown, set_index=0, bay_count=3)
    assert key(grown,0) == key(reduced,0)
    assert key(grown,1) == key(reduced,1)
    assert key(grown,2) != key(reduced,2)


def test_issue1817_tail_settings_values_trim_only_when_not_shared_with_front():
    from ae_engine.receiving_shared_settings import (
        normalize_set_settings, edit_setting, share_setting)
    from ae_engine.receiving_layout import normalize_receiving_layout
    original = _layout(3)
    row = original["sets"][0]
    row["settings"] = normalize_set_settings(None,row["bays"])
    original = normalize_receiving_layout(original)
    grown = resize_receiving_bays(original,set_index=0,bay_count=4)
    def key(layout):
        projected = project_receiving_bay_legacy_aliases(
            {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":layout},
            set_index=0,bay_index=0,validate_common=False)
        return stable_fingerprint(_receiving_bay_preview_fingerprint_snapshot(
            projected,set_index=0,bay_index=0,
            allow_suffix_topology_reuse=True))
    assert key(original) == key(grown)
    isolated_edit = edit_setting(
        grown,set_index=0,bay_index=3,kind="back_panel_mode",value="HALF")
    assert key(grown) == key(isolated_edit)  # no shared ref to Bay1
    linked = share_setting(
        grown,set_index=0,bay_indices=(0,3),source_bay_index=0,
        kind="back_panel_mode")
    shared_value_change=edit_setting(
        linked,set_index=0,bay_index=3,kind="back_panel_mode",value="HALF")
    assert key(linked) != key(shared_value_change)  # Bay1's own value changed


def test_issue1817_tail_key_preserves_joint_and_nearest_bay_mutations():
    original = _layout(4)
    def key(layout):
        projected = project_receiving_bay_legacy_aliases(
            {"model":"受電箱", "active_mode":"set_bay", "receiving_layout":layout},
            set_index=0,bay_index=0,validate_common=False)
        return stable_fingerprint(_receiving_bay_preview_fingerprint_snapshot(
            projected,set_index=0,bay_index=0,
            allow_suffix_topology_reuse=True))
    baseline=key(original)
    touching=update_receiving_bay(
        original,set_index=0,bay_index=1,width=1010)
    assert baseline != key(touching)
    joint_edit=update_receiving_bay(
        original,set_index=0,bay_index=1,depth=410)
    joint_edit=update_receiving_joint_alignment(
        joint_edit,set_index=0,joint_index=0,depth_alignment="REAR")
    assert baseline != key(joint_edit)
    other_set=deepcopy(original)
    other_set["sets"][0]["switch_brand"]="三菱"
    from ae_engine.receiving_layout import normalize_receiving_layout
    assert baseline != key(normalize_receiving_layout(other_set))


def test_issue1817_three_bay_tail_whd_edit_selects_only_affected_local_neighbors():
    """Plain adjacent Set/Bay joints: Bay0 source survives Bay2's dimension edit."""
    original = _layout(3)
    edited = update_receiving_bay(
        original, set_index=0, bay_index=2, width=930, height=1750, depth=410,
    )
    def key(layout, index):
        projected = project_receiving_bay_legacy_aliases(
            {"model": "受電箱", "active_mode": "set_bay", "receiving_layout": layout},
            set_index=0, bay_index=index, validate_common=False,
        )
        return stable_fingerprint(_receiving_bay_preview_fingerprint_snapshot(
            projected, set_index=0, bay_index=index,
            allow_suffix_topology_reuse=True,
        ))
    before = tuple(key(original, i) for i in range(3))
    after = tuple(key(edited, i) for i in range(3))
    assert before[0] == after[0], "distant untouched Bay0 must keep its local material"
    assert before[1] != after[1], "Bay1's right Joint depends on edited Bay2"
    assert before[2] != after[2], "edited Bay2's PartSpec must change"


def test_issue1817_unknown_cross_bay_dependencies_never_trim_far_dimensions():
    """RED: custom Joint / relief may connect distant Bays outside the linear chain."""
    original = _layout(4)
    edited = update_receiving_bay(
        original, set_index=0, bay_index=3, width=1010, height=1750, depth=390,
    )
    for source_extension in (
        {"assembly_joints": [{"joint_id": "custom:cross-bay"}]},
        {"custom_parts": {"custom:remote-attachment": {"stable_id": "cross"}}},
        {"joint_relief_state": {"items": {"custom:cross": {"verified": True}}}},
    ):
        def projected(layout):
            return project_receiving_bay_legacy_aliases(
                {"model": "受電箱", "active_mode": "set_bay",
                 "receiving_layout": layout, **source_extension},
                set_index=0, bay_index=0, validate_common=False,
            )
        a, b = projected(original), projected(edited)
        for allow_translation, allow_trim in ((False, False), (True, True)):
            ka = _receiving_bay_preview_fingerprint_snapshot(
                a, set_index=0, bay_index=0,
                allow_upstream_translation=allow_translation,
                allow_suffix_topology_reuse=allow_trim,
            )
            kb = _receiving_bay_preview_fingerprint_snapshot(
                b, set_index=0, bay_index=0,
                allow_upstream_translation=allow_translation,
                allow_suffix_topology_reuse=allow_trim,
            )
            assert stable_fingerprint(ka) != stable_fingerprint(kb), (
                "unknown user cross-Bay dependency incorrectly reused an old FinalScene"
            )
            assert ka == a and kb == b, (
                "unknown user-defined dependency must use full authoritative key"
            )


def test_issue1817_preview_key_discards_only_recomputed_selected_bay_joint_locks():
    """A selection switch cannot invalidate a remote Bay's sheet material."""
    from dataclasses import dataclass
    from phase6_sync_envelope import stable_fingerprint
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_bay_preview_face_features_key,
    )

    @dataclass(frozen=True)
    class Hole:
        source_type: str
        identity: str

    manual = Hole("user_drawn_hole", "explicit")
    before = {
        "box_body": {"left": [Hole("receiving_joint_side_lock", "Bay0"), manual]},
        "head": {"top": [Hole("user_drawn_hole", "head")]}
    }
    after_remote_selection = {
        "box_body": {"right": [Hole("receiving_joint_side_lock", "Bay2")],
                     "left": [manual]},
        "head": before["head"],
    }
    before_key = _receiving_bay_preview_face_features_key(before)
    after_key = _receiving_bay_preview_face_features_key(after_remote_selection)
    assert stable_fingerprint(before_key) == stable_fingerprint(after_key)
    assert "right" not in after_key["box_body"]
    assert before["box_body"]["left"][0].identity == "Bay0"
    assert after_remote_selection["box_body"]["right"][0].identity == "Bay2"

    changed_user_hole = {
        **after_remote_selection,
        "box_body": {"left": [Hole("user_drawn_hole", "modified")]},
    }
    assert stable_fingerprint(_receiving_bay_preview_face_features_key(
        changed_user_hole)) != stable_fingerprint(before_key)
    unfamiliar = {"box_body": {"left": object()}}
    assert _receiving_bay_preview_face_features_key(unfamiliar) is unfamiliar


def test_issue1817_real_bay_panel_material_uses_projected_payload_not_host_snapshot(monkeypatch):
    """3rd-Bay W/H/D edit must not rematerialize a physically unchanged panel.

    The original GUI callback belongs to a primary host whose active_mode can
    differ from the projected Bay request. Key against actual typed input.
    """
    from dataclasses import replace
    from types import SimpleNamespace
    from ae_engine.inner_door_panels import InnerDoorPanelPart
    from ae_engine.cabinet_types import policy as family
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_cached_bay_inner_door_panel,
    )

    panel = InnerDoorPanelPart(
        stable_id="inner_door:upper:panel", inner_door_id="upper",
        cell_key="upper", width=689, height=1040, thickness=2,
    )
    selection = [panel]
    monkeypatch.setattr(family, "derive_inner_door_panels",
                        lambda _input: tuple(selection))
    owner = SimpleNamespace()
    made = []
    def factory():
        token = object()
        made.append(token)
        return token
    data = {"model": "受電箱", "active_mode": "set_bay", "features": ()}
    original = _receiving_cached_bay_inner_door_panel(
        owner, panel.stable_id, data, factory)
    # A real Bay callback may be bound to the primary host in quantity mode.
    primary_host = SimpleNamespace(active_mode="quantity")
    assert primary_host.active_mode == "quantity"
    # The cache authority is the canonical projected source, not this host.
    assert _receiving_cached_bay_inner_door_panel(
        owner, panel.stable_id, data, factory) is original
    assert len(made) == 1
    selection[:] = [replace(panel, width=690)]
    assert _receiving_cached_bay_inner_door_panel(
        owner, panel.stable_id, data, factory) is not original
    assert len(made) == 2
    selection[:] = [panel]
    new_holes = {**data, "features": ({"kind": "圓孔", "x": 9, "y": 15, "d1": 5},)}
    changed = _receiving_cached_bay_inner_door_panel(
        owner, panel.stable_id, new_holes, factory)
    assert changed is not original and len(made) == 3
    assert _receiving_cached_bay_inner_door_panel(
        owner, panel.stable_id, new_holes, factory) is changed

    # Unknown feature shapes and unsupported modes cannot hit a past entry.
    unreadable = {**data, "features": (object(),)}
    assert _receiving_cached_bay_inner_door_panel(
        owner, panel.stable_id, unreadable, factory) is not original
    assert _receiving_cached_bay_inner_door_panel(
        owner, panel.stable_id, unreadable, factory) is not original
    assert len(made) == 5
    for changed_mode in ("quantity", "unknown"):
        _receiving_cached_bay_inner_door_panel(
            owner, panel.stable_id, {**data, "active_mode": changed_mode}, factory)
    _receiving_cached_bay_inner_door_panel(
        owner, "inner_door:upper:left_frame", data, factory)
    assert len(made) == 8

    # Bounded scope: only the latest eight distinct canonical raw sheets.
    for width in range(700, 711):
        selection[:] = [replace(panel, width=width)]
        _receiving_cached_bay_inner_door_panel(
            owner, panel.stable_id, data, factory)
    assert len(owner._receiving_raw_inner_door_panel_history) == 8


def test_issue1817_cached_bay_panel_is_exact_source_free_manufacturing_material():
    from types import SimpleNamespace
    from ae_engine import manufacturing_api
    from ae_engine.inner_door_panels import InnerDoorPanelPart
    from ae_engine.cabinet_types import policy as family
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_cached_bay_inner_door_panel,
    )

    panel = InnerDoorPanelPart(
        stable_id="inner_door:parity:panel", inner_door_id="parity",
        cell_key="upper", width=689, height=1040, thickness=2,
    )
    owner = SimpleNamespace()
    data = {"model": "受電箱", "active_mode": "set_bay", "features": ()}
    original = family.derive_inner_door_panels
    try:
        family.derive_inner_door_panels = lambda _source: (panel,)
        built = manufacturing_api.build_inner_door_panel_render_data(panel)
        one = _receiving_cached_bay_inner_door_panel(
            owner, panel.stable_id, data,
            lambda: manufacturing_api.build_inner_door_panel_render_data(panel))
        two = _receiving_cached_bay_inner_door_panel(
            owner, panel.stable_id, data,
            lambda: (_ for _ in ()).throw(AssertionError("material rebuilt")))
    finally:
        family.derive_inner_door_panels = original
    assert one is two
    assert one.material.equals(built.material)
    assert one.scene.primitives == built.scene.primitives
    assert one.fold_guides == built.fold_guides
    assert one.unfolded_topology == built.unfolded_topology
    assert one.metadata == built.metadata


def test_issue1817_exact_frame_source_and_authoring_dependencies(monkeypatch, tmp_path):
    """An A/B/D raw-frame cache needs identical certified source + typed part."""
    from dataclasses import replace
    from types import SimpleNamespace
    from ae_engine.inner_door_frames import derive_inner_door_frames
    from ae_engine import receiving_frame_baseline
    from gui_modules.application import fold_designer_manufacturing_projection as projection
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_cached_bay_inner_door_frame,
    )

    source = tmp_path / "框.dxf"
    source.write_bytes(b"certified-source-1")
    monkeypatch.setattr(receiving_frame_baseline, "frame_source_file", lambda: source)
    original = derive_inner_door_frames("demo", spans={"top": 700, "left": 1100,
        "right": 1100, "bottom": 700}, thickness=2)
    active = [next(frame for frame in original if frame.side == "top")]
    monkeypatch.setattr(projection, "_inner_door_frame_from_payload",
                        lambda key, payload: active[0])
    owner = SimpleNamespace()
    produced = []
    from hashlib import sha256
    def factory():
        material = SimpleNamespace(
            metadata={
                "receiving_frame_source_sha256": sha256(source.read_bytes()).hexdigest(),
                "receiving_frame_source_path": str(source),
            }
        )
        produced.append(material)
        return material
    data = {"model":"受電箱","active_mode":"set_bay","features":()}
    key = active[0].stable_id
    a = _receiving_cached_bay_inner_door_frame(owner, key, data, factory)
    assert _receiving_cached_bay_inner_door_frame(owner,key,data,factory) is a
    assert len(produced)==1
    # Exact source byte edits MUST retire material even if the frame is stable.
    source.write_bytes(b"certified-source-2")
    b = _receiving_cached_bay_inner_door_frame(owner,key,data,factory)
    assert b is not a and len(produced)==2
    active[0] = replace(active[0], span=701)
    c = _receiving_cached_bay_inner_door_frame(owner,key,data,factory)
    assert c is not b and len(produced)==3
    active[0] = next(frame for frame in original if frame.side == "top")
    changed_features = {**data, "features":({"kind":"圓孔","x":8,"y":8,"d1":4},)}
    d = _receiving_cached_bay_inner_door_frame(owner,key,changed_features,factory)
    assert d is not a and len(produced)==4
    # Unknown arbitrary feature DTOs are not fingerprinted optimistically.
    unknown = {**data, "features":(object(),)}
    e = _receiving_cached_bay_inner_door_frame(owner,key,unknown,factory)
    assert _receiving_cached_bay_inner_door_frame(owner,key,unknown,factory) is not e
    assert len(produced)==6
    # No permitted false hits for missing or unreliable source.
    source.unlink()
    sentinel = object()
    x = _receiving_cached_bay_inner_door_frame(
        owner,key,data,lambda: sentinel)
    assert x is sentinel

    active[0] = next(frame for frame in original if frame.side == "bottom")
    assert _receiving_cached_bay_inner_door_frame(
        owner, active[0].stable_id, data, lambda: sentinel) is sentinel
    assert len(owner._receiving_raw_inner_door_frame_history) <= 8


def test_issue1817_frame_factory_parity_and_source_generation(tmp_path, monkeypatch):
    """Actual certified source-backed frame survives only exact source authority."""
    from types import SimpleNamespace
    from ae_engine.inner_door_frames import derive_inner_door_frames
    from ae_engine import manufacturing_api
    from gui_modules.application import fold_designer_manufacturing_projection as projection
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_cached_bay_inner_door_frame,
    )
    from ae_engine.baseline_source import force_reload_baseline_dxf_sources

    # The actual Receiving physical trio excludes the optional generic
    # bottom role, whose independent explicit span is not supplied here.
    frames = derive_inner_door_frames("parity", spans={"top":700,"left":1100,
        "right":1100}, thickness=2, included_sides=("top", "left", "right"))
    frame = next(item for item in frames if item.side=="top")
    monkeypatch.setattr(projection,"_inner_door_frame_from_payload",
                        lambda key, payload: frame)
    data = {"model":"受電箱","active_mode":"set_bay","features":()}
    owner=SimpleNamespace()
    freshly = manufacturing_api.build_inner_door_frame_render_data(frame)
    cached=_receiving_cached_bay_inner_door_frame(
        owner,frame.stable_id,data,
        lambda: manufacturing_api.build_inner_door_frame_render_data(frame))
    again=_receiving_cached_bay_inner_door_frame(
        owner,frame.stable_id,data,
        lambda: (_ for _ in ()).throw(AssertionError("raw A/B/D rebuilt")))
    assert again is cached
    assert cached.material.equals(freshly.material)
    assert cached.scene.primitives == freshly.scene.primitives
    assert cached.fold_guides == freshly.fold_guides
    assert cached.unfolded_topology == freshly.unfolded_topology
    assert cached.metadata == freshly.metadata
    force_reload_baseline_dxf_sources()
    reload = _receiving_cached_bay_inner_door_frame(
        owner,frame.stable_id,data,
        lambda: manufacturing_api.build_inner_door_frame_render_data(frame))
    assert reload is not cached


def test_issue1817_receiving_divider_requires_two_exact_dxf_witnesses(
        monkeypatch, tmp_path):
    """Both Divider and EndCap DXF input versions invalidate raw reuse."""
    from dataclasses import replace
    from types import SimpleNamespace
    from hashlib import sha256
    from ae_engine.door_dividers import derive_box_body_dividers
    from ae_engine.manufacturing_baseline_policy import _baseline_path
    from ae_engine import manufacturing_baseline_policy as baseline_policy
    from ae_engine import cabinet_types
    from gui_modules.application import fold_designer_manufacturing_projection as projection
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_cached_bay_box_body_divider,
    )

    sources = {name: tmp_path / name for name in ("中隔.dxf", "封頭尾.dxf")}
    for name, path in sources.items():
        path.write_bytes(("source:"+name).encode("utf-8"))
    monkeypatch.setattr(baseline_policy, "_baseline_path",
        lambda _model, name, _ctx: sources[name] if sources[name].is_file() else None)
    monkeypatch.setattr(cabinet_types.policy,
        "divider_uses_endcap_6p4_shared_datum", lambda _model: True)
    monkeypatch.setattr(cabinet_types.policy, "baseline_feature_model_name",
                        lambda _model: "受電箱")
    from ae_engine.door_dividers import BoxBodyDividerPart
    frame = BoxBodyDividerPart(
        stable_id="box_body:divider:sample:HORIZONTAL:upper",
        owner="box_body", axis="HORIZONTAL", boundary_key="upper",
        span=800, thickness=2, formed_core_depth=350, handle_side=False,
        signed_fold_chain=(22, 46, 22), material_lengths=(22,46,22),
        fold_profile=(), adjacent_cells=("upper",), model_name="受電箱")
    current = [frame]
    monkeypatch.setattr(projection, "_box_body_divider_from_payload",
                        lambda key, payload: current[0])
    owner = SimpleNamespace()
    produced = []
    def factory():
        output = SimpleNamespace(metadata={
            "stable_id": current[0].stable_id,
            "baseline_feature_model": "受電箱",
            "endcap_shared_6p4_mother_rule": {"diameter":6.4}})
        produced.append(output)
        return output
    key = frame.stable_id
    data = {"model": "受電箱", "active_mode": "set_bay", "features": ()}
    one = _receiving_cached_bay_box_body_divider(owner,key,data,factory)
    assert _receiving_cached_bay_box_body_divider(owner,key,data,factory) is one
    assert len(produced) == 1
    sources["中隔.dxf"].write_bytes(b"divider source changed")
    two = _receiving_cached_bay_box_body_divider(owner,key,data,factory)
    assert two is not one and len(produced) == 2
    sources["封頭尾.dxf"].write_bytes(b"endcap mother changed")
    three = _receiving_cached_bay_box_body_divider(owner,key,data,factory)
    assert three is not two and len(produced) == 3
    current[:] = [replace(frame, span=801)]
    assert _receiving_cached_bay_box_body_divider(
        owner,key,data,factory) is not three
    current[:] = [frame]
    altered = {**data, "features": ({"kind":"圓孔","x":12,"y":12,"d1":6.4},)}
    assert _receiving_cached_bay_box_body_divider(
        owner,key,altered,factory) is not three
    sources["封頭尾.dxf"].unlink()
    assert _receiving_cached_bay_box_body_divider(
        owner,key,data,factory) is not three
    bad = {**data, "features": (object(),)}
    assert _receiving_cached_bay_box_body_divider(owner,key,bad,factory) is not three
    assert _receiving_cached_bay_box_body_divider(owner,key,bad,factory) is not three


def test_issue1817_divider_source_generation_and_real_factory_parity():
    """Certified Divider source + EndCap mother yield identical 2D material."""
    from ae_engine import manufacturing_api
    from ae_engine.cabinet_types import policy
    from ae_engine.door_dividers import derive_box_body_dividers
    from gui_modules.application import fold_designer_manufacturing_projection as projection
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_cached_bay_box_body_divider,
    )
    from ae_engine.baseline_source import force_reload_baseline_dxf_sources
    from types import SimpleNamespace

    # Derive the real signed folded physical Divider through the canonical
    # published door-layout boundary; no invented fold lengths or test mock.
    divider_keys = derive_box_body_dividers(
        ((800.0, (1100.0, 500.0)),),
        depth=350, thickness=2, layout_scope="demo",
        model_name="受電箱",
    )
    if not divider_keys:
        raise AssertionError("no canonical divider topology")
    divider = divider_keys[0]
    original = projection._box_body_divider_from_payload
    try:
        projection._box_body_divider_from_payload = lambda _key,_payload:divider
        target = divider.stable_id
        raw = manufacturing_api.build_box_body_divider_render_data(divider)
        owner = SimpleNamespace()
        data = {"model":"受電箱","active_mode":"set_bay","features":()}
        first = _receiving_cached_bay_box_body_divider(owner,target,data,
            lambda: manufacturing_api.build_box_body_divider_render_data(divider))
        second = _receiving_cached_bay_box_body_divider(owner,target,data,
            lambda: (_ for _ in ()).throw(AssertionError("recomputed Divider")))
        assert first is second
        assert first.material.equals(raw.material)
        assert first.scene.primitives == raw.scene.primitives
        assert first.unfolded_topology == raw.unfolded_topology
        assert first.metadata == raw.metadata
        force_reload_baseline_dxf_sources()
        assert _receiving_cached_bay_box_body_divider(owner,target,data,
            lambda: manufacturing_api.build_box_body_divider_render_data(divider)) is not first
    finally:
        projection._box_body_divider_from_payload = original


def test_issue1817_output_parity_reads_real_dxf_and_detects_changed_sheet(tmp_path):
    """A successful comparison must read exported CUTTING/BEND entities."""
    import pytest
    from ae_engine import manufacturing_api
    from ae_engine.sheetmetal_drawing import DrawingScene
    from phase6_final_scene_contracts import (
        AssemblyScenePart, AssemblySceneRenderData, FinalSceneViewRequest,
    )
    from tools.issue1817_output_parity import assert_preview_output_parity

    def view(extra_hole=False, offset=(0.0, 0.0, 0.0)):
        scene = DrawingScene()
        scene.add_polyline(((0,0),(100,0),(100,60),(0,60)),
                           layer="CUTTING", closed=True)
        scene.add_line((20,0),(20,60),layer="BEND")
        if extra_hole:
            scene.add_circle((30,30), 3, layer="CUTTING")
        render = manufacturing_api.PartRenderData(
            scene=scene,
            material=manufacturing_api.material_polygon_from_final_scene(scene),
            fold_guides=manufacturing_api.fold_guides_from_final_scene(scene),
            metadata={"part": "real-authority"},
        )
        part = AssemblyScenePart(
            part_key="box_body", render_data=render, x_profile=(),
            y_profile=(), placement="offset", offset=offset)
        return FinalSceneViewRequest(
            render_data=AssemblySceneRenderData(assembly_parts=(part,)),
            x_profile=(), y_profile=(), part_key="assembly",
        )

    original = view()
    assert assert_preview_output_parity(original, view(), tmp_path, label="same") == 1
    with pytest.raises(AssertionError, match="material|cutting"):
        assert_preview_output_parity(original, view(extra_hole=True), tmp_path,
                                     label="hole-change")
    with pytest.raises(AssertionError, match="3D/world"):
        assert_preview_output_parity(original, view(offset=(5,0,0)), tmp_path,
                                     label="world-change")


def test_issue1817_actual_p6fold_save_reload_preserves_three_bay_joint_authority(tmp_path):
    from ae_engine.receiving_layout import (
        new_receiving_layout, resize_receiving_bays, update_receiving_bay,
        normalize_receiving_layout,
    )
    from tools.issue1817_output_parity import save_reload_receiving_authority

    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=3,
    )
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=2,
        width=900, height=1700, depth=400,
    )
    original = {
        "model":"受電箱", "active_mode":"set_bay",
        "w":800.0,"h":1600.0,"d":350.0,"t":2.0,"fw":29.0,
        "receiving_layout":layout,
    }
    reopened = save_reload_receiving_authority(original, tmp_path)
    assert normalize_receiving_layout(reopened["receiving_layout"]) == (
        normalize_receiving_layout(layout))
    assert reopened["receiving_layout"]["sets"][0]["bays"][2]["width"] == 900.0


def test_issue1819_committed_bay_preview_history_is_bounded_and_recent_first():
    """Repeated add/remove and set switching cannot retain unbounded scenes."""
    from gui_modules.application.fold_designer_composition_receiving import (
        _retain_committed_receiving_bay_preview,
    )

    cache = {}
    identity = [object() for _ in range(48)]
    for number, receipt in enumerate(identity):
        assert _retain_committed_receiving_bay_preview(
            cache, (number // 6, number % 6), receipt
        ) is receipt
    assert len(cache) == 32
    assert (0, 0) not in cache
    assert (7, 5) in cache

    # Most recently selected committed Bay stays resident. Eviction never
    # fabricates its value or aliases another Bay's physical render request.
    warm = cache[(3, 0)]
    assert _retain_committed_receiving_bay_preview(cache, (3, 0), warm) is warm
    for i in range(20):
        _retain_committed_receiving_bay_preview(
            cache, (100 + i, 0), object(),
        )
    assert len(cache) == 32
    assert cache[(3, 0)] is warm
    # Replacing the same Bay with a changed exact fingerprint is a *new*
    # receipt; callers still require exact fingerprint matching before hits.
    replacement = object()
    _retain_committed_receiving_bay_preview(cache, (3, 0), replacement)
    assert cache[(3, 0)] is replacement
    assert replacement is not warm
    # Old evicted Bay must be rebuilt by the full canonical path on access.
    assert (0, 0) not in cache


def test_issue1819_committed_bay_preview_capacity_limits_cache_memory_references():
    from weakref import ref
    from gui_modules.application.fold_designer_composition_receiving import (
        _retain_committed_receiving_bay_preview,
    )

    class PhysicalResult:
        pass

    cache = {}
    first = PhysicalResult()
    probe = ref(first)
    _retain_committed_receiving_bay_preview(cache, (0, 0), first)
    del first
    for index in range(1, 48):
        _retain_committed_receiving_bay_preview(
            cache, (0, index), PhysicalResult(),
        )
    assert len(cache) == 32
    assert probe() is None, "evicted Result still retained by this cache"


def test_issue1817_real_default_intent_joints_allow_tail_reuse_but_custom_joints_do_not():
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
    from gui_modules.application.fold_designer_composition_receiving import (
        _receiving_default_local_joints_only,
    )

    # Fresh GUI defaults contain EndCap-to-BoxBody joints. They are local,
    # unlike user-authored or unknown graph dependencies.
    migrated = migrate_legacy_snapshot_joints({
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_type": "INSERT_OVERLAY",
    })
    joints = migrated["assembly_joints"]
    assert joints
    assert _receiving_default_local_joints_only(joints)
    initial = _layout(count=3)
    appended = resize_receiving_bays(initial, set_index=0, bay_count=4)
    assert _key(initial, 0, assembly_joints=joints) == _key(
        appended, 0, assembly_joints=joints
    )

    custom = deepcopy(joints)
    custom[0]["source"] = "USER_ADDED"
    assert not _receiving_default_local_joints_only(custom)
    assert _key(initial, 0, assembly_joints=custom) != _key(
        appended, 0, assembly_joints=custom
    )
    unknown = deepcopy(joints)
    unknown[0]["target_part"] = "some_other_bay"
    assert not _receiving_default_local_joints_only(unknown)
    assert _key(initial, 0, assembly_joints=unknown) != _key(
        appended, 0, assembly_joints=unknown
    )
