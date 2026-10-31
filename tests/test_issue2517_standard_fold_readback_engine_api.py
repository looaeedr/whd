"""#2517: GUI standard Fold readback must delegate manufacturing semantics to Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api, read_standard_part_fold_profiles, build_standard_part_fold_profiles
from phase6_manufacturing_adapter import read_standard_part_profiles as gui_readback, build_scene_payload_for_app


def _snapshot():
    return {
        "model": "金庫型", "w": 400, "h": 600, "d": 250, "t": 2,
        "part_dimensions": {
            "door": {"width": 300, "height": 500},
            "door_c1_r1": {"width": 300, "height": 500},
            "base_plate": {"width": 250, "height": 450},
            "indicator_box": {"width": 180, "height": 210},
            "indicator_door": {"width": 100, "height": 130},
        },
    }


@pytest.mark.parametrize("key,result", [
    ("door", {"door_fold_l": 20.0, "door_fold_r": 20.0,
              "door_fold_b": 20.0, "door_fold_t": 20.0}),
    ("door_c1_r1", {"door_fold_l": 20.0, "door_fold_r": 20.0,
                    "door_fold_b": 20.0, "door_fold_t": 20.0}),
    ("base_plate", {"base_plate_bend": 20.0}),
    ("indicator_box", {"indicator_box_fold": 49.0}),
    ("indicator_door", {"indicator_door_fold": 19.0}),
])
def test_real_engine_forward_fold_can_be_read_back_through_public_api(key, result):
    snapshot = _snapshot()
    rows = build_standard_part_fold_profiles(snapshot, key)
    prior = deepcopy((rows, snapshot))
    assert read_standard_part_fold_profiles(key, rows, snapshot) == result
    assert gui_readback(key, rows, snapshot) == result
    assert (rows, snapshot) == prior


def test_missing_key_defaults_and_custom_unknown_do_not_invent_standard_settings():
    snapshot = _snapshot()
    assert read_standard_part_fold_profiles("door", {}, snapshot) == {
        "door_fold_l": 20.0, "door_fold_r": 20.0,
        "door_fold_b": 20.0, "door_fold_t": 20.0,
    }
    assert read_standard_part_fold_profiles("custom:1", {}, snapshot) == {}
    assert read_standard_part_fold_profiles("head", {}, snapshot) == {}


@pytest.mark.parametrize("key,left,right,expected", [
    ("base_plate", "base_bend_l", "base_bend_r", "底板四邊折彎"),
    ("indicator_box", "ib_fold_l", "ib_fold_r", "指示燈盒四邊折彎"),
    ("indicator_door", "id_fold_l", "id_fold_r", "指示燈小門四邊折彎"),
])
def test_asymmetric_shared_fold_rejected_not_silently_projected(key,left,right,expected):
    profiles = {"X": [
        {"len": 20, "phase6_key": left},
        {"len": 21, "phase6_key": right},
    ]}
    with pytest.raises(ValueError, match=expected):
        read_standard_part_fold_profiles(key, profiles, _snapshot())


def test_receiving_root_baseplate_never_overwrites_actual_source_material_with_generic_bend(monkeypatch):
    from ae_engine import receiving_base_plate_3d_profiles as base_owner
    snapshot = {**_snapshot(), "model": "受電箱"}
    rows = {"X": [{"phase6_key": "base_bend_l", "len": 999}]}
    monkeypatch.setattr(base_owner, "receiving_base_plate_3d_profiles",
                        lambda values: {"X": [{"len": 33}], "Y": [{"len": 35}]})
    assert read_standard_part_fold_profiles("base_plate", rows, snapshot) == {}
    assert gui_readback("base_plate", rows, snapshot) == {}


def test_public_engine_owner_and_actual_gui_request_path_are_only_adapters():
    assert manufacturing_api.read_standard_part_fold_profiles is read_standard_part_fold_profiles
    code = inspect.getsource(gui_readback)
    assert "manufacturing_api.read_standard_part_fold_profiles(" in code
    for forbidden in ("phase6_key", "base_bend", "indicator_box_fold",
                      "receiving_base_plate_3d_profiles", "float("):
        assert forbidden not in code
    assert "values.update(read_standard_part_profiles(key, profiles, values))" in inspect.getsource(
        build_scene_payload_for_app
    )
    import ae_engine.standard_part_fold_readback as engine
    owner_source = inspect.getsource(engine)
    assert "from phase6_" not in owner_source
    assert "import phase6_" not in owner_source
