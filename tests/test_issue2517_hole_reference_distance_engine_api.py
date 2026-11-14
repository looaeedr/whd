"""#2517: Hole Editor reference source is canonical Engine finite/nonnegative."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, ReferenceAnchor,
    feature_surface_from_rect, feature_finished_point,
)
from ae_engine.sheetmetal_feature_reference import (
    normalize_operator_hole_reference_distance as owner_normalizer,
    move_feature_by_reference_distance as owner_move,
)
from gui_modules.editors.hole_editor import HoleEditorReferenceActions


def _world():
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(300, 200))
    feature = CircleFeature(
        diameter=20.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100, 100),
    )
    return surface, [feature]


def _gui_actions(raw):
    surface, features = _world()
    writes = []
    handler = HoleEditorReferenceActions(
        hole_session=SimpleNamespace(
            selected_index=0, execute=lambda action: writes.append(("commit", action)),
        ),
        context_provider=lambda: {
            "feature_list": features, "surface": surface,
            "width": 300, "height": 200,
        },
        suppress_entry_events=[False],
        reference_variables={
            ("x", "edge"): SimpleNamespace(get=lambda: raw),
        },
        pending_after={}, editor=SimpleNamespace(),
        feature_with_reference_anchor=lambda f, a: f,
        feature_reference_anchor=lambda f: ReferenceAnchor.CENTER,
        move_feature_by_reference_distance=api.operator_hole_move_feature_by_reference_distance,
        active_reference_guide=lambda: None,
        refresh_reference_fields=lambda: writes.append(("refresh",)),
        redraw=lambda: writes.append(("redraw",)),
        sync_all=lambda: writes.append(("sync",)),
        show_format_error=lambda: writes.append(("format_error",)),
    )
    return handler, writes, features


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("raw", (
    "-1", "-3.125", "-inf", "nan", "inf", "invalid",
    None, False, True, float("nan"), float("inf"),
))
def test_bad_reference_source_rejects_before_engine_geometry_and_gui_commit(family, raw):
    surface, features = _world()
    before = deepcopy(features)
    with pytest.raises((ValueError, TypeError), match="reference distance"):
        api.normalize_operator_hole_reference_distance(raw)
    with pytest.raises((ValueError, TypeError), match="reference distance"):
        api.operator_hole_move_feature_by_reference_distance(
            surface, features, 0, ReferenceAnchor.CENTER,
            300, 200, axis="x", mode="edge", value=raw,
        )
    handler, writes, staged = _gui_actions(raw)
    handler.apply_reference_value("x", "edge", show_errors=True)
    assert writes == [("format_error",), ("refresh",)]
    assert features == before and staged == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("raw", (0, "0", "30.25", 35.75, "120"))
def test_valid_reference_source_engine_geometry_and_gui_transaction_parity(family, raw):
    surface, features = _world()
    before = deepcopy(features)
    expected = api.normalize_operator_hole_reference_distance(raw)
    assert expected == owner_normalizer(raw)
    moved = api.operator_hole_move_feature_by_reference_distance(
        surface, features, 0, ReferenceAnchor.CENTER,
        300, 200, axis="x", mode="edge", value=raw,
    )
    assert moved == owner_move(
        surface, features, 0, ReferenceAnchor.CENTER,
        300, 200, axis="x", mode="edge", value=expected,
    )
    assert features == before
    handler, writes, staged = _gui_actions(raw)
    handler.apply_reference_value("x", "edge", show_errors=True)
    if moved == features[0]:
        assert writes == [("refresh",)]
    else:
        assert len(writes) == 4
        assert writes[0][0] == "commit"
        assert [event[0] for event in writes[1:]] == ["refresh", "redraw", "sync"]
    assert staged == before


def test_real_positive_operator_reference_distance_moves_actual_hole_center():
    surface, features = _world()
    moved = api.operator_hole_move_feature_by_reference_distance(
        surface, features, 0, ReferenceAnchor.CENTER, 300, 200,
        axis="x", mode="edge", value="40.125",
    )
    assert feature_finished_point(moved, 300, 200).x == pytest.approx(40.125)
    assert feature_finished_point(features[0], 300, 200).x == 100


def test_empty_field_is_gui_no_op_not_manufacturing_zero():
    handler, writes, features = _gui_actions("")
    before = deepcopy(features)
    handler.apply_reference_value("x", "edge", show_errors=True)
    assert writes == [] and features == before


def test_broken_selected_index_does_not_move_last_physical_hole():
    s, features = _world()
    with pytest.raises(ValueError, match="out of range"):
        api.operator_hole_move_feature_by_reference_distance(
            s, features, -1, ReferenceAnchor.CENTER, 300, 200,
            axis="x", mode="edge", value="30",
        )


def test_gui_hole_reference_distance_has_no_private_manufacturing_rule():
    code = inspect.getsource(HoleEditorReferenceActions.apply_reference_value)
    assert "manufacturing_api.normalize_operator_hole_reference_distance(" in code
    assert "isfinite(" not in code and "value < 0" not in code
    assert "value = float(raw)" not in code
    engine = inspect.getsource(owner_move)
    assert "normalize_operator_hole_reference_distance(value)" in engine
    assert api.normalize_operator_hole_reference_distance is owner_normalizer
    assert ae_engine.normalize_operator_hole_reference_distance is owner_normalizer
