"""#2517 custom hole cutting/blind process must be sourced through public Engine boolean."""
from copy import deepcopy
from pathlib import Path
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.hole_catalog import custom_circle_definition, custom_rectangle_definition
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import CircleFeature, RectFeature, FeatureAnchor
from gui_modules.editors.hole_editor import HoleEditorFeatureFactory
from tests.test_issue2517_custom_hole_raw_dimensions_public_engine import Var


def _factory(label, blind):
    errors = []
    factory = HoleEditorFeatureFactory(
        selected_catalog_text=Var(label),
        rotation_var=Var("90°"),
        diameter_var=Var("12.25"),
        width_var=Var("40.375"),
        height_var=Var("21.125"),
        blind_var=Var(blind),
        context_provider=lambda: {"width": 800.0, "height": 600.0},
        catalog_by_label={},
        custom_circle_definition=api.operator_custom_circle_definition,
        custom_rectangle_definition=api.operator_custom_rectangle_definition,
        feature_from_definition=api.operator_hole_feature_from_definition,
        feature_with_reference_anchor=api.operator_hole_feature_with_reference_anchor,
        center_anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        show_error=lambda title, message: errors.append((title, message)),
    )
    return factory, errors


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("shape,label,cls", (
    ("circle", "＋ 自訂圓孔", CircleFeature),
    ("rect", "＋ 自訂方孔", RectFeature),
))
@pytest.mark.parametrize("raw,blind", (
    (False, False), ("false", False), ("off", False),
    ("no", False), ("0", False), (0, False), ("", False),
    (True, True), ("true", True), ("on", True),
    ("yes", True), ("1", True), (1, True),
))
def test_real_gui_custom_hole_process_matches_engine_serialized_flag(
    family, shape, label, cls, raw, blind,
):
    assert api.normalize_operator_settings_boolean(raw) is blind
    factory, errors = _factory(label, raw)
    before = deepcopy(raw)
    feature = factory.make_feature(Vec2(100, 100))
    assert isinstance(feature, cls)
    expected_process = "BLIND_HOLE" if blind else "CUTTING"
    assert feature.layer == expected_process
    constructor = (api.operator_custom_circle_definition if shape == "circle"
                   else api.operator_custom_rectangle_definition)
    expected = (constructor("12.25", blind=raw) if shape == "circle"
                else constructor("40.375", "21.125", blind=raw))
    assert expected.process == expected_process
    canonical = (
        custom_circle_definition("12.25", blind=raw)
        if shape == "circle"
        else custom_rectangle_definition("40.375", "21.125", blind=raw)
    )
    assert expected == canonical
    assert api.operator_hole_feature_from_definition(
        expected, Vec2(100, 100), 800.0, 600.0, rotation_deg=90
    ) == feature
    assert errors == []
    assert raw == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("shape,label", (
    ("circle", "＋ 自訂圓孔"), ("rect", "＋ 自訂方孔"),
))
@pytest.mark.parametrize("raw", (
    None, "maybe", "2", -1, 2, 1.5, float("nan"), float("inf"),
))
def test_bad_blind_flag_cannot_create_cutting_or_blind_geometry(
    family, shape, label, raw,
):
    factory, errors = _factory(label, raw)
    before = deepcopy(raw)
    assert factory.make_feature(Vec2(100, 100)) is None
    assert len(errors) == 1 and errors[0][0] == "開孔錯誤"
    assert "布林值" in errors[0][1]
    if shape == "circle":
        with pytest.raises(ValueError, match="布林值"):
            api.operator_custom_circle_definition("12.25", blind=raw)
    else:
        with pytest.raises(ValueError, match="布林值"):
            api.operator_custom_rectangle_definition(
                "40.375", "21.125", blind=raw,
            )
    assert raw == before


def test_public_catalog_process_contract_is_same_original_engine_callable():
    assert api.operator_custom_circle_definition is custom_circle_definition
    assert api.operator_custom_rectangle_definition is custom_rectangle_definition
    assert ae_engine.operator_custom_circle_definition is custom_circle_definition
    assert ae_engine.operator_custom_rectangle_definition is custom_rectangle_definition
    code = inspect.getsource(custom_circle_definition)
    code_rect = inspect.getsource(custom_rectangle_definition)
    assert "normalize_operator_settings_boolean(blind)" in code
    assert "normalize_operator_settings_boolean(blind)" in code_rect
    assert '"BLIND_HOLE" if blind else "CUTTING"' not in (code + code_rect)


def test_original_hole_owners_keep_valid_dimension_guard_before_process_decision():
    for creator, args in (
        (api.operator_custom_circle_definition, (True,)),
        (api.operator_custom_rectangle_definition, (True, "21.125")),
        (api.operator_custom_rectangle_definition, ("40.375", True)),
    ):
        with pytest.raises(ValueError, match="finite positive dimension"):
            creator(*args, blind="false")
