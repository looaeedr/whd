"""#2517: Hole Editor IndicatorBox CUTTING preview is one Engine projection."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_features import DoorIndicatorContext, ResolvedRect
from gui_modules.editors.hole_editor_render import HoleEditorCanvasRenderer


@pytest.mark.parametrize("groups,t,ox,oy", [
    ((1,), 2.0, 0.0, 0.0),
    ((2, 3), 2.0, 12.0, -7.0),
    ((4,), 1.5, -25.0, 30.0),
])
def test_public_engine_preview_reuses_actual_opening_size(groups, t, ox, oy):
    context = DoorIndicatorContext(
        finished_width=900.0, finished_height=1200.0,
        left_fold=19.0, bottom_fold=20.0,
    )
    feature = manufacturing_api.project_operator_hole_editor_indicator_box_opening(
        context, groups, thickness=t, offset_x=ox, offset_y=oy,
    )
    assert isinstance(feature, ResolvedRect)
    assert (feature.width, feature.height) == manufacturing_api.indicator_box_opening_size(
        groups, thickness=t,
    )
    assert (feature.center.x, feature.center.y) == (
        19.0 + 450.0 + ox, 20.0 + 600.0 + oy,
    )
    assert feature.layer == "CUTTING"
    assert feature.source_type == "indicator_box_opening"
    with pytest.raises(FrozenInstanceError):
        feature.width = 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "wrong"])
def test_preview_rejects_invalid_operator_offsets(bad):
    context = DoorIndicatorContext(
        finished_width=900, finished_height=1200, left_fold=19, bottom_fold=19,
    )
    with pytest.raises(ValueError):
        manufacturing_api.project_operator_hole_editor_indicator_box_opening(
            context, (2,), thickness=2, offset_x=bad,
        )


def test_preview_rejects_missing_groups_without_an_unverified_fallback():
    context = DoorIndicatorContext(
        finished_width=900, finished_height=1200, left_fold=19, bottom_fold=19,
    )
    with pytest.raises(ValueError):
        manufacturing_api.project_operator_hole_editor_indicator_box_opening(
            context, (), thickness=2,
        )


def test_gui_indicator_box_preview_uses_only_engine_feature(monkeypatch):
    expected = object()
    evidence = []
    def project(context, groups, **kwargs):
        evidence.append((context, groups, kwargs))
        return expected
    monkeypatch.setattr(
        manufacturing_api, "project_operator_hole_editor_indicator_box_opening",
        project,
    )
    indicator_context = object()
    canvas = object()
    transform = object()
    renderer = HoleEditorCanvasRenderer.__new__(HoleEditorCanvasRenderer)
    renderer.context_provider = lambda: {
        "active_part_key": "door",
        "indicator_mode_available": True,
        "door_indicator_context": indicator_context,
        "door_thickness": 2.0,
    }
    renderer._draw_enclosure = lambda *args: None
    renderer.collect_indicator_state = lambda: {
        "mode": "indicator_box", "groups": [2, 3], "layers": 2,
        "offset_x": 12.0, "offset_y": -7.0,
    }
    renderer.render_resolved_features = lambda *args, **kwargs: evidence.append(
        (args, kwargs)
    )
    renderer.draw_extra(None, canvas, transform, 800, 600)
    assert evidence[0] == (indicator_context, (2, 3), {
        "thickness": 2.0, "offset_x": 12.0, "offset_y": -7.0,
    })
    assert evidence[1] == ((canvas, [expected], transform), {"color": "#64d2ff"})
    src = inspect.getsource(HoleEditorCanvasRenderer.draw_extra)
    assert "manufacturing_api.project_operator_hole_editor_indicator_box_opening(" in src
    assert "indicator_context.left_fold" not in src
    assert "indicator_context.finished_width / 2.0" not in src
