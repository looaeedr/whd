"""#2517: Engine owns physical Receiving inner-door Hole Editor geometry."""
from __future__ import annotations
import inspect
import pytest
from ae_engine import manufacturing_api
from gui_modules.application import receiving_inner_door_hole_editor as gui_editor

PART = "inner_door:upper:panel"

def snapshot():
    return {
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    }

def test_headless_real_panel_and_independent_reference_guides():
    request = snapshot()
    context = manufacturing_api.resolve_inner_door_hole_editor_context(request, PART)
    assert context.panel.stable_id == PART
    assert context.panel.width == pytest.approx(689.0)
    assert context.panel.height == pytest.approx(1041.0)
    assert context.structural.width == pytest.approx(723.0)
    assert context.structural.height == pytest.approx(1075.0)
    assert context.work_area_guide.width == pytest.approx(800.0)
    assert context.work_area_guide.height == pytest.approx(1100.0)
    assert context.local_reference_guide.width == pytest.approx(context.panel.width)
    assert context.local_reference_guide.height == pytest.approx(context.panel.height)
    assert context.work_area_guide.role == "receiving_inner_door_work_area"
    assert context.work_area_guide.min_point.x == pytest.approx(-38.5)
    assert context.work_area_guide.min_point.y == pytest.approx(13.5)
    assert request["door_layout_columns"][0][1][0] == 1100.0

def test_engine_context_canonical_cutting_and_bend_not_display_rectangle():
    context = manufacturing_api.resolve_inner_door_hole_editor_context(snapshot(), PART)
    assert context.render.metadata["stable_id"] == PART
    assert context.render.fold_guides
    assert context.render.material.area < context.structural.width * context.structural.height
    assert context.feature_surface is not None
    assert context.work_area_guide.width != context.structural.width
    assert (context.frame_edges.left, context.frame_edges.right,
            context.frame_edges.top, context.frame_edges.bottom) == (False,) * 4

@pytest.mark.parametrize("key", ["door", "inner_door:upper:top_frame", "inner_door:absent:panel"])
def test_api_rejects_invalid_or_absent_physical_panel(key):
    with pytest.raises(ValueError, match="內門"):
        manufacturing_api.resolve_inner_door_hole_editor_context(snapshot(), key)

def test_api_rejects_disabled_panel_without_preview_fallback():
    request = snapshot()
    request["inner_doors"] = []
    with pytest.raises(ValueError, match="目前專案沒有"):
        manufacturing_api.resolve_inner_door_hole_editor_context(request, PART)

def test_gui_delegates_without_recomputing_manufacturing_dimensions():
    source = inspect.getsource(gui_editor.open_inner_door_hole_editor)
    assert "manufacturing_api.resolve_inner_door_hole_editor_context(" in source
    for private_call in (
        "build_door_result(", "derive_inner_door_panels(",
        "inner_door_panel_vertical_contract(", "build_finished_reference_guide(",
    ):
        assert private_call not in source
    assert not hasattr(gui_editor, "inner_door_work_area_guide")
