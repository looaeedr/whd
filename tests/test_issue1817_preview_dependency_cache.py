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
                projected, set_index=0, bay_index=0),
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
