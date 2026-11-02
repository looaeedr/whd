"""#2517 committed Receiving live W/H/D must override stale Settings controls."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.fold_designer_part_session import Phase6PartSessionOwner


LIVE = {"w": 820, "h": 1600.5, "d": 360, "extra": "unrelated"}


@pytest.mark.parametrize("model", ["受電箱", "RECEIVING", "receiving", "ReCeIvInG"])
def test_receiving_aliases_use_exact_committed_box_values(model):
    snapshot = {"model": model, "active_mode": "set_bay"}
    before = deepcopy((snapshot, LIVE))
    result = api.project_operator_receiving_settings_live_dimensions(
        snapshot, LIVE, applying_settings=True,
    )
    assert result == {"w": 820, "h": 1600.5, "d": 360}
    assert result is not LIVE
    assert (snapshot, LIVE) == before


@pytest.mark.parametrize("snapshot,applying,dimensions", [
    ({"model": "金庫型"}, True, LIVE),
    ({"model": "RO"}, True, LIVE),
    ({"model": "受電箱"}, False, LIVE),
    ({"model": "受電箱"}, True, None),
    ({"model": "受電箱"}, True, {"w": 800, "h": 1600}),
    ({}, True, LIVE),
])
def test_non_receiving_or_missing_data_keeps_existing_editor_flow(snapshot, applying, dimensions):
    assert api.project_operator_receiving_settings_live_dimensions(
        snapshot, dimensions, applying_settings=applying,
    ) is None


@pytest.mark.parametrize("field,bad", [
    ("w", 0), ("w", -100), ("w", "nan"), ("w", True),
    ("h", float("inf")), ("h", "invalid"), ("d", None),
])
def test_invalid_committed_physical_source_must_fail_closed(field, bad):
    source = {**LIVE, field: bad}
    before = deepcopy(source)
    with pytest.raises(ValueError, match="包外尺寸"):
        api.project_operator_receiving_settings_live_dimensions(
            {"model": "受電箱"}, source, applying_settings=True,
        )
    assert source == before


def test_gui_delegates_physical_settings_source_decision_to_public_engine():
    gui = inspect.getsource(Phase6PartSessionOwner.save_current_part)
    assert "manufacturing_api.project_operator_receiving_settings_live_dimensions(" in gui
    assert 'str(app._phase6_input_snapshot.get("model")' not in gui
    assert "values.update(receiving_settings_whd)" in gui
    from ae_engine import operator_part_session_profiles as owner
    assert "from gui_modules" not in inspect.getsource(owner)
