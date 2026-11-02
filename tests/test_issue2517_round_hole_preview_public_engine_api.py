"""#2517 physical round-hole preview belongs to Engine; GUI stages only."""
from dataclasses import FrozenInstanceError
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, FeatureAnchor, feature_finished_point,
    feature_surface_from_rect,
)
from gui_modules.editors import hole_editor_round_settings as gui
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession


def hole(x, y, diameter=20):
    return CircleFeature(
        diameter=diameter, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y),
    )


def point(feature):
    value = feature_finished_point(feature, 100.0, 80.0)
    return value.x, value.y


@pytest.mark.parametrize("refill,expected", [
    (False, [(20.0, 40.0), (45.0, 40.0), (70.0, 40.0)]),
    (True, [(15.0, 40.0), (40.0, 40.0), (65.0, 40.0), (90.0, 40.0)]),
])
def test_public_engine_preview_matches_actual_fill_and_refill(refill, expected):
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(100, 80))
    source = [hole(20, 40)]
    result = manufacturing_api.plan_operator_round_hole_preview(
        source, 0, surface, width=100, height=80,
        direction="right", driver="center", value=25, refill=refill,
    )
    assert sorted(point(p) for p in result.features) == expected
    assert result.generated_count == len(expected)
    assert result.selected_index == 0
    assert source == [hole(20, 40)]
    with pytest.raises(FrozenInstanceError):
        result.selected_index = 4


def test_nearest_neighbor_and_top_alignment_preserve_unrelated_physical_holes():
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(100, 80))
    source = [
        hole(20, 30),
        RectFeature(width=10, height=10, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(80, 60)),
        hole(60, 50, 30),
        hole(90, 70),
    ]
    nearest = manufacturing_api.nearest_operator_round_hole_neighbor_index(
        source, 0, width=100, height=80,
    )
    assert nearest == 2
    result = manufacturing_api.plan_operator_round_hole_preview(
        source, 0, surface, width=100, height=80, direction="right",
        driver="center", value=25, neighbor_index=nearest, alignment="top",
    )
    assert point(result.features[0]) == (20.0, 55.0)
    assert result.features[1:4] == tuple(source[1:4])
    assert point(source[0]) == (20.0, 30.0)


@pytest.mark.parametrize("index,neighbor", [
    (True, None), (1, None), (0, True), (0, 0), (0, 8),
])
def test_invalid_selected_or_neighbor_identity_fails_without_mutation(index, neighbor):
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(100, 80))
    source = [hole(20, 40)]
    with pytest.raises(ValueError):
        manufacturing_api.plan_operator_round_hole_preview(
            source, index, surface, width=100, height=80,
            direction="right", driver="center", value=25,
            neighbor_index=neighbor,
        )
    assert source == [hole(20, 40)]


def test_real_engine_preview_can_cancel_and_undo_through_existing_session():
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(100, 80))
    source = [hole(20, 40)]
    session = Phase6HoleEditorSession("door", source)
    options = dict(width=100, height=80, direction="right", driver="center", value=25)
    plan = manufacturing_api.plan_operator_round_hole_preview(source, 0, surface, **options)
    session.execute(HoleEditorAction.preview_all(plan.features, selected_index=plan.selected_index))
    assert len(source) == 3
    session.execute(HoleEditorAction.cancel_active())
    assert source == [hole(20, 40)]
    plan = manufacturing_api.plan_operator_round_hole_preview(source, 0, surface, **options)
    session.execute(HoleEditorAction.preview_all(plan.features, selected_index=plan.selected_index))
    session.execute(HoleEditorAction.commit_active())
    session.execute(HoleEditorAction.undo())
    assert source == [hole(20, 40)]


def test_gui_pattern_adapter_has_no_independent_geometry():
    body = inspect.getsource(gui._RoundHoleSettingsDialog._apply_pattern)
    assert "manufacturing_api.plan_operator_round_hole_preview(" in body
    nearest = inspect.getsource(gui._RoundHoleSettingsDialog._find_neighbor)
    assert "manufacturing_api.nearest_operator_round_hole_neighbor_index(" in nearest
    for forbidden in ("generate_round_fill(", "align_circle_to_neighbor(", "feature_finished_point("):
        assert forbidden not in body + nearest


def test_gui_pattern_consumes_engine_preview_and_does_not_derive_positions(monkeypatch):
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(100, 80))
    source = [hole(20, 40)]
    session = Phase6HoleEditorSession("door", source)
    original = manufacturing_api.plan_operator_round_hole_preview
    observed = []

    def spy(*args, **kwargs):
        observed.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(manufacturing_api, "plan_operator_round_hole_preview", spy)

    class Field:
        def __init__(self, value): self.value = value
        def get(self): return self.value
        def set(self, value): self.value = value

    dialog = gui._RoundHoleSettingsDialog.__new__(gui._RoundHoleSettingsDialog)
    dialog.seed_snapshot = list(source)
    dialog.idx = 0
    dialog.surface = surface
    dialog.width, dialog.height = 100.0, 80.0
    dialog.hole_session = session
    dialog.direction_map = {"向右": "right"}
    dialog.round_direction = Field("向右")
    dialog.round_driver = Field("center")
    dialog.round_center = Field("25")
    dialog.round_alignment = Field("center")
    dialog.neighbor_index = None
    dialog.status_var = Field("")
    dialog._refresh_all = lambda: None
    dialog._apply_pattern()
    assert observed[0]["direction"] == "right" and observed[0]["value"] == 25
    assert len(source) == 3
    assert dialog.status_var.get() == "預覽：3 孔；填滿。"
    session.execute(HoleEditorAction.cancel_active())
    assert source == [hole(20, 40)]
