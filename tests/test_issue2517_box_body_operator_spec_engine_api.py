"""#2517: BoxBody manufacturing PartSpec ownership belongs to the Engine."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import build_box_body_operator_part_spec, manufacturing_api
from ae_engine.contracts import BoxBodyPartSpec
from ae_engine.box_body_fold_profile import profile_to_fold_segments
from gui_modules.application import manufacturing_adapter as gui


def values(model):
    return {
        "model": model, "w": 800, "h": 1800, "d": 400, "t": 2,
        "fw": 29, "zl1": 15, "zl2": 15, "zr1": 15, "zr2": 15,
        "z_comp": 0, "ybottom1": 16,
    }


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_engine_material_and_endcap_outside_source_contract(model):
    data = values(model)
    before = deepcopy(data)
    profile = [
        {"phase6_key": "zl1", "len": 15, "angle": -90, "ui_len_add": 2},
        {"phase6_key": "box_w", "len": 770, "core": "W"},
    ]
    pieces = {
        "box_body:piece:left": [{"source": "left"}],
        "box_body:divider:1": [{"source": "divider"}],
    }
    spec = manufacturing_api.build_box_body_operator_part_spec(
        data, model_name=model, fold_profile=profile,
        source_part_features=pieces,
        endcap_y_profiles={
            "head": [{"phase6_key": "ybottom1", "len": 13, "ui_len_add": 2}],
            "tail": [{"phase6_key": "ybottom1", "len": 21, "ui_len_add": 2}],
        },
        features=("body",), face_features={"front": ["hole"]},
    )
    assert isinstance(spec, BoxBodyPartSpec)
    assert spec == build_box_body_operator_part_spec(
        data, model_name=model, fold_profile=profile,
        source_part_features=pieces,
        endcap_y_profiles={
            "head": [{"phase6_key": "ybottom1", "len": 13, "ui_len_add": 2}],
            "tail": [{"phase6_key": "ybottom1", "len": 21, "ui_len_add": 2}],
        },
        features=("body",), face_features={"front": ["hole"]},
    )
    assert (spec.width, spec.height, spec.depth, spec.thickness, spec.frame_width) == (
        800, 1800, 400, 2, 29
    )
    assert spec.fold_profile == profile_to_fold_segments(profile)
    assert spec.fold_profile[0].formed_length == 17.0
    assert (spec.head_ybottom1, spec.tail_ybottom1) == (15.0, 23.0)
    assert spec.physical_piece_features == {"box_body:piece:left": [{"source": "left"}]}
    assert spec.face_features == {"front": ("hole",)}
    assert spec.features == ("body",)
    assert data == before
    with pytest.raises(FrozenInstanceError):
        spec.width = 999


def test_operator_override_priority_saved_physical_features_and_fallback():
    data = values("金庫型")
    physical = {"box_body:piece:rear": ["committed"]}
    spec = manufacturing_api.build_box_body_operator_part_spec(
        data, model_name="金庫型", endcap_y_profiles={
            "head": [{"phase6_key": "ybottom1", "len": 5}],
            "tail": [{"phase6_key": "fw", "len": 50}],
        },
        head_ybottom1=33,
        snapshot={**data, "physical_piece_features": physical},
        source_part_features={"box_body:piece:rear": ["stale"]},
    )
    assert (spec.head_ybottom1, spec.tail_ybottom1) == (33.0, 16.0)
    assert spec.physical_piece_features == physical


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_gui_is_only_operator_request_collector_with_engine_spy(monkeypatch, model):
    data = values(model)
    class Workspace:
        def profile_for(self, part):
            return {"Y": [{"phase6_key": "ybottom1", "len": 18}]}
        def box_body_profile(self):
            return [{"phase6_key": "box_w", "len": 800, "core": "W"}]
        def box_body_structure_state(self):
            return {}
        def part_features_snapshot(self):
            return {"box_body:piece:left": ["part"], "box_body:divider:1": ["skip"]}
    host = SimpleNamespace(workspace_controller=Workspace())
    called = []
    original = manufacturing_api.build_box_body_operator_part_spec
    def spy(val, **kw):
        called.append((val, kw))
        return original(val, **kw)
    monkeypatch.setattr(manufacturing_api, "build_box_body_operator_part_spec", spy)
    got = gui._box_body_part_spec_from_values(
        host, data, model_name=model,
        features=["body"], face_features={"front": ["sample"]},
    )
    assert got.head_ybottom1 == 18.0 and got.tail_ybottom1 == 18.0
    assert got.physical_piece_features == {"box_body:piece:left": ["part"]}
    assert called[0][0] is data
    assert called[0][1]["model_name"] == model
    assert len(called) == 1


def test_invalid_operator_request_fails_closed_and_gui_has_no_second_solver():
    data = values("金庫型")
    data.pop("t")
    with pytest.raises(KeyError):
        manufacturing_api.build_box_body_operator_part_spec(data, model_name="金庫型")
    source = inspect.getsource(gui._box_body_part_spec_from_values)
    assert "manufacturing_api.build_box_body_operator_part_spec(" in source
    assert "BoxBodyPartSpec(" not in source
    assert "resolve_box_body_back_panel_contract" not in source
    assert "fold_material_segment_outside_length" not in source
    assert "ybottom1" not in source.split("return manufacturing_api.")[0].replace("head_ybottom1", "").replace("tail_ybottom1", "")
