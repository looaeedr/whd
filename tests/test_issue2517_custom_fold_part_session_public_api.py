"""#2517 CustomFold editor Save and Hole Editor use public Engine sources."""
from copy import deepcopy
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.custom_fold_manufacturing import custom_fold_feature_context
from gui_modules.application import fold_designer_part_session as gui


def _source(model="金庫型", axis="X", thickness=2.0):
    catalog = api.CustomPartCatalog()
    key = catalog.add(display_name="加強板", fold_axis=axis,
                      transverse_length=123.456, per_box_count=2)
    return key, {"model": model, "t": thickness, "custom_parts": catalog.snapshot()}


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("axis", ("X", "Y"))
def test_custom_save_and_real_dxf_reopen_are_same_engine_parts(family, axis, tmp_path):
    key, snapshot = _source(family, axis)
    original = api.build_custom_part_profiles(snapshot, key)
    edited = deepcopy(original)
    for row in edited[axis]:
        row.pop("ui_len_add", None)
    before = deepcopy((snapshot, edited))
    saved = api.project_operator_custom_fold_save_profiles(snapshot, key, edited)
    assert (snapshot, edited) == before
    assert saved[axis][0]["ui_len_add"] == pytest.approx(2.0)
    assert saved[axis][1]["ui_len_add"] == pytest.approx(2.0)
    other = "Y" if axis == "X" else "X"
    assert saved[other] == original[other]
    spec = api.custom_part_spec(snapshot, key, profiles=saved)
    assert [row.formed_length for row in spec.fold_profile] == [17.0, 100.0]
    surface, width, height, guide = api.custom_fold_feature_context(spec)
    assert api.custom_fold_feature_context is custom_fold_feature_context
    assert width > 0 and height > 0 and guide is not None and surface is not None
    material = api.build_part_render_data(spec)
    path = tmp_path / (family + "-" + axis + ".dxf")
    api.generate_part(spec, path)
    reopened = ezdxf.readfile(path)
    assert len(reopened.modelspace().query('LINE[layer=="BEND"]')) == 1
    assert api.verify_saved_part_render_data_dxf(material, path).ok


@pytest.mark.parametrize("bad", (True, 0, -1, 17, float("nan"), float("inf")))
def test_invalid_thickness_cannot_enter_saved_custom_fold(bad):
    key, snapshot = _source(thickness=bad)
    valid = api.build_custom_part_profiles({**snapshot, "t": 2.0}, key)
    with pytest.raises(ValueError):
        api.project_operator_custom_fold_save_profiles(snapshot, key, valid)


def test_missing_axis_or_invalid_flat_span_is_never_saved():
    key, snapshot = _source(axis="Y")
    profiles = api.build_custom_part_profiles(snapshot, key)
    with pytest.raises(ValueError):
        api.project_operator_custom_fold_save_profiles(snapshot, key, {"Y": profiles["Y"]})
    wrong = deepcopy(profiles)
    wrong["X"][0]["len"] = 999
    with pytest.raises(ValueError, match="metadata"):
        api.project_operator_custom_fold_save_profiles(snapshot, key, wrong)
    assert profiles["X"][0]["len"] == pytest.approx(123.456)


def test_gui_part_session_contains_no_custom_manufacturing_logic():
    save = inspect.getsource(gui.Phase6PartSessionOwner.save_current_part)
    activate = inspect.getsource(gui.Phase6PartSessionOwner.activate_part)
    assert "bridge.manufacturing_api.project_operator_custom_fold_save_profiles(" in save
    assert "bridge.apply_outside_dimension_compensation(" not in save
    assert "custom_fold_feature_context(spec)" in activate
    assert "bridge.manufacturing_api.custom_fold_feature_context(spec)" in activate
    assert "from ae_engine.custom_fold_manufacturing import" not in activate
    assert "bridge.manufacturing_api.custom_part_spec(" in activate
