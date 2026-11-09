"""#2517 Hole Editor insert/rotate physical Features via one public Engine API."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import _normalize_rotation
from ae_engine.sheetmetal_features import (
    FeatureAnchor, RectFeature, feature_surface_from_rect,
)
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.editors.hole_editor import (
    HoleEditorFeatureFactory, HoleEditorSelectedFeatureActions,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession


def hole(*, x=50., y=50., w=32., h=14.):
    return RectFeature(
        width=w, height=h, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(x, y), layer="CUTTING", rotation_deg=0,
    )


@pytest.mark.parametrize("raw,expected", [
    (0, 0), (90, 90), (180, 180), (270, 270), (360, 0),
    ("90°", 90), ("180°", 180), ("270°", 270), ("360°", 0),
    (" 90 ° ", 90), ("+270°", 270), (90.0, 90),
])
def test_engine_control_rotation_matches_canonical_feature_geometry(raw, expected):
    source = hole()
    unchanged = deepcopy(source)
    assert api.operator_hole_rotation_from_control(raw) == expected
    candidate = api.operator_hole_feature_with_rotation(source, raw)
    assert candidate == replace(source, rotation_deg=_normalize_rotation(expected))
    assert candidate.rotation_deg == expected
    assert source == unchanged
    assert ae_engine.operator_hole_feature_with_rotation is (
        api.operator_hole_feature_with_rotation
    )
    assert ae_engine.operator_hole_rotation_from_control is (
        api.operator_hole_rotation_from_control
    )
    # A detached Feature's rotation is the same stored Save→Reload scalar.
    assert json.loads(json.dumps({"rotation_deg": candidate.rotation_deg})) == {
        "rotation_deg": expected,
    }


@pytest.mark.parametrize("invalid", [
    True, False, None, "", "°", "90.5°", "90_0°", "true",
    "NaN", float("nan"), float("inf"), 90.5, -1, 45, {}, [],
])
def test_invalid_rotation_never_changes_original_physical_hole(invalid):
    current = hole()
    before = deepcopy(current)
    with pytest.raises((TypeError, ValueError, OverflowError)):
        api.operator_hole_rotation_from_control(invalid)
    with pytest.raises((TypeError, ValueError, OverflowError)):
        api.operator_hole_feature_with_rotation(current, invalid)
    assert current == before


def test_engine_rejects_unsupported_feature_instead_of_forging_new_physical_hole():
    with pytest.raises(ValueError, match="unsupported"):
        api.operator_hole_feature_with_rotation({"rotation_deg": 0}, 90)


def _var(value):
    return SimpleNamespace(get=lambda: value)


def _factory(rotation, errors):
    return HoleEditorFeatureFactory(
        selected_catalog_text=_var("＋ 自訂方孔"), rotation_var=_var(rotation),
        diameter_var=_var("10"), width_var=_var("30.25"),
        height_var=_var("11.5"), blind_var=_var(False),
        context_provider=lambda: {"width": 100., "height": 100.},
        catalog_by_label={},
        custom_circle_definition=api.operator_custom_circle_definition,
        custom_rectangle_definition=api.operator_custom_rectangle_definition,
        feature_from_definition=api.operator_hole_feature_from_definition,
        feature_with_reference_anchor=lambda feature, anchor: feature,
        center_anchor=None,
        show_error=lambda title, message: errors.append((title, message)),
    )


def test_real_gui_factory_passes_engine_validated_angle_into_original_feature_builder():
    errors = []
    built = _factory("270°", errors).make_feature(Vec2(50., 50.))
    assert isinstance(built, RectFeature)
    assert (built.width, built.height, built.rotation_deg) == (30.25, 11.5, 270)
    assert errors == []
    assert api.operator_hole_feature_is_within_surface(
        feature_surface_from_rect("door", Vec2(0., 0.), Vec2(100., 100.)),
        built, 100., 100.,
    )
    assert _factory("360°", errors).make_feature(Vec2(50., 50.)).rotation_deg == 0
    assert errors == []
    for invalid in ("89.5°", "90_0°", "nan", ""):
        assert _factory(invalid, errors).make_feature(Vec2(50., 50.)) is None
    assert len(errors) == 4
    assert all(title == "開孔錯誤" for title, _ in errors)


def _action_host(*, x=50., y=50., w=32., h=14.):
    original = hole(x=x, y=y, w=w, h=h)
    features = [original]
    session = Phase6HoleEditorSession("door", features)
    session.execute(HoleEditorAction.select(0))
    ui = SimpleNamespace(value="360°", set=lambda value: setattr(ui, "value", value))
    events = []
    surface = feature_surface_from_rect("door", Vec2(0., 0.), Vec2(100., 100.))
    actions = HoleEditorSelectedFeatureActions(
        hole_session=session, canvas_view=None,
        context_provider=lambda: {
            "feature_list": features, "surface": surface, "width": 100.,
            "height": 100.,
        },
        select_feature=lambda idx: None, menu_factory=lambda: None,
        reference_anchor_labels={}, feature_reference_anchor=lambda _: None,
        set_reference_anchor=lambda _: None, var_rotation=ui,
        rotate_feature=api.operator_hole_feature_with_rotation,
        feature_is_within_surface=api.operator_hole_feature_is_within_surface,
        warn_rotation_out_of_bounds=lambda: events.append("out-of-bounds"),
        refresh_reference_fields=lambda: events.append("refresh"),
        redraw=lambda: events.append("redraw"),
        sync_all=lambda: events.append("sync"),
    )
    return actions, features, session, ui, events


def test_actual_gui_rotation_uses_engine_and_retains_undo_and_no_side_effect_on_invalid():
    actions, features, session, ui, events = _action_host()
    before = session.snapshot()
    for invalid in (True, "89.5°", 45, float("nan")):
        with pytest.raises(ValueError):
            actions.rotate_selected(invalid)
        assert session.snapshot() == before
        assert ui.value == "360°"
        assert events == []
    actions.rotate_selected(90)
    assert features[0].rotation_deg == 90
    assert ui.value == "90°"
    assert events == ["refresh", "redraw", "sync"]
    session.execute(HoleEditorAction.undo())
    assert features[0].rotation_deg == 0


def test_rotation_that_exceeds_surface_keeps_selected_feature_and_control_unchanged():
    # Unrotated 20×42 rectangle fits within x=85; rotating to 90° does not.
    actions, features, session, ui, events = _action_host(x=85., y=50., w=20., h=42.)
    before = session.snapshot()
    actions.rotate_selected(90)
    assert session.snapshot() == before
    assert ui.value == "360°"
    assert events == ["out-of-bounds"]


def test_no_selected_feature_preserves_toolbar_insert_angle_intent():
    actions, features, session, ui, events = _action_host()
    session.execute(HoleEditorAction.select(-1))
    original = deepcopy(features)
    actions.rotate_selected(270)
    assert ui.value == "270°"
    assert features == original
    assert events == []
    actions.rotate_selected(360)
    assert ui.value == "360°"


def test_gui_has_no_private_rotation_mutation_or_lossy_int_conversion():
    root = Path("gui_modules/editors/hole_editor.py").read_text(encoding="utf-8")
    composition = Path("gui_modules/editors/hole_editor_composition.py").read_text(
        encoding="utf-8"
    )
    assert "manufacturing_api.operator_hole_rotation_from_control(" in root
    assert "rotation = int(self.rotation_var.get().replace" not in root
    assert "rotation = int(\n                getattr(feature_list[idx]" not in root
    assert "rotate_feature=d.manufacturing_api.operator_hole_feature_with_rotation" in composition
    assert "d.replace(feature, rotation_deg=rotation)" not in composition
    owner = Path("ae_engine/operator_hole_feature_rotation.py").read_text(
        encoding="utf-8"
    )
    assert "from gui_modules" not in owner and "from phase6_" not in owner
