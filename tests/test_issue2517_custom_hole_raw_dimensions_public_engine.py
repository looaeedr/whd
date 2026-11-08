"""#2517 custom Hole Editor raw dimensions cannot be fabricated by GUI float()."""
from copy import deepcopy
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import hole_catalog as owner
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, FeatureAnchor, feature_finished_point,
    feature_surface_from_rect, feature_is_within_surface,
)
from gui_modules.editors.hole_editor import HoleEditorFeatureFactory


class Var:
    def __init__(self, raw):
        self.raw = raw
    def get(self):
        return self.raw


def _make(label, *, diameter="12.25", width="40.375", height="21.125",
          rotation="90°", blind=False, model="金庫型"):
    errors = []
    calls = []
    context = {"width": 800.0, "height": 600.0, "model": model}
    factory = HoleEditorFeatureFactory(
        selected_catalog_text=Var(label), rotation_var=Var(rotation),
        diameter_var=Var(diameter), width_var=Var(width),
        height_var=Var(height), blind_var=Var(blind),
        context_provider=lambda: context,
        catalog_by_label={},
        custom_circle_definition=api.operator_custom_circle_definition,
        custom_rectangle_definition=api.operator_custom_rectangle_definition,
        feature_from_definition=api.operator_hole_feature_from_definition,
        feature_with_reference_anchor=api.operator_hole_feature_with_reference_anchor,
        center_anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        show_error=lambda title, message: errors.append((title, message)),
    )
    return factory, calls, errors


@pytest.mark.parametrize("alias,owner_fn", (
    ("operator_custom_circle_definition", owner.custom_circle_definition),
    ("operator_custom_rectangle_definition", owner.custom_rectangle_definition),
    ("operator_hole_feature_from_definition", owner.feature_from_definition),
    ("operator_load_hole_catalog", owner.load_hole_catalog),
    ("operator_load_pipe_catalog", owner.load_pipe_catalog),
))
def test_public_catalog_api_is_exact_canonical_engine_callable(alias, owner_fn):
    assert getattr(api, alias) is owner_fn
    assert getattr(ae_engine, alias) is owner_fn
    assert alias in ae_engine.__all__


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("broken", (True, False, None, "nan", "inf", 0, -1, "bogus"))
def test_custom_circle_raw_invalid_source_rejects_without_cutting_hole(model, broken):
    factory, _calls, errors = _make(
        "＋ 自訂圓孔", diameter=broken, model=model,
    )
    result = factory.make_feature(Vec2(100, 100))
    assert result is None
    assert len(errors) == 1 and errors[0][0] == "開孔錯誤"


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field", ("width", "height"))
@pytest.mark.parametrize("broken", (True, False, None, "nan", "inf", 0, -1, "bogus"))
def test_custom_rectangle_raw_invalid_source_rejects_without_cutting_hole(
    model, field, broken,
):
    dims = {"width": "40.375", "height": "21.125"}
    dims[field] = broken
    factory, _calls, errors = _make(
        "＋ 自訂方孔", model=model, **dims,
    )
    result = factory.make_feature(Vec2(100, 100))
    assert result is None
    assert errors and errors[0][0] == "開孔錯誤"


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("shape", ("circle", "rectangle"))
def test_real_gui_custom_hole_produces_same_engine_feature_on_finished_face(model, shape):
    is_circle = shape == "circle"
    factory, _calls, errors = _make(
        "＋ 自訂圓孔" if is_circle else "＋ 自訂方孔",
        model=model, rotation="90°",
    )
    point = Vec2(100, 100)
    saved = factory.make_feature(point)
    assert isinstance(saved, CircleFeature if is_circle else RectFeature)
    expected_definition = (
        api.operator_custom_circle_definition("12.25")
        if is_circle else api.operator_custom_rectangle_definition("40.375", "21.125")
    )
    original = api.operator_hole_feature_from_definition(
        expected_definition, point, 800.0, 600.0, rotation_deg=90,
    )
    original = api.operator_hole_feature_with_reference_anchor(
        original, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
    )
    assert saved == original
    assert errors == []
    assert feature_finished_point(saved, 800, 600) == point
    surface = feature_surface_from_rect("door", Vec2(0, 0), Vec2(800, 600))
    assert feature_is_within_surface(surface, saved, 800, 600)


@pytest.mark.parametrize("rotation", ("invalid", "90.5°", "45°", None, True))
def test_invalid_rotation_option_causes_gui_error_no_hole_or_uncaught_exception(rotation):
    factory, _calls, errors = _make("＋ 自訂圓孔", rotation=rotation)
    assert factory.make_feature(Vec2(100, 100)) is None
    assert errors and errors[0][0] == "開孔錯誤"


def test_gui_hole_factory_does_not_coerce_physical_dimensions_before_engine():
    code = inspect.getsource(HoleEditorFeatureFactory.make_feature)
    assert "float(self.diameter_var.get())" not in code
    assert "float(self.width_var.get())" not in code
    assert "float(self.height_var.get())" not in code
    assert "self.custom_circle_definition(" in code
    assert "self.custom_rectangle_definition(" in code
    assert code.index("try:") < code.index("rotation =")
    gui = Path("gui.py").read_text(encoding="utf-8")
    assert "from ae_engine.hole_catalog import" not in gui
    for name in (
        "operator_load_hole_catalog", "operator_load_pipe_catalog",
        "operator_hole_feature_from_definition",
        "operator_custom_circle_definition", "operator_custom_rectangle_definition",
    ):
        assert f"manufacturing_api.{name}" in gui
