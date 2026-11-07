# -*- coding: utf-8 -*-
"""#2517 physical sheet Hole Editor candidate must pass canonical Engine surface."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import ae_engine
import pytest
from ae_engine import manufacturing_api
from ae_engine.contracts import CustomFoldPartSpec, FoldProfileSegment
from ae_engine.custom_fold_manufacturing import build_custom_fold_render_data
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import physical_part_hole_editor as gui


def _spec(axis="X", key="custom:17"):
    return CustomFoldPartSpec(
        physical_id=key, fold_axis=axis,
        fold_profile=(
            FoldProfileSegment(15., angle=-90., phase6_key="flange"),
            FoldProfileSegment(98., angle=None, core="CUSTOM_FACE", phase6_key="face"),
        ),
        transverse_length=300., thickness=2.,
    )


def _context(axis="X"):
    spec = _spec(axis)
    render = build_custom_fold_render_data(spec)
    return manufacturing_api.resolve_physical_sheet_editor_context(
        spec.physical_id, render, custom_spec=spec,
    ), spec, render


def _hole(x=60., y=80.):
    return CircleFeature(
        diameter=8., anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y), layer="CUTTING",
    )


def test_root_facade_and_owner_identity():
    from ae_engine.physical_sheet_editor_context import (
        propose_operator_physical_sheet_hole_features as canonical,
    )
    assert ae_engine.propose_operator_physical_sheet_hole_features is canonical
    assert manufacturing_api.propose_operator_physical_sheet_hole_features is canonical
    assert "propose_operator_physical_sheet_hole_features" in ae_engine.__all__


@pytest.mark.parametrize("axis", ("X", "Y"))
def test_typed_physical_candidate_is_validated_and_detached(axis):
    context, spec, render = _context(axis)
    original = [_hole()]
    before = deepcopy(original)
    proposed = manufacturing_api.propose_operator_physical_sheet_hole_features(
        spec.physical_id, context, original,
    )
    assert proposed == tuple(original)
    assert proposed[0] is not original[0]
    assert original == before
    assert context.render_data is render and context.part_key == spec.physical_id


def test_legacy_hole_dict_roundtrips_unchanged_after_engine_validation():
    context, spec, _ = _context()
    features = [{"type": "round", "x": 60., "y": 80.,
                 "params": {"diameter": 6.}}]
    before = deepcopy(features)
    accepted = manufacturing_api.propose_operator_physical_sheet_hole_features(
        spec.physical_id, context, features,
    )
    assert accepted == tuple(before)
    assert accepted[0] is not features[0]
    assert features == before


@pytest.mark.parametrize("bad", (
    [_hole(700., 700.)], ["not_a_feature"], [False],
    None, {"shape": "circle"}, "bad_feature_sequence",
    [{"type": "round", "x": 60., "y": 80.}],
))
def test_bad_or_outside_features_reject_without_touching_draft(bad):
    context, spec, _ = _context()
    before = deepcopy(bad)
    with pytest.raises((ValueError, TypeError, KeyError)):
        manufacturing_api.propose_operator_physical_sheet_hole_features(
            spec.physical_id, context, bad,
        )
    assert bad == before


def test_cross_part_context_rejected_without_mutation():
    context, spec, _ = _context()
    holes = [_hole()]
    before = deepcopy(holes)
    with pytest.raises(ValueError, match="板件身分"):
        manufacturing_api.propose_operator_physical_sheet_hole_features(
            "custom:18", context, holes,
        )
    assert holes == before


def test_gui_editor_rechecks_on_save_before_stash_or_update(monkeypatch):
    import phase6_manufacturing_adapter
    import phase6_part_navigation

    context, spec, render = _context()
    workspace_values = []
    notifications = []
    draft = [_hole()]
    workspace = SimpleNamespace(
        available_parts=(spec.physical_id,),
        active_part=spec.physical_id,
        features_for=lambda key: draft,
        stash_features=lambda key, rows: workspace_values.append((key, tuple(rows))),
    )
    app = SimpleNamespace(
        designer_workspace=workspace,
        _load_part_holes=lambda _key: None,
        submit_update_intent=lambda *a, **kw: notifications.append((a, kw)),
    )
    params = {}
    host = SimpleNamespace(
        fold_designer_app=app,
        _query_fold_designer_render_data=lambda *_args: render,
        _fold_designer_part_spec_from_payload=lambda *_args: (spec, None),
        _open_unified_hole_editor=lambda *args, **kw: params.update(kw) or object(),
    )
    monkeypatch.setattr(phase6_manufacturing_adapter,
                        "build_scene_payload_for_app", lambda *_args: {})
    monkeypatch.setattr(phase6_part_navigation,
                        "operator_part_label", lambda *_args, **_kw: "自訂板件")
    gui.open_workspace_sheet_editor(host, spec.physical_id)
    staged = params["feature_list_override"]
    staged.append(_hole(900., 900.))
    with pytest.raises(ValueError, match="feature outside"):
        params["sync_callback"]()
    assert workspace_values == [] and notifications == []
    staged.pop()
    params["sync_callback"]()
    assert len(workspace_values) == len(notifications) == 1
    assert workspace_values[0][0] == spec.physical_id


def test_gui_seam_uses_public_transaction_and_never_resolves_geometry_itself():
    source = inspect.getsource(gui.open_workspace_sheet_editor)
    assert "manufacturing_api.propose_operator_physical_sheet_hole_features(" in source
    assert source.index("propose_operator_physical_sheet_hole_features(") < source.index("workspace.stash_features(")
    assert "legacy_hole_to_feature(" not in source
    assert "resolve_surface_features(" not in source
