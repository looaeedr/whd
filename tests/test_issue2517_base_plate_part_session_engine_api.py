"""#2517 real Receiving BasePlate Part Session uses only public Engine sources."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
from gui_modules.application import fold_designer_part_session as gui
from tests.test_receiving_base_3d_profile_source_bends import _snap


@pytest.mark.parametrize("model", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_receiving_source_can_override_stale_editor_fold_on_activation(model):
    source = _snap()
    source["model"] = model
    defaults = receiving_base_plate_3d_profiles(source)
    old = {"X": [{"len": 1.}], "Y": [{"len": 2.}]}
    before = deepcopy((source, defaults, old))
    selected, refresh = api.project_operator_part_activation_profiles(
        "base_plate", source, old, defaults,
    )
    assert selected is defaults and refresh is True
    assert (source, defaults, old) == before
    assert gui._activation_profiles_from_authoritative_source(
        "base_plate", source, old, defaults,
    ) == (defaults, True)


@pytest.mark.parametrize("model", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_save_only_exact_configured_receiving_physical_profile(model):
    source = _snap()
    source["model"] = model
    before = deepcopy(source)
    physical = api.project_operator_receiving_base_plate_save_profiles(source, "base_plate")
    assert physical == receiving_base_plate_3d_profiles(source)
    assert physical["X"][1]["len"] == pytest.approx(33.)
    assert physical["Y"][0]["len"] == pytest.approx(35.)
    assert source == before


def test_unconfigured_receiving_and_vault_keep_old_editable_profiles():
    snapshot = _snap()
    snapshot.pop("receiving_base_plate")
    old = {"X": [{"len": 99.}], "Y": [{"len": 98.}]}
    for model in ("受電箱", "金庫型"):
        snapshot["model"] = model
        assert api.project_operator_receiving_base_plate_save_profiles(
            snapshot, "base_plate",
        ) is None
        assert api.project_operator_part_activation_profiles(
            "base_plate", snapshot, old, old,
        ) == (old, False)
    snapshot = _snap()
    snapshot["model"] = "金庫型"
    assert api.project_operator_receiving_base_plate_save_profiles(
        snapshot, "base_plate",
    ) is None
    assert api.project_operator_part_activation_profiles(
        "base_plate", snapshot, old, {"X": [{"len": 4.}], "Y": []},
    ) == (old, False)


def test_no_cross_part_or_unproven_profile_override():
    source = _snap()
    old = {"X": [{"len": 100.}], "Y": [{"len": 200.}]}
    derived = {"X": [{"phase6_key": "receiving_left_first_40", "len": 40.}],
               "Y": [{"phase6_key": "not_verified", "len": 35.}]}
    assert api.project_operator_part_activation_profiles(
        "base_plate", source, old, derived,
    ) == (old, False)
    assert api.project_operator_part_activation_profiles(
        "head", source, old, derived,
    ) == (old, False)
    assert api.project_operator_receiving_base_plate_save_profiles(
        source, "head",
    ) is None
    assert api.project_operator_part_activation_profiles(
        "head", source, None, derived,
    ) == (derived, True)


def test_physical_source_error_never_turns_into_generic_fallback(monkeypatch):
    from ae_engine import operator_part_session_profiles as owner
    source = _snap()
    def invalid(_):
        raise ValueError("CURRENT_NFB_FOLD_SOURCE_INVALID")
    monkeypatch.setattr(owner, "receiving_base_plate_3d_profiles", invalid)
    with pytest.raises(ValueError, match="CURRENT_NFB_FOLD_SOURCE_INVALID"):
        api.project_operator_receiving_base_plate_save_profiles(source, "base_plate")


def test_gui_part_session_only_uses_public_engine_for_source_decisions():
    activation = inspect.getsource(gui._activation_profiles_from_authoritative_source)
    saved = inspect.getsource(gui.Phase6PartSessionOwner.save_current_part)
    assert "manufacturing_api.project_operator_part_activation_profiles(" in activation
    assert "bridge.manufacturing_api.project_operator_receiving_base_plate_save_profiles(" in saved
    assert "from ae_engine.receiving_base_plate_3d_profiles import" not in saved
    assert "receiving_base_plate_3d_profiles(" not in saved
    assert 'snapshot.get("model")' not in activation
    from ae_engine import operator_part_session_profiles as owner
    assert "from gui_modules" not in inspect.getsource(owner)
