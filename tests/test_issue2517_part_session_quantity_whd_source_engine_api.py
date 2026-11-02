"""#2517 Part Session W/H/D uses one Engine outside-dimension source."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.fold_designer_part_session import Phase6PartSessionOwner


RAW = {"w": "800", "h": "1600", "d": "350"}
QUANTITY = {"w": 825.25, "h": 1600.5, "d": 375.75}


@pytest.mark.parametrize("model", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_real_quantity_source_overrides_stale_set_bay_operator_header(model):
    snapshot = {"model": model, "active_mode": "quantity", "receiving_quantity_box": QUANTITY}
    before = deepcopy(snapshot)
    expected = {axis: QUANTITY[axis] for axis in ("w", "h", "d")}
    assert api.project_operator_quantity_box_dimensions(snapshot) == expected
    assert api.project_operator_part_session_source_dimensions(
        snapshot, {"w": "0", "h": "stale", "d": True},
    ) == expected
    assert snapshot == before


@pytest.mark.parametrize("family", ["金庫型", "RO", "UNKNOWN"])
def test_other_families_cannot_use_receiving_quantity_cache(family):
    snapshot = {"model": family, "active_mode": "quantity", "receiving_quantity_box": QUANTITY}
    assert api.project_operator_quantity_box_dimensions(snapshot) is None
    assert api.project_operator_part_session_source_dimensions(snapshot, RAW) == {
        "w": 800.0, "h": 1600.0, "d": 350.0,
    }


def test_live_operator_fractional_finished_dimensions_never_get_rounded():
    raw = {"w": "800.25", "h": 1600.125, "d": "350.75"}
    original = deepcopy(raw)
    assert api.project_operator_part_session_source_dimensions(
        {"model": "金庫型"}, raw,
    ) == {"w": 800.25, "h": 1600.125, "d": 350.75}
    assert api.project_operator_part_session_source_dimensions(
        {"model": "受電箱", "active_mode": "set_bay"}, raw,
    ) == {"w": 800.25, "h": 1600.125, "d": 350.75}
    assert raw == original


@pytest.mark.parametrize("bad", [True, 0, -1, "nan", "inf", None, "not-a-number"])
def test_invalid_actual_operator_source_rejected_without_mutation(bad):
    raw = {**RAW, "w": bad}
    before = deepcopy(raw)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_part_session_source_dimensions(
            {"model": "金庫型"}, raw,
        )
    assert raw == before


@pytest.mark.parametrize("bad", [True, 0, -3, "nan", "inf", "invalid", None])
def test_invalid_confirmed_quantity_box_never_falls_back_to_header(bad):
    snapshot = {
        "model": "受電箱", "active_mode": "quantity",
        "receiving_quantity_box": {**QUANTITY, "d": bad},
    }
    before = deepcopy(snapshot)
    with pytest.raises(ValueError):
        api.project_operator_part_session_source_dimensions(snapshot, RAW)
    assert snapshot == before


def test_unconfigured_legacy_quantity_keeps_valid_operator_dimensions():
    snapshot = {"model": "受電箱", "active_mode": "quantity"}
    assert api.project_operator_quantity_box_dimensions(snapshot) is None
    assert api.project_operator_part_session_source_dimensions(snapshot, RAW) == {
        "w": 800.0, "h": 1600.0, "d": 350.0,
    }


def test_gui_part_session_has_no_manufacturing_dimension_parser_or_quantity_projection():
    source = inspect.getsource(Phase6PartSessionOwner.save_current_part)
    assert "manufacturing_api.project_operator_part_session_source_dimensions(" in source
    assert source.count("manufacturing_api.project_operator_quantity_box_dimensions(") == 2
    assert "bridge.original.get_int(" not in source
    assert "float(app._phase6_input_snapshot['receiving_quantity_box']" not in source
    assert "manufacturing_api.normalize_operator_source_dimension(" in source
    from ae_engine import operator_part_session_profiles as owner
    assert "from gui_modules" not in inspect.getsource(owner)
