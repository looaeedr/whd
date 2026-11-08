"""#2517: custom Hole Editor blind process is canonical Engine boolean state."""
from copy import deepcopy
import inspect
import json
import math

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import hole_catalog as owner
from ae_engine.sheetmetal_geometry import Vec2
from tests.test_issue2517_custom_hole_raw_dimensions_public_engine import _make


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("shape", ("circle", "rectangle"))
@pytest.mark.parametrize("raw,expected", (
    (False, False), (0, False), ("false", False),
    ("FALSE", False), ("off", False), ("no", False), ("0", False),
    (True, True), (1, True), ("true", True), ("TRUE", True),
    ("on", True), ("yes", True), ("1", True),
))
def test_gui_custom_hole_process_flag_matches_public_engine_feature_and_json_source(
    model, shape, raw, expected,
):
    original = deepcopy(raw)
    direct = (
        api.operator_custom_circle_definition("12.25", blind=raw)
        if shape == "circle"
        else api.operator_custom_rectangle_definition("40.375", "21.125", blind=raw)
    )
    process = "BLIND_HOLE" if expected else "CUTTING"
    assert direct.process == process
    point = Vec2(100, 100)
    physical = api.operator_hole_feature_from_definition(
        direct, point, 800, 600, rotation_deg=90,
    )
    assert physical.layer == process
    gui, _calls, errors = _make(
        "＋ 自訂圓孔" if shape == "circle" else "＋ 自訂方孔",
        blind=raw, model=model,
    )
    result = gui.make_feature(point)
    assert type(result) is type(physical)
    assert result.layer == process
    assert errors == []
    assert raw == original
    restored = json.loads(json.dumps({"shape": shape, "blind": raw}))
    returned = (
        api.operator_custom_circle_definition("12.25", blind=restored["blind"])
        if shape == "circle"
        else api.operator_custom_rectangle_definition("40.375", "21.125",
                                                       blind=restored["blind"])
    )
    assert returned.process == direct.process


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("shape", ("circle", "rectangle"))
@pytest.mark.parametrize("bad", ("maybe", "2", 2, None, 1.5, float("nan"), [], {}))
def test_invalid_custom_hole_process_never_creates_cutting_or_blind_feature(model, shape, bad):
    before = deepcopy(bad)
    make = (
        lambda: api.operator_custom_circle_definition("12.25", blind=bad)
        if shape == "circle"
        else api.operator_custom_rectangle_definition("40.375", "21.125", blind=bad)
    )
    with pytest.raises(ValueError, match="布林值"):
        make()
    gui, _calls, errors = _make(
        "＋ 自訂圓孔" if shape == "circle" else "＋ 自訂方孔",
        blind=bad, model=model,
    )
    assert gui.make_feature(Vec2(100, 100)) is None
    assert len(errors) == 1 and errors[0][0] == "開孔錯誤"
    if isinstance(bad, float) and math.isnan(bad):
        assert math.isnan(before)
    else:
        assert bad == before


def test_default_blind_source_unchanged_through_hole_and_exact_engine_aliases():
    assert api.operator_custom_circle_definition("14").process == "CUTTING"
    assert api.operator_custom_rectangle_definition("20", "30").process == "CUTTING"
    for public, origin in (
        (api.operator_custom_circle_definition, owner.custom_circle_definition),
        (api.operator_custom_rectangle_definition, owner.custom_rectangle_definition),
    ):
        assert public is origin
    assert ae_engine.operator_custom_circle_definition is owner.custom_circle_definition
    assert ae_engine.operator_custom_rectangle_definition is owner.custom_rectangle_definition


def test_engine_owns_process_boolean_no_gui_coercion_or_regrowth():
    for func in (owner.custom_circle_definition, owner.custom_rectangle_definition):
        assert "normalize_operator_settings_boolean(blind)" in inspect.getsource(func)
        assert "if blind else" not in inspect.getsource(func)
    from gui_modules.editors.hole_editor import HoleEditorFeatureFactory
    gui = inspect.getsource(HoleEditorFeatureFactory.make_feature)
    assert "blind=self.blind_var.get()" in gui
    assert "bool(self.blind_var.get())" not in gui
