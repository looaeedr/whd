"""#2517: Small Door operator Policy/Spec must be built by the headless Engine."""
from dataclasses import replace
import inspect

import pytest

from ae_engine import manufacturing_api, indicator_small_door_operator_spec
from ae_engine.contracts import ManufacturingContext
from gui_modules.application import manufacturing_adapter as adapter


@pytest.mark.parametrize("groups,fw,gapw,gaph,fold", [
    ((2,), 25.0, 3.5, 3.5, 19.0),
    ((3, 2), 29.0, 4.0, 2.0, 17.0),
])
def test_operator_small_door_api_matches_existing_engine_policy_pipeline(groups, fw, gapw, gaph, fold):
    assert manufacturing_api.indicator_small_door_operator_spec is indicator_small_door_operator_spec
    prior = replace(
        manufacturing_api.resolve_policy(),
        frame_width=fw, door_gap_w=gapw, door_gap_h=gaph,
        indicator_small_door_fold=fold,
    )
    context = ManufacturingContext(policy=prior, draw_stock=False)
    old_base = manufacturing_api.indicator_small_door_spec(
        groups, thickness=2.0, context=context,
    )
    expected = replace(
        old_base, features=("legacy-feature",),
        feature_space="legacy_unfolded", model_name=None, corner_policy=None,
    )
    actual, actual_context = indicator_small_door_operator_spec(
        groups, thickness=2, frame_width=fw, door_gap_w=gapw, door_gap_h=gaph,
        indicator_door_fold=fold, features=["legacy-feature"],
    )
    assert actual == expected
    assert actual_context == context
    assert actual_context.policy == prior


def test_omitted_small_door_fold_uses_engine_factory_default():
    from ae_engine import ae
    spec, context = indicator_small_door_operator_spec(
        (2,), thickness=2, frame_width=25, door_gap_w=3.5, door_gap_h=3.5,
    )
    assert context.policy.indicator_small_door_fold == float(
        getattr(ae, "indicator_small_door_fold_def", 19.0)
    )
    assert spec.fold_top == context.policy.indicator_small_door_fold
    assert spec.feature_space == "legacy_unfolded"


@pytest.mark.parametrize("family", ["金庫型", "受電箱"])
def test_gui_only_forwards_operator_inputs_without_policy_construction(monkeypatch, family):
    captured = {}
    result = (object(), object())
    def factory(groups, **kw):
        captured.update({"groups": groups, **kw})
        return result
    monkeypatch.setattr(manufacturing_api, "indicator_small_door_operator_spec", factory)
    value = {
        "model": family, "t": 2, "fw": 29,
        "door_gap_w": 3.5, "door_gap_h": 4.5,
        "indicator_door_fold": 18,
    }
    actual = adapter._indicator_door_part_spec_from_values(
        None, value, [2, 3], features=["hole"],
    )
    assert actual is result
    assert captured == {
        "groups": [2, 3], "thickness": 2, "frame_width": 29,
        "door_gap_w": 3.5, "door_gap_h": 4.5,
        "indicator_door_fold": 18, "features": ["hole"],
    }


def test_gui_small_door_spec_derivation_has_no_private_manufacturing_owner():
    source = inspect.getsource(adapter._indicator_door_part_spec_from_values)
    assert "manufacturing_api.indicator_small_door_operator_spec(" in source
    for forbidden in ("replace(", "resolve_policy(", "indicator_small_door_spec(",
                      "ManufacturingContext(", "ae.indicator_small_door_fold_def"):
        assert forbidden not in source


def test_small_door_operator_factory_rejects_invalid_groups():
    with pytest.raises(ValueError):
        indicator_small_door_operator_spec(
            (), thickness=2, frame_width=25,
            door_gap_w=3.5, door_gap_h=3.5,
        )
