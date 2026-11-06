"""#2517: GUI CornerType save path consumes the one canonical Engine codec."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.endcap_factory_fold import selection_to_raw as engine_codec
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection,
)
from gui_modules.application import state_sync


@pytest.mark.parametrize("selection", [
    CornerTypeSelection(CornerTypeId.C01),
    CornerTypeSelection(CornerTypeId.C02, rotation_quadrants=1),
    CornerTypeSelection(CornerTypeId.C03),
    CornerTypeSelection(CornerTypeId.C04),
    CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
                        direction=CornerDirection.BOTH, amount_t=0.5),
    CornerTypeSelection(CornerTypeId.INSERT_OVERLAY, amount_t=1.0,
                        secondary_retain_t=0.5, secondary_depth_t=2.0),
])
def test_gui_save_matches_existing_engine_codec_exactly(selection):
    original = deepcopy(selection)
    assert manufacturing_api.endcap_corner_selection_to_raw is engine_codec
    gui_raw = state_sync.serialize_corner_selection(selection)
    engine_raw = manufacturing_api.endcap_corner_selection_to_raw(selection)
    assert gui_raw == engine_raw
    assert selection == original
    # The same Engine persisted schema must reopen and serialize identically.
    restored = manufacturing_api.endcap_corner_selection_from_raw(gui_raw)
    assert manufacturing_api.endcap_corner_selection_to_raw(restored) == gui_raw


def test_gui_save_forwards_live_corner_source_without_copy_or_reinterpretation(monkeypatch):
    marker = {"type_id": "CROSS", "rotation_quadrants": 0}
    passed = []
    def codec(value):
        passed.append(value)
        return marker
    monkeypatch.setattr(manufacturing_api, "endcap_corner_selection_to_raw", codec)
    selection = CornerTypeSelection(CornerTypeId.CROSS)
    assert state_sync.serialize_corner_selection(selection) is marker
    assert passed == [selection]


def test_entire_manual_corner_snapshot_uses_engine_for_each_corner():
    rows = {
        "head": {
            "top_left": CornerTypeSelection(CornerTypeId.C02, rotation_quadrants=1),
            "top_right": CornerTypeSelection(CornerTypeId.OVERLAY),
        },
        "tail": {
            "bottom_left": CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.RETAIN,
                                                direction=CornerDirection.WIDTH, amount_t=1.0),
        },
    }
    prior = deepcopy(rows)
    host = SimpleNamespace(
        manual_corner_state=rows,
        _serialize_corner_selection=state_sync.serialize_corner_selection,
    )
    actual = state_sync.serialize_manual_corner_state(host)
    assert actual == {
        part: {key: engine_codec(value) for key, value in part_rows.items()}
        for part, part_rows in rows.items()
    }
    assert rows == prior
    actual["head"]["top_left"]["type_id"] = "ALTERED"
    assert rows == prior


def test_invalid_corner_source_rejected_without_commit():
    state = {"head": {"top_left": "not-a-corner"}}
    prior = deepcopy(state)
    host = SimpleNamespace(
        manual_corner_state=state,
        _serialize_corner_selection=state_sync.serialize_corner_selection,
    )
    with pytest.raises(ValueError):
        state_sync.serialize_manual_corner_state(host)
    assert state == prior


def test_serializer_contains_no_gui_owned_manufacturing_fields():
    source = inspect.getsource(state_sync.serialize_corner_selection)
    assert "manufacturing_api.endcap_corner_selection_to_raw" in source
    for private_formula in ("normalize_corner_selection(", "selection.type_id", "rotation_quadrants", "secondary_depth_t"):
        assert private_formula not in source
