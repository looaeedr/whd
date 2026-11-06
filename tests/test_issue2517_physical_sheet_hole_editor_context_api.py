"""#2517 physical-sheet Hole Editor selects actual canonical part through Engine."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import CustomFoldPartSpec, FoldProfileSegment
from ae_engine.custom_fold_manufacturing import build_custom_fold_render_data
from ae_engine.physical_sheet_features import physical_sheet_feature_context
from gui_modules.application import physical_part_hole_editor as gui_editor


def _spec(key="custom:17", axis="X"):
    return CustomFoldPartSpec(
        physical_id=key, fold_axis=axis,
        fold_profile=(
            FoldProfileSegment(15.0, angle=-90.0, phase6_key="flange"),
            FoldProfileSegment(98.0, angle=None, core="CUSTOM_FACE", phase6_key="face"),
        ),
        transverse_length=300.0, thickness=2.0,
    )


@pytest.mark.parametrize("axis", ["X", "Y"])
def test_custom_fold_editor_uses_real_engine_surface_and_material_reference(axis):
    spec = _spec(axis=axis)
    render = build_custom_fold_render_data(spec)
    context = manufacturing_api.resolve_physical_sheet_editor_context(
        spec.physical_id, render, custom_spec=spec,
    )
    assert isinstance(context, manufacturing_api.PhysicalSheetEditorContext)
    assert context.render_data is render
    assert context.reference_guide.role == "custom_finished_face"
    assert context.width > 0 and context.height > 0
    assert context.feature_surface is not None
    assert context.render_data.scene is render.scene
    assert render.fold_guides


def test_one_box_body_physical_sheet_is_selected_by_engine_not_guessed_by_gui():
    spec = _spec()
    render = build_custom_fold_render_data(spec)
    pieces = (
        SimpleNamespace(role="left_side", render_data=render),
        SimpleNamespace(role="right_side", render_data=render),
    )
    bundle = SimpleNamespace(pieces=pieces)
    context = manufacturing_api.resolve_physical_sheet_editor_context(
        "box_body:right_side", bundle,
    )
    surface, width, height, guide = physical_sheet_feature_context("box_body:right_side", render)
    assert context.render_data is render
    assert (context.width, context.height) == (width, height)
    assert context.reference_guide == guide
    assert context.feature_surface.polygon.equals(surface.polygon)


def test_physical_sheet_selection_fails_closed_for_missing_or_duplicate_piece():
    render = build_custom_fold_render_data(_spec())
    for pieces in (
        (), (SimpleNamespace(role="left_side", render_data=render),) * 2,
    ):
        with pytest.raises(ValueError, match="唯一實體箱身板件"):
            manufacturing_api.resolve_physical_sheet_editor_context(
                "box_body:left_side", SimpleNamespace(pieces=pieces),
            )


def test_engine_rejects_missing_scene_and_mismatched_custom_source():
    spec = _spec()
    render = build_custom_fold_render_data(spec)
    with pytest.raises(ValueError, match="PartSpec"):
        manufacturing_api.resolve_physical_sheet_editor_context(
            "custom:17", render, custom_spec=_spec("custom:18"),
        )
    with pytest.raises(ValueError, match="DrawingScene"):
        manufacturing_api.resolve_physical_sheet_editor_context(
            "base_plate", SimpleNamespace(scene=None),
        )
    with pytest.raises(ValueError, match="不接受"):
        manufacturing_api.resolve_physical_sheet_editor_context(
            "base_plate", render, custom_spec=spec,
        )


def test_gui_only_invokes_public_engine_context_and_keeps_commit_port():
    source = inspect.getsource(gui_editor.open_workspace_sheet_editor)
    assert "manufacturing_api.resolve_physical_sheet_editor_context(" in source
    assert "physical_sheet_feature_context(" not in source
    assert "custom_fold_feature_context(" not in source
    assert "f'box_body:{p.role}'" not in source
    assert "workspace.stash_features(" in source
    assert "submit_update_intent('geometry', commit=True)" in source
