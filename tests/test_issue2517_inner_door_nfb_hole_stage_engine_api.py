"""#2517 Engine owns source/physical admission of Receiving NFB inner-door holes."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import (
    CircleFeature, FeatureAnchor, ProfileFeature,
)
from ae_engine.sheetmetal_feature_surface import feature_surface_from_outline
from ae_engine.sheetmetal_geometry import Vec2


PANEL = "inner_door:upper:panel"


def _surface():
    return feature_surface_from_outline(
        PANEL, (Vec2(0, 0), Vec2(100, 0), Vec2(100, 60), Vec2(0, 60)),
    )


def _hole(*, x=50, y=30, kind="NFB_CSV_SOURCE", part_id=PANEL):
    return ProfileFeature(
        points=(Vec2(-10, -8), Vec2(10, -8), Vec2(10, 8), Vec2(-10, 8)),
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y), source_type=kind,
        source_params=(("part_id", part_id),),
    )


def _normal():
    return CircleFeature(
        diameter=8, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(15, 15),
    )


def _plan(current=(), incoming=(), mode="csv_replace", part_key=PANEL):
    return api.plan_operator_inner_door_nfb_hole_stage(
        part_key=part_key, surface=_surface(), width=100.0, height=60.0,
        current_features=current, incoming_features=incoming, mode=mode,
    )


def test_verified_import_appends_to_operator_holes_without_mutation():
    operator = _normal()
    verified = _hole(kind="NFB_VERIFIED_SOURCE")
    existing = [operator]
    incoming = [verified]
    projected = _plan(existing, incoming, mode="verified_append")
    assert projected == (operator, verified)
    assert existing == [operator] and incoming == [verified]


def test_duplicate_or_untrusted_verified_source_rejected():
    with pytest.raises(ValueError, match="不能帶入未完成"):
        _plan(incoming=(), mode="verified_append")
    with pytest.raises(ValueError, match="不能帶入未完成"):
        _plan(incoming=(_normal(),), mode="verified_append")
    with pytest.raises(ValueError, match="相同 NFB"):
        _plan(current=(_hole(),), incoming=(_hole(kind="NFB_VERIFIED_SOURCE"),),
              mode="verified_append")
    with pytest.raises(ValueError, match="其他實體內門"):
        _plan(incoming=(_hole(part_id="inner_door:other:panel"),),
              mode="verified_append")


def test_csv_stage_preserves_operator_features_and_replaces_only_its_drafts():
    operator = _normal()
    old = _hole(x=35)
    fresh = _hole(x=70)
    before = (operator, old)
    assert _plan(current=before, incoming=(fresh,)) == (operator, fresh)
    assert _plan(current=before, incoming=()) == (operator,)
    assert before == (operator, old)


def test_csv_rejects_wrong_type_cross_part_and_older_verified_source():
    with pytest.raises(ValueError, match="CSV 主孔"):
        _plan(incoming=(_hole(kind="NFB_VERIFIED_SOURCE"),))
    with pytest.raises(ValueError, match="其他實體內門"):
        _plan(incoming=(_hole(part_id="inner_door:other:panel"),))
    with pytest.raises(ValueError, match="已有來源驗證"):
        _plan(current=(_hole(kind="NFB_VERIFIED_SOURCE"),), incoming=(_hole(),))
    verified = _hole(kind="NFB_VERIFIED_SOURCE")
    assert _plan(current=(verified,), incoming=()) == (verified,)


@pytest.mark.parametrize("mode,error", [
    ("verified_append", "超出內門實體平面"),
    ("csv_replace", "超出目前內門板面"),
])
def test_real_finished_face_boundary_and_outside_fail_closed(mode, error):
    for x in (10.0, 9.9, 101.0):
        with pytest.raises(ValueError, match=error):
            _plan(incoming=(_hole(x=x),), mode=mode)


def test_fail_closed_on_other_part_role_and_operation():
    with pytest.raises(ValueError, match="實體內門板"):
        _plan(part_key="inner_door:upper:left_frame", incoming=(_hole(),))
    with pytest.raises(ValueError, match="unknown NFB"):
        _plan(incoming=(_hole(),), mode="unknown")


def test_gui_uses_only_engine_admission_before_undoable_preview():
    from gui_modules.editors import hole_editor_composition as gui
    source = inspect.getsource(gui._bind_editor_actions)
    assert source.count("d.manufacturing_api.plan_operator_inner_door_nfb_hole_stage(") == 2
    assert "feature_is_strictly_within_surface(" not in source
    assert "from ae_engine.sheetmetal_features import ProfileFeature" not in source
    assert source.count("HoleEditorAction.preview_all(projected)") == 2
    import ae_engine.receiving_nfb_hole_stage as owner
    engine = inspect.getsource(owner)
    assert "from gui_modules" not in engine and "from phase6_" not in engine
