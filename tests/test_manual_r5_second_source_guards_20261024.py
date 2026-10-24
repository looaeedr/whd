"""Manual source-reviewed R5 Set/Bay, frame, lock and editor guards."""
from types import SimpleNamespace
import pytest
from ae_engine.receiving_inner_door_pairing import paired_bay_parts, paired_set_parts
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_frame_baseline import receiving_frame_source
from ae_engine.receiving_joint_locks import resolve_receiving_joint_lock_pattern
from ae_engine.sheetmetal_features import ResolvedProfile, Vec2
from phase6_hole_editor_canvas_view import Phase6HoleEditorCanvasView
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession


def _layout():
    return new_receiving_layout(width=800., height=1800., depth=400.)


@pytest.mark.parametrize("bad", [-1, True, False])
def test_r5_80_rejects_bad_set_bay_indices(bad):
    for fn in (
        lambda: paired_bay_parts(_layout(), set_index=bad, bay_index=0),
        lambda: paired_bay_parts(_layout(), set_index=0, bay_index=bad),
        lambda: paired_set_parts(_layout(), set_index=bad),
    ):
        with pytest.raises((IndexError, ValueError)):
            fn()
    assert paired_bay_parts(_layout(), set_index=0, bay_index=0)["bay_id"] == "receiving:set:1:bay:1"


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf")])
def test_r5_85_invalid_frame_dimensions_fail_before_external_dxf_load(bad):
    for field in ("material_width", "span"):
        args = {"material_width": 90., "span": 1000.}
        args[field] = bad
        with pytest.raises(ValueError, match="DIMENSIONS_INVALID"):
            receiving_frame_source("left", **args)


@pytest.mark.parametrize("bad", [True, False])
def test_r5_86_joint_lock_indices_must_be_real_integers(bad):
    with pytest.raises(TypeError):
        resolve_receiving_joint_lock_pattern(_layout(), set_index=bad, joint_index=0)
    with pytest.raises(TypeError):
        resolve_receiving_joint_lock_pattern(_layout(), set_index=0, joint_index=bad)


def test_r5_88_layered_canvas_profile_without_primary_geometry():
    view = Phase6HoleEditorCanvasView(
        canvas=SimpleNamespace(), draw_grid=lambda: None,
        render_secondary_scene=lambda *args: None,
        render_resolved_features=lambda *args: None,
    )
    view.transform = SimpleNamespace(world_to_canvas=lambda pt: (float(pt.x), float(pt.y)))
    prof = ResolvedProfile(
        points=(), layer="FROM_DXF", source_type="test",
        layered_profiles=(("CUTTING", (Vec2(10., 20.), Vec2(30., 50.)), False),),
    )
    assert view._resolved_canvas_rect(prof) == (10., 20., 30., 50.)
    empty = ResolvedProfile(points=(), layer="FROM_DXF", source_type="test", layered_profiles=())
    assert view._resolved_canvas_rect(empty) is None


def test_r5_89_hole_session_bool_selection_never_mutates():
    with pytest.raises(TypeError):
        HoleEditorAction.select(False)
    with pytest.raises(TypeError):
        HoleEditorAction.preview_all([], selected_index=False)
    session = Phase6HoleEditorSession("door", ["hole0"])
    before = session.snapshot()
    with pytest.raises(ValueError):
        session.execute(HoleEditorAction("select", index=False))
    with pytest.raises(ValueError):
        session.execute(HoleEditorAction("preview_all", features=(), selected_index=False))
    assert session.snapshot() == before
